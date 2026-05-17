import logging
import asyncio
from io import BytesIO
from uuid import UUID
from typing import List

import httpx
from pypdf import PdfReader
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.pdf_document import PDFDocument, ProcessingStatus
from app.services.embedding_service import EmbeddingService
from app.core.embedding_provider import EmbeddingProvider

logger = logging.getLogger(__name__)


class PDFPipelineService:
    """Background pipeline: download -> extract -> chunk -> embed -> save"""

    BATCH_SIZE = 32

    @staticmethod
    async def _download_file(url: str) -> bytes:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.get(url)
                r.raise_for_status()
                return r.content
        except Exception as e:
            logger.error(f"Failed to download PDF from {url}: {e}")
            raise

    @classmethod
    async def process(cls, pdf_id: UUID) -> None:
        async with AsyncSessionLocal() as session:
            try:
                # Reload document
                stmt = select(PDFDocument).where(PDFDocument.id == pdf_id)
                result = await session.execute(stmt)
                doc: PDFDocument = result.scalar_one_or_none()
                if not doc:
                    logger.error(f"PDF not found in pipeline: {pdf_id}")
                    return

                logger.info(f"Starting pipeline for PDF {pdf_id}")

                # Download file from public url
                try:
                    content = await cls._download_file(doc.file_path)
                except Exception as e:
                    doc.status = ProcessingStatus.FAILED
                    doc.error_message = f"Download failed: {e}"
                    session.add(doc)
                    await session.commit()
                    return

                # Extract text per page
                try:
                    reader = PdfReader(BytesIO(content))
                    pages_text: List[str] = []
                    for i, page in enumerate(reader.pages):
                        text = page.extract_text() or ""
                        pages_text.append(text)

                    full_text = "\n".join(pages_text).strip()
                    doc.extracted_text = full_text
                    # mark extracted (already set by caller when claiming)
                    doc.status = ProcessingStatus.EXTRACTED
                    session.add(doc)
                    await session.flush()
                    logger.info(f"Extracted text ({len(pages_text)} pages) for {pdf_id}")
                except Exception as e:
                    logger.exception(f"Extraction failed for {pdf_id}: {e}")
                    doc.status = ProcessingStatus.FAILED
                    doc.error_message = f"Extraction failed: {e}"
                    session.add(doc)
                    await session.commit()
                    return

                # Chunking
                try:
                    chunks = await EmbeddingService.chunk_pdf(session, pdf_id, full_text, chunk_size=500, overlap=50)
                    await session.flush()
                    logger.info(f"Chunked into {len(chunks)} pieces")
                except Exception as e:
                    logger.exception(f"Chunking failed for {pdf_id}: {e}")
                    doc.status = ProcessingStatus.FAILED
                    doc.error_message = f"Chunking failed: {e}"
                    session.add(doc)
                    await session.commit()
                    return

                # Embedding in batches
                try:
                    chunk_ids = [c.id for c in chunks]
                    texts = [c.chunk_text for c in chunks]

                    created = 0
                    for i in range(0, len(texts), cls.BATCH_SIZE):
                        batch_texts = texts[i : i + cls.BATCH_SIZE]
                        batch_chunk_ids = chunk_ids[i : i + cls.BATCH_SIZE]

                        vectors = EmbeddingProvider.embed_texts(batch_texts)

                        await EmbeddingService.batch_create_embeddings(session, batch_chunk_ids, vectors)
                        created += len(vectors)
                        logger.info(f"Embedded batch: {created}/{len(texts)}")

                    # Mark indexed
                    doc.status = ProcessingStatus.INDEXED
                    session.add(doc)
                    await session.commit()
                    logger.info(f"Indexing complete for {pdf_id}")
                except Exception as e:
                    logger.exception(f"Embedding/indexing failed for {pdf_id}: {e}")
                    doc.status = ProcessingStatus.FAILED
                    doc.error_message = f"Embedding/indexing failed: {e}"
                    session.add(doc)
                    await session.commit()
                    return

            except Exception as e:
                logger.exception(f"Unexpected pipeline error for {pdf_id}: {e}")
                try:
                    if 'doc' in locals() and doc:
                        doc.status = ProcessingStatus.FAILED
                        doc.error_message = f"Unexpected error: {e}"
                        session.add(doc)
                        await session.commit()
                except Exception:
                    logger.exception("Failed to mark document as failed")