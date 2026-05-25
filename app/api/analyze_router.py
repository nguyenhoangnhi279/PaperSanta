"""analyze_router.py — Analyze endpoints (placeholder)"""

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analyze", tags=["Analyze"])


@router.get("/health")
async def analyze_health():
    return {"status": "analyze router ready"}
