"""
Dump full extracted content for one page from pypdf and pymupdf4llm.

Use a local PDF:
    python scripts/inspect_extractor_page.py --file path/to/paper.pdf --page 2

Use an uploaded PDF by id:
    python scripts/inspect_extractor_page.py --pdf-id <uuid> --page 2
"""

import argparse
import asyncio
from pathlib import Path
import sys
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.pdf_document import PDFDocument
from app.services.extraction_service import PyMuPDF4LLMExtractor, PyPDFExtractor
from app.services.pdf_service import get_supabase_client


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect full extracted text for a single page.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--file", type=Path, help="Local PDF path.")
    source.add_argument("--pdf-id", type=UUID, help="Existing PDFDocument id to download from Supabase.")
    parser.add_argument("--page", type=int, required=True, help="1-based page number to inspect.")
    parser.add_argument("--output", type=Path, default=None, help="Optional output .md path.")
    return parser.parse_args()


async def load_pdf_bytes(args: argparse.Namespace) -> tuple[bytes, str]:
    if args.file:
        path = args.file.resolve()
        return path.read_bytes(), path.stem

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(PDFDocument).where(PDFDocument.id == args.pdf_id))
        doc = result.scalar_one_or_none()
        if not doc:
            raise SystemExit(f"PDF not found: {args.pdf_id}")

    supabase = get_supabase_client()
    downloaded = supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET).download(doc.filename)
    if isinstance(downloaded, (bytes, bytearray)):
        return bytes(downloaded), f"{doc.original_name}-{args.pdf_id}"
    if hasattr(downloaded, "read"):
        return downloaded.read(), f"{doc.original_name}-{args.pdf_id}"
    raise RuntimeError("Could not download PDF bytes from Supabase Storage")


def page_text(result, page: int) -> str:
    blocks = [block for block in result.blocks if block.page_number == page]
    if not blocks:
        return ""
    return "\n\n".join(block.content_markdown for block in sorted(blocks, key=lambda b: b.order_index))


async def main() -> None:
    args = parse_args()
    pdf_bytes, source_name = await load_pdf_bytes(args)
    outputs = []

    for name, extractor in {
        "pypdf": PyPDFExtractor(),
        "pymupdf4llm": PyMuPDF4LLMExtractor(),
    }.items():
        try:
            result = extractor.extract(pdf_bytes)
            text = page_text(result, args.page)
            outputs.append(
                "\n".join([
                    f"# {name} - page {args.page}",
                    "",
                    f"Source: {source_name}",
                    f"Chars: {len(text)}",
                    "",
                    "```text",
                    text,
                    "```",
                    "",
                ])
            )
        except Exception as exc:
            outputs.append(f"# {name} - page {args.page}\n\nERROR: {exc}\n")

    final = "\n---\n\n".join(outputs)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(final, encoding="utf-8")
        print(f"Wrote {args.output}")
    else:
        print(final)


if __name__ == "__main__":
    asyncio.run(main())
