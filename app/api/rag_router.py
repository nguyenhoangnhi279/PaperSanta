"""
rag_router.py — API endpoints cho RAG: Retrieval + Chat
"""

import logging
import time
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.auth import get_current_user
from app.services.rag_service import RAGService
from app.services.pdf_service import PDFService
from app.schemas.embedding_schema import (
    RAGQueryRequest,
    RAGQueryResponse,
    RAGQueryResult,
)
from app.schemas.chat_schema import (
    ChatRequest,
    ChatResponse,
    CitationResult,
    ChatSessionResponse,
    ChatSessionListResponse,
    ChatMessageResponse,
)
from app.models.chat import ChatSession, ChatMessage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rag", tags=["RAG"])


@router.post("/query", response_model=RAGQueryResponse)
async def retrieve_chunks(
    req: RAGQueryRequest,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Chỉ retrieval: embed câu hỏi → tìm chunks tương tự → trả về danh sách
    (Không gọi LLM, không lưu lịch sử)
    """
    t0 = time.time()
    pdf_ids = [req.pdf_id] if req.pdf_id else None

    results = await RAGService.similarity_search(
        session=session,
        query_text=req.query_text,
        pdf_ids=pdf_ids,
        top_k=req.top_k,
    )

    query_time_ms = round((time.time() - t0) * 1000, 2)

    rag_results = [
        RAGQueryResult(
            chunk=r["chunk"],
            score=r["score"],
            pdf_id=r["pdf_id"],
        )
        for r in results
    ]

    logger.info(
        f"RAG query: {len(rag_results)} results in {query_time_ms}ms"
    )
    return RAGQueryResponse(
        results=rag_results,
        query_time_ms=query_time_ms,
        total_chunks_searched=req.top_k,
    )


@router.post("/chat", response_model=ChatResponse)
async def chat_with_pdfs(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Full RAG chat: retrieve chunks → DeepSeek generate → lưu session + citations
    - Nếu session_id = null: tạo session mới
    - Nếu session_id có: tiếp tục hội thoại (chỉ dùng context từ PDFs)
    """
    # Verify all PDF IDs belong to user
    for pid in req.pdf_ids:
        await PDFService.get_by_id(pid, db, current_user["user_id"])

    result = await RAGService.generate_answer(
        db=db,
        user_id=current_user["user_id"],
        query_text=req.query_text,
        pdf_ids=req.pdf_ids,
        session_id=req.session_id,
        top_k=req.top_k,
    )

    await db.commit()

    return ChatResponse(
        answer=result["answer"],
        session_id=result["session_id"],
        citations=[
            CitationResult(**c) for c in result["citations"]
        ],
        prompt_tokens=result["prompt_tokens"],
        completion_tokens=result["completion_tokens"],
    )


@router.get("/sessions", response_model=ChatSessionListResponse)
async def list_sessions(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Lấy danh sách chat sessions của user"""
    total_q = await db.execute(
        select(func.count(ChatSession.id)).where(ChatSession.user_id == current_user["user_id"])
    )
    total = total_q.scalar_one()

    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == current_user["user_id"])
        .order_by(ChatSession.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    sessions = result.scalars().all()
    return ChatSessionListResponse(sessions=sessions, total=total)


@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
async def get_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Lấy chi tiết session + messages"""
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user["user_id"],
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    msg_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    session.messages = msg_result.scalars().all()
    return session


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Xóa session"""
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user["user_id"],
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    await db.delete(session)
    await db.flush()
    logger.info(f"Deleted session {session_id}")
    return {"message": "Deleted", "id": session_id}
