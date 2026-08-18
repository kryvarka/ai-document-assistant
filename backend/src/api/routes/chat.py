import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.deps import get_rag_pipeline
from src.config import settings
from src.db.models import ChatMessage as DbChatMessage
from src.db.models import Conversation, User
from src.db.session import async_session_maker, get_db
from src.middleware.logging import get_logger
from src.middleware.rate_limit import rate_limit_chat
from src.models.schemas import ChatRequest, ChatResponse
from src.services.rag_pipeline import RAGPipeline

logger = get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


async def _get_or_create_user_conversation(
    db: AsyncSession, conversation_id: str | None, user: User, question: str
) -> Conversation:
    now = datetime.now(timezone.utc)
    if conversation_id:
        stmt = (
            select(Conversation)
            .where(
                Conversation.id == conversation_id,
                Conversation.user_id == user.id,
            )
            .options(selectinload(Conversation.messages))
        )
        result = await db.execute(stmt)
        conv = result.scalar_one_or_none()
        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found or access denied",
            )
        conv.updated_at = now
        return conv

    title = (question[:45] + "...") if len(question) > 45 else question
    conv_id = f"conv_{uuid.uuid4().hex[:12]}"
    conv = Conversation(
        id=conv_id,
        title=title,
        user_id=user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv, ["messages"])
    return conv


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(rate_limit_chat),
    pipeline: RAGPipeline = Depends(get_rag_pipeline),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    conv = await _get_or_create_user_conversation(
        db, request.conversation_id, current_user, request.question
    )

    chat_history = [{"role": m.role, "content": m.content} for m in (conv.messages or [])]

    user_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
    user_msg = DbChatMessage(
        id=user_msg_id,
        conversation_id=conv.id,
        role="user",
        content=request.question,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user_msg)

    answer, sources = await pipeline.query(
        question=request.question,
        document_ids=request.document_ids,
        user_id=current_user.id,
        chat_history=chat_history,
    )

    asst_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
    sources_data = [s.model_dump() for s in sources]
    asst_msg = DbChatMessage(
        id=asst_msg_id,
        conversation_id=conv.id,
        role="assistant",
        content=answer,
        sources_json=json.dumps(sources_data),
        created_at=datetime.now(timezone.utc),
    )
    db.add(asst_msg)
    conv.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return ChatResponse(
        answer=answer,
        sources=sources,
        model=settings.llm_model,
        conversation_id=conv.id,
        message_id=asst_msg_id,
    )


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    current_user: User = Depends(rate_limit_chat),
    pipeline: RAGPipeline = Depends(get_rag_pipeline),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    conv = await _get_or_create_user_conversation(
        db, request.conversation_id, current_user, request.question
    )

    chat_history = [{"role": m.role, "content": m.content} for m in (conv.messages or [])]

    user_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
    user_msg = DbChatMessage(
        id=user_msg_id,
        conversation_id=conv.id,
        role="user",
        content=request.question,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user_msg)
    conv.updated_at = datetime.now(timezone.utc)
    await db.commit()

    stream, sources = await pipeline.query_stream(
        question=request.question,
        document_ids=request.document_ids,
        user_id=current_user.id,
        chat_history=chat_history,
    )

    conversation_id = conv.id

    async def event_generator():
        accumulated_answer = ""
        try:
            sources_data = [s.model_dump() for s in sources]
            meta_payload = {
                "conversation_id": conversation_id,
                "sources": sources_data,
            }
            yield _format_sse("meta", meta_payload)
            yield _format_sse("sources", sources_data)

            async for token in stream:
                accumulated_answer += token
                yield _format_sse("token", token)

            async with async_session_maker() as save_db:
                asst_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
                asst_msg = DbChatMessage(
                    id=asst_msg_id,
                    conversation_id=conversation_id,
                    role="assistant",
                    content=accumulated_answer,
                    sources_json=json.dumps(sources_data),
                    created_at=datetime.now(timezone.utc),
                )
                save_db.add(asst_msg)

                stmt = select(Conversation).where(Conversation.id == conversation_id)
                res = await save_db.execute(stmt)
                c = res.scalar_one_or_none()
                if c:
                    c.updated_at = datetime.now(timezone.utc)

                await save_db.commit()

            yield _format_sse("done", {})
        except Exception as exc:
            logger.error("stream_error", error=str(exc))
            yield _format_sse("error", {"detail": str(exc)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _format_sse(event_type: str, data: object) -> str:
    payload = json.dumps(data, default=str)
    return f"event: {event_type}\ndata: {payload}\n\n"
