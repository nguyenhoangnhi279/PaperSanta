import os
import uuid
import shutil
import logging
from pathlib import Path
from io import BytesIO
from datetime import datetime

from fastapi import UploadFile, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from supabase import create_client, Client
from pypdf import PdfReader

from app.core.config import settings
from app.models.pdf_document import PDFDocument, ProcessingStatus

logger = logging.getLogger(__name__)

from app.core.database import AsyncSessionLocal
from app.services.embedding_service import EmbeddingService
from app.core.embedding_provider import EmbeddingProvider
from app.core.deepseek_provider import DeepSeekProvider
import httpx
import asyncio

_supabase_client: Client | None = None

def get_supabase_client() -> Client:
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(500, "Supabase credentials chưa được cấu hình")
    _supabase_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    return _supabase_client


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

        unique_filename = f"{uuid.uuid4().hex}.pdf"
        storage_path = f"{user_id}/{unique_filename}"

        try:
            supabase = get_supabase_client()
            bucket = supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET)
            await asyncio.to_thread(
                lambda: bucket.upload(
                    path=storage_path,
                    file=content,
                    file_options={"content-type": "application/pdf"}
                )
            )

            public_url = await asyncio.to_thread(lambda: bucket.get_public_url(storage_path))

            logger.info(f"Uploaded to Supabase Storage: {storage_path} ({len(content)} bytes)")

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
            bucket = supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET)
            await asyncio.to_thread(lambda: bucket.remove([doc.filename]))
            logger.info(f"Deleted from Supabase Storage: {doc.filename}")
        except Exception as e:
            logger.warning(f"Could not delete file from Supabase Storage: {e}")

        # Bulk delete chunks (DB cascade ON DELETE CASCADE xoá embeddings tự động)
        from app.models.embedding import PDFChunk
        await db.execute(delete(PDFChunk).where(PDFChunk.pdf_id == doc_id))
        await db.execute(delete(PDFDocument).where(PDFDocument.id == doc_id))
        await db.commit()

        return doc

    @staticmethod
    async def get_file_url(doc_id: uuid.UUID, db: AsyncSession, user_id: str) -> str:
        doc = await PDFService.get_by_id(doc_id, db, user_id)
        return doc.file_path

    @staticmethod
    async def summarize(
        doc_id: uuid.UUID,
        db: AsyncSession,
        user_id: str,
    ) -> dict:
        """Generate TL;DR summary from parent chunks using DeepSeek."""
        from app.models.pdf_document import PDFDocument
        from app.models.embedding import PDFChunk

        doc = await PDFService.get_by_id(doc_id, db, user_id)

        # Return cached summary if exists
        if doc.summary:
            return {
                "summary": doc.summary,
                "generated_at": doc.summary_generated_at,
                "cached": True,
            }

        # Get all parent chunks ordered
        result = await db.execute(
            select(PDFChunk)
            .where(PDFChunk.pdf_id == doc_id, PDFChunk.chunk_type == "parent")
            .order_by(PDFChunk.chunk_index)
        )
        parents = result.scalars().all()
        if not parents:
            raise HTTPException(400, "Chưa có parent chunks. Vui lòng đợi indexing hoàn tất.")

        # Build prompt with parent texts
        text_parts = [f"[Section {p.chunk_index}] {p.chunk_text}" for p in parents]
        full_text = "\n\n".join(text_parts)

        system_prompt = (
            "Bạn là trợ lý nghiên cứu AI chuyên phân tích paper. "
            "Trả lời bằng tiếng Việt.\n\n"
            "Cấu trúc tóm tắt:\n"
            "## Vấn đề nghiên cứu\nÝ chính, motivation, gap mà paper giải quyết\n\n"
            "## Phương pháp\nCách tiếp cận chính, điểm mới so với prior work\n\n"
            "## Kết quả chính\nCác findings quan trọng, con số/metrics nếu có\n\n"
            "## Kết luận / Đóng góp\nTL;DR 2-3 câu: paper này đã làm gì, tại sao quan trọng"
        )
        user_prompt = f"Dưới đây là nội dung paper:\n\n{full_text}\n\nHãy tóm tắt chi tiết theo cấu trúc trên:"

        answer, prompt_tokens, completion_tokens = await asyncio.to_thread(
            lambda: DeepSeekProvider.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=settings.RAG_TEMPERATURE,
                max_tokens=settings.RAG_MAX_TOKENS,
            )
        )

        # Cache summary
        now = datetime.utcnow()
        doc.summary = answer
        doc.summary_generated_at = now
        await db.flush()
        # commit will be handled by get_db

        logger.info(f"Generated summary for PDF: {doc_id} ({prompt_tokens + completion_tokens} tokens)")

        return {
            "summary": answer,
            "generated_at": now,
            "cached": False,
        }

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
                    await session.commit()
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
                    await session.commit()
                    logger.exception("Failed to extract PDF text")
                    return

                if not doc.extracted_text or not doc.extracted_text.strip():
                    doc.status = ProcessingStatus.FAILED
                    doc.error_message = "Không thể trích xuất văn bản từ PDF (có thể là scanned PDF)"
                    await session.flush()
                    await session.commit()
                    logger.warning(f"No text extracted from PDF: {pdf_id}")
                    return

                # Remove any existing chunks (idempotency)
                try:
                    await EmbeddingService.delete_chunks_by_pdf(session, pdf_id)
                    await session.flush()
                except Exception:
                    logger.exception("Failed to delete existing chunks; continuing")

                # Chunk per-page: mỗi page chunk riêng, gắn page_number
                chunks = []
                chunk_offset = 0
                for page_num, page_text in enumerate(pages_text, start=1):
                    if not page_text.strip():
                        continue
                    page_chunks = await EmbeddingService.chunk_pdf(
                        session, pdf_id, page_text,
                        page_number=page_num,
                        chunk_index_offset=chunk_offset,
                    )
                    chunks.extend(page_chunks)
                    chunk_offset += len(page_chunks)
                await session.flush()

                if not chunks:
                    doc.status = ProcessingStatus.FAILED
                    doc.error_message = "Không thể tạo chunks từ văn bản"
                    await session.flush()
                    await session.commit()
                    logger.warning(f"No chunks created for PDF: {pdf_id}")
                    return

                # Embed only children chunks (parents dùng cho context/summarize)
                child_chunks = [c for c in chunks if c.chunk_type == "child"]
                if child_chunks:
                    chunk_texts = [c.chunk_text for c in child_chunks]
                    chunk_ids = [c.id for c in child_chunks]
                    batch_size = 32
                    for i in range(0, len(chunk_texts), batch_size):
                        batch_texts = chunk_texts[i : i + batch_size]
                        batch_ids = chunk_ids[i : i + batch_size]
                        vectors = await asyncio.to_thread(EmbeddingProvider.embed_texts, batch_texts)
                        await EmbeddingService.batch_create_embeddings(session, batch_ids, vectors)
                    await session.flush()
                    logger.info(f"Embedded {len(child_chunks)} children for PDF: {pdf_id}")
                else:
                    logger.warning(f"No children to embed for PDF: {pdf_id}")

                # Mark as indexed (done)
                doc.status = ProcessingStatus.INDEXED
                await session.flush()
                await session.commit()
                logger.info(f"Completed indexing PDF: {pdf_id}")

            except Exception as e:
                await session.rollback()
                logger.exception(f"Unexpected error in PDF processing pipeline: {e}")
                
                try:
                    result = await session.execute(select(PDFDocument).where(PDFDocument.id == pdf_id))
                    clean_doc = result.scalar_one_or_none()
                    
                    if clean_doc:
                        clean_doc.status = ProcessingStatus.FAILED
                        clean_doc.error_message = str(e)
                        await session.commit()
                        logger.info(f"Successfully marked PDF {pdf_id} as FAILED.")
                except Exception as inner_e:
                    logger.exception(f"Failed to mark document as failed: {inner_e}")
                    await session.rollback()
