"""
analysis.py — ORM model cho bảng multi_analyses (Multi-paper Analyzer)
"""

import uuid
from datetime import datetime
from sqlalchemy import ForeignKey, String, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.pdf_document import PDFDocument

class AnalysisDocument(Base):
    """Bảng trung gian nối MultiAnalysis <-> PDFDocument"""
    __tablename__ = "analysis_documents"

    analysis_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("multi_analyses.id", ondelete="CASCADE"), primary_key=True)
    pdf_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pdf_documents.id", ondelete="CASCADE"), primary_key=True)


class MultiAnalysis(Base):
    __tablename__ = "multi_analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    analysis_type: Mapped[str] = mapped_column(String(100), nullable=False) # benchmark_matrix, v.v.
    result_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    documents: Mapped[list["PDFDocument"]] = relationship("PDFDocument", secondary="analysis_documents")