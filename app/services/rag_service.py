"""
rag_service.py — RAG: Retrieval + Generation
"""

import logging
import time
import asyncio
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.embedding_provider import EmbeddingProvider
from app.core.deepseek_provider import DeepSeekProvider
from app.models.pdf_document import PDFDocument
from app.models.embedding import PDFChunk, PDFEmbedding
from app.models.chat import ChatSession

logger = logging.getLogger(__name__)


class RAGService:

    @staticmethod
    async def similarity_search(
        session: AsyncSession,
        query_text: str,
        pdf_ids: list[UUID] | None = None,
        top_k: int = 5,
    ) -> list[dict]:
        logger.info(f"Similarity search: query='{query_text[:50]}...', pdf_ids={pdf_ids}, top_k={top_k}")

        query_vector = await asyncio.to_thread(EmbeddingProvider.embed_text, query_text)

        stmt = (
            select(
                PDFChunk,
                PDFEmbedding.vector.cosine_distance(query_vector).label("distance"),
                PDFDocument.id.label("pdf_id"),
                PDFDocument.original_name.label("pdf_name"),
            )
            .join(PDFEmbedding, PDFEmbedding.chunk_id == PDFChunk.id)
            .join(PDFDocument, PDFDocument.id == PDFChunk.pdf_id)
            .where(PDFChunk.chunk_type == "child")
            .order_by(PDFEmbedding.vector.cosine_distance(query_vector))
            .limit(top_k)
        )

        if pdf_ids:
            stmt = stmt.where(PDFChunk.pdf_id.in_(pdf_ids))

        result = await session.execute(stmt)
        rows = result.all()

        results = []
        for chunk, distance, pdf_id, pdf_name in rows:
            score = max(0.0, 1.0 - distance)
            if score < settings.RAG_MIN_SCORE:
                continue
            # Resolve parent context
            context_text = chunk.chunk_text
            if chunk.parent_id:
                parent = await session.get(PDFChunk, chunk.parent_id)
                if parent:
                    context_text = parent.chunk_text
            results.append({
                "chunk": chunk,
                "context_text": context_text,
                "score": round(score, 4),
                "pdf_id": pdf_id,
                "pdf_name": pdf_name,
            })

        logger.info(f"Found {len(results)} relevant chunks")
        return results

    @staticmethod
    async def generate_answer(
        db: AsyncSession,
        user_id: str,
        query_text: str,
        pdf_ids: list[UUID],
        session_id: UUID | None = None,
        top_k: int = 5,
    ) -> dict:
        logger.info(f"generate_answer: session={session_id}, query='{query_text[:50]}...'")

        # ── 1. Retrieve ──────────────────────────────────────────────────────
        t0 = time.time()
        retrieved = await RAGService.similarity_search(
            db, query_text, pdf_ids=pdf_ids, top_k=top_k
        )
        retrieve_time = time.time() - t0

        if not retrieved:
            return {
                "answer": "Không tìm thấy thông tin liên quan trong tài liệu.",
                "session_id": session_id,
                "citations": [],
                "prompt_tokens": 0,
                "completion_tokens": 0,
            }

        # ── 2. Build context ────────────────────────────────────────────────
        context_parts = []
        citation_list = []
        for i, r in enumerate(retrieved):
            chunk: PDFChunk = r["chunk"]
            context_text = r.get("context_text", chunk.chunk_text)
            context_parts.append(
                f"[Chunk {i + 1}] (PDF: {r['pdf_name']}, Độ liên quan: {r['score']})\n"
                f"{context_text}\n"
            )
            citation_list.append({
                "chunk_id": chunk.id,
                "chunk_text": chunk.chunk_text[:200],
                "score": r["score"],
                "pdf_id": r["pdf_id"],
                "pdf_name": r["pdf_name"],
                "page_number": chunk.page_number,
            })

        context = "\n---\n".join(context_parts)
        user_prompt = (
            f"Dựa vào các đoạn trích dẫn từ tài liệu PDF, hãy phân tích và trả lời câu hỏi sau.\n\n"
            f"Ngữ cảnh trích dẫn:\n{context}\n\n"
            f"Câu hỏi: {query_text}\n\n"
            f"Hãy trả lời chi tiết, có trích dẫn trang cụ thể, dùng markdown. "
            f"Kết luận bằng 2-3 câu tóm tắt."
        )

        # ── 3. Generate ─────────────────────────────────────────────────────
        t1 = time.time()
        answer, prompt_tokens, completion_tokens = await asyncio.to_thread(
            lambda: DeepSeekProvider.generate(
                system_prompt=settings.RAG_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=settings.RAG_TEMPERATURE,
                max_tokens=settings.RAG_MAX_TOKENS,
            )
        )
        generate_time = time.time() - t1

        logger.info(
            f"RAG done: retrieve={retrieve_time:.2f}s, generate={generate_time:.2f}s, "
            f"tokens={prompt_tokens + completion_tokens}"
        )

        # ── 4. Save to DB (JSONB) ──────────────────────────────────────────
        now = datetime.now(timezone.utc)

        # Get or create session
        if session_id:
            chat_session = await db.get(ChatSession, session_id)
            if not chat_session or chat_session.user_id != user_id:
                chat_session = ChatSession(user_id=user_id, title=query_text[:200])
                db.add(chat_session)
                await db.flush()
        else:
            chat_session = ChatSession(user_id=user_id, title=query_text[:200])
            db.add(chat_session)
            await db.flush()

        # Merge pdf_ids
        for pid in pdf_ids:
            if pid not in chat_session.pdf_ids:
                chat_session.pdf_ids.append(pid)

        # Save user message to JSONB
        user_msg = {
            "role": "user",
            "content": query_text,
            "ts": now.isoformat(),
        }
        chat_session.messages.append(user_msg)

        # Save AI message to JSONB
        ai_msg = {
            "role": "assistant",
            "content": answer,
            "ts": now.isoformat(),
            "tokens": {"prompt": prompt_tokens, "completion": completion_tokens},
            "citations": citation_list,
        }
        chat_session.messages.append(ai_msg)

        # Update char count
        chat_session.history_char_count = sum(
            len(m.get("content", "")) for m in chat_session.messages
        )

        await db.flush()
        logger.info(f"Saved session={chat_session.id}, messages={len(chat_session.messages)}")

        return {
            "answer": answer,
            "session_id": chat_session.id,
            "citations": citation_list,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        }
