"""
chat_schema.py — Pydantic schemas cho Chat/RAG feature
"""

from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional


class CitationResult(BaseModel):
    source_id: Optional[int] = None
    chunk_id: UUID
    chunk_text: str
    score: float
    pdf_id: UUID
    pdf_name: str
    page_number: Optional[int] = None
    block_id: Optional[UUID] = None
    bbox: Optional[list[float]] = None
    section_path: list[str] | None = None
    source_block_type: Optional[str] = None
    retrieval_sources: list[str] = []


class CitationInput(BaseModel):
    source_id: Optional[int] = None
    chunk_id: UUID
    chunk_text: str
    score: float
    pdf_id: UUID
    pdf_name: str
    page_number: Optional[int] = None
    block_id: Optional[UUID] = None
    bbox: Optional[list[float]] = None
    section_path: list[str] | None = None
    source_block_type: Optional[str] = None
    retrieval_sources: list[str] = []


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
    retrieval_query: Optional[str] = None


class ExplainSelectionRequest(BaseModel):
    pdf_id: UUID
    selected_text: str = Field(..., min_length=1)
    page_number: Optional[int] = Field(None, ge=1)
    surrounding_text: Optional[str] = None
    top_k: int = Field(default=8, ge=1, le=20)


class ExplainSelectionResponse(BaseModel):
    answer: str
    citations: list[CitationResult]
    prompt_tokens: int = 0
    completion_tokens: int = 0


class ChatMessageItem(BaseModel):
    role: str
    content: str
    ts: datetime
    tokens: Optional[dict] = None
    citations: list[CitationResult] = []
    retrieval_query: Optional[str] = None


class ChatSessionResponse(BaseModel):
    id: UUID
    title: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    messages: list[ChatMessageItem] = []
    pdf_ids: list[UUID] = []

    model_config = ConfigDict(from_attributes=True)


class ChatSessionListItem(BaseModel):
    id: UUID
    title: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    pdf_ids: list[UUID] = []

    model_config = ConfigDict(from_attributes=True)


class ChatSessionListResponse(BaseModel):
    sessions: list[ChatSessionListItem]
    total: int
