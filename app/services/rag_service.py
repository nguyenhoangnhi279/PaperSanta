"""
rag_service.py — RAG: Retrieval + Generation
"""

import logging
import time
import asyncio
import re
from uuid import UUID
from collections import defaultdict
from datetime import datetime, timezone
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import settings
from app.core.embedding_provider import EmbeddingProvider
from app.core.deepseek_provider import DeepSeekProvider
from app.models.pdf_document import PDFDocument
from app.models.embedding import PDFChunk, PDFEmbedding
from app.models.chat import ChatSession
from app.models.pdf_block import PDFBlock

logger = logging.getLogger(__name__)


FTS_STOPWORDS = {
    "the", "and", "or", "for", "with", "without", "what", "when", "where", "which",
    "why", "how", "are", "is", "was", "were", "does", "do", "did", "in", "on",
    "of", "to", "a", "an", "this", "that", "paper", "main", "into", "from",
}


def _extract_query_terms(query_text: str, max_terms: int = 18) -> list[str]:
    raw_terms = re.findall(r"[A-Za-z][A-Za-z0-9_-]*|\d+[A-Za-z]+\d*|\d+", query_text)
    terms: list[str] = []
    seen: set[str] = set()
    for raw in raw_terms:
        for part in re.split(r"[-_]+", raw):
            term = re.sub(r"[^A-Za-z0-9]", "", part).lower()
            if not term or term in FTS_STOPWORDS:
                continue
            if len(term) < 3 and not re.match(r"^[a-z]+\d+$", term):
                continue
            if term in seen:
                continue
            seen.add(term)
            terms.append(term)
            if len(terms) >= max_terms:
                return terms
    return terms


def _build_fts_query(query_text: str, max_terms: int = 16) -> str:
    terms = _extract_query_terms(query_text, max_terms=max_terms)
    return " | ".join(f"{term}:*" for term in terms)


def _term_coverage(terms: list[str], text: str) -> float:
    if not terms:
        return 0.0
    text = text.lower()
    matched = sum(1 for term in terms if term in text)
    return matched / len(terms)


def _phrase_coverage(terms: list[str], text: str) -> float:
    if len(terms) < 2:
        return 0.0
    text = text.lower()
    pairs = [f"{left} {right}" for left, right in zip(terms, terms[1:])]
    matched = sum(1 for pair in pairs if pair in text)
    return matched / len(pairs)


FOLLOW_UP_MARKERS = {
    "it", "that", "this", "they", "them", "those", "these", "above", "previous",
    "same", "second", "first", "method", "approach", "cái", "đó", "nó", "trên",
    "vậy", "khác", "tiếp", "phần", "đấy",
}


def _recent_history(messages: list[dict], max_messages: int = 6, max_chars: int = 2200) -> list[dict]:
    if not messages:
        return []
    recent = [
        message for message in messages[-max_messages:]
        if message.get("role") in {"user", "assistant"} and message.get("content")
    ]
    total = 0
    selected: list[dict] = []
    for message in reversed(recent):
        content = str(message.get("content", "")).strip()
        if not content:
            continue
        budgeted = content[:700]
        if total + len(budgeted) > max_chars and selected:
            break
        selected.append({"role": message.get("role"), "content": budgeted})
        total += len(budgeted)
    return list(reversed(selected))


def _format_history(messages: list[dict]) -> str:
    if not messages:
        return "(no previous turns)"
    lines = []
    for message in messages:
        role = "User" if message.get("role") == "user" else "Assistant"
        lines.append(f"{role}: {message.get('content', '')}")
    return "\n".join(lines)


def _looks_like_follow_up(query_text: str) -> bool:
    terms = set(_extract_query_terms(query_text, max_terms=24))
    if len(query_text.split()) <= 8:
        return True
    return bool(terms & FOLLOW_UP_MARKERS)


def _rewrite_query_with_history(query_text: str, history: list[dict]) -> str:
    if not history or not _looks_like_follow_up(query_text):
        return query_text

    history_text = _format_history(history)
    system_prompt = (
        "Rewrite follow-up questions for academic paper retrieval. "
        "Return only one standalone search query. Do not answer the question."
    )
    user_prompt = (
        f"Conversation history:\n{history_text}\n\n"
        f"Latest question:\n{query_text}\n\n"
        "Rewrite the latest question into a standalone retrieval query that preserves paper-specific terms, acronyms, methods, datasets, and compared entities."
    )
    try:
        rewritten, _, _ = DeepSeekProvider.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.0,
            max_tokens=160,
        )
    except Exception:
        logger.exception("Query rewrite failed; falling back to original query")
        return query_text

    rewritten = rewritten.strip().strip('"')
    if not rewritten or len(rewritten) > 500:
        return query_text
    return rewritten


def _build_chat_context_and_citations(retrieved: list[dict]) -> tuple[str, list[dict], int]:
    paper_groups: dict[str, list[dict]] = defaultdict(list)
    for result in retrieved:
        paper_groups[str(result["pdf_id"])].append(result)

    context_parts: list[str] = []
    citation_list: list[dict] = []

    source_idx = 0
    for _paper_idx, (pid, paper_chunks) in enumerate(paper_groups.items(), 1):
        paper_label = paper_chunks[0].get("pdf_name", "Unknown")
        for chunk_data in paper_chunks:
            source_idx += 1
            chunk: PDFChunk = chunk_data["chunk"]
            context_text = chunk_data.get("context_text", chunk.chunk_text)
            page_label = chunk.page_number or "unknown"
            section_label = " > ".join(chunk.section_path or [])

            context_header = f"[{source_idx}: {paper_label}, page {page_label}]"
            if section_label:
                context_header = f"{context_header}\nSection: {section_label}"
            context_parts.append(f"{context_header}\n{context_text}\n")

            citation_list.append({
                "source_id": source_idx,
                "chunk_id": str(chunk.id),
                "chunk_text": chunk.chunk_text[:200],
                "score": chunk_data["score"],
                "pdf_id": pid,
                "pdf_name": paper_label,
                "page_number": chunk.page_number,
                "block_id": str(chunk.block_id) if chunk.block_id else None,
                "bbox": chunk_data.get("block_bbox"),
                "section_path": chunk.section_path,
                "source_block_type": chunk.source_block_type,
                "retrieval_sources": chunk_data.get("retrieval_sources", []),
            })

    return "\n---\n".join(context_parts), citation_list, len(paper_groups)


def _compact_numeric_citations(answer: str) -> str:
    def replace_source_list(match: re.Match) -> str:
        raw_numbers = match.group(1)
        numbers = re.findall(r"\d+", raw_numbers)
        return ", ".join(f"[{number}]" for number in numbers)

    answer = re.sub(
        r"\[(?:Source|Paper)\s+([\d,\s]+)(?:,\s*page\s+\d+)?\]",
        replace_source_list,
        answer,
        flags=re.IGNORECASE,
    )
    answer = re.sub(r"\s+([.,;:])", r"\1", answer)
    return answer


def _build_chat_prompt(
    query_text: str,
    retrieval_query: str,
    history: list[dict],
    context: str,
    num_papers: int,
) -> str:
    history_text = _format_history(history)
    retrieval_note = ""
    if retrieval_query.strip() != query_text.strip():
        retrieval_note = f"\nStandalone retrieval query used: {retrieval_query}\n"

    if num_papers <= 1:
        scope_rules = (
            "Scope: single-paper QA.\n"
            "- Treat the retrieved sources as coming from the currently opened PDF.\n"
            "- Answer only what the paper supports. If the paper does not provide enough evidence, say that clearly.\n"
            "- Cite source-backed claims with compact numeric citations only, e.g. [1], [2].\n"
        )
    else:
        scope_rules = (
            "Scope: multi-paper QA.\n"
            "- Keep claims separated by paper; do not merge evidence from different papers into one unsupported claim.\n"
            "- If the user asks for comparison, answer with a compact comparison table or clearly separated bullets.\n"
            "- If one paper lacks evidence for a point, say that evidence was not found for that paper.\n"
            "- Cite source-backed claims with compact numeric citations only, e.g. [1], [2].\n"
        )

    return (
        f"Recent conversation:\n{history_text}\n\n"
        f"Retrieved sources:\n{context}\n\n"
        f"User question: {query_text}\n"
        f"{retrieval_note}\n"
        "Requirements:\n"
        f"{scope_rules}"
        "- Answer primarily from the retrieved sources.\n"
        "- If you add background knowledge that is not directly in the sources, put it under a short 'Outside the paper' note.\n"
        "- Never use labels such as [Paper 1], [Paper 2], [Source 1], or source names inside citations.\n"
        "- Numeric citations must refer to the numbered retrieved sources above.\n"
        "- Do not mention chunk numbers, embedding, vector search, or internal retrieval mechanics."
    )


class RAGService:

    @staticmethod
    async def _dense_search(
        session: AsyncSession,
        user_id: str,
        query_text: str,
        pdf_ids: list[UUID] | None = None,
        limit: int = 30,
    ) -> list[dict]:
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
            .limit(limit)
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
            results.append({
                "chunk": chunk,
                "score": round(score, 4),
                "dense_score": round(score, 4),
                "pdf_id": pdf_id,
                "pdf_name": pdf_name,
                "retrieval_sources": ["dense"],
            })
        return results

    @staticmethod
    async def _text_search(
        session: AsyncSession,
        user_id: str,
        query_text: str,
        pdf_ids: list[UUID] | None = None,
        limit: int = 30,
    ) -> list[dict]:
        fts_query = _build_fts_query(query_text)
        if not fts_query:
            return []

        ts_query = func.to_tsquery("english", fts_query)
        ts_vector = func.to_tsvector("english", func.coalesce(PDFChunk.chunk_text, ""))
        rank_expr = func.ts_rank_cd(ts_vector, ts_query)

        stmt = (
            select(
                PDFChunk,
                rank_expr.label("rank"),
                PDFDocument.id.label("pdf_id"),
                PDFDocument.original_name.label("pdf_name"),
            )
            .join(PDFDocument, PDFDocument.id == PDFChunk.pdf_id)
            .where(PDFChunk.chunk_type == "child")
            .where(PDFDocument.user_id == user_id)
            .where(ts_vector.op("@@")(ts_query))
            .where(
                or_(
                    PDFChunk.source_block_type.is_(None),
                    PDFChunk.source_block_type != "heading",
                )
            )
            .where(
                or_(
                    PDFChunk.token_count >= settings.EMBED_MIN_CHUNK_WORDS,
                    PDFChunk.source_block_type.in_(["table", "equation"]),
                )
            )
            .order_by(rank_expr.desc())
            .limit(limit)
        )

        if pdf_ids:
            stmt = stmt.where(PDFChunk.pdf_id.in_(pdf_ids))

        result = await session.execute(stmt)
        rows = result.all()

        results = []
        for chunk, rank, pdf_id, pdf_name in rows:
            score = float(rank or 0.0)
            results.append({
                "chunk": chunk,
                "score": round(score, 4),
                "text_score": round(score, 4),
                "pdf_id": pdf_id,
                "pdf_name": pdf_name,
                "retrieval_sources": ["text"],
            })
        return results

    @staticmethod
    async def _attach_parent_context(session: AsyncSession, results: list[dict]) -> list[dict]:
        parent_ids = {
            result["chunk"].parent_id
            for result in results
            if result["chunk"].parent_id
        }
        parents = {}
        if parent_ids:
            parent_rows = await session.execute(select(PDFChunk).where(PDFChunk.id.in_(parent_ids)))
            parents = {parent.id: parent for parent in parent_rows.scalars().all()}

        block_ids = {
            result["chunk"].block_id
            for result in results
            if result["chunk"].block_id
        }
        blocks = {}
        if block_ids:
            block_rows = await session.execute(select(PDFBlock).where(PDFBlock.id.in_(block_ids)))
            blocks = {block.id: block for block in block_rows.scalars().all()}

        for result in results:
            chunk = result["chunk"]
            parent = parents.get(chunk.parent_id)
            result["context_text"] = parent.chunk_text if parent else chunk.chunk_text
            block = blocks.get(chunk.block_id)
            result["block_bbox"] = block.bbox if block else None
        return results

    @staticmethod
    def _fuse_results(dense_results: list[dict], text_results: list[dict], limit: int) -> list[dict]:
        fused: dict[UUID, dict] = {}

        def add_results(results: list[dict], source: str, weight: float) -> None:
            for rank, result in enumerate(results, 1):
                chunk_id = result["chunk"].id
                contribution = weight / (settings.RAG_RRF_K + rank)
                if chunk_id not in fused:
                    fused[chunk_id] = {
                        **result,
                        "score": 0.0,
                        "retrieval_sources": [],
                    }
                fused_item = fused[chunk_id]
                fused_item["score"] += contribution
                if source not in fused_item["retrieval_sources"]:
                    fused_item["retrieval_sources"].append(source)
                if source == "dense":
                    fused_item["dense_rank"] = rank
                    fused_item["dense_score"] = result.get("dense_score")
                else:
                    fused_item["text_rank"] = rank
                    fused_item["text_score"] = result.get("text_score")

        add_results(dense_results, "dense", settings.RAG_DENSE_WEIGHT)
        add_results(text_results, "text", settings.RAG_TEXT_WEIGHT)

        sorted_results = sorted(
            fused.values(),
            key=lambda item: (item["score"], item.get("dense_score") or 0.0, item.get("text_score") or 0.0),
            reverse=True,
        )
        for result in sorted_results:
            result["score"] = round(result["score"], 4)
        return sorted_results[:limit]

    @staticmethod
    def _heuristic_rerank(query_text: str, results: list[dict], top_k: int) -> list[dict]:
        terms = _extract_query_terms(query_text)
        if not results or not terms:
            return results[:top_k]

        reranked = []
        for original_rank, result in enumerate(results, 1):
            chunk = result["chunk"]
            context_text = result.get("context_text") or chunk.chunk_text or ""
            section_text = " > ".join(chunk.section_path or [])
            combined_text = f"{section_text}\n{context_text}"

            rank_prior = 1.0 / (original_rank + 2)
            lexical_score = _term_coverage(terms, combined_text)
            phrase_score = _phrase_coverage(terms, combined_text)
            section_score = _term_coverage(terms, section_text)
            source_bonus = 0.01 if len(result.get("retrieval_sources", [])) > 1 else 0.0

            rerank_score = (
                rank_prior
                + settings.RAG_RERANK_LEXICAL_WEIGHT * lexical_score
                + settings.RAG_RERANK_PHRASE_WEIGHT * phrase_score
                + settings.RAG_RERANK_SECTION_WEIGHT * section_score
                + source_bonus
            )
            reranked.append({
                **result,
                "pre_rerank_rank": original_rank,
                "pre_rerank_score": result.get("score"),
                "rerank_score": round(rerank_score, 4),
                "lexical_score": round(lexical_score, 4),
                "phrase_score": round(phrase_score, 4),
                "section_score": round(section_score, 4),
            })

        reranked.sort(
            key=lambda item: (
                item["rerank_score"],
                item.get("dense_score") or 0.0,
                item.get("text_score") or 0.0,
            ),
            reverse=True,
        )
        for result in reranked:
            result["score"] = result["rerank_score"]
        return reranked[:top_k]

    @staticmethod
    async def similarity_search(
        session: AsyncSession,
        user_id: str,
        query_text: str,
        pdf_ids: list[UUID] | None = None,
        top_k: int = 5,
    ) -> list[dict]:
        retrieval_mode = settings.RAG_RETRIEVAL_MODE.lower().strip()
        logger.info(
            "Similarity search: mode=%s user=%s query='%s...' pdf_ids=%s top_k=%s",
            retrieval_mode,
            user_id,
            query_text[:50],
            pdf_ids,
            top_k,
        )

        rerank_mode = settings.RAG_RERANK_MODE.lower().strip()
        candidate_limit = max(top_k, settings.RAG_RERANK_CANDIDATES) if rerank_mode != "none" else top_k
        dense_limit = max(candidate_limit, settings.RAG_DENSE_CANDIDATES)
        text_limit = max(candidate_limit, settings.RAG_TEXT_CANDIDATES)

        if retrieval_mode == "dense":
            results = await RAGService._dense_search(session, user_id, query_text, pdf_ids, dense_limit)
            results = results[:candidate_limit]
        elif retrieval_mode in {"hybrid", "rrf"}:
            dense_results = await RAGService._dense_search(
                session, user_id, query_text, pdf_ids, dense_limit
            )
            text_results = await RAGService._text_search(
                session, user_id, query_text, pdf_ids, text_limit
            )
            results = RAGService._fuse_results(dense_results, text_results, candidate_limit)
        else:
            raise ValueError("Unsupported RAG_RETRIEVAL_MODE. Use 'dense' or 'hybrid'.")

        results = await RAGService._attach_parent_context(session, results)
        if rerank_mode == "heuristic":
            results = RAGService._heuristic_rerank(query_text, results, top_k)
        elif rerank_mode == "none":
            results = results[:top_k]
        else:
            raise ValueError("Unsupported RAG_RERANK_MODE. Use 'none' or 'heuristic'.")
        logger.info("Found %s relevant chunks", len(results))
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
        now = datetime.now(timezone.utc)
        chat_session: ChatSession | None = None
        if session_id:
            chat_session = await db.get(ChatSession, session_id)
            if not chat_session or chat_session.user_id != user_id:
                chat_session = None

        history = _recent_history(chat_session.messages if chat_session else [])
        retrieval_query = await asyncio.to_thread(_rewrite_query_with_history, query_text, history)

        # ── 1. Retrieve ──────────────────────────────────────────────────────
        t0 = time.time()
        retrieved = await RAGService.similarity_search(
            db, user_id, retrieval_query, pdf_ids=pdf_ids, top_k=top_k
        )
        retrieve_time = time.time() - t0

        if not retrieved:
            return {
                "answer": "Không tìm thấy thông tin liên quan trong tài liệu.",
                "session_id": session_id,
                "citations": [],
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "retrieval_query": retrieval_query,
            }

        context, citation_list, num_papers = _build_chat_context_and_citations(retrieved)
        user_prompt = _build_chat_prompt(
            query_text=query_text,
            retrieval_query=retrieval_query,
            history=history,
            context=context,
            num_papers=num_papers,
        )

        t1 = time.time()
        answer, prompt_tokens, completion_tokens = await asyncio.to_thread(
            lambda: DeepSeekProvider.generate(
                system_prompt=settings.RAG_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=settings.RAG_TEMPERATURE,
                max_tokens=settings.RAG_MAX_TOKENS,
            )
        )
        answer = _compact_numeric_citations(answer)
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
            "retrieval_query": retrieval_query,
        }
        chat_session.messages.append(user_msg)

        # Save AI message to JSONB
        ai_msg = {
            "role": "assistant",
            "content": answer,
            "ts": now.isoformat(),
            "tokens": {"prompt": prompt_tokens, "completion": completion_tokens},
            "citations": citation_list,
            "retrieval_query": retrieval_query,
        }
        chat_session.messages.append(ai_msg)
        chat_session.updated_at = now

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
            "retrieval_query": retrieval_query,
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
                f"[{idx}: {r['pdf_name']}, page {chunk.page_number or 'unknown'}]\n"
                f"{context_text}"
            )
            citation_list.append({
                "source_id": idx,
                "chunk_id": str(chunk.id),
                "chunk_text": chunk.chunk_text[:200],
                "score": r["score"],
                "pdf_id": str(r["pdf_id"]),
                "pdf_name": r["pdf_name"],
                "page_number": chunk.page_number,
                "block_id": str(chunk.block_id) if chunk.block_id else None,
                "bbox": r.get("block_bbox"),
                "section_path": chunk.section_path,
                "source_block_type": chunk.source_block_type,
                "retrieval_sources": r.get("retrieval_sources", []),
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
        answer = _compact_numeric_citations(answer)
        return {
            "answer": answer,
            "citations": citation_list,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        }
