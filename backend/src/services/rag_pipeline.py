from collections.abc import AsyncGenerator

from src.config import settings
from src.middleware.logging import get_logger
from src.models.schemas import SourceChunk
from src.services.llm_service import LLMService
from src.services.vector_store import DOCUMENTS_COLLECTION, VectorStore

logger = get_logger(__name__)


class RAGPipeline:
    def __init__(self, vector_store: VectorStore, llm_service: LLMService) -> None:
        self._vector_store = vector_store
        self._llm_service = llm_service

    def _build_context(self, results: dict) -> tuple[list[dict], list[SourceChunk]]:
        context_chunks: list[dict] = []
        sources: list[SourceChunk] = []

        if not results.get("documents") or not results["documents"][0]:
            return context_chunks, sources

        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        for doc, metadata, distance in zip(documents, metadatas, distances, strict=True):
            relevance_score = max(0.0, 1.0 - distance)

            if relevance_score < settings.min_relevance_score:
                continue

            context_chunks.append(
                {
                    "content": doc,
                    "document_name": metadata.get("filename", "Unknown"),
                }
            )

            sources.append(
                SourceChunk(
                    content=doc[:300] + "..." if len(doc) > 300 else doc,
                    document_name=metadata.get("filename", "Unknown"),
                    chunk_index=metadata.get("chunk_index", 0),
                    relevance_score=round(relevance_score, 4),
                )
            )

        return context_chunks, sources

    def _build_where_filter(
        self, user_id: str | None, document_ids: list[str] | None
    ) -> dict | None:
        filters = []
        if user_id:
            filters.append({"user_id": user_id})
        if document_ids:
            filters.append({"document_id": {"$in": document_ids}})

        if len(filters) == 1:
            return filters[0]
        elif len(filters) > 1:
            return {"$and": filters}
        return None

    async def query(
        self,
        question: str,
        document_ids: list[str] | None = None,
        user_id: str | None = None,
        chat_history: list[dict] | None = None,
    ) -> tuple[str, list[SourceChunk]]:
        where_filter = self._build_where_filter(user_id, document_ids)

        logger.info("rag_query_start", question=question[:100], user_id=user_id)

        results = await self._vector_store.aquery(
            collection_name=DOCUMENTS_COLLECTION,
            query_text=question,
            where=where_filter,
        )

        context_chunks, sources = self._build_context(results)

        if not context_chunks:
            return (
                "I couldn't find any sufficiently relevant information in your uploaded "
                "documents. Please ensure relevant documents are uploaded or try rephrasing.",
                [],
            )

        prompt = self._llm_service.build_prompt(
            question, context_chunks, chat_history=chat_history
        )
        answer = await self._llm_service.generate(prompt)

        logger.info("rag_query_complete", sources_count=len(sources))
        return answer, sources

    async def query_stream(
        self,
        question: str,
        document_ids: list[str] | None = None,
        user_id: str | None = None,
        chat_history: list[dict] | None = None,
    ) -> tuple[AsyncGenerator[str, None], list[SourceChunk]]:
        where_filter = self._build_where_filter(user_id, document_ids)

        logger.info("rag_stream_start", question=question[:100], user_id=user_id)

        results = await self._vector_store.aquery(
            collection_name=DOCUMENTS_COLLECTION,
            query_text=question,
            where=where_filter,
        )

        context_chunks, sources = self._build_context(results)

        if not context_chunks:

            async def empty_response() -> AsyncGenerator[str, None]:
                yield (
                    "I couldn't find any sufficiently relevant information in your uploaded "
                    "documents. Please ensure relevant documents are uploaded or try rephrasing."
                )

            return empty_response(), []

        prompt = self._llm_service.build_prompt(
            question, context_chunks, chat_history=chat_history
        )
        stream = self._llm_service.generate_stream(prompt)

        return stream, sources
