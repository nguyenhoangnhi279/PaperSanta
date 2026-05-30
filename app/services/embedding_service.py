"""
embedding_service.py — Business logic cho chunking & embedding
"""

import re
import uuid
import logging
from uuid import UUID
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import import_all_models
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


def _overlap_tail(text: str, overlap_size: int) -> str:
    if overlap_size <= 0 or len(text) <= overlap_size:
        return text if overlap_size > 0 else ""
    tail = text[-overlap_size:]
    first_space = tail.find(" ")
    if first_space > 0:
        tail = tail[first_space + 1:]
    return tail.strip()


def _to_children(text: str, child_size: int = 450, overlap_size: int = 120) -> list[str]:
    sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if len(sentences) <= 1:
        return [text.strip()] if text.strip() else []

    children = []
    current = []
    current_len = 0
    for sent in sentences:
        if current_len + len(sent) > child_size and current:
            chunk = " ".join(current).strip()
            children.append(chunk)
            overlap = _overlap_tail(chunk, overlap_size)
            current = [overlap] if overlap else []
            current_len = len(overlap)
        current.append(sent)
        current_len += len(sent)
    if current:
        children.append(" ".join(current).strip())

    return children


def _table_children(text: str, child_size: int, section_path: list[str] | None) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []

    title_lines = [line for line in lines[:3] if not line.startswith("|")]
    table_lines = [line for line in lines if line.startswith("|")]
    if len(table_lines) < 3:
        return [_with_section_context(text, section_path)]

    header = table_lines[:2]
    rows = table_lines[2:]
    children: list[str] = []
    current_rows: list[str] = []
    current_len = len("\n".join(title_lines + header))

    for row in rows:
        if current_rows and current_len + len(row) > child_size:
            child = "\n".join(title_lines + header + current_rows).strip()
            children.append(_with_section_context(child, section_path))
            current_rows = []
            current_len = len("\n".join(title_lines + header))
        current_rows.append(row)
        current_len += len(row)

    if current_rows:
        child = "\n".join(title_lines + header + current_rows).strip()
        children.append(_with_section_context(child, section_path))
    return children


def _section_header(section_path: list[str] | None) -> str:
    if not section_path:
        return ""
    clean_path = [part.strip() for part in section_path if part and part.strip()]
    if not clean_path:
        return ""
    return " > ".join(clean_path)


def _with_section_context(text: str, section_path: list[str] | None) -> str:
    header = _section_header(section_path)
    if not header:
        return text
    if text.lstrip().startswith("[Section:"):
        return text
    return f"[Section: {header}]\n{text}"


def _create_parent_child(
    pdf_id: UUID,
    text: str,
    child_size: int,
    child_overlap: int,
    page_number: int | None,
    chunk_index: int,
    section_path: list[str] | None = None,
    source_block_type: str | None = None,
) -> tuple[PDFChunk, list[PDFChunk]]:
    parent_id = uuid.uuid4()
    parent_text = _with_section_context(text, section_path)
    parent = PDFChunk(
        id=parent_id,
        pdf_id=pdf_id,
        chunk_index=chunk_index,
        chunk_text=parent_text,
        page_number=page_number,
        chunk_type="parent",
        token_count=len(parent_text.split()),
    )

    if source_block_type in {"table", "equation"}:
        if source_block_type == "table":
            children_texts = _table_children(text, child_size, section_path)
        else:
            children_texts = [_with_section_context(text, section_path)]
    else:
        children_texts = [
            _with_section_context(child_text, section_path)
            for child_text in _to_children(text, child_size=child_size, overlap_size=child_overlap)
        ]
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


def _attach_chunk_metadata(
    chunks: list[PDFChunk],
    block_id: UUID | None,
    source_block_type: str | None,
    section_path: list[str] | None,
) -> None:
    for chunk in chunks:
        chunk.block_id = block_id
        chunk.source_block_type = source_block_type
        chunk.section_path = section_path


class EmbeddingService:

    @staticmethod
    async def chunk_pdf(
        session: AsyncSession,
        pdf_id: UUID,
        text: str,
        parent_size: int | None = None,
        child_size: int | None = None,
        child_overlap: int | None = None,
        page_number: int | None = None,
        chunk_index_offset: int = 0,
        block_id: UUID | None = None,
        source_block_type: str | None = None,
        section_path: list[str] | None = None,
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
        parent_size = parent_size or settings.CHUNK_PARENT_SIZE_CHARS
        child_size = child_size or settings.CHUNK_CHILD_SIZE_CHARS
        child_overlap = child_overlap if child_overlap is not None else settings.CHUNK_CHILD_OVERLAP_CHARS
        import_all_models()
        text = text.replace("\x00", "")

        if source_block_type in {"table", "equation"}:
            parent_chunk, child_chunks = _create_parent_child(
                pdf_id,
                text.strip(),
                child_size,
                child_overlap,
                page_number,
                chunk_index_offset,
                section_path,
                source_block_type,
            )
            chunks = [parent_chunk, *child_chunks]
            _attach_chunk_metadata(chunks, block_id, source_block_type, section_path)
            for chunk in chunks:
                session.add(chunk)
            await session.flush()
            logger.info(
                f"Created {len(chunks)} chunks for PDF {pdf_id} (page={page_number}, block={source_block_type}): "
                f"{sum(1 for c in chunks if c.chunk_type == 'parent')} parents, "
                f"{sum(1 for c in chunks if c.chunk_type == 'child')} children"
            )
            return chunks

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
                pdf_id, parent_text, child_size, child_overlap, page_number, chunk_index, section_path, source_block_type,
            )
            _attach_chunk_metadata([parent_chunk, *child_chunks], block_id, source_block_type, section_path)
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
                            pdf_id, parent_text, child_size, child_overlap, page_number, chunk_index, section_path, source_block_type,
                        )
                        _attach_chunk_metadata([parent_chunk, *child_chunks], block_id, source_block_type, section_path)
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
                        pdf_id, parent_text, child_size, child_overlap, page_number, chunk_index, section_path, source_block_type,
                    )
                    _attach_chunk_metadata([parent_chunk, *child_chunks], block_id, source_block_type, section_path)
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
        embedding_model: str | None = None,
    ) -> PDFEmbedding:
        embedding_dimension = len(vector)
        embedding = PDFEmbedding(
            chunk_id=chunk_id,
            vector=vector,
            embedding_model=embedding_model or settings.EMBEDDING_MODEL_NAME,
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
        embedding_model: str | None = None,
    ) -> list[PDFEmbedding]:
        if len(chunk_ids) != len(vectors):
            raise ValueError(f"Mismatch: {len(chunk_ids)} chunks vs {len(vectors)} vectors")
        embeddings = []
        for chunk_id, vector in zip(chunk_ids, vectors):
            embedding = PDFEmbedding(
                chunk_id=chunk_id,
                vector=vector,
                embedding_model=embedding_model or settings.EMBEDDING_MODEL_NAME,
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
