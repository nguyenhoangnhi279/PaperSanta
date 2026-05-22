"""
search_schema.py — Validate cấu trúc dữ liệu cho Paper Search
"""

from pydantic import BaseModel, Field
from typing import List, Optional


class Author(BaseModel):
    """Thông tin tác giả"""
    name: str = Field(..., description="Tên tác giả")


class PaperSearchResult(BaseModel):
    """
    Một paper từ Semantic Scholar search
    """
    s2_id: str = Field(..., description="Semantic Scholar ID")
    title: str = Field(..., description="Tiêu đề paper")
    abstract: Optional[str] = Field(default=None, description="Tóm tắt")
    year: Optional[int] = Field(default=None, description="Năm xuất bản")
    authors: List[str] = Field(default=[], description="Danh sách tác giả")
    venue: Optional[str] = Field(default=None, description="Nơi công bố (conference/journal)")
    citation_count: int = Field(default=0, description="Số lần được trích dẫn")
    open_access_pdf: Optional[str] = Field(default=None, description="URL PDF nếu open access")


class PaperSearchResponse(BaseModel):
    """
    Response cho GET /api/search/papers
    """
    total: int = Field(..., description="Tổng số kết quả")
    query: str = Field(..., description="Query đã tìm kiếm")
    papers: List[PaperSearchResult] = Field(..., description="Danh sách papers")


class PaperDetailResponse(BaseModel):
    """
    Response chi tiết một paper từ Semantic Scholar
    """
    s2_id: str = Field(..., description="Semantic Scholar ID")
    title: str = Field(..., description="Tiêu đề")
    abstract: Optional[str] = Field(default=None, description="Tóm tắt")
    year: Optional[int] = Field(default=None, description="Năm")
    authors: List[str] = Field(default=[], description="Danh sách tác giả")
    venue: Optional[str] = Field(default=None, description="Nơi công bố")
    citation_count: int = Field(default=0, description="Số trích dẫn")
    reference_count: int = Field(default=0, description="Số tài liệu tham khảo")
    open_access_pdf: Optional[str] = Field(default=None, description="URL PDF")


class RelatedPapersResponse(BaseModel):
    """
    Response cho GET /api/search/related/{pdf_id}
    """
    source_pdf_id: str = Field(..., description="ID của PDF gốc")
    extracted_topics: List[str] = Field(..., description="Topics được trích xuất")
    related_papers: List[PaperSearchResult] = Field(..., description="Các papers liên quan")
    method: str = Field(..., description="Phương pháp: 'precomputed' | 'title_fallback'")
