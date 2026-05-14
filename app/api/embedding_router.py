"""
embedding_router.py — API endpoints cho embeddings (RAG Phase 2)
"""

import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.pdf_document import PDFDocument
from app.schemas.embedding_schema import (
    PDFChunkResponse,
    PDFChunkListResponse,
    ChunkingResponse,
    EmbeddingBatchResponse,
)
from app.services.embedding_service import EmbeddingService
from app.services.pdf_service import PDFService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/embeddings", tags=["Embeddings"])


@router.post("/{pdf_id}/chunk", response_model=ChunkingResponse)
async def chunk_pdf(
    pdf_id: UUID,
    chunk_size: int = 1000,
    overlap: int = 200,
    session: AsyncSession = Depends(get_db),
):
    """
    Split PDF content thành chunks
    
    - **pdf_id**: PDF document ID
    - **chunk_size**: Kích thước mỗi chunk (default: 1000 characters)
    - **overlap**: Overlap giữa chunks (default: 200 characters)
    """
    # Get PDF document
    pdf = await PDFService.get_pdf_by_id(session, pdf_id)
    if not pdf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PDF {pdf_id} not found",
        )

    if not pdf.extracted_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PDF text not extracted yet. Please extract text first.",
        )

    # Delete existing chunks
    await EmbeddingService.delete_chunks_by_pdf(session, pdf_id)

    # Chunk the PDF
    chunks = await EmbeddingService.chunk_pdf(
        session,
        pdf_id,
        pdf.extracted_text,
        chunk_size=chunk_size,
        overlap=overlap,
    )

    await session.commit()

    chunk_responses = [
        PDFChunkResponse.model_validate(chunk) for chunk in chunks
    ]

    return ChunkingResponse(
        pdf_id=pdf_id,
        total_chunks=len(chunks),
        chunks=chunk_responses,
    )


@router.get("/{pdf_id}/chunks", response_model=PDFChunkListResponse)
async def get_pdf_chunks(
    pdf_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Lấy tất cả chunks của một PDF"""
    # Verify PDF exists
    pdf = await PDFService.get_pdf_by_id(session, pdf_id)
    if not pdf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PDF {pdf_id} not found",
        )

    chunks = await EmbeddingService.get_chunks_by_pdf(session, pdf_id)
    chunk_responses = [
        PDFChunkResponse.model_validate(chunk) for chunk in chunks
    ]

    return PDFChunkListResponse(
        chunks=chunk_responses,
        total=len(chunks),
    )


@router.get("/{pdf_id}/embedding-status")
async def get_embedding_status(
    pdf_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Lấy trạng thái embedding của một PDF"""
    pdf = await PDFService.get_pdf_by_id(session, pdf_id)
    if not pdf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PDF {pdf_id} not found",
        )

    total_chunks = len(await EmbeddingService.get_chunks_by_pdf(session, pdf_id))
    total_embeddings = await EmbeddingService.count_embeddings_by_pdf(
        session, pdf_id
    )

    return {
        "pdf_id": pdf_id,
        "total_chunks": total_chunks,
        "total_embeddings": total_embeddings,
        "embedding_complete": total_chunks > 0 and total_chunks == total_embeddings,
        "pdf_status": pdf.status,
    }


@router.delete("/{pdf_id}/chunks")
async def delete_pdf_chunks(
    pdf_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Xóa tất cả chunks của một PDF"""
    pdf = await PDFService.get_pdf_by_id(session, pdf_id)
    if not pdf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PDF {pdf_id} not found",
        )

    deleted_count = await EmbeddingService.delete_chunks_by_pdf(session, pdf_id)
    await session.commit()

    return {
        "pdf_id": pdf_id,
        "deleted_chunks": deleted_count,
        "message": f"Deleted {deleted_count} chunks",
    }
