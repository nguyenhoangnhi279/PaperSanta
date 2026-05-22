"""search_router.py — Paper Search endpoint (V2)
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user
from app.services.paper_search_service import PaperSearchService
from app.schemas.search_schema import (
    PaperSearchResponse,
    PaperDetailResponse,
    RelatedPapersResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/search", tags=["Search"])


@router.get("/papers", response_model=PaperSearchResponse)
async def search_papers(
    q: str = Query(..., description="Query tìm kiếm"),
    limit: int = Query(10, ge=1, le=20, description="Số kết quả (max 20)"),
    offset: int = Query(0, ge=0, description="Offset"),
    year_from: int = Query(None, description="Năm từ"),
    year_to: int = Query(None, description="Năm đến"),
    min_citations: int = Query(None, description="Số trích dẫn tối thiểu"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    GET /api/search/papers — Gọi thẳng Semantic Scholar API + TTL Cache 1 giờ
    """
    logger.info(f"📡 Request search papers from S2 for query: '{q}'")
    
    result = await PaperSearchService.search_papers(
        query=q,
        limit=limit,
        offset=offset,
        year_from=year_from,
        year_to=year_to,
        min_citations=min_citations,
    )
    
    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result["error"],
        )
    
    return result


@router.get("/papers/{s2_id}", response_model=PaperDetailResponse)
async def get_paper_detail(
    s2_id: str = Path(..., description="Semantic Scholar ID"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    GET /api/search/papers/{s2_id} — Chi tiết 1 paper từ Semantic Scholar
    """
    result = await PaperSearchService.get_paper_detail(s2_id)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper not found or S2 API error",
        )
    
    return result


@router.get("/related/{pdf_id}", response_model=RelatedPapersResponse)
async def get_related_papers(
    pdf_id: str = Path(..., description="PDF ID"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    GET /api/search/related/{pdf_id} ⭐ Core — Tìm papers liên quan dựa trên các topic đã trích xuất sẵn
    """
    logger.info(f"🔍 GET /api/search/related/{pdf_id} called")
    user_id = current_user["user_id"]
    
    # Để nguyên định dạng chuỗi truyền xuống Service xử lý truy vấn cho khớp thiết kế
    result = await PaperSearchService.search_related_papers(
        pdf_id=pdf_id,
        user_id=user_id,
        db=db,
    )
    
    if "error" in result:
        status_code = result.get("status_code", 500)
        raise HTTPException(
            status_code=status_code,
            detail=result["error"],
        )
    
    return result