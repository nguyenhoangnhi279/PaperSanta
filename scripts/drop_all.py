"""
Drop toàn bộ dữ liệu: xoá file trong Supabase Storage + truncate tất cả tables.
Chạy: python scripts/drop_all.py
"""
import asyncio
import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.core.database import engine, Base, AsyncSessionLocal
from app.services.pdf_service import get_supabase_client
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format="%(levelname)s │ %(message)s")
logger = logging.getLogger("drop_all")

TABLES = [
    "message_citations",
    "chat_messages",
    "session_pdfs",
    "chat_sessions",
    "pdf_embeddings",
    "pdf_chunks",
    "analysis_documents",
    "multi_analyses",
    "pdf_documents",
]

async def drop_storage():
    logger.info("Dropping all files from Supabase Storage...")
    try:
        supabase = get_supabase_client()
        bucket = settings.SUPABASE_STORAGE_BUCKET
        # List all files (paginated)
        all_paths = []
        offset = 0
        while True:
            files = supabase.storage.from_(bucket).list(
                path="",
                options={"limit": 100, "offset": offset, "sortBy": {"column": "name", "order": "asc"}},
            )
            if not files:
                break
            paths = [f["name"] for f in files]
            all_paths.extend(paths)
            offset += 100
        if all_paths:
            supabase.storage.from_(bucket).remove(all_paths)
            logger.info(f"Deleted {len(all_paths)} files from storage")
        else:
            logger.info("No files in storage")
    except Exception as e:
        logger.warning(f"Storage cleanup error (may be empty): {e}")

async def drop_tables():
    logger.info("Dropping all tables...")
    async with engine.begin() as conn:
        for table in TABLES:
            await conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
            logger.info(f"Truncated {table}")
    logger.info("All tables truncated")

async def main():
    logger.info("=" * 50)
    logger.info("DROP ALL DATA")
    logger.info("=" * 50)
    await drop_storage()
    await drop_tables()
    logger.info("Done! All data dropped.")

if __name__ == "__main__":
    asyncio.run(main())
