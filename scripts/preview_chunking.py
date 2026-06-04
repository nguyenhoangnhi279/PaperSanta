"""
Preview extraction blocks and section-aware parent/child chunks without writing DB.

Use:
    python scripts/preview_chunking.py --file path/to/paper.pdf --page 2
"""

import argparse
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.extraction_service import PyMuPDF4LLMExtractor, PyPDFExtractor
from app.core.config import settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preview section-aware chunking.")
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--page", type=int, default=None)
    parser.add_argument("--extractor", choices=["pypdf", "pymupdf4llm"], default="pymupdf4llm")
    parser.add_argument("--parent-size", type=int, default=settings.CHUNK_PARENT_SIZE_CHARS)
    parser.add_argument("--child-size", type=int, default=settings.CHUNK_CHILD_SIZE_CHARS)
    parser.add_argument("--child-overlap", type=int, default=settings.CHUNK_CHILD_OVERLAP_CHARS)
    return parser.parse_args()


def parent_chunks(text: str, parent_size: int) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    parents: list[str] = []
    buffer: list[str] = []
    buffer_len = 0
    for para in paragraphs or [text.strip()]:
        if buffer and buffer_len + len(para) > parent_size:
            parents.append(" ".join(buffer).strip())
            buffer = []
            buffer_len = 0
        if len(para) > parent_size:
            sentences = re.split(r"(?<=[.!?])\s+", para)
            sent_buffer: list[str] = []
            sent_len = 0
            for sent in sentences:
                if sent_buffer and sent_len + len(sent) > parent_size:
                    parents.append(" ".join(sent_buffer).strip())
                    sent_buffer = []
                    sent_len = 0
                sent_buffer.append(sent)
                sent_len += len(sent)
            if sent_buffer:
                parents.append(" ".join(sent_buffer).strip())
            continue
        buffer.append(para)
        buffer_len += len(para)
    if buffer:
        parents.append(" ".join(buffer).strip())
    return parents


def overlap_tail(text: str, overlap_size: int) -> str:
    if overlap_size <= 0 or len(text) <= overlap_size:
        return text if overlap_size > 0 else ""
    tail = text[-overlap_size:]
    first_space = tail.find(" ")
    if first_space > 0:
        tail = tail[first_space + 1:]
    return tail.strip()


def to_children(text: str, child_size: int, child_overlap: int) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if len(sentences) <= 1:
        return [text.strip()] if text.strip() else []

    children: list[str] = []
    current: list[str] = []
    current_len = 0
    for sentence in sentences:
        if current and current_len + len(sentence) > child_size:
            chunk = " ".join(current).strip()
            children.append(chunk)
            overlap = overlap_tail(chunk, child_overlap)
            current = [overlap] if overlap else []
            current_len = len(overlap)
        current.append(sentence)
        current_len += len(sentence)
    if current:
        children.append(" ".join(current).strip())
    return children


def with_section_context(text: str, section_path: list[str] | None) -> str:
    if not section_path:
        return text
    clean_path = [part.strip() for part in section_path if part and part.strip()]
    if not clean_path:
        return text
    return f"[Section: {' > '.join(clean_path)}]\n{text}"


def main() -> None:
    args = parse_args()
    pdf_bytes = args.file.read_bytes()
    extractor = PyMuPDF4LLMExtractor() if args.extractor == "pymupdf4llm" else PyPDFExtractor()
    result = extractor.extract(pdf_bytes)
    blocks = result.blocks
    if args.page:
        blocks = [block for block in blocks if block.page_number == args.page]

    print(f"Extractor: {args.extractor}")
    print(f"Blocks: {len(blocks)}")
    print()
    for block in blocks:
        section = " > ".join(block.section_path or [])
        print(f"BLOCK page={block.page_number} order={block.order_index} type={block.block_type} section={section!r}")
        for parent_idx, parent in enumerate(parent_chunks(block.content_markdown, args.parent_size), 1):
            parent_with_section = with_section_context(parent, block.section_path)
            print(f"  Parent {parent_idx}: {parent_with_section[:500].replace(chr(10), ' ')}")
            children = to_children(parent, args.child_size, args.child_overlap)
            for child_idx, child in enumerate(children[:3], 1):
                child_with_section = with_section_context(child, block.section_path)
                print(f"    Child {child_idx}: {child_with_section[:260].replace(chr(10), ' ')}")
            if len(children) > 3:
                print(f"    ... {len(children) - 3} more children")
        print()


if __name__ == "__main__":
    main()
