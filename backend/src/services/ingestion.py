from pathlib import Path

from sqlalchemy import select

from src.db.models import Document as DbDocument
from src.db.session import async_session_maker
from src.middleware.logging import get_logger
from src.models.schemas import DocumentStatus
from src.services.document_processor import chunk_text, extract_text
from src.services.vector_store import DOCUMENTS_COLLECTION, VectorStore

logger = get_logger(__name__)


async def _record_outcome(
    document_id: str,
    status: DocumentStatus,
    chunk_count: int = 0,
    error_message: str | None = None,
) -> None:
    async with async_session_maker() as session:
        result = await session.execute(select(DbDocument).where(DbDocument.id == document_id))
        document = result.scalar_one_or_none()
        if document is None:
            logger.warning("ingestion_document_vanished", document_id=document_id)
            return
        document.status = status
        document.chunk_count = chunk_count
        document.error_message = error_message
        await session.commit()


async def ingest_document(
    document_id: str,
    filename: str,
    stored_path: Path,
    user_id: str,
    vector_store: VectorStore,
) -> None:
    logger.info("ingestion_started", document_id=document_id, user_id=user_id)

    try:
        content = stored_path.read_bytes()
        text = extract_text(Path(filename), file_content=content)
        chunks = chunk_text(text)

        if not chunks:
            raise ValueError("No text content could be extracted from this document")

        await vector_store.aadd_documents(
            collection_name=DOCUMENTS_COLLECTION,
            chunks=chunks,
            metadatas=[
                {
                    "document_id": document_id,
                    "filename": filename,
                    "chunk_index": index,
                    "file_type": stored_path.suffix,
                    "user_id": user_id,
                }
                for index in range(len(chunks))
            ],
            ids=[f"{document_id}_chunk_{index}" for index in range(len(chunks))],
        )
    except Exception as exc:
        logger.error("ingestion_failed", document_id=document_id, error=str(exc))
        await _record_outcome(
            document_id,
            DocumentStatus.FAILED,
            error_message=str(exc)[:500],
        )
        return

    await _record_outcome(document_id, DocumentStatus.READY, chunk_count=len(chunks))
    logger.info("ingestion_completed", document_id=document_id, chunk_count=len(chunks))
