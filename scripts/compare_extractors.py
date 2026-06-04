"""
Compare PDF extraction quality between pypdf and pymupdf4llm.

Use a local PDF:
    python scripts/compare_extractors.py --file path/to/paper.pdf

Use an uploaded PDF by id:
    python scripts/compare_extractors.py --pdf-id <uuid>

Output:
    reports/extraction_quality/<timestamp>_<source>.json
    reports/extraction_quality/<timestamp>_<source>.md
"""

import argparse
import asyncio
import json
import logging
from collections import Counter
from datetime import datetime
from pathlib import Path
import re
import sys
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.pdf_document import PDFDocument
from app.services.extraction_service import PyMuPDF4LLMExtractor, PyPDFExtractor, ExtractionResult
from app.services.pdf_service import get_supabase_client

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger("compare_extractors")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare pypdf vs pymupdf4llm extraction quality.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--file", type=Path, help="Local PDF path.")
    source.add_argument("--pdf-id", type=UUID, help="Existing PDFDocument id to download from Supabase.")
    parser.add_argument("--output-dir", type=Path, default=Path("reports/extraction_quality"))
    parser.add_argument("--sample-blocks", type=int, default=8)
    parser.add_argument("--preview-chars", type=int, default=2000)
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
    bucket = supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET)
    downloaded = bucket.download(doc.filename)
    if isinstance(downloaded, (bytes, bytearray)):
        return bytes(downloaded), f"{doc.original_name}-{args.pdf_id}"
    if hasattr(downloaded, "read"):
        return downloaded.read(), f"{doc.original_name}-{args.pdf_id}"
    raise RuntimeError("Could not download PDF bytes from Supabase Storage")


def extract_quality(result: ExtractionResult) -> dict:
    blocks = result.blocks
    block_types = Counter(block.block_type for block in blocks)
    chars_by_type = Counter()
    pages_with_blocks = set()
    heading_count = 0
    table_like_blocks = 0
    equation_like_blocks = 0
    figure_like_blocks = 0
    references_like_blocks = 0

    for block in blocks:
        text = block.content_markdown or ""
        chars_by_type[block.block_type] += len(text)
        if block.page_number:
            pages_with_blocks.add(block.page_number)
        if re.search(r"(?m)^#{1,6}\s+\S+", text):
            heading_count += 1
        if "|" in text and re.search(r"(?m)^\s*\|.*\|\s*$", text):
            table_like_blocks += 1
        if "$$" in text or re.search(r"\\(?:begin|frac|sum|int|alpha|beta|theta|lambda)", text):
            equation_like_blocks += 1
        if re.search(r"(?i)\b(fig\.|figure\s+\d+|table\s+\d+)\b", text):
            figure_like_blocks += 1
        if re.search(r"(?i)\breferences\b", text[:200]):
            references_like_blocks += 1

    total_chars = sum(len(block.content_markdown or "") for block in blocks)
    page_count = result.page_count or 0
    empty_pages = sorted(set(range(1, page_count + 1)) - pages_with_blocks) if page_count else []
    return {
        "extractor": result.extractor,
        "page_count": page_count,
        "block_count": len(blocks),
        "character_count": total_chars,
        "avg_chars_per_block": round(total_chars / len(blocks), 2) if blocks else 0,
        "block_types": dict(block_types),
        "chars_by_type": dict(chars_by_type),
        "pages_with_blocks": len(pages_with_blocks),
        "empty_pages": empty_pages[:30],
        "empty_page_count": len(empty_pages),
        "heading_like_blocks": heading_count,
        "table_like_blocks": table_like_blocks,
        "equation_like_blocks": equation_like_blocks,
        "figure_or_caption_like_blocks": figure_like_blocks,
        "references_like_blocks": references_like_blocks,
        "warnings": result.warnings,
    }


def sample_blocks(result: ExtractionResult, limit: int, preview_chars: int) -> list[dict]:
    samples = []
    interesting = [
        block for block in result.blocks
        if block.block_type in {"heading", "table", "equation", "caption"}
    ]
    fallback = result.blocks[:limit]
    for block in (interesting[:limit] or fallback):
        text = (block.content_markdown or "").strip().replace("\n", " ")
        samples.append({
            "page_number": block.page_number,
            "order_index": block.order_index,
            "block_type": block.block_type,
            "chars": len(block.content_markdown or ""),
            "preview": text[:preview_chars],
        })
    return samples


def write_reports(
    output_dir: Path,
    source_name: str,
    report: dict,
    sample_limit: int,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_source = re.sub(r"[^A-Za-z0-9_.-]+", "_", source_name)[:80]
    json_path = output_dir / f"{timestamp}_{safe_source}.json"
    md_path = output_dir / f"{timestamp}_{safe_source}.md"

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# Extraction Quality Report: {source_name}",
        "",
        f"Generated: {timestamp}",
        "",
        "## Summary",
        "",
        "| Extractor | Pages | Blocks | Chars | Empty pages | Tables | Equations | Headings | Figures/Captions |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, data in report["extractors"].items():
        q = data["quality"]
        lines.append(
            f"| {name} | {q['page_count']} | {q['block_count']} | {q['character_count']} | "
            f"{q['empty_page_count']} | {q['table_like_blocks']} | {q['equation_like_blocks']} | "
            f"{q['heading_like_blocks']} | {q['figure_or_caption_like_blocks']} |"
        )

    lines.extend(["", "## Details", ""])
    for name, data in report["extractors"].items():
        q = data["quality"]
        lines.extend([
            f"### {name}",
            "",
            f"- Block types: `{q['block_types']}`",
            f"- Avg chars/block: `{q['avg_chars_per_block']}`",
            f"- Empty pages: `{q['empty_pages']}`",
            f"- Warnings: `{q['warnings']}`",
            "",
            f"#### Sample Blocks (max {sample_limit})",
            "",
        ])
        for sample in data["samples"]:
            lines.extend([
                f"- Page `{sample['page_number']}`, order `{sample['order_index']}`, type `{sample['block_type']}`, chars `{sample['chars']}`",
                "",
                "```text",
                sample["preview"],
                "```",
                "",
            ])

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


async def main() -> None:
    args = parse_args()
    pdf_bytes, source_name = await load_pdf_bytes(args)

    extractors = {
        "pypdf": PyPDFExtractor(),
        "pymupdf4llm": PyMuPDF4LLMExtractor(),
    }
    report = {
        "source": source_name,
        "generated_at": datetime.now().isoformat(),
        "extractors": {},
    }

    for name, extractor in extractors.items():
        logger.info("Running extractor: %s", name)
        try:
            result = extractor.extract(pdf_bytes)
            report["extractors"][name] = {
                "quality": extract_quality(result),
                "samples": sample_blocks(result, args.sample_blocks, args.preview_chars),
            }
        except Exception as exc:
            logger.exception("Extractor failed: %s", name)
            report["extractors"][name] = {
                "quality": {"extractor": name, "error": str(exc)},
                "samples": [],
            }

    json_path, md_path = write_reports(args.output_dir, source_name, report, args.sample_blocks)
    logger.info("Wrote JSON report: %s", json_path)
    logger.info("Wrote Markdown report: %s", md_path)


if __name__ == "__main__":
    asyncio.run(main())
