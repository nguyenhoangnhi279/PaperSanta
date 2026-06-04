"""
Normalize extracted text for inspection.

Use:
    python scripts/normalize_extracted_text.py --input raw.txt --output cleaned.txt
"""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.text_normalization_service import normalize_extracted_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize extracted PDF text.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw = args.input.read_text(encoding="utf-8")
    cleaned = normalize_extracted_text(raw)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(cleaned, encoding="utf-8")
        print(f"Wrote {args.output}")
    else:
        print(cleaned)


if __name__ == "__main__":
    main()
