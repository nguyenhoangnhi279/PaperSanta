import uuid
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import APIRouter, UploadFile, File, Depends, Query, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, RedirectResponse

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from sqlalchemy import text


from app.core.database import get_db
from app.core.auth import get_current_user
from app.services.pdf_service import PDFService
from app.models.pdf_document import ProcessingStatus
from app.schemas.pdf_schema import (
    UploadResponse,
    PDFListResponse,
    PDFDocumentResponse,
    DeleteResponse,
    SummarizeResponse,
)
from app.models.pdf_document import PDFDocument
from app.models.embedding import PDFChunk, PDFEmbedding

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/pdf", tags=["PDF"])

# @router.get("/fix-db-favorite")
# async def fix_database_schema(db: AsyncSession = Depends(get_db)):
#     try:
#         await db.execute(text("ALTER TABLE pdf_documents ADD COLUMN IF NOT EXISTS is_favorite BOOLEAN DEFAULT FALSE NOT NULL;"))
#         await db.commit()
#         return {"message": "Tuyệt vời! Đã thêm cột is_favorite vào Database thành công!"}
#     except Exception as e:
#         await db.rollback()
#         return {"error": f"Có lỗi xảy ra: {str(e)}"}
@router.post("/upload", response_model=UploadResponse, status_code=201)
async def upload_pdf(
    file: UploadFile = File(..., description="File PDF cần upload"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    doc = await PDFService.upload_pdf(file, db, current_user["user_id"])

    await db.commit()
    background_tasks.add_task(PDFService.process_pdf, doc.id)

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

@asynccontextmanager
async def get_background_db():
    """Tạo một Database Session độc lập dành riêng cho Background Task"""
    gen = get_db()
    db = await anext(gen)
    try:
        yield db
    finally:
        try:
            await anext(gen)
        except StopAsyncIteration:
            pass

async def execute_background_delete(doc_id: uuid.UUID, user_id: str):
    """Hàm âm thầm dọn dẹp VectorDB và Supabase ở dưới nền"""
    async with get_background_db() as db:
        try:
            await PDFService.delete(doc_id, db, user_id)
            logger.info(f"Đã xóa ngầm hoàn tất PDF: {doc_id}")
        except Exception as e:
            logger.error(f"Lỗi khi xóa ngầm PDF {doc_id}: {e}")

@router.delete("/{doc_id}", response_model=DeleteResponse)
async def delete_pdf(
    doc_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    doc = await PDFService.get_by_id(doc_id, db, current_user["user_id"])
    background_tasks.add_task(execute_background_delete, doc_id, current_user["user_id"])
    return DeleteResponse(message="Đã xóa thành công.", id=doc.id)

@router.post("/{doc_id}/summarize", response_model=SummarizeResponse)
async def summarize_pdf(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await PDFService.summarize(doc_id, db, current_user["user_id"])
    return SummarizeResponse(
        summary=result["summary"],
        generated_at=result["generated_at"],
        cached=result["cached"],
    )


@router.post("/{doc_id}/index", status_code=202)
async def index_pdf(
    doc_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Trigger indexing pipeline for a PDF. Uses an atomic UPDATE to avoid races.

    If the PDF is in `pending` or `failed` state, transition it to processing
    and spawn a background task to run the pipeline. Otherwise return 409.
    """
    # Atomic update: only update when status is PENDING or FAILED
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
    updated = result.scalar_one_or_none()

    if not updated:
        raise HTTPException(409, "Tài liệu đang xử lý hoặc đã hoàn tất")

    # Commit will happen when dependency finishes; spawn background task
    background_tasks.add_task(PDFService.process_pdf, doc_id)

    return {"message": "Đang xử lý", "pdf_id": str(doc_id)}
@router.patch("/{doc_id}/favorite")
async def toggle_favorite(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    doc = await PDFService.get_by_id(doc_id, db, current_user["user_id"])
    
    doc.is_favorite = not doc.is_favorite
    await db.commit()
    
    return {"id": doc.id, "is_favorite": doc.is_favorite, "message": "Đã cập nhật yêu thích"}