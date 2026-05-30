"""Conservative cleanup for extracted academic PDF text."""

from __future__ import annotations

import re
import unicodedata


MOJIBAKE_REPLACEMENTS = {
    "â€¢": "-",
    "â‰¤": "≤",
    "â‰¥": "≥",
    "â‰¼": "≼",
    "â‰¾": "≾",
    "âˆˆ": "∈",
    "âˆ…": "∅",
    "âˆƒ": "∃",
    "âˆ€": "∀",
    "â†’": "→",
    "Â·": "·",
    "Î£": "Σ",
    "Îµ": "ε",
    "Ïˆ": "ψ",
    "Ï‰": "ω",
    "Î±": "α",
    "Î²": "β",
    "Î¸": "θ",
    "ï¬": "fi",
    "ï¬‚": "fl",
    "â€²": "'",
    "â€“": "-",
    "â€”": "-",
    "âˆ—": "*",
    "â€ ": "†",
}


LINE_WRAP_REPLACEMENTS = {
    r"\bcon\s+secutive\b": "consecutive",
    r"\bau\s+tomata\b": "automata",
    r"\bAuto\s+mata\b": "Automata",
    r"\bpeb\s+bles\b": "pebbles",
    r"\bfrag\s+ment\b": "fragment",
    r"\bord\s+er\b": "order",
    r"\btailor\s+ed\b": "tailored",
    r"\bunvisit\s+ed\b": "unvisited",
    r"\bregu\s+lar\b": "regular",
    r"\bveri\s+fication\b": "verification",
    r"\bsatis\s+fiability\b": "satisfiability",
    r"\bde\s+finable\b": "definable",
    r"\bE\s+XPSPACE\b": "EXPSPACE",
    r"\bPS\s+PACE\b": "PSPACE",
    r"\ban\s+d\b": "and",
    r"\bwhic\s+h\b": "which",
}


def normalize_extracted_text(text: str) -> str:
    """Normalize extracted text while avoiding aggressive semantic rewrites."""
    text = text.replace("\x00", "").replace("\u00ad", "")
    text = unicodedata.normalize("NFKC", text)
    text = repair_common_mojibake(text)
    text = repair_hyphenated_line_breaks(text)
    text = normalize_lines(text)
    text = repair_line_wrap_spacing(text)
    text = normalize_reference_number_spacing(text)
    text = normalize_list_markers(text)
    text = normalize_math_spacing(text)
    return text.strip()


def repair_common_mojibake(text: str) -> str:
    for bad, good in MOJIBAKE_REPLACEMENTS.items():
        text = text.replace(bad, good)
    return text


def repair_hyphenated_line_breaks(text: str) -> str:
    return re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", text)


def normalize_lines(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def repair_line_wrap_spacing(text: str) -> str:
    for pattern, replacement in LINE_WRAP_REPLACEMENTS.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    text = re.sub(r"\bA\s*PIA\s*is\b", "A PIA is", text)
    text = re.sub(r"\bPIA\s*reads\s*a\s*position\s*([a-z])\b", r"PIA reads a position \1", text)
    text = re.sub(r"\bpebbles\s*([a-z]),\s*([a-z]),\s*([a-z])\b", r"pebbles \1, \2, \3", text)
    text = re.sub(r"\bpositions\s*of\s*([a-z])\s*and\s*([a-z])\b", r"positions of \1 and \2", text)
    return text


def normalize_reference_number_spacing(text: str) -> str:
    # Fix references split by PDF line wrapping, e.g. [4, 3, 10, 2 4] -> [4, 3, 10, 24].
    return re.sub(r"(\[[0-9,\s]{0,40}\d)\s+(?=\d(?:\]|\s*,))", r"\1", text)


def normalize_list_markers(text: str) -> str:
    text = re.sub(r"(?m)^[•●]\s*", "- ", text)
    text = re.sub(r"(?<!\n)\s+-\s+(?=[A-Z])", "\n- ", text)
    return text


def normalize_math_spacing(text: str) -> str:
    text = re.sub(r"FO\[(\d+)\]", r"FO\1", text)
    text = re.sub(r"\bS\s+(\d)\b", r"S\1", text)
    text = re.sub(r"≤\s+(\d)", r"≤\1", text)
    text = re.sub(r"≼\s+(\d)", r"≼\1", text)
    text = re.sub(r"≾\s+(\d)", r"≾\1", text)
    return text
