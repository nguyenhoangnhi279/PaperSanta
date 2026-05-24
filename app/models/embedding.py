"""
embedding.py — ORM model cho bảng vector embeddings (RAG Phase 2)
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.pdf_document import PDFDocument


class PDFChunk(Base):
    """Bảng lưu chunks của PDF sau khi split"""
    __tablename__ = "pdf_chunks"

    # ── Identity ──────────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    
    pdf_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pdf_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pdf_chunks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ── Chunk info ────────────────────────────────────────────────────────────
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_type: Mapped[str] = mapped_column(String(10), default="child", nullable=False)

    # ── Metadata ──────────────────────────────────────────────────────────────
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_char: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_char: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # ── Relationship ──────────────────────────────────────────────────────────
    pdf_document: Mapped["PDFDocument"] = relationship("PDFDocument", back_populates="chunks")
    embeddings: Mapped[list["PDFEmbedding"]] = relationship(
        "PDFEmbedding",
        back_populates="chunk",
        cascade="all, delete-orphan",
    )
    parent: Mapped["PDFChunk | None"] = relationship(
        "PDFChunk", remote_side="PDFChunk.id", back_populates="children",
    )
    children: Mapped[list["PDFChunk"]] = relationship(
        "PDFChunk", back_populates="parent",
    )

    def __repr__(self) -> str:
        return f"<PDFChunk pdf_id={self.pdf_id} chunk_index={self.chunk_index} type={self.chunk_type}>"


class PDFEmbedding(Base):
    """Bảng lưu vector embeddings cho mỗi chunk (dùng cho RAG)"""
    __tablename__ = "pdf_embeddings"

    # ── Identity ──────────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pdf_chunks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Embedding vector ──────────────────────────────────────────────────────
    # Dùng pgvector extension của PostgreSQL (dimension = 384 cho all-MiniLM-L6-v2)
    vector: Mapped[str] = mapped_column(
        Vector(384),
        nullable=False,
        index=True,
    )

    # ── Embedding metadata ────────────────────────────────────────────────────
    embedding_model: Mapped[str] = mapped_column(
        String(100),
        default="all-MiniLM-L6-v2",
        nullable=False,
    )
    embedding_dimension: Mapped[int] = mapped_column(
        Integer,
        default=384,
        nullable=False,
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    # ── Relationship ──────────────────────────────────────────────────────────
    chunk: Mapped["PDFChunk"] = relationship("PDFChunk", back_populates="embeddings")

    def __repr__(self) -> str:
        return f"<PDFEmbedding chunk_id={self.chunk_id} model={self.embedding_model}>"
