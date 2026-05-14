"""
embedding_schema.py — Pydantic schemas cho embeddings (request/response)
"""

from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional
from enum import Enum


# ── Chunk Schemas ─────────────────────────────────────────────────────────────
class PDFChunkBase(BaseModel):
    """Base schema cho PDF chunk"""
    chunk_index: int = Field(..., description="Thứ tự chunk")
    chunk_text: str = Field(..., description="Nội dung chunk")
    page_number: Optional[int] = None
    token_count: Optional[int] = None


class PDFChunkCreate(PDFChunkBase):
    """Schema để tạo chunk"""
    pdf_id: UUID


class PDFChunkResponse(PDFChunkBase):
    """Response schema cho chunk"""
    id: UUID
    pdf_id: UUID
    start_char: Optional[int] = None
    end_char: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PDFChunkListResponse(BaseModel):
    """Response cho danh sách chunks"""
    chunks: list[PDFChunkResponse]
    total: int


# ── Embedding Schemas ─────────────────────────────────────────────────────────
class PDFEmbeddingBase(BaseModel):
    """Base schema cho embedding"""
    embedding_model: str = Field(default="text-embedding-3-small")
    embedding_dimension: int = Field(default=1536)


class PDFEmbeddingCreate(PDFEmbeddingBase):
    """Schema để tạo embedding (dùng bên trong service)"""
    chunk_id: UUID
    vector: list[float] = Field(..., description="Vector embedding")


class PDFEmbeddingResponse(PDFEmbeddingBase):
    """Response schema cho embedding"""
    id: UUID
    chunk_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PDFEmbeddingWithChunk(BaseModel):
    """Response embedding kèm chunk info"""
    embedding: PDFEmbeddingResponse
    chunk: PDFChunkResponse


# ── Batch Response ────────────────────────────────────────────────────────────
class ChunkingResponse(BaseModel):
    """Response sau khi chunk PDF"""
    pdf_id: UUID
    total_chunks: int
    chunks: list[PDFChunkResponse]
    message: str = "PDF chunked successfully"


class EmbeddingBatchResponse(BaseModel):
    """Response sau khi embed chunks"""
    pdf_id: UUID
    total_embeddings: int
    embedding_model: str
    message: str = "Embeddings created successfully"


# ── RAG Query Schema ──────────────────────────────────────────────────────────
class RAGQueryRequest(BaseModel):
    """Request cho RAG similarity search"""
    query_vector: list[float] = Field(..., description="Query embedding vector")
    top_k: int = Field(default=5, ge=1, le=100)
    pdf_id: Optional[UUID] = None  # Filter by specific PDF


class RAGQueryResult(BaseModel):
    """Kết quả từ RAG search"""
    chunk: PDFChunkResponse
    similarity_score: float = Field(..., ge=0, le=1)
    pdf_id: UUID


class RAGQueryResponse(BaseModel):
    """Response cho RAG query"""
    results: list[RAGQueryResult]
    query_time_ms: float
    total_chunks_searched: int
