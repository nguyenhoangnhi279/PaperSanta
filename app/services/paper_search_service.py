"""
paper_search_service.py — Search papers via Semantic Scholar API
"""

import logging
import asyncio
import json
from typing import List, Dict, Optional
from datetime import datetime, timezone, timedelta
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models.pdf_document import PDFDocument
from app.core.config import settings
from deep_translator import GoogleTranslator

logger = logging.getLogger(__name__)
_search_cache: Dict[str, Dict[str, any]] = {}


class PaperSearchService:
    """Tìm kiếm papers từ ngoại sàn (Semantic Scholar)"""
    
    CACHE_TTL_MINUTES = 60
    S2_BASE_URL = "https://api.semanticscholar.org/graph/v1"
    _semaphore = asyncio.Semaphore(1)

    @staticmethod
    def _check_cache(cache_key: str) -> Optional[Dict]:
        if cache_key in _search_cache:
            cached = _search_cache[cache_key]
            if datetime.now(timezone.utc) - cached["created_at"] < timedelta(minutes=PaperSearchService.CACHE_TTL_MINUTES):
                return cached["data"]
        return None

    @staticmethod
    async def _safe_get_request(url: str, params: dict, headers: dict) -> dict:
        backoff = 2.0
        for retry in range(3):
            is_429 = False
            async with PaperSearchService._semaphore:
                try:
                    async with httpx.AsyncClient(timeout=10) as client:
                        response = await client.get(url, params=params, headers=headers)
                        if response.status_code == 429:
                            is_429 = True
                        else:
                            response.raise_for_status()
                            await asyncio.sleep(1.0)  # Giãn cách gói Free
                            return response.json()
                except (httpx.HTTPStatusError, httpx.RequestError) as e:
                    if getattr(e, "response", None) and e.response.status_code == 429:
                        is_429 = True
                    elif retry == 2: raise

            if is_429:
                logger.warning(f"⚠️ S2 429 Rate Limit. Ngủ {backoff}s rồi thử lại...")
                await asyncio.sleep(backoff)
                backoff *= 2
                continue
        return {}

    @staticmethod
    async def _tavily_fallback_search(query: str, limit: int = 10) -> list:
        """Tavily fallback + Gemini 1.5 Flash — chỉ dùng khi S2 = 0 kết quả"""
        if not settings.TAVILY_API_KEY or not settings.GEMINI_API_KEY:
            return []
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    "https://api.tavily.com/search",
                    json={"api_key": settings.TAVILY_API_KEY, "query": query, "max_results": limit, "include_answer": False},
                )
                resp.raise_for_status()
                data = resp.json()
            
            results = data.get("results", [])[:limit]
            if not results:
                return []
            
            # Format qua Gemini 1.5 Flash
            async with httpx.AsyncClient(timeout=15) as client:
                gemini_resp = await client.post(
                    "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
                    params={"key": settings.GEMINI_API_KEY},                  
                    json={
                        "contents": [{
                            "parts": [{
                                "text": f"""Extract structured paper data. Return ONLY a valid JSON array with: title, abstract (200-300 chars, professional summary), year (extract or null), authors (list), url.

{json.dumps(results)}

Return ONLY JSON array, no markdown."""
                            }]
                        }],
                        "generationConfig": {"responseMimeType": "application/json"}
                    },
                )
                gemini_resp.raise_for_status()
                gemini_data = gemini_resp.json()
                content = gemini_data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                formatted = json.loads(content)
                return [{
                    "s2_id": p.get("url", ""),
                    "title": p.get("title", ""),
                    "abstract": p.get("abstract", ""),
                    "year": p.get("year"),
                    "authors": p.get("authors", []),
                    "venue": "Tavily Search",
                    "citation_count": 0,
                    "open_access_pdf": p.get("url", ""),
                } for p in formatted]
        except Exception as e:
            logger.warning(f"Tavily/Gemini error: {e}")
            return []

    @staticmethod
    async def search_papers(query: str, limit: int = 10, offset: int = 0, year_from: Optional[int] = None, year_to: Optional[int] = None, min_citations: Optional[int] = None) -> Dict[str, any]:
        try:
            if any(ord(char) > 127 for char in query):
                translated_query = GoogleTranslator(source='auto', target='en').translate(query)
                if translated_query and translated_query != query:
                    query = translated_query
        except Exception as e:
            logger.warning(f"Dịch query thất bại: {e}")
        
        cache_key = f"{query}|{limit}|{offset}|{year_from}|{year_to}"
        cached_result = PaperSearchService._check_cache(cache_key)
        if cached_result: 
            return cached_result

        try:
            params = {
                "query": query, "limit": limit, "offset": offset,
                "fields": "title,abstract,year,authors,venue,citationCount,openAccessPdf"
            }
            if year_from or year_to:
                params["year"] = f"{year_from or ''}-{year_to or ''}".strip("-")

            data = await PaperSearchService._safe_get_request(
                f"{PaperSearchService.S2_BASE_URL}/paper/search", 
                params, 
                {"x-api-key": settings.SEMANTIC_SCHOLAR_API_KEY}
            )

            papers = []
            for paper in data.get("data", []):
                citation_count = paper.get("citationCount", 0)
                if min_citations and citation_count < min_citations: continue
                
                pdf_url = None
                if paper.get("openAccessPdf") and isinstance(paper["openAccessPdf"], dict):
                    pdf_url = paper["openAccessPdf"].get("url")
                if not pdf_url:
                    pdf_url = f"https://www.semanticscholar.org/paper/{paper.get('paperId', '')}"

                papers.append({
                    "s2_id": paper.get("paperId", ""), "title": paper.get("title", ""),
                    "abstract": paper.get("abstract"), "year": paper.get("year"),
                    "authors": [a.get("name", "") for a in paper.get("authors", [])],
                    "venue": paper.get("venue") or "Nguồn học thuật",
                    "citation_count": citation_count, "open_access_pdf": pdf_url,
                })

            # Fallback: Tavily nếu S2 = 0 kết quả
            if not papers:
                fallback_papers = await PaperSearchService._tavily_fallback_search(query, limit)
                papers.extend(fallback_papers)

            result = {"total": len(papers), "query": query, "papers": papers}
            _search_cache[cache_key] = {"data": result, "created_at": datetime.now(timezone.utc)}
            return result
        except Exception as e:
            logger.error(f"S2 search error: {e}")
            return {"total": 0, "query": query, "papers": []}

    @staticmethod
    async def get_paper_detail(s2_id: str) -> Dict[str, any]:
        cache_key = f"detail|{s2_id}"
        cached_result = PaperSearchService._check_cache(cache_key)
        if cached_result: return cached_result

        try:
            paper = await PaperSearchService._safe_get_request(
                f"{PaperSearchService.S2_BASE_URL}/paper/{s2_id}",
                {"fields": "title,abstract,year,authors,venue,citationCount,referenceCount,openAccessPdf"},
                {"x-api-key": settings.SEMANTIC_SCHOLAR_API_KEY}
            )
            if not paper: return {}

            pdf_url = None
            if paper.get("openAccessPdf") and isinstance(paper["openAccessPdf"], dict):
                pdf_url = paper["openAccessPdf"].get("url")
            if not pdf_url:
                pdf_url = f"https://www.semanticscholar.org/paper/{s2_id}"

            result = {
                "s2_id": s2_id, "title": paper.get("title", ""), "abstract": paper.get("abstract"), "year": paper.get("year"),
                "authors": [a.get("name", "") for a in paper.get("authors", [])], "venue": paper.get("venue") or "Nguồn học thuật",
                "citation_count": paper.get("citationCount", 0), "reference_count": paper.get("referenceCount", 0), "open_access_pdf": pdf_url,
            }
            _search_cache[cache_key] = {"data": result, "created_at": datetime.now(timezone.utc)}
            return result
        except Exception as e:
            logger.error(f"❌ S2 detail error: {e}")
            return {}

    @staticmethod
    async def search_related_papers(
        pdf_id: str,
        user_id: str,
        db: AsyncSession,
        limit: int = 10,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        min_citations: Optional[int] = None,
        open_access: bool = True,
    ) -> Dict[str, any]:
        try:
            result = await db.execute(
                select(PDFDocument).where(and_(PDFDocument.id == pdf_id, PDFDocument.user_id == user_id))
            )
            paper = result.scalar_one_or_none()
            if not paper:
                return {"error": "Không tìm thấy tài liệu", "status_code": 404}

            if hasattr(paper, "extracted_topics") and isinstance(paper.extracted_topics, list) and len(paper.extracted_topics) > 0:
                extracted_topics = paper.extracted_topics
                method = "precomputed"
            else:
                filename = paper.original_name
                if filename.lower().endswith(".pdf"):
                    filename = filename[:-4]
                for char in ["_", "-", ".", "@", "+"]:
                    filename = filename.replace(char, " ")
                extracted_topics = [" ".join(filename.split())]
                method = "title_fallback"

            # Build parallel tasks with provided filters
            if len(extracted_topics) > 1:
                tasks = [
                    PaperSearchService.search_papers(
                        query=topic,
                        limit=limit,
                        year_from=year_from,
                        year_to=year_to,
                        min_citations=min_citations,
                    )
                    for topic in extracted_topics
                ]
                results = await asyncio.gather(*tasks)
            else:
                res = await PaperSearchService.search_papers(
                    query=extracted_topics[0],
                    limit=limit,
                    year_from=year_from,
                    year_to=year_to,
                    min_citations=min_citations,
                )
                results = [res]

            all_papers = {}
            for res in results:
                for p in res.get("papers", []):
                    has_pdf = bool(p.get("open_access_pdf"))
                    if (not open_access or has_pdf) and p["s2_id"] not in all_papers:
                        all_papers[p["s2_id"]] = p

            sorted_papers = sorted(all_papers.values(), key=lambda p: p.get("citation_count", 0), reverse=True)[:limit]
            return {"source_pdf_id": str(pdf_id), "extracted_topics": extracted_topics, "related_papers": sorted_papers, "method": method}
        except Exception as e:
            logger.error(f"Related papers error: {e}")
            return {"error": f"Lỗi hệ thống: {str(e)}", "status_code": 500}