"""
embedding_service.py — Business logic cho chunking & embedding
"""

import logging
from uuid import UUID
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pdf_document import PDFDocument
from app.models.embedding import PDFChunk, PDFEmbedding
from app.schemas.embedding_schema import PDFChunkResponse, PDFEmbeddingCreate

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service để manage PDF chunks & embeddings"""

    @staticmethod
    async def chunk_pdf(
        session: AsyncSession,
        pdf_id: UUID,
        text: str,
        chunk_size: int = 1000,
        overlap: int = 200,
    ) -> list[PDFChunk]:
        """
        Split PDF text thành chunks với overlap
        
        Args:
            session: Database session
            pdf_id: PDF document ID
            text: Extracted text từ PDF
            chunk_size: Kích thước mỗi chunk (characters)
            overlap: Overlap giữa các chunks
        
        Returns:
            List of created PDFChunk objects
        """
        if not text or not text.strip():
            logger.warning(f"Empty text for PDF {pdf_id}")
            return []

        chunks = []
        start_char = 0
        chunk_index = 0

        while start_char < len(text):
            end_char = min(start_char + chunk_size, len(text))
            chunk_text = text[start_char:end_char].strip()

            if chunk_text:
                chunk = PDFChunk(
                    pdf_id=pdf_id,
                    chunk_index=chunk_index,
                    chunk_text=chunk_text,
                    start_char=start_char,
                    end_char=end_char,
                    token_count=len(chunk_text.split()),  # rough estimate
                )
                chunks.append(chunk)
                session.add(chunk)
                chunk_index += 1

            # Move to next chunk with overlap
            start_char = end_char - overlap

        await session.flush()  # Flush to generate IDs
        logger.info(f"Created {len(chunks)} chunks for PDF {pdf_id}")
        return chunks

    @staticmethod
    async def create_embedding(
        session: AsyncSession,
        chunk_id: UUID,
        vector: list[float],
        embedding_model: str = "text-embedding-3-small",
    ) -> PDFEmbedding:
        """
        Tạo embedding cho một chunk
        
        Args:
            session: Database session
            chunk_id: Chunk ID
            vector: Vector embedding
            embedding_model: Tên model dùng để embed
        
        Returns:
            Created PDFEmbedding object
        """
        embedding_dimension = len(vector)

        embedding = PDFEmbedding(
            chunk_id=chunk_id,
            vector=vector,
            embedding_model=embedding_model,
            embedding_dimension=embedding_dimension,
        )
        session.add(embedding)
        await session.flush()
        logger.debug(f"Created embedding for chunk {chunk_id}")
        return embedding

    @staticmethod
    async def batch_create_embeddings(
        session: AsyncSession,
        chunk_ids: list[UUID],
        vectors: list[list[float]],
        embedding_model: str = "text-embedding-3-small",
    ) -> list[PDFEmbedding]:
        """
        Batch tạo embeddings cho nhiều chunks
        
        Args:
            session: Database session
            chunk_ids: List of chunk IDs
            vectors: List of vectors (phải cùng độ dài với chunk_ids)
            embedding_model: Tên model
        
        Returns:
            List of created embeddings
        """
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

        await session.flush()
        logger.info(f"Created {len(embeddings)} embeddings")
        return embeddings

    @staticmethod
    async def get_chunks_by_pdf(
        session: AsyncSession,
        pdf_id: UUID,
    ) -> list[PDFChunk]:
        """Lấy tất cả chunks của một PDF"""
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
        """Lấy chunk kèm embedding của nó"""
        chunk_stmt = select(PDFChunk).where(PDFChunk.id == chunk_id)
        chunk_result = await session.execute(chunk_stmt)
        chunk = chunk_result.scalar()

        if not chunk:
            return None, None

        embedding_stmt = select(PDFEmbedding).where(
            PDFEmbedding.chunk_id == chunk_id
        )
        embedding_result = await session.execute(embedding_stmt)
        embedding = embedding_result.scalar()

        return chunk, embedding

    @staticmethod
    async def delete_chunks_by_pdf(
        session: AsyncSession,
        pdf_id: UUID,
    ) -> int:
        """Xóa tất cả chunks của một PDF (embeddings xóa tự động via cascade)"""
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
        """Đếm số embeddings của một PDF"""
        stmt = (
            select(PDFEmbedding)
            .join(PDFChunk, PDFEmbedding.chunk_id == PDFChunk.id)
            .where(PDFChunk.pdf_id == pdf_id)
        )
        result = await session.execute(stmt)
        return len(result.scalars().all())
