import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_vector_store
from src.config import settings
from src.db.models import Document as DbDocument
from src.db.models import User
from src.db.session import get_db
from src.middleware.auth import get_current_user
from src.middleware.error_handler import DocumentProcessingError
from src.middleware.logging import get_logger
from src.middleware.rate_limit import rate_limit_upload
from src.models.schemas import DocumentListResponse, DocumentResponse, DocumentStatus
from src.services.ingestion import ingest_document
from src.services.vector_store import DOCUMENTS_COLLECTION, VectorStore

logger = get_logger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentResponse, status_code=202)
async def upload_document(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(rate_limit_upload),
    vs: VectorStore = Depends(get_vector_store),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    if not file.filename:
        raise DocumentProcessingError("Filename is required")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in settings.allowed_extensions:
        raise DocumentProcessingError(
            f"Unsupported file type: {suffix}. "
            f"Allowed: {', '.join(sorted(settings.allowed_extensions))}"
        )

    content = await file.read()
    file_size = len(content)

    if file_size == 0:
        raise DocumentProcessingError("File is empty")

    if file_size > settings.max_file_size_mb * 1024 * 1024:
        raise DocumentProcessingError(
            f"File too large. Maximum size: {settings.max_file_size_mb}MB"
        )

    document_id = str(uuid.uuid4())
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    saved_path = upload_dir / f"{document_id}{suffix}"
    saved_path.write_bytes(content)

    db_doc = DbDocument(
        id=document_id,
        filename=file.filename,
        file_type=suffix,
        file_size_bytes=file_size,
        chunk_count=0,
        status=DocumentStatus.PROCESSING,
        user_id=current_user.id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(db_doc)
    await db.commit()
    await db.refresh(db_doc)

    background_tasks.add_task(
        ingest_document,
        document_id=document_id,
        filename=file.filename,
        stored_path=saved_path,
        user_id=current_user.id,
        vector_store=vs,
    )

    logger.info(
        "document_upload_accepted",
        document_id=document_id,
        filename=file.filename,
        user_id=current_user.id,
    )
    return DocumentResponse.model_validate(db_doc)


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentListResponse:
    stmt = (
        select(DbDocument)
        .where(DbDocument.user_id == current_user.id)
        .order_by(DbDocument.created_at.desc())
    )
    result = await db.execute(stmt)
    documents = result.scalars().all()
    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(d) for d in documents],
        total=len(documents),
    )


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    vs: VectorStore = Depends(get_vector_store),
    db: AsyncSession = Depends(get_db),
) -> None:
    stmt = select(DbDocument).where(
        DbDocument.id == document_id,
        DbDocument.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or access denied",
        )

    try:
        await vs.adelete_by_filter(DOCUMENTS_COLLECTION, where={"document_id": document_id})
    except Exception as e:
        logger.warning("chroma_delete_warning", error=str(e))

    upload_dir = Path(settings.upload_dir)
    for file_path in upload_dir.glob(f"{document_id}*"):
        file_path.unlink(missing_ok=True)

    await db.delete(doc)
    await db.commit()
    logger.info("document_deleted", document_id=document_id, user_id=current_user.id)
