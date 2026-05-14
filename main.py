"""
main.py — FastAPI app entry point
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from app.core.config import settings
from app.core.database import init_db
from app.api.pdf_router import router as pdf_router
from app.api.embedding_router import router as embedding_router

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(levelname)s │ %(name)s │ %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan: chạy khi startup/shutdown ──────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME}...")

    # KHÔNG dùng try-except ở đây. Nếu init_db lỗi, hãy để app dừng lại.
    await init_db()

    logger.info("Database initialized successfully.")
    yield
    logger.info("Shutting down.")

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="PDF Upload & Storage service với RAG pipeline (phase 2)",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(pdf_router)
app.include_router(embedding_router)

# Serve frontend static files
frontend_path = Path(__file__).resolve().parent / "frontend"
frontend_dist = frontend_path / "dist"
if frontend_dist.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dist), html=True), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_frontend():
        return FileResponse(frontend_dist / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        return FileResponse(frontend_dist / "index.html")


# Health check
@app.get("/health", tags=["System"])
async def health():
    return {"status": "ok", "app": settings.APP_NAME}
