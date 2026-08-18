from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import auth, chat, conversations, documents, health
from src.db.session import init_db
from src.middleware.error_handler import (
    DocumentProcessingError,
    LLMServiceError,
    VectorStoreError,
    document_processing_error_handler,
    generic_error_handler,
    llm_service_error_handler,
    vector_store_error_handler,
)
from src.middleware.logging import RequestLoggingMiddleware, get_logger, setup_logging
from src.services.llm_service import llm_service
from src.services.vector_store import vector_store

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging()
    logger.info("application_starting")
    await init_db()
    vector_store.initialize()
    llm_service.initialize()
    logger.info("application_ready")
    yield
    logger.info("application_shutting_down")


def create_app() -> FastAPI:
    application = FastAPI(
        title="DocQA — Chat With Your Docs",
        description=(
            "RAG-powered document Q&A API with PostgreSQL 16, "
            "JWT multi-tenant security, and multi-turn conversation context"
        ),
        version="0.3.0",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(RequestLoggingMiddleware)

    application.add_exception_handler(DocumentProcessingError, document_processing_error_handler)
    application.add_exception_handler(VectorStoreError, vector_store_error_handler)
    application.add_exception_handler(LLMServiceError, llm_service_error_handler)
    application.add_exception_handler(Exception, generic_error_handler)

    application.include_router(health.router, prefix="/api")
    application.include_router(auth.router, prefix="/api")
    application.include_router(conversations.router, prefix="/api")
    application.include_router(documents.router, prefix="/api")
    application.include_router(chat.router, prefix="/api")

    return application


app = create_app()
