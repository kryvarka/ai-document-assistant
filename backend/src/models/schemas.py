from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field


class DocumentStatus(StrEnum):
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "0.3.0"
    database: str = "connected"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    chunk_count: int
    status: DocumentStatus
    error_message: str | None = None
    file_size_bytes: int
    user_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int


class SourceChunk(BaseModel):
    content: str
    document_name: str
    chunk_index: int
    relevance_score: float


class ChatMessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    sources: list[SourceChunk] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationResponse(BaseModel):
    id: str
    title: str
    user_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationDetailResponse(BaseModel):
    id: str
    title: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessageResponse] = []

    model_config = {"from_attributes": True}


class ConversationCreate(BaseModel):
    title: str = Field(default="New Conversation", max_length=200)


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    conversation_id: str | None = None
    document_ids: list[str] | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]
    model: str
    conversation_id: str | None = None
    message_id: str | None = None


class ErrorResponse(BaseModel):
    detail: str
    error_code: str | None = None
