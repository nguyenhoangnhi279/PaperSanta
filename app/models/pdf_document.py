"""
pdf_document.py — ORM model cho bảng pdf_documents
"""

import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
import enum

from app.core.database import Base
from app.models.embedding import PDFChunk  # tránh circular import


class ProcessingStatus(str, enum.Enum):
    PENDING   = "pending"    # vừa upload, chưa xử lý
    EXTRACTED = "extracted"  # đã extract text
    INDEXED   = "indexed"    # đã index vào vector DB (RAG - phase 2)
    FAILED    = "failed"     # lỗi


class PDFDocument(Base):
    __tablename__ = "pdf_documents"

    # ── Identity ──────────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )

    # ── File info ─────────────────────────────────────────────────────────────
    filename: Mapped[str]      = mapped_column(String(255), nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int]     = mapped_column(Integer, nullable=False)        # bytes
    file_path: Mapped[str]     = mapped_column(String(512), nullable=False)    # local path
    mime_type: Mapped[str]     = mapped_column(String(100), default="application/pdf")

    # ── Metadata ──────────────────────────────────────────────────────────────
    title: Mapped[str | None]    = mapped_column(String(500), nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)   # raw text (phase 2)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Status ────────────────────────────────────────────────────────────────
    status: Mapped[ProcessingStatus] = mapped_column(
        SAEnum(ProcessingStatus, name="processingstatus"),
        default=ProcessingStatus.PENDING,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

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

    # ── Relationships ─────────────────────────────────────────────────────────
    chunks: Mapped[list["PDFChunk"]] = relationship(
        "PDFChunk",
        back_populates="pdf_document",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<PDFDocument id={self.id} name={self.original_name} status={self.status}>"
