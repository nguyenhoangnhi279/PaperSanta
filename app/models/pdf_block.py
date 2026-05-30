"""Structured extraction blocks for PDFs."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PDFBlock(Base):
    __tablename__ = "pdf_blocks"

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
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    block_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    section_path: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    content_json: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    bbox: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    extractor: Mapped[str] = mapped_column(String(100), nullable=False)

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

    pdf_document = relationship("PDFDocument", back_populates="blocks")
    chunks = relationship("PDFChunk", back_populates="block")

    def __repr__(self) -> str:
        return f"<PDFBlock pdf_id={self.pdf_id} page={self.page_number} type={self.block_type}>"
