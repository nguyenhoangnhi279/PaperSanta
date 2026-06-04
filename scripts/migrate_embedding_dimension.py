"""
Migrate pgvector dimension for PDF embeddings.

This clears existing chunks/embeddings because vectors from different models or
dimensions cannot be compared. Uploaded PDF files and PDF metadata are kept.

Dry run:
    python scripts/migrate_embedding_dimension.py --dimension 1024

Apply:
    python scripts/migrate_embedding_dimension.py --dimension 1024 --apply
"""

import argparse
import asyncio
import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger("migrate_embedding_dimension")


async def get_current_dimension() -> int | None:
    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                """
                SELECT atttypmod
                FROM pg_attribute
                WHERE attrelid = 'pdf_embeddings'::regclass
                  AND attname = 'vector'
                  AND NOT attisdropped
                """
            )
        )
        typmod = result.scalar_one_or_none()
        if typmod is None:
            return None
        # pgvector stores dimension as typmod - 4.
        return int(typmod) - 4


async def count_existing_rows() -> dict[str, int]:
    async with engine.begin() as conn:
        counts = {}
        for table in ("pdf_documents", "pdf_chunks", "pdf_embeddings"):
            result = await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
            counts[table] = int(result.scalar_one())
        return counts


async def migrate_dimension(target_dimension: int) -> None:
    async with engine.begin() as conn:
        logger.info("Deleting existing chunks and embeddings...")
        await conn.execute(text("DELETE FROM pdf_chunks"))

        logger.info("Altering pdf_embeddings.vector to vector(%s)...", target_dimension)
        await conn.execute(
            text(
                f"""
                ALTER TABLE pdf_embeddings
                ALTER COLUMN vector TYPE vector({target_dimension})
                USING vector::vector({target_dimension})
                """
            )
        )

        logger.info("Resetting PDF indexing status...")
        await conn.execute(
            text(
                """
                UPDATE pdf_documents
                SET status = 'pending',
                    error_message = NULL,
                    updated_at = NOW()
                """
            )
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Change pdf_embeddings.vector dimension and clear existing RAG index data."
    )
    parser.add_argument(
        "--dimension",
        type=int,
        default=settings.EMBEDDING_DIMENSION,
        help="Target embedding dimension, usually matching EMBEDDING_DIMENSION.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually perform the migration. Without this flag, only prints a dry run.",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    if args.dimension <= 0:
        raise SystemExit("--dimension must be a positive integer")

    current_dimension = await get_current_dimension()
    counts = await count_existing_rows()

    logger.info("Configured EMBEDDING_MODEL_NAME: %s", settings.EMBEDDING_MODEL_NAME)
    logger.info("Configured EMBEDDING_DIMENSION: %s", settings.EMBEDDING_DIMENSION)
    logger.info("Current DB vector dimension: %s", current_dimension)
    logger.info("Target DB vector dimension: %s", args.dimension)
    logger.info("Existing rows: %s", counts)

    if current_dimension == args.dimension:
        logger.info("No dimension change needed.")
        return

    logger.warning(
        "This migration deletes all pdf_chunks/pdf_embeddings and resets PDFs to pending."
    )
    logger.warning("PDF metadata and Supabase Storage files are kept.")

    if not args.apply:
        logger.info("Dry run only. Re-run with --apply to perform the migration.")
        return

    await migrate_dimension(args.dimension)
    logger.info("Done. Re-index PDFs from the app or the /api/pdf/{id}/index endpoint.")


if __name__ == "__main__":
    asyncio.run(main())
