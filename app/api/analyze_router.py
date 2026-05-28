"""analyze_router.py — Multi-paper analysis endpoints"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.analysis import MultiAnalysis, AnalysisDocument
from app.models.pdf_document import PDFDocument
from app.schemas.analysis_schema import AnalysisRequest, AnalysisResult, AnalysisHistoryResponse
from app.services.analyze_service import AnalyzeService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analyze", tags=["Analyze"])


@router.post("/run", response_model=AnalysisResult)
async def run_analysis(
    req: AnalysisRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    user_id = user["user_id"]
    if len(req.pdf_ids) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 PDFs for analysis")

    try:
        result = await AnalyzeService.run_analysis(
            db=db,
            user_id=user_id,
            pdf_ids=req.pdf_ids,
            analysis_type=req.analysis_type,
            custom_prompt=req.custom_prompt,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail="Analysis failed")


@router.get("/history", response_model=AnalysisHistoryResponse)
async def list_analyses(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    user_id = user["user_id"]

    count_q = select(func.count()).select_from(MultiAnalysis).where(MultiAnalysis.user_id == user_id)
    total = (await db.execute(count_q)).scalar() or 0

    q = (
        select(MultiAnalysis)
        .where(MultiAnalysis.user_id == user_id)
        .order_by(MultiAnalysis.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    rows = (await db.execute(q)).scalars().all()

    analyses = []
    for a in rows:
        doc_ids_q = select(AnalysisDocument.pdf_id).where(AnalysisDocument.analysis_id == a.id)
        doc_ids = (await db.execute(doc_ids_q)).scalars().all()
        if doc_ids:
            pdfs_q = select(PDFDocument.original_name).where(PDFDocument.id.in_(doc_ids))
            pdf_names = list((await db.execute(pdfs_q)).scalars().all())
        else:
            pdf_names = []

        analyses.append(AnalysisResult(
            id=str(a.id),
            analysis_type=a.analysis_type,
            result_json=a.result_json,
            pdf_names=pdf_names,
            created_at=a.created_at,
        ))

    return AnalysisHistoryResponse(analyses=analyses, total=total)


@router.get("/history/{analysis_id}", response_model=AnalysisResult)
async def get_analysis(
    analysis_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    user_id = user["user_id"]
    a = await db.get(MultiAnalysis, UUID(analysis_id))
    if not a or a.user_id != user_id:
        raise HTTPException(status_code=404, detail="Analysis not found")

    doc_ids_q = select(AnalysisDocument.pdf_id).where(AnalysisDocument.analysis_id == a.id)
    doc_ids = (await db.execute(doc_ids_q)).scalars().all()
    pdf_names = []
    if doc_ids:
        pdfs_q = select(PDFDocument.original_name).where(PDFDocument.id.in_(doc_ids))
        pdf_names = list((await db.execute(pdfs_q)).scalars().all())

    return AnalysisResult(
        id=str(a.id),
        analysis_type=a.analysis_type,
        result_json=a.result_json,
        pdf_names=pdf_names,
        created_at=a.created_at,
    )


@router.delete("/history/{analysis_id}")
async def delete_analysis(
    analysis_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    user_id = user["user_id"]
    a = await db.get(MultiAnalysis, UUID(analysis_id))
    if not a or a.user_id != user_id:
        raise HTTPException(status_code=404, detail="Analysis not found")
    await db.delete(a)
    await db.commit()
    return {"status": "deleted"}
