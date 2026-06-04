"""
Build seed evaluation cases for Analyzer from public scientific QA datasets.

This script intentionally avoids the HuggingFace `datasets` dependency. It uses
the HuggingFace datasets-server API via `requests`, writes raw JSONL samples, and
normalizes whatever it can into a local Analyzer eval seed file.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "eval" / "analyzer_external"
DEFAULT_SEED_PATH = ROOT_DIR / "eval" / "analyzer_eval_seed.json"
HF_DATASETS_API = "https://datasets-server.huggingface.co"


@dataclass(frozen=True)
class DatasetSpec:
    key: str
    dataset: str
    config: str | None
    split: str
    default_limit: int
    analysis_type: str


DATASET_SPECS: dict[str, DatasetSpec] = {
    "qasper": DatasetSpec(
        key="qasper",
        dataset="allenai/qasper",
        config="qasper",
        split="test",
        default_limit=30,
        analysis_type="methodology_mapping",
    ),
    # QMSum is less evidence-local than QASPER, so these cases are better for
    # synthesis/gap smoke tests than page-level retrieval scoring.
    "qmsum": DatasetSpec(
        key="qmsum",
        dataset="ioeddk/qmsum",
        config="default",
        split="test",
        default_limit=20,
        analysis_type="methodology_mapping",
    ),
    # ArXiv-QA datasets on HF are not as standardized. Keep this as an opt-in
    # source and let users override dataset/config/split from CLI.
    "arxiv_qa": DatasetSpec(
        key="arxiv_qa",
        dataset="TitanMLData/arxiv_qa",
        config="default",
        split="validation",
        default_limit=20,
        analysis_type="performance_gap",
    ),
}


def _request_json(path: str, params: dict[str, Any], timeout: int = 60) -> dict[str, Any]:
    url = f"{HF_DATASETS_API}{path}?{urlencode({k: v for k, v in params.items() if v is not None})}"
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for item in rows:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _clean_text(value: Any, max_chars: int | None = None) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        value = " ".join(_clean_text(item) for item in value)
    text = re.sub(r"\s+", " ", str(value)).strip()
    if max_chars and len(text) > max_chars:
        return text[: max_chars - 3].rstrip() + "..."
    return text


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _safe_get_list(data: dict[str, Any], key: str, idx: int) -> Any:
    value = data.get(key)
    if isinstance(value, list) and idx < len(value):
        return value[idx]
    return None


def fetch_rows(spec: DatasetSpec, limit: int, page_size: int = 100) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while len(rows) < limit:
        batch_size = min(page_size, limit - len(rows))
        payload = _request_json(
            "/rows",
            {
                "dataset": spec.dataset,
                "config": spec.config,
                "split": spec.split,
                "offset": offset,
                "length": batch_size,
            },
        )
        batch = payload.get("rows") or []
        if not batch:
            break
        rows.extend(batch)
        offset += len(batch)
        if len(batch) < batch_size:
            break
    return rows[:limit]


def _extract_qasper_answers(answer_group: Any) -> tuple[list[str], list[str]]:
    answers: list[str] = []
    evidence: list[str] = []

    if isinstance(answer_group, dict) and isinstance(answer_group.get("answer"), list):
        answer_group = [
            {"answer": answer}
            for answer in answer_group.get("answer", [])
        ]

    for answer_item in _as_list(answer_group):
        if isinstance(answer_item, dict) and "answer" in answer_item:
            answer_item = answer_item.get("answer")
        if not isinstance(answer_item, dict):
            continue

        if answer_item.get("unanswerable"):
            continue

        free_form = _clean_text(answer_item.get("free_form_answer"))
        if free_form:
            answers.append(free_form)

        for span in _as_list(answer_item.get("extractive_spans")):
            span_text = _clean_text(span)
            if span_text:
                answers.append(span_text)

        for ev in _as_list(answer_item.get("evidence")):
            ev_text = _clean_text(ev)
            if ev_text:
                evidence.append(ev_text)

    return list(dict.fromkeys(answers)), list(dict.fromkeys(evidence))


def normalize_qasper(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for raw in rows:
        row = raw.get("row", raw)
        qas = row.get("qas") or {}
        if not isinstance(qas, dict):
            continue

        questions = qas.get("question") or []
        question_ids = qas.get("question_id") or []
        answers = qas.get("answers") or []
        for idx, question in enumerate(questions):
            answer_texts, evidence_texts = _extract_qasper_answers(
                answers[idx] if idx < len(answers) else []
            )
            if not evidence_texts and not answer_texts:
                continue
            paper_id = row.get("id") or row.get("paper_id") or f"qasper-row-{raw.get('row_idx', 0)}"
            question_id = (
                question_ids[idx]
                if idx < len(question_ids)
                else f"{paper_id}-q{idx + 1}"
            )
            cases.append(
                {
                    "id": f"qasper-{question_id}",
                    "source_dataset": "qasper",
                    "source_paper_id": paper_id,
                    "source_title": row.get("title"),
                    "analysis_type": "methodology_mapping",
                    "question": _clean_text(question),
                    "expected_answer": answer_texts[:3],
                    "expected_evidence_text": evidence_texts[:5],
                    "expected_pdf_ids": [],
                    "expected_pages": [],
                    "notes": (
                        "QASPER evidence is paragraph-level. Map this source paper to an indexed "
                        "local PDF before using it for strict page/chunk scoring."
                    ),
                }
            )
    return cases


def normalize_qmsum(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for raw in rows:
        row = raw.get("row", raw)
        text = row.get("text") or ""
        question_match = re.search(r"\[Question\]:\s*(.*?)\s*\[Answer\]:", text, re.S)
        context_match = re.search(r"\[Context\]:\s*(.*?)\s*\[Prompt\]:\s*Answer", text, re.S)
        query = (
            row.get("query")
            or row.get("question")
            or row.get("instruction")
            or row.get("input")
            or (question_match.group(1) if question_match else None)
        )
        answer = row.get("answer") or row.get("summary") or row.get("output")
        if not query or not answer:
            continue
        case_id = row.get("id") or row.get("meeting_id") or f"qmsum-row-{raw.get('row_idx', 0)}"
        evidence = _clean_text(context_match.group(1), max_chars=1600) if context_match else ""
        cases.append(
            {
                "id": f"qmsum-{case_id}",
                "source_dataset": "qmsum",
                "source_paper_id": case_id,
                "source_title": row.get("topic") or row.get("title"),
                "analysis_type": "methodology_mapping",
                "question": _clean_text(query),
                "expected_answer": [_clean_text(answer, max_chars=1200)],
                "expected_evidence_text": [evidence] if evidence else [],
                "expected_pdf_ids": [],
                "expected_pages": [],
                "notes": (
                    "QMSum is useful for synthesis-style behavior, but it is not paper/PDF "
                    "evidence-local like QASPER."
                ),
            }
        )
    return cases


def normalize_generic_arxiv_qa(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for raw in rows:
        row = raw.get("row", raw)
        question = row.get("question") or row.get("Question") or row.get("query") or row.get("prompt")
        answer = row.get("answer") or row.get("Response") or row.get("response") or row.get("completion")
        evidence = (
            row.get("evidence")
            or row.get("context")
            or row.get("Text")
            or row.get("text")
            or row.get("abstract")
            or row.get("paper_text")
        )
        if not question or not answer:
            continue
        source_id = (
            row.get("id")
            or row.get("paper_id")
            or row.get("arxiv_id")
            or row.get("TextIndex")
            or f"arxivqa-row-{raw.get('row_idx', 0)}"
        )
        row_idx = raw.get("row_idx", 0)
        cases.append(
            {
                "id": f"arxivqa-{row_idx}-{source_id}",
                "source_dataset": "arxiv_qa",
                "source_paper_id": source_id,
                "source_title": row.get("title"),
                "analysis_type": "performance_gap",
                "question": _clean_text(question),
                "expected_answer": [_clean_text(answer, max_chars=1200)],
                "expected_evidence_text": [_clean_text(evidence, max_chars=1200)] if evidence else [],
                "expected_pdf_ids": [],
                "expected_pages": [],
                "notes": (
                    "ArXiv-QA schemas vary across HF mirrors. Inspect raw JSONL before "
                    "using this for strict Analyzer scoring."
                ),
            }
        )
    return cases


def _normalize_cases(key: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if key == "qasper":
        return normalize_qasper(rows)
    if key == "qmsum":
        return normalize_qmsum(rows)
    return normalize_generic_arxiv_qa(rows)


def _merge_cases(existing: list[dict[str, Any]], new_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {case["id"]: case for case in existing if case.get("id")}
    for case in new_cases:
        merged[case["id"]] = case
    return list(merged.values())


def build(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir)
    seed_path = Path(args.seed_file)
    all_new_cases: list[dict[str, Any]] = []

    for source in args.sources:
        base_spec = DATASET_SPECS[source]
        spec = DatasetSpec(
            key=base_spec.key,
            dataset=args.dataset if args.dataset and len(args.sources) == 1 else base_spec.dataset,
            config=args.config if args.config and len(args.sources) == 1 else base_spec.config,
            split=args.split if args.split and len(args.sources) == 1 else base_spec.split,
            default_limit=base_spec.default_limit,
            analysis_type=base_spec.analysis_type,
        )
        limit = args.limit or spec.default_limit
        raw_path = output_dir / f"{source}_{spec.split}_raw.jsonl"

        if args.use_cached and raw_path.exists():
            rows = _read_jsonl(raw_path)
            print(f"Using cached {source}: {raw_path} ({len(rows)} rows)")
        else:
            print(f"Fetching {source}: dataset={spec.dataset} config={spec.config} split={spec.split} limit={limit}")
            rows = fetch_rows(spec, limit=limit, page_size=args.page_size)
            _write_jsonl(raw_path, rows)
            print(f"Wrote raw rows: {raw_path} ({len(rows)} rows)")
            time.sleep(args.sleep)

        cases = _normalize_cases(source, rows)
        if args.max_cases_per_source:
            cases = cases[: args.max_cases_per_source]
        all_new_cases.extend(cases)
        normalized_path = output_dir / f"{source}_{spec.split}_cases.json"
        normalized_path.write_text(
            json.dumps({"source": source, "cases": cases}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"Wrote normalized cases: {normalized_path} ({len(cases)} cases)")

    existing_data = {}
    existing_cases: list[dict[str, Any]] = []
    if seed_path.exists() and not args.overwrite:
        existing_data = json.loads(seed_path.read_text(encoding="utf-8"))
        existing_cases = existing_data.get("cases", [])

    final_cases = all_new_cases if args.overwrite else _merge_cases(existing_cases, all_new_cases)
    payload = {
        "description": (
            "Seed Analyzer evaluation set built from public scientific QA datasets. "
            "Cases with empty expected_pdf_ids must be mapped to locally indexed PDFs "
            "before strict retrieval/page scoring."
        ),
        "sources": args.sources,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "cases": final_cases,
    }
    seed_path.parent.mkdir(parents=True, exist_ok=True)
    seed_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote seed eval set: {seed_path} ({len(final_cases)} cases)")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=sorted(DATASET_SPECS.keys()),
        default=["qasper"],
        help="Dataset sources to fetch.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Rows to fetch per source.")
    parser.add_argument("--max-cases-per-source", type=int, default=None)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--seed-file", default=str(DEFAULT_SEED_PATH))
    parser.add_argument("--page-size", type=int, default=50)
    parser.add_argument("--sleep", type=float, default=0.2)
    parser.add_argument("--use-cached", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--dataset",
        default=None,
        help="Override HF dataset id. Only valid with a single source.",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Override HF config. Only valid with a single source.",
    )
    parser.add_argument(
        "--split",
        default=None,
        help="Override HF split. Only valid with a single source.",
    )
    args = parser.parse_args(argv)
    if (args.dataset or args.config or args.split) and len(args.sources) != 1:
        parser.error("--dataset/--config/--split overrides require exactly one --sources value")
    return args


if __name__ == "__main__":
    build(parse_args(sys.argv[1:]))
