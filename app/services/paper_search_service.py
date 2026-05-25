"""
paper_search_service.py — Search papers via Semantic Scholar API
"""

import logging
import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timedelta
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
        """Check cache nội bộ (TTL 1 giờ)"""
        if cache_key in _search_cache:
            cached = _search_cache[cache_key]
            if datetime.utcnow() - cached["created_at"] < timedelta(minutes=PaperSearchService.CACHE_TTL_MINUTES):
                return cached["data"]
        return None

    @staticmethod
    async def _safe_get_request(url: str, params: dict, headers: dict) -> dict:
        """Hàm bọc giúp gọi API an toàn, xử lý Rate Limit (429) và giãn cách luồng khi demo"""
        backoff = 1.5
        for retry in range(3):
            async with PaperSearchService._semaphore:
                try:
                    async with httpx.AsyncClient(timeout=8) as client:
                        response = await client.get(url, params=params, headers=headers)
                        
                        if response.status_code == 429:
                            logger.warning(f"S2 Rate Limited (429). Thử lại sau {backoff}s...")
                            await asyncio.sleep(backoff)
                            backoff *= 2
                            continue
                            
                        response.raise_for_status()
                        await asyncio.sleep(1.0)  # Giãn cách cưỡng bức 1s giữa các request để bảo vệ gói Free
                        return response.json()
                except httpx.HTTPStatusError as e:
                    if e.response.status_code != 429 or retry == 2: raise
        return {}

    @staticmethod
    async def search_papers(query: str, limit: int = 10, offset: int = 0, year_from: Optional[int] = None, year_to: Optional[int] = None, min_citations: Optional[int] = None) -> Dict[str, any]:
        # 🔄 Translate query if Vietnamese, keep English
        original_query = query
        try:
            translated_query = GoogleTranslator(source='auto', target='en').translate(query)
            if translated_query and translated_query != query:
                logger.info(f"🔄 [Query Translation] '{query}' → '{translated_query}'")
                query = translated_query
        except Exception as e:
            logger.warning(f"⚠️ Query translation failed, using original: {e}")
        
        cache_key = f"{query}|{limit}|{offset}|{year_from}|{year_to}"
        cached_result = PaperSearchService._check_cache(cache_key)
        if cached_result: 
            logger.info(f"📦 Cache hit for: {query}")
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
                
                # Sửa lại lấy đúng trường url bên trong object openAccessPdf nếu có
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

            result = {"total": data.get("total", 0), "query": query, "papers": papers}
            _search_cache[cache_key] = {"data": result, "created_at": datetime.utcnow()}
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
            _search_cache[cache_key] = {"data": result, "created_at": datetime.utcnow()}
            return result
        except Exception as e:
            logger.error(f"S2 detail error: {e}")
            return {}

    @staticmethod
    async def search_related_papers(pdf_id: str, user_id: str, db: AsyncSession) -> Dict[str, any]:
        try:
            result = await db.execute(
                select(PDFDocument).where(
                    and_(PDFDocument.id == pdf_id, PDFDocument.user_id == user_id)
                )
            )
            paper = result.scalar_one_or_none()
            if not paper: 
                return {"error": "Không tìm thấy tài liệu yêu cầu", "status_code": 404}

            # ⚙️ KIỂM TRA & XỬ LÝ NHÁNH TÌM KIẾM
            if paper.extracted_topics is not None and isinstance(paper.extracted_topics, list):
                topics = paper.extracted_topics
                method = "precomputed"
            else:
                #LÀM SẠCH TÊN FILE THÔ (TITLE FALLBACK)
                filename = paper.original_name
                # 1. Chặt đuôi .pdf (không phân biệt hoa thường)
                if filename.lower().endswith(".pdf"): filename = filename[:-4]
                
                # 2. Thay thế các ký tự đặc biệt, dấu gạch dưới, gạch ngang thành khoảng trắng
                for char in ["_", "-", ".", "@", "+"]: filename = filename.replace(char, " ")
                
                # 3. Chuẩn hóa khoảng trắng thừa
                clean_title = " ".join(filename.split())
                
                topics = [clean_title]
                
                method = "title_fallback"

            # Bắn request bất đồng bộ song song lên S2 theo danh sách topics
            tasks = [PaperSearchService.search_papers(query=topic, limit=10) for topic in topics]
            results = await asyncio.gather(*tasks)

            # Gộp kết quả và lọc trùng theo s2_id
            all_papers = {}
            for res in results:
                for p in res.get("papers", []):
                    # Chỉ giữ lại bài có link PDF và tránh trùng lặp
                    if p.get("open_access_pdf") and p["s2_id"] not in all_papers:
                        all_papers[p["s2_id"]] = p
            
            # Sắp xếp theo số lượng trích dẫn giảm dần và cắt lấy Top 10 bài uy tín nhất
            sorted_papers = sorted(all_papers.values(), key=lambda p: p["citation_count"], reverse=True)[:10]
            
            return {
                "source_pdf_id": str(pdf_id), 
                "extracted_topics": topics, 
                "related_papers": sorted_papers, 
                "method": method
            }

        except Exception as e:
            logger.error(f"Related papers search error: {e}")
            return {"error": f"Lỗi hệ thống: {str(e)}", "status_code": 500}