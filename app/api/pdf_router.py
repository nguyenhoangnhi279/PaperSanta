import uuid
import logging
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Depends, Query, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, RedirectResponse

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.auth import get_current_user
from app.services.pdf_service import PDFService
from app.schemas.pdf_schema import (
    UploadResponse,
    PDFListResponse,
    PDFDocumentResponse,
    DeleteResponse,
)
from app.services.pdf_pipeline_service import PDFPipelineService
from app.models.pdf_document import PDFDocument
from app.models.embedding import PDFChunk, PDFEmbedding

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/pdf", tags=["PDF"])


@router.post("/upload", response_model=UploadResponse, status_code=201)
async def upload_pdf(
    file: UploadFile = File(..., description="File PDF cần upload"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    doc = await PDFService.upload_pdf(file, db, current_user["user_id"])

    response = UploadResponse(
        id=doc.id,
        filename=doc.filename,
        original_name=doc.original_name,
        file_size=doc.file_size,
        status=doc.status,
        created_at=doc.created_at,
        message="Upload thành công!"
    )

    logger.info(f"Upload response: {response.model_dump()}")

    return response



@router.get("/", response_model=PDFListResponse)
async def list_pdfs(
    skip:  int = Query(0,  ge=0,   description="Bỏ qua N records đầu"),
    limit: int = Query(20, ge=1, le=100, description="Số records mỗi trang"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    total, items = await PDFService.get_all(db, current_user["user_id"], skip=skip, limit=limit)
    return PDFListResponse(total=total, documents=items)


@router.get("/{doc_id}", response_model=PDFDocumentResponse)
async def get_pdf(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    doc = await PDFService.get_by_id(doc_id, db, current_user["user_id"])
    return PDFDocumentResponse.model_validate(doc)


@router.get("/{doc_id}/file")
async def serve_pdf(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    redirect: bool = Query(True, description="Redirect to file or return URL"),
):
    url = await PDFService.get_file_url(doc_id, db, current_user["user_id"])

    if redirect:
        return RedirectResponse(url=url, status_code=307)
    else:
        return {"url": url}


@router.delete("/{doc_id}", response_model=DeleteResponse)
async def delete_pdf(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    doc = await PDFService.delete(doc_id, db, current_user["user_id"])
    return DeleteResponse(message="Đã xóa thành công.", id=doc.id)


@router.post("/{doc_id}/index", status_code=202)
async def index_pdf(
    doc_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    # Atomic update: only set to 'extracted' when currently pending or failed
    from sqlalchemy import update, select
    from app.models.pdf_document import PDFDocument, ProcessingStatus

    stmt = (
        update(PDFDocument)
        .where(
            PDFDocument.id == doc_id,
            PDFDocument.user_id == current_user["user_id"],
            PDFDocument.status.in_([ProcessingStatus.PENDING, ProcessingStatus.FAILED]),
        )
        .values(status=ProcessingStatus.EXTRACTED)
        .returning(PDFDocument.id)
    )

    result = await db.execute(stmt)
    row = result.first()
    if not row:
        # nothing updated — resource is either not found or already processing/done
        raise HTTPException(409, "Tài liệu đang xử lý hoặc đã hoàn tất")

    # Spawn background pipeline
    background_tasks.add_task(PDFPipelineService.process, doc_id)

    return {"message": "Đang xử lý", "pdf_id": str(doc_id)}



@router.get("/{doc_id}/status")
async def pdf_status(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Trả về status, total_chunks, indexed_chunks, progress(%), error_message"""
    # load document
    doc = await PDFService.get_by_id(doc_id, db, current_user["user_id"])

    # count total chunks
    total_q = await db.execute(select(func.count()).select_from(PDFChunk).where(PDFChunk.pdf_id == doc_id))
    total_chunks = int(total_q.scalar_one() or 0)

    # count indexed embeddings (joined via chunks)
    idx_q = await db.execute(
        select(func.count())
        .select_from(PDFEmbedding)
        .join(PDFChunk, PDFEmbedding.chunk_id == PDFChunk.id)
        .where(PDFChunk.pdf_id == doc_id)
    )
    indexed_chunks = int(idx_q.scalar_one() or 0)

    progress = 0
    if total_chunks > 0:
        try:
            progress = round(indexed_chunks / total_chunks * 100)
        except Exception:
            progress = 0

    return {
        "status": str(doc.status.value if hasattr(doc.status, 'value') else doc.status),
        "total_chunks": total_chunks,
        "indexed_chunks": indexed_chunks,
        "progress": progress,
        "error_message": doc.error_message,
    }
