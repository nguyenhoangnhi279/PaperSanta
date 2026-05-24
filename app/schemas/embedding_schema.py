"""
embedding_schema.py — Pydantic schemas cho RAG query & chunk response
"""

from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional


class PDFChunkResponse(BaseModel):
    """Response schema cho chunk"""
    id: UUID
    pdf_id: UUID
    chunk_index: int
    chunk_text: str
    page_number: Optional[int] = None
    start_char: Optional[int] = None
    end_char: Optional[int] = None
    token_count: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── RAG Query Schema ──────────────────────────────────────────────────────────
class RAGQueryRequest(BaseModel):
    """Request cho RAG similarity search"""
    query_text: str = Field(..., min_length=1, description="Câu hỏi của user")
    top_k: int = Field(default=5, ge=1, le=100)
    pdf_id: Optional[UUID] = None  # Filter by specific PDF


class RAGQueryResult(BaseModel):
    """Kết quả từ RAG search"""
    chunk: PDFChunkResponse
    score: float = Field(..., ge=0, le=1)
    pdf_id: UUID

    model_config = ConfigDict(from_attributes=True)


class RAGQueryResponse(BaseModel):
    """Response cho RAG query"""
    results: list[RAGQueryResult]
    query_time_ms: float
    total_chunks_searched: int
