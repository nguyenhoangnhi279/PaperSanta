"""
embedding_service.py — Business logic cho chunking & embedding
"""

import re
import uuid
import logging
from uuid import UUID
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.embedding import PDFChunk, PDFEmbedding

logger = logging.getLogger(__name__)


GARBAGE_PATTERNS = [
    re.compile(r'^\d+$'),
    re.compile(r'^Page \d+', re.IGNORECASE),
    re.compile(r'^https?://'),
    re.compile(r'^[\W_]+$'),
    re.compile(r'^Fig(ure)?\.?\s*\d+', re.IGNORECASE),
    re.compile(r'^Table\s*\d+', re.IGNORECASE),
    re.compile(r'^References?$', re.IGNORECASE),
    re.compile(r'^Bibliography$', re.IGNORECASE),
]


def _is_garbage(text: str) -> bool:
    t = text.strip()
    if len(t) < 50:
        return True
    for pat in GARBAGE_PATTERNS:
        if pat.match(t):
            return True
    return False


def _to_children(text: str, child_size: int = 150) -> list[str]:
    sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if len(sentences) <= 1:
        return [text.strip()] if text.strip() else []

    children = []
    current = []
    current_len = 0
    for sent in sentences:
        if current_len + len(sent) > child_size and current:
            children.append(" ".join(current).strip())
            current = []
            current_len = 0
        current.append(sent)
        current_len += len(sent)
    if current:
        children.append(" ".join(current).strip())

    return children


def _create_parent_child(
    pdf_id: UUID,
    text: str,
    child_size: int,
    page_number: int | None,
    chunk_index: int,
) -> tuple[PDFChunk, list[PDFChunk]]:
    parent_id = uuid.uuid4()
    parent = PDFChunk(
        id=parent_id,
        pdf_id=pdf_id,
        chunk_index=chunk_index,
        chunk_text=text,
        page_number=page_number,
        chunk_type="parent",
        token_count=len(text.split()),
    )

    children_texts = _to_children(text, child_size=child_size)
    children = []
    for i, child_text in enumerate(children_texts):
        child = PDFChunk(
            id=uuid.uuid4(),
            pdf_id=pdf_id,
            parent_id=parent_id,
            chunk_index=chunk_index + 1 + i,
            chunk_text=child_text,
            page_number=page_number,
            chunk_type="child",
            token_count=len(child_text.split()),
        )
        children.append(child)

    return parent, children


class EmbeddingService:

    @staticmethod
    async def chunk_pdf(
        session: AsyncSession,
        pdf_id: UUID,
        text: str,
        parent_size: int = 800,
        child_size: int = 150,
        page_number: int | None = None,
        chunk_index_offset: int = 0,
    ) -> list[PDFChunk]:
        """
        Paragraph-aware chunking với parent-child hierarchy.
        
        - Split text → paragraphs (\\n\\n)
        - Filter garbage (<50 chars, page numbers, URLs, ...)
        - Gom paragraphs vào parent chunks (~parent_size chars)
        - Split parent thành children (~child_size chars, sentence boundary)
        - Children: dùng cho embedding + similarity search
        - Parents: dùng cho LLM context / summarize
        """
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        paragraphs = [p for p in paragraphs if not _is_garbage(p)]
        if not paragraphs:
            return []

        chunks: list[PDFChunk] = []
        buffer: list[str] = []
        buffer_len = 0
        chunk_index = chunk_index_offset

        def flush_buffer() -> None:
            nonlocal buffer, buffer_len, chunk_index
            if not buffer:
                return
            parent_text = " ".join(buffer).strip()
            if not parent_text:
                return
            parent_chunk, child_chunks = _create_parent_child(
                pdf_id, parent_text, child_size, page_number, chunk_index,
            )
            chunks.append(parent_chunk)
            chunks.extend(child_chunks)
            chunk_index += 1 + len(child_chunks)
            buffer = []
            buffer_len = 0

        for para in paragraphs:
            para_len = len(para)

            # Single paragraph > parent_size → split into sentence-based parents
            if para_len > parent_size and not buffer:
                sentences = re.split(r'(?<=[.!?])\s+', para)
                sentences = [s.strip() for s in sentences if s.strip()]
                sent_buffer: list[str] = []
                sent_len = 0
                for sent in sentences:
                    if sent_len + len(sent) > parent_size and sent_buffer:
                        parent_text = " ".join(sent_buffer).strip()
                        parent_chunk, child_chunks = _create_parent_child(
                            pdf_id, parent_text, child_size, page_number, chunk_index,
                        )
                        chunks.append(parent_chunk)
                        chunks.extend(child_chunks)
                        chunk_index += 1 + len(child_chunks)
                        sent_buffer = []
                        sent_len = 0
                    sent_buffer.append(sent)
                    sent_len += len(sent)
                if sent_buffer:
                    parent_text = " ".join(sent_buffer).strip()
                    parent_chunk, child_chunks = _create_parent_child(
                        pdf_id, parent_text, child_size, page_number, chunk_index,
                    )
                    chunks.append(parent_chunk)
                    chunks.extend(child_chunks)
                    chunk_index += 1 + len(child_chunks)
                continue

            # Accumulate paragraphs
            if buffer_len + para_len > parent_size and buffer:
                flush_buffer()

            buffer.append(para)
            buffer_len += para_len

        flush_buffer()

        for c in chunks:
            session.add(c)
        await session.flush()

        logger.info(
            f"Created {len(chunks)} chunks for PDF {pdf_id} (page={page_number}): "
            f"{sum(1 for c in chunks if c.chunk_type == 'parent')} parents, "
            f"{sum(1 for c in chunks if c.chunk_type == 'child')} children"
        )
        return chunks

    @staticmethod
    async def create_embedding(
        session: AsyncSession,
        chunk_id: UUID,
        vector: list[float],
        embedding_model: str = "all-MiniLM-L6-v2",
    ) -> PDFEmbedding:
        embedding_dimension = len(vector)
        embedding = PDFEmbedding(
            chunk_id=chunk_id,
            vector=vector,
            embedding_model=embedding_model,
            embedding_dimension=embedding_dimension,
        )
        session.add(embedding)
        logger.debug(f"Created embedding for chunk {chunk_id}")
        return embedding

    @staticmethod
    async def batch_create_embeddings(
        session: AsyncSession,
        chunk_ids: list[UUID],
        vectors: list[list[float]],
        embedding_model: str = "all-MiniLM-L6-v2",
    ) -> list[PDFEmbedding]:
        if len(chunk_ids) != len(vectors):
            raise ValueError(f"Mismatch: {len(chunk_ids)} chunks vs {len(vectors)} vectors")
        embeddings = []
        for chunk_id, vector in zip(chunk_ids, vectors):
            embedding = PDFEmbedding(
                chunk_id=chunk_id,
                vector=vector,
                embedding_model=embedding_model,
                embedding_dimension=len(vector),
            )
            embeddings.append(embedding)
            session.add(embedding)
        logger.info(f"Created {len(embeddings)} embeddings")
        return embeddings

    @staticmethod
    async def get_chunks_by_pdf(
        session: AsyncSession,
        pdf_id: UUID,
    ) -> list[PDFChunk]:
        stmt = (
            select(PDFChunk)
            .where(PDFChunk.pdf_id == pdf_id)
            .order_by(PDFChunk.chunk_index)
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_chunk_with_embedding(
        session: AsyncSession,
        chunk_id: UUID,
    ) -> tuple[PDFChunk, PDFEmbedding | None]:
        chunk_stmt = select(PDFChunk).where(PDFChunk.id == chunk_id)
        chunk_result = await session.execute(chunk_stmt)
        chunk = chunk_result.scalar()
        if not chunk:
            return None, None
        embedding_stmt = select(PDFEmbedding).where(PDFEmbedding.chunk_id == chunk_id)
        embedding_result = await session.execute(embedding_stmt)
        embedding = embedding_result.scalar()
        return chunk, embedding

    @staticmethod
    async def delete_chunks_by_pdf(
        session: AsyncSession,
        pdf_id: UUID,
    ) -> int:
        stmt = delete(PDFChunk).where(PDFChunk.pdf_id == pdf_id)
        result = await session.execute(stmt)
        deleted_count = result.rowcount
        logger.info(f"Deleted {deleted_count} chunks for PDF {pdf_id}")
        return deleted_count

    @staticmethod
    async def count_embeddings_by_pdf(
        session: AsyncSession,
        pdf_id: UUID,
    ) -> int:
        stmt = (
            select(PDFEmbedding)
            .join(PDFChunk, PDFEmbedding.chunk_id == PDFChunk.id)
            .where(PDFChunk.pdf_id == pdf_id)
        )
        result = await session.execute(stmt)
        return len(result.scalars().all())
