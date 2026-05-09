import uuid
import logging
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Depends, Query
from fastapi.responses import FileResponse, RedirectResponse

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user
from app.services.pdf_service import PDFService
from app.schemas.pdf_schema import (
    UploadResponse,
    PDFListResponse,
    PDFDocumentResponse,
    DeleteResponse,
)

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
