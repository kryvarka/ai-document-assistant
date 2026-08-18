from src.services.llm_service import llm_service
from src.services.rag_pipeline import RAGPipeline
from src.services.vector_store import vector_store


def get_vector_store():
    return vector_store


def get_rag_pipeline():
    return RAGPipeline(vector_store=vector_store, llm_service=llm_service)
