import asyncio

import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings
from google import genai

from src.config import settings
from src.middleware.error_handler import VectorStoreError
from src.middleware.logging import get_logger

logger = get_logger(__name__)

DOCUMENTS_COLLECTION = "documents"


class GeminiEmbeddingFunction(EmbeddingFunction):
    def __init__(self, api_key: str, model_name: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model_name = model_name

    def __call__(self, input: Documents) -> Embeddings:
        results: Embeddings = []
        batch_size = 100
        for i in range(0, len(input), batch_size):
            batch = input[i : i + batch_size]
            response = self._client.models.embed_content(
                model=self._model_name,
                contents=batch,
                config={"task_type": "RETRIEVAL_DOCUMENT"},
            )
            for embedding in response.embeddings:
                results.append(embedding.values)
        return results

    def embed_query(self, query_text: str) -> list[float]:
        response = self._client.models.embed_content(
            model=self._model_name,
            contents=[query_text],
            config={"task_type": "RETRIEVAL_QUERY"},
        )
        return response.embeddings[0].values


class VectorStore:
    def __init__(self) -> None:
        self._client: chromadb.ClientAPI | None = None
        self._embedding_fn: GeminiEmbeddingFunction | None = None

    def initialize(self) -> None:
        try:
            self._client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
            self._embedding_fn = GeminiEmbeddingFunction(
                api_key=settings.gemini_api_key,
                model_name=settings.embedding_model,
            )
            logger.info(
                "vector_store_initialized",
                persist_dir=settings.chroma_persist_dir,
                embedding_model=settings.embedding_model,
            )
        except Exception as exc:
            raise VectorStoreError(f"Failed to initialize vector store: {exc}") from exc

    @property
    def is_ready(self) -> bool:
        return self._client is not None

    @property
    def client(self) -> chromadb.ClientAPI:
        if self._client is None:
            raise VectorStoreError("Vector store not initialized")
        return self._client

    def _get_collection(self, collection_name: str) -> chromadb.Collection:
        return self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self._embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )

    def add_documents(
        self,
        collection_name: str,
        chunks: list[str],
        metadatas: list[dict],
        ids: list[str],
    ) -> None:
        try:
            collection = self._get_collection(collection_name)
            batch_size = 100
            for i in range(0, len(chunks), batch_size):
                collection.add(
                    documents=chunks[i : i + batch_size],
                    metadatas=metadatas[i : i + batch_size],
                    ids=ids[i : i + batch_size],
                )
            logger.info(
                "documents_added",
                collection=collection_name,
                chunk_count=len(chunks),
            )
        except Exception as exc:
            raise VectorStoreError(f"Failed to add documents: {exc}") from exc

    async def aadd_documents(
        self,
        collection_name: str,
        chunks: list[str],
        metadatas: list[dict],
        ids: list[str],
    ) -> None:
        await asyncio.to_thread(self.add_documents, collection_name, chunks, metadatas, ids)

    def query(
        self,
        collection_name: str,
        query_text: str,
        n_results: int = settings.top_k,
        where: dict | None = None,
    ) -> dict:
        try:
            collection = self._get_collection(collection_name)
            if collection.count() == 0:
                return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

            if self._embedding_fn:
                query_embeddings = [self._embedding_fn.embed_query(query_text)]
                query_params: dict = {
                    "query_embeddings": query_embeddings,
                    "n_results": min(n_results, collection.count()),
                }
            else:
                query_params = {
                    "query_texts": [query_text],
                    "n_results": min(n_results, collection.count()),
                }

            if where:
                query_params["where"] = where

            results = collection.query(**query_params)
            logger.info(
                "query_executed",
                collection=collection_name,
                results_count=(len(results["documents"][0]) if results["documents"] else 0),
            )
            return results
        except Exception as exc:
            raise VectorStoreError(f"Query failed: {exc}") from exc

    async def aquery(
        self,
        collection_name: str,
        query_text: str,
        n_results: int = settings.top_k,
        where: dict | None = None,
    ) -> dict:
        return await asyncio.to_thread(self.query, collection_name, query_text, n_results, where)

    def delete_by_filter(self, collection_name: str, where: dict) -> None:
        try:
            collection = self._get_collection(collection_name)
            collection.delete(where=where)
            logger.info("chunks_deleted_by_filter", collection=collection_name, where=where)
        except Exception as exc:
            raise VectorStoreError(f"Failed to delete chunks: {exc}") from exc

    async def adelete_by_filter(self, collection_name: str, where: dict) -> None:
        await asyncio.to_thread(self.delete_by_filter, collection_name, where)


vector_store = VectorStore()
