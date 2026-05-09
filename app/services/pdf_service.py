import os
import uuid
import shutil
import logging
from pathlib import Path
from io import BytesIO

from fastapi import UploadFile, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from supabase import create_client, Client
from pypdf import PdfReader, PdfWriter

from app.core.config import settings
from app.models.pdf_document import PDFDocument, ProcessingStatus

logger = logging.getLogger(__name__)

def get_supabase_client() -> Client:
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(500, "Supabase credentials chưa được cấu hình")
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)


def compress_pdf(content: bytes) -> bytes:
    try:
        reader = PdfReader(BytesIO(content))
        writer = PdfWriter()

        for page in reader.pages:
            writer.add_page(page)

        for page in writer.pages:
            page.compress_content_streams()

        writer.add_metadata({"/Producer": "PaperSanta PDF Service"})

        output = BytesIO()
        writer.write(output)
        compressed = output.getvalue()

        original_size = len(content)
        compressed_size = len(compressed)
        compression_ratio = (1 - compressed_size / original_size) * 100

        logger.info(f"PDF compressed: {original_size} -> {compressed_size} bytes ({compression_ratio:.1f}% reduction)")

        return compressed

    except Exception as e:
        logger.warning(f"PDF compression failed: {e}, using original file")
        return content


class PDFService:

    @staticmethod
    async def upload_pdf(
        file: UploadFile,
        db: AsyncSession,
        user_id: str,
    ) -> PDFDocument:
        ext = Path(file.filename).suffix.lower().lstrip(".")
        if ext not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(400, f"Chỉ chấp nhận file PDF, nhận được: .{ext}")

        content = await file.read()
        if len(content) > settings.max_file_size_bytes:
            raise HTTPException(
                413,
                f"File quá lớn. Tối đa {settings.MAX_FILE_SIZE_MB}MB."
            )

        compressed_content = compress_pdf(content)

        unique_filename = f"{uuid.uuid4().hex}.pdf"
        storage_path = f"{user_id}/{unique_filename}"

        try:
            supabase = get_supabase_client()
            supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET).upload(
                path=storage_path,
                file=compressed_content,
                file_options={"content-type": "application/pdf"}
            )

            public_url = supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET).get_public_url(storage_path)

            logger.info(f"Uploaded to Supabase Storage: {storage_path} ({len(compressed_content)} bytes)")

        except Exception as e:
            logger.error(f"Failed to upload to Supabase Storage: {e}")
            raise HTTPException(500, f"Lỗi khi upload file: {str(e)}")

        doc = PDFDocument(
            filename=storage_path,
            original_name=file.filename,
            file_size=len(content),
            file_path=public_url,
            mime_type=file.content_type or "application/pdf",
            status=ProcessingStatus.PENDING,
            user_id=user_id,
        )
        db.add(doc)
        await db.flush()
        await db.refresh(doc)

        logger.info(f"Created PDF record: {doc.id} for user: {user_id}")
        return doc

    @staticmethod
    async def get_all(
        db: AsyncSession,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[int, list[PDFDocument]]:
        base = select(PDFDocument).where(PDFDocument.user_id == user_id)

        total_q = await db.execute(select(func.count()).select_from(PDFDocument).where(PDFDocument.user_id == user_id))
        total = total_q.scalar_one()

        result = await db.execute(
            base
            .order_by(PDFDocument.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        items = result.scalars().all()
        return total, list(items)

    @staticmethod
    async def get_by_id(doc_id: uuid.UUID, db: AsyncSession, user_id: str) -> PDFDocument:
        result = await db.execute(
            select(PDFDocument).where(PDFDocument.id == doc_id, PDFDocument.user_id == user_id)
        )
        doc = result.scalar_one_or_none()
        if not doc:
            raise HTTPException(404, f"Không tìm thấy PDF: {doc_id}")
        return doc

    @staticmethod
    async def delete(doc_id: uuid.UUID, db: AsyncSession, user_id: str) -> PDFDocument:
        doc = await PDFService.get_by_id(doc_id, db, user_id)

        try:
            supabase = get_supabase_client()
            supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET).remove([doc.filename])
            logger.info(f"Deleted from Supabase Storage: {doc.filename}")
        except Exception as e:
            logger.warning(f"Could not delete file from Supabase Storage: {e}")

        await db.delete(doc)
        await db.flush()

        return doc

    @staticmethod
    async def get_file_url(doc_id: uuid.UUID, db: AsyncSession, user_id: str) -> str:
        doc = await PDFService.get_by_id(doc_id, db, user_id)
        return doc.file_path
