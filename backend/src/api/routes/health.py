from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.models.schemas import HealthResponse
from src.services.vector_store import vector_store

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> HealthResponse:
    db_connected = False
    try:
        res = await db.execute(text("SELECT 1"))
        if res.scalar() == 1:
            db_connected = True
    except Exception:
        db_connected = False

    is_healthy = db_connected and vector_store.is_ready
    if not is_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status="healthy" if is_healthy else "degraded",
        version="0.3.0",
        database="connected" if db_connected else "disconnected",
        timestamp=datetime.now(timezone.utc),
    )
