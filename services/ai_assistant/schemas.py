from datetime import datetime

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    conversation_id: int | None = None
    message: str = Field(..., min_length=1, max_length=4000)
    top_k: int = Field(4, ge=1, le=10)


class Citation(BaseModel):
    document_id: int
    document_title: str
    position: int
    score: float
    snippet: str
    source_type: str = "raw"
    source_uri: str | None = None


class ChatResponse(BaseModel):
    conversation_id: int
    answer: str
    citations: list[Citation]
    provider: str
    used_rag: bool


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    citations: list
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationOut(BaseModel):
    id: int
    title: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
