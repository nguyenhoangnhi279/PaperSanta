"""
rag_service.py — RAG: Retrieval + Generation
"""

import logging
import time
import asyncio
from uuid import UUID
from collections import defaultdict
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

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
        user_id: str,
        query_text: str,
        pdf_ids: list[UUID] | None = None,
        top_k: int = 5,
    ) -> list[dict]:
        logger.info(f"Similarity search: user={user_id}, query='{query_text[:50]}...', pdf_ids={pdf_ids}, top_k={top_k}")

        query_vector = await asyncio.to_thread(EmbeddingProvider.embed_query, query_text)

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
            .where(PDFDocument.user_id == user_id)
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
            db, user_id, query_text, pdf_ids=pdf_ids, top_k=top_k
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

        # ── 2. Build context — group chunks by paper ─────────────────────────
        paper_groups: dict[str, list[dict]] = defaultdict(list)
        for r in retrieved:
            paper_groups[str(r["pdf_id"])].append(r)

        context_parts = []
        citation_list = []

        for paper_idx, (pid, paper_chunks) in enumerate(paper_groups.items(), 1):
            paper_label = paper_chunks[0].get("pdf_name", "Unknown")
            for chunk_data in paper_chunks:
                chunk: PDFChunk = chunk_data["chunk"]
                context_text = chunk_data.get("context_text", chunk.chunk_text)

                context_parts.append(
                    f"[Paper {paper_idx}: {paper_label}]\n"
                    f"{context_text}\n"
                )

                citation_list.append({
                    "source_id": paper_idx,
                    "chunk_id": str(chunk.id),
                    "chunk_text": chunk.chunk_text[:200],
                    "score": chunk_data["score"],
                    "pdf_id": pid,
                    "pdf_name": paper_label,
                    "page_number": chunk.page_number,
                })

        context = "\n---\n".join(context_parts)
        
        user_prompt = (
            f"Dưới đây là các tài liệu tham khảo (Nguồn):\n{context}\n\n"
            f"Câu hỏi: {query_text}\n\n"
            f"Yêu cầu bắt buộc: Bạn phải trả lời dựa trên các Nguồn trên. "
            f"Khi lấy thông tin từ Nguồn nào, trích dẫn bằng nhãn Paper trong ngoặc vuông ở cuối câu, ví dụ: [Paper 1]. "
            f"TUYỆT ĐỐI KHÔNG dùng từ 'Chunk' hay số thứ tự kiểu [1], [2] trong câu trả lời."
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
            str_pid = str(pid)
            if str_pid not in chat_session.pdf_ids:
                chat_session.pdf_ids.append(str_pid)

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
        flag_modified(chat_session, "messages")
        flag_modified(chat_session, "pdf_ids")

        await db.flush() 
        logger.info(f"Saved session={chat_session.id}, messages={len(chat_session.messages)}")
        
        return {
            "answer": answer,
            "session_id": chat_session.id,
            "citations": citation_list,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        }

    @staticmethod
    async def explain_selection(
        db: AsyncSession,
        user_id: str,
        pdf_id: UUID,
        selected_text: str,
        page_number: int | None = None,
        surrounding_text: str | None = None,
        top_k: int = 8,
    ) -> dict:
        query_text = selected_text
        if surrounding_text:
            query_text = f"{selected_text}\n\nContext around selection:\n{surrounding_text[:1200]}"

        retrieved = await RAGService.similarity_search(
            db,
            user_id,
            query_text,
            pdf_ids=[pdf_id],
            top_k=max(top_k, 12),
        )
        if page_number:
            retrieved = sorted(
                retrieved,
                key=lambda r: (r["chunk"].page_number == page_number, r["score"]),
                reverse=True,
            )
        retrieved = retrieved[:top_k]

        if not retrieved:
            return {
                "answer": "Không tìm thấy ngữ cảnh phù hợp trong PDF để giải thích đoạn đã chọn.",
                "citations": [],
                "prompt_tokens": 0,
                "completion_tokens": 0,
            }

        context_parts = []
        citation_list = []
        for idx, r in enumerate(retrieved, 1):
            chunk: PDFChunk = r["chunk"]
            context_text = r.get("context_text", chunk.chunk_text)
            context_parts.append(
                f"[Source {idx}: {r['pdf_name']}, page {chunk.page_number or 'unknown'}]\n"
                f"{context_text}"
            )
            citation_list.append({
                "chunk_id": str(chunk.id),
                "chunk_text": chunk.chunk_text[:200],
                "score": r["score"],
                "pdf_id": str(r["pdf_id"]),
                "pdf_name": r["pdf_name"],
                "page_number": chunk.page_number,
            })

        system_prompt = (
            "Bạn là PaperSanta, trợ lý giải thích thuật ngữ trong paper. "
            "Giải thích ngắn gọn, đúng ngữ cảnh bài báo, và nêu rõ khi thông tin nào là kiến thức nền ngoài paper."
        )
        user_prompt = (
            f"Thuật ngữ/đoạn được chọn: {selected_text}\n\n"
            f"Ngữ cảnh xung quanh do frontend cung cấp:\n{surrounding_text or '(không có)'}\n\n"
            f"Các nguồn tìm thấy trong PDF:\n{chr(10).join(context_parts)}\n\n"
            "Hãy giải thích theo cấu trúc:\n"
            "1. Ý nghĩa trong ngữ cảnh bài báo\n"
            "2. Giải thích rộng hơn nếu cần\n"
            "3. Vì sao nó quan trọng trong đoạn/paper này\n"
            "Trích dẫn nguồn bằng [Source X] khi dùng thông tin từ PDF."
        )

        answer, prompt_tokens, completion_tokens = await asyncio.to_thread(
            lambda: DeepSeekProvider.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.3,
                max_tokens=min(settings.RAG_MAX_TOKENS, 1200),
            )
        )
        return {
            "answer": answer,
            "citations": citation_list,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        }
