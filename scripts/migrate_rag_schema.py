"""
Add structured RAG extraction schema without dropping existing PDF metadata.

Dry run:
    python scripts/migrate_rag_schema.py

Apply:
    python scripts/migrate_rag_schema.py --apply
"""

import argparse
import asyncio
import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.core.database import engine

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger("migrate_rag_schema")


STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS pdf_blocks (
        id UUID PRIMARY KEY,
        pdf_id UUID NOT NULL REFERENCES pdf_documents(id) ON DELETE CASCADE,
        page_number INTEGER,
        order_index INTEGER NOT NULL,
        block_type VARCHAR(32) NOT NULL,
        section_path JSONB,
        content_markdown TEXT NOT NULL,
        content_json JSONB,
        bbox JSONB,
        confidence FLOAT,
        extractor VARCHAR(100) NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_pdf_blocks_pdf_id ON pdf_blocks(pdf_id)",
    "CREATE INDEX IF NOT EXISTS ix_pdf_blocks_page_number ON pdf_blocks(page_number)",
    "CREATE INDEX IF NOT EXISTS ix_pdf_blocks_order_index ON pdf_blocks(order_index)",
    "CREATE INDEX IF NOT EXISTS ix_pdf_blocks_block_type ON pdf_blocks(block_type)",
    "ALTER TABLE pdf_chunks ADD COLUMN IF NOT EXISTS block_id UUID",
    "ALTER TABLE pdf_chunks ADD COLUMN IF NOT EXISTS source_block_type VARCHAR(32)",
    "ALTER TABLE pdf_chunks ADD COLUMN IF NOT EXISTS section_path JSONB",
    "ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
    "CREATE INDEX IF NOT EXISTS ix_pdf_chunks_block_id ON pdf_chunks(block_id)",
    "CREATE INDEX IF NOT EXISTS ix_pdf_chunks_source_block_type ON pdf_chunks(source_block_type)",
    """
    CREATE INDEX IF NOT EXISTS ix_pdf_chunks_chunk_text_fts
    ON pdf_chunks
    USING GIN (to_tsvector('english', coalesce(chunk_text, '')))
    """,
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'fk_pdf_chunks_block_id_pdf_blocks'
        ) THEN
            ALTER TABLE pdf_chunks
            ADD CONSTRAINT fk_pdf_chunks_block_id_pdf_blocks
            FOREIGN KEY (block_id) REFERENCES pdf_blocks(id) ON DELETE SET NULL;
        END IF;
    END $$;
    """,
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Add pdf_blocks and chunk metadata columns.")
    parser.add_argument("--apply", action="store_true", help="Apply the schema migration.")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    logger.info("This migration adds pdf_blocks and chunk block metadata columns.")
    if not args.apply:
        logger.info("Dry run only. Re-run with --apply to apply %s statements.", len(STATEMENTS))
        return

    async with engine.begin() as conn:
        for stmt in STATEMENTS:
            await conn.execute(text(stmt))
    logger.info("Done.")


if __name__ == "__main__":
    asyncio.run(main())
