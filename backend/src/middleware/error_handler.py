from fastapi import Request
from fastapi.responses import JSONResponse

from src.middleware.logging import get_logger
from src.models.schemas import ErrorResponse

logger = get_logger(__name__)


class DocumentProcessingError(Exception):
    def __init__(self, detail: str):
        self.detail = detail


class VectorStoreError(Exception):
    def __init__(self, detail: str):
        self.detail = detail


class LLMServiceError(Exception):
    def __init__(self, detail: str):
        self.detail = detail


async def document_processing_error_handler(
    _request: Request, exc: DocumentProcessingError
) -> JSONResponse:
    logger.error("document_processing_error", detail=exc.detail)
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            detail=exc.detail, error_code="DOCUMENT_PROCESSING_ERROR"
        ).model_dump(),
    )


async def vector_store_error_handler(_request: Request, exc: VectorStoreError) -> JSONResponse:
    logger.error("vector_store_error", detail=exc.detail)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(detail=exc.detail, error_code="VECTOR_STORE_ERROR").model_dump(),
    )


async def llm_service_error_handler(_request: Request, exc: LLMServiceError) -> JSONResponse:
    logger.error("llm_service_error", detail=exc.detail)
    return JSONResponse(
        status_code=502,
        content=ErrorResponse(detail=exc.detail, error_code="LLM_SERVICE_ERROR").model_dump(),
    )


async def generic_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled_error", error=str(exc), error_type=type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            detail="An unexpected error occurred", error_code="INTERNAL_ERROR"
        ).model_dump(),
    )
