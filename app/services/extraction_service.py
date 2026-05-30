"""PDF extraction adapters that produce structured blocks."""

from __future__ import annotations

import re
import tempfile
import uuid
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from pypdf import PdfReader

from app.core.config import settings
from app.services.text_normalization_service import normalize_extracted_text

if TYPE_CHECKING:
    from app.models.pdf_block import PDFBlock


@dataclass
class DocumentBlock:
    block_type: str
    content_markdown: str
    page_number: int | None
    order_index: int
    section_path: list[str] | None = None
    content_json: dict | list | None = None
    bbox: list | None = None
    confidence: float | None = None
    extractor: str = "unknown"
    id: uuid.UUID = field(default_factory=uuid.uuid4)


@dataclass
class ExtractionResult:
    blocks: list[DocumentBlock]
    extracted_text: str
    page_count: int
    extractor: str
    stats: dict
    warnings: list[str] = field(default_factory=list)


class PDFExtractor(Protocol):
    name: str

    def extract(self, file_bytes: bytes) -> ExtractionResult:
        ...


class PyPDFExtractor:
    name = "pypdf"

    def extract(self, file_bytes: bytes) -> ExtractionResult:
        reader = PdfReader(BytesIO(file_bytes))
        blocks: list[DocumentBlock] = []
        pages_text: list[str] = []
        warnings: list[str] = []
        order_index = 0

        for page_number, page in enumerate(reader.pages, start=1):
            try:
                text = (page.extract_text() or "").replace("\x00", "")
            except Exception as exc:
                text = ""
                warnings.append(f"page {page_number}: extraction failed: {exc}")
            pages_text.append(text)
            cleaned = normalize_extracted_text(text)
            if cleaned:
                blocks.append(
                    DocumentBlock(
                        block_type="text",
                        content_markdown=cleaned,
                        page_number=page_number,
                        order_index=order_index,
                        extractor=self.name,
                    )
                )
                order_index += 1

        extracted_text = "\n\n".join(pages_text)[:200_000].replace("\x00", "")
        stats = build_stats(blocks, len(reader.pages))
        return ExtractionResult(
            blocks=blocks,
            extracted_text=extracted_text,
            page_count=len(reader.pages),
            extractor=self.name,
            stats=stats,
            warnings=warnings,
        )


class PyMuPDF4LLMExtractor:
    name = "pymupdf4llm"

    def extract(self, file_bytes: bytes) -> ExtractionResult:
        try:
            import pymupdf4llm
        except ImportError as exc:
            raise RuntimeError("pymupdf4llm is not installed") from exc

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = Path(tmp.name)

        try:
            blocks = self._extract_blocks(pymupdf4llm, tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

        page_count = max((b.page_number or 0 for b in blocks), default=0)
        extracted_text = "\n\n".join(b.content_markdown for b in blocks)[:200_000]
        stats = build_stats(blocks, page_count)
        return ExtractionResult(
            blocks=blocks,
            extracted_text=extracted_text,
            page_count=page_count,
            extractor=self.name,
            stats=stats,
        )

    def _extract_blocks(self, pymupdf4llm, pdf_path: Path) -> list[DocumentBlock]:
        markdown = pymupdf4llm.to_markdown(
            str(pdf_path),
            page_chunks=True,
            write_images=settings.PDF_EXTRACT_WRITE_IMAGES,
        )
        blocks: list[DocumentBlock] = []
        if isinstance(markdown, list):
            current_section_path: list[str] | None = None
            for order_index, item in enumerate(markdown):
                text = item.get("text") or item.get("markdown") or ""
                text = normalize_extracted_text(text)
                if not text:
                    continue
                metadata = item.get("metadata") or {}
                page_number = item.get("page") or metadata.get("page") or metadata.get("page_number")
                page_blocks = split_markdown_page(
                    text=text,
                    page_number=int(page_number) if page_number else order_index + 1,
                    start_order_index=len(blocks),
                    extractor=self.name,
                    content_json=item,
                    current_section_path=current_section_path,
                )
                for block in page_blocks:
                    if block.block_type == "heading" and block.section_path:
                        current_section_path = block.section_path
                blocks.extend(page_blocks)
            return blocks

        text = normalize_extracted_text(str(markdown))
        if not text:
            return []
        return [
            DocumentBlock(
                block_type="text",
                content_markdown=text,
                page_number=None,
                order_index=0,
                extractor=self.name,
            )
        ]


def get_pdf_extractor() -> PDFExtractor:
    extractor = settings.PDF_EXTRACTOR.lower().strip()
    if extractor == "pypdf":
        return PyPDFExtractor()
    if extractor in {"pymupdf4llm", "pymupdf"}:
        return PyMuPDF4LLMExtractor()
    raise ValueError("Unsupported PDF_EXTRACTOR. Use 'pypdf' or 'pymupdf4llm'.")


def split_markdown_page(
    text: str,
    page_number: int | None,
    start_order_index: int,
    extractor: str,
    content_json: dict | list | None = None,
    current_section_path: list[str] | None = None,
) -> list[DocumentBlock]:
    parts = [part.strip() for part in re.split(r"(?m)(?=^#{1,6}\s+)", text) if part.strip()]
    if not parts:
        return []

    blocks: list[DocumentBlock] = []
    section_stack: list[str] = list(current_section_path or [])
    for part in parts:
        heading_match = re.match(r"(?m)^(#{1,6})\s+(.+)$", part)
        body = part
        if heading_match:
            level = len(heading_match.group(1))
            heading_text = clean_heading_text(heading_match.group(2))
            section_stack = section_stack[: max(level - 1, 0)]
            section_stack.append(heading_text)
            section_path = list(section_stack)
            blocks.append(
                DocumentBlock(
                    block_type="heading",
                    content_markdown=heading_match.group(0).strip(),
                    page_number=page_number,
                    order_index=start_order_index + len(blocks),
                    section_path=section_path,
                    content_json=content_json,
                    extractor=extractor,
                )
            )
            body = part[heading_match.end():].strip()

        for body_block in split_body_blocks(body):
            blocks.append(
                DocumentBlock(
                    block_type=infer_block_type(body_block),
                    content_markdown=body_block,
                    page_number=page_number,
                    order_index=start_order_index + len(blocks),
                    section_path=list(section_stack) if section_stack else None,
                    content_json=content_json,
                    extractor=extractor,
                )
            )
    return blocks


def clean_heading_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^\*+|\*+$", "", text).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def split_body_blocks(text: str) -> list[str]:
    if not text.strip():
        return []

    raw_blocks = re.split(r"\n\s*\n+", text.strip())
    blocks: list[str] = []
    for raw in raw_blocks:
        raw = raw.strip()
        if not raw:
            continue
        table_match = re.search(r"(?ms)(^Table\s+\d+:.*?)(?=\n[A-Z][a-z]|\n#{1,6}\s+|\Z)", raw)
        if table_match:
            for piece in (raw[:table_match.start()].strip(), table_match.group(1).strip(), raw[table_match.end():].strip()):
                if piece:
                    blocks.extend(split_long_paragraph(piece))
            continue
        blocks.extend(split_long_paragraph(raw))
    return blocks


def split_long_paragraph(text: str, max_chars: int = 1400) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for sentence in sentences:
        if current and current_len + len(sentence) > max_chars:
            chunks.append(" ".join(current).strip())
            current = []
            current_len = 0
        current.append(sentence)
        current_len += len(sentence)
    if current:
        chunks.append(" ".join(current).strip())
    return chunks


def infer_block_type(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("|") and "\n|" in stripped:
        return "table"
    if stripped.startswith("#"):
        return "heading"
    if "$$" in stripped:
        return "equation"
    lowered = stripped.lower()
    if lowered.startswith(("fig.", "figure ")):
        return "caption"
    if lowered.startswith("table "):
        return "caption"
    return "text"


def infer_section_path(text: str) -> list[str] | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return [stripped.lstrip("#").strip()]
    return None


def build_stats(blocks: list[DocumentBlock], page_count: int) -> dict:
    by_type: dict[str, int] = {}
    for block in blocks:
        by_type[block.block_type] = by_type.get(block.block_type, 0) + 1
    return {
        "page_count": page_count,
        "block_count": len(blocks),
        "block_types": by_type,
        "character_count": sum(len(block.content_markdown) for block in blocks),
    }


def to_pdf_block(pdf_id: uuid.UUID, block: DocumentBlock) -> "PDFBlock":
    from app.models.pdf_block import PDFBlock

    return PDFBlock(
        id=block.id,
        pdf_id=pdf_id,
        page_number=block.page_number,
        order_index=block.order_index,
        block_type=block.block_type,
        section_path=block.section_path,
        content_markdown=block.content_markdown,
        content_json=block.content_json,
        bbox=block.bbox,
        confidence=block.confidence,
        extractor=block.extractor,
    )
