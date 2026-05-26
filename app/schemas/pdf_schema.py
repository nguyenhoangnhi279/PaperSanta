"""
pdf_schema.py — Pydantic schemas cho PDF documents (request/response)
"""

from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional

from app.models.pdf_document import ProcessingStatus


    # ── Base Schema ───────────────────────────────────────────────────────────────
class PDFDocumentBase(BaseModel):
    """Các field chung cho PDF document"""
    filename: str
    original_name: str
    file_size: int = Field(..., description="File size in bytes")
    mime_type: str = "application/pdf"
    title: Optional[str] = None
    page_count: Optional[int] = None
    user_id: str = Field(..., description="Supabase Auth user ID")


# ── Response Schema ───────────────────────────────────────────────────────────
class PDFDocumentResponse(PDFDocumentBase):
    """Response khi query PDF document từ DB"""
    id: UUID
    file_path: str
    status: ProcessingStatus
    error_message: Optional[str] = None
    extracted_text: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    is_favorite: bool = False
    model_config = ConfigDict(from_attributes=True)


# ── Upload Response ───────────────────────────────────────────────────────────
class PDFUploadResponse(BaseModel):
    """Response sau khi upload PDF thành công"""
    id: UUID
    filename: str
    original_name: str
    file_size: int
    status: ProcessingStatus
    created_at: datetime
    message: str = "PDF uploaded successfully"

    model_config = ConfigDict(from_attributes=True)


# ── List Response ─────────────────────────────────────────────────────────────
class PDFDocumentListResponse(BaseModel):
    """Response cho danh sách PDF documents"""
    documents: list[PDFDocumentResponse]
    total: int


# ── Aliases ───────────────────────────────────────────────────────────────────
UploadResponse = PDFUploadResponse
PDFListResponse = PDFDocumentListResponse


# ── Summarize Response ────────────────────────────────────────────────────────
class SummarizeResponse(BaseModel):
    summary: str
    generated_at: datetime
    cached: bool = False


# ── Delete Response ───────────────────────────────────────────────────────────
class DeleteResponse(BaseModel):
    """Response sau khi xóa PDF thành công"""
    id: UUID
    message: str = "PDF deleted successfully"
    deleted: bool = True
