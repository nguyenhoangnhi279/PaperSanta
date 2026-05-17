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

from app.core.database import AsyncSessionLocal
from app.services.embedding_service import EmbeddingService
from app.core.embedding_provider import EmbeddingProvider
import httpx
import asyncio

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

    @staticmethod
    async def process_pdf(pdf_id: uuid.UUID) -> None:
        """Background pipeline: download -> extract -> chunk -> embed -> finish

        This function creates its own DB session and commits changes itself.
        """
        async with AsyncSessionLocal() as session:
            try:
                # load document
                result = await session.execute(select(PDFDocument).where(PDFDocument.id == pdf_id))
                doc = result.scalar_one_or_none()
                if not doc:
                    logger.error(f"PDF not found for processing: {pdf_id}")
                    return

                # Download file bytes from Supabase (try storage.download, fallback to public URL)
                supabase = get_supabase_client()
                file_bytes = None
                try:
                    try:
                        downloaded = supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET).download(doc.filename)
                        # some clients return bytes, others a file-like object
                        if isinstance(downloaded, (bytes, bytearray)):
                            file_bytes = bytes(downloaded)
                        elif hasattr(downloaded, "read"):
                            file_bytes = downloaded.read()
                    except Exception:
                        public_url = supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET).get_public_url(doc.filename)
                        async with httpx.AsyncClient() as client:
                            r = await client.get(public_url)
                            r.raise_for_status()
                            file_bytes = r.content

                    if not file_bytes:
                        raise RuntimeError("Could not download file bytes")

                except Exception as e:
                    doc.status = ProcessingStatus.FAILED
                    doc.error_message = f"Download failed: {e}"
                    await session.flush()
                    logger.exception("Failed to download PDF for processing")
                    return

                # Extract text per page
                try:
                    reader = PdfReader(BytesIO(file_bytes))
                    pages_text = []
                    for i, page in enumerate(reader.pages, start=1):
                        try:
                            text = page.extract_text() or ""
                        except Exception:
                            text = ""
                        pages_text.append(text)

                    doc.page_count = len(pages_text)
                    # keep only a truncated raw text to avoid huge DB fields
                    doc.extracted_text = "\n".join(pages_text)[: 200_000]
                    await session.flush()
                except Exception as e:
                    doc.status = ProcessingStatus.FAILED
                    doc.error_message = f"Extraction failed: {e}"
                    await session.flush()
                    logger.exception("Failed to extract PDF text")
                    return

                # Remove any existing chunks (idempotency)
                try:
                    await EmbeddingService.delete_chunks_by_pdf(session, pdf_id)
                    await session.flush()
                except Exception:
                    logger.exception("Failed to delete existing chunks; continuing")

                # Chunk the full document text
                full_text = "\n".join(pages_text)
                chunks = await EmbeddingService.chunk_pdf(session, pdf_id, full_text)
                await session.flush()

                # Prepare embeddings in batches
                chunk_texts = [c.chunk_text for c in chunks]
                chunk_ids = [c.id for c in chunks]
                batch_size = 32
                for i in range(0, len(chunk_texts), batch_size):
                    batch_texts = chunk_texts[i : i + batch_size]
                    batch_ids = chunk_ids[i : i + batch_size]
                    # Offload heavy embedding work to thread to avoid blocking event loop
                    vectors = await asyncio.to_thread(EmbeddingProvider.embed_texts, batch_texts)
                    await EmbeddingService.batch_create_embeddings(session, batch_ids, vectors)
                    await session.flush()

                # Mark as indexed (done)
                doc.status = ProcessingStatus.INDEXED
                await session.flush()
                logger.info(f"Completed indexing PDF: {pdf_id}")

            except Exception as e:
                logger.exception("Unexpected error in PDF processing pipeline")
                try:
                    if 'doc' in locals() and doc is not None:
                        doc.status = ProcessingStatus.FAILED
                        doc.error_message = str(e)
                        await session.flush()
                except Exception:
                    logger.exception("Failed to mark document as failed")
