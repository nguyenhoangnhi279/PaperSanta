"""
chat_schema.py — Pydantic schemas cho Chat/RAG feature
"""

from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional


class CitationResult(BaseModel):
    chunk_id: UUID
    chunk_index: int
    chunk_text: str
    score: float
    pdf_id: UUID
    pdf_name: str


class ChatRequest(BaseModel):
    query_text: str = Field(..., min_length=1, description="Câu hỏi của user")
    session_id: Optional[UUID] = Field(None, description="Session ID để tiếp tục hội thoại (null = tạo mới)")
    pdf_ids: list[UUID] = Field(..., min_length=1, description="List PDF IDs để search")
    top_k: int = Field(default=5, ge=1, le=20)


class ChatResponse(BaseModel):
    answer: str
    session_id: UUID
    citations: list[CitationResult]
    prompt_tokens: int = 0
    completion_tokens: int = 0

    model_config = ConfigDict(from_attributes=True)


class ChatMessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class ChatSessionResponse(BaseModel):
    id: UUID
    title: Optional[str] = None
    created_at: datetime
    messages: list[ChatMessageResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ChatSessionListItem(BaseModel):
    id: UUID
    title: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatSessionListResponse(BaseModel):
    sessions: list[ChatSessionListItem]
    total: int
