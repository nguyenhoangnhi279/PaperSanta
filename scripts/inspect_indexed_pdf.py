"""
Inspect stored pdf_blocks and pdf_chunks for an indexed PDF.

Use:
    python scripts/inspect_indexed_pdf.py --pdf-id <uuid> --page 2
"""

import argparse
import asyncio
from pathlib import Path
import sys
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal
from app.models.embedding import PDFChunk
from app.models.pdf_block import PDFBlock
from app.models.pdf_document import PDFDocument


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect stored extraction blocks and chunks.")
    parser.add_argument("--pdf-id", type=UUID, required=True)
    parser.add_argument("--page", type=int, default=None)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--chars", type=int, default=900)
    return parser.parse_args()


def preview(text: str, chars: int) -> str:
    return (text or "").replace("\n", " ")[:chars]


async def main() -> None:
    args = parse_args()
    async with AsyncSessionLocal() as session:
        doc = await session.get(PDFDocument, args.pdf_id)
        if not doc:
            raise SystemExit(f"PDF not found: {args.pdf_id}")

        print(f"PDF: {doc.original_name}")
        print(f"ID: {doc.id}")
        print(f"Status: {doc.status}")
        print(f"Pages: {doc.page_count}")
        print()

        block_filters = [PDFBlock.pdf_id == args.pdf_id]
        chunk_filters = [PDFChunk.pdf_id == args.pdf_id]
        if args.page:
            block_filters.append(PDFBlock.page_number == args.page)
            chunk_filters.append(PDFChunk.page_number == args.page)

        block_count = await session.scalar(select(func.count()).select_from(PDFBlock).where(*block_filters))
        parent_count = await session.scalar(
            select(func.count()).select_from(PDFChunk).where(*chunk_filters, PDFChunk.chunk_type == "parent")
        )
        child_count = await session.scalar(
            select(func.count()).select_from(PDFChunk).where(*chunk_filters, PDFChunk.chunk_type == "child")
        )
        print(f"Blocks: {block_count}")
        print(f"Parent chunks: {parent_count}")
        print(f"Child chunks: {child_count}")
        print()

        blocks = (
            await session.execute(
                select(PDFBlock)
                .where(*block_filters)
                .order_by(PDFBlock.page_number, PDFBlock.order_index)
                .limit(args.limit)
            )
        ).scalars().all()

        print("== Blocks ==")
        for block in blocks:
            section = " > ".join(block.section_path or [])
            print(
                f"- block={block.id} page={block.page_number} order={block.order_index} "
                f"type={block.block_type} section={section!r} chars={len(block.content_markdown or '')}"
            )
            print(f"  {preview(block.content_markdown, args.chars)}")
            print()

        chunks = (
            await session.execute(
                select(PDFChunk)
                .where(*chunk_filters)
                .order_by(PDFChunk.page_number, PDFChunk.chunk_index)
                .limit(args.limit)
            )
        ).scalars().all()

        print("== Chunks ==")
        for chunk in chunks:
            section = " > ".join(chunk.section_path or [])
            print(
                f"- chunk={chunk.id} page={chunk.page_number} idx={chunk.chunk_index} "
                f"type={chunk.chunk_type} block={chunk.block_id} source={chunk.source_block_type} "
                f"section={section!r} chars={len(chunk.chunk_text or '')}"
            )
            print(f"  {preview(chunk.chunk_text, args.chars)}")
            print()


if __name__ == "__main__":
    asyncio.run(main())
