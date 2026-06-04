"""
Evaluate RAG retrieval quality against a small local benchmark.

The benchmark is JSON so it can be edited without extra dependencies.
This script measures retrieval only: hit@k, MRR, expected PDF hit,
expected page hit, and optional expected text/section matches.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.database import AsyncSessionLocal, import_all_models
from app.core.config import settings
from app.services.rag_service import RAGService


@dataclass
class EvalCase:
    id: str
    question: str
    expected_pdf_ids: list[UUID]
    expected_pages: list[int]
    expected_text_contains: list[str]
    expected_section_contains: list[str]
    notes: str = ""


def _load_cases(path: Path) -> tuple[str, list[EvalCase]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    user_id = data["user_id"]
    cases: list[EvalCase] = []
    for idx, item in enumerate(data.get("cases", []), 1):
        case_id = item.get("id") or f"case-{idx:03d}"
        expected_pdf_ids = [UUID(pid) for pid in item.get("expected_pdf_ids", [])]
        cases.append(
            EvalCase(
                id=case_id,
                question=item["question"],
                expected_pdf_ids=expected_pdf_ids,
                expected_pages=[int(page) for page in item.get("expected_pages", [])],
                expected_text_contains=[
                    text.lower() for text in item.get("expected_text_contains", [])
                ],
                expected_section_contains=[
                    text.lower() for text in item.get("expected_section_contains", [])
                ],
                notes=item.get("notes", ""),
            )
        )
    return user_id, cases


def _match_expected(result: dict, case: EvalCase) -> dict:
    chunk = result["chunk"]
    pdf_id = result["pdf_id"]
    chunk_text = (chunk.chunk_text or "").lower()
    context_text = (result.get("context_text") or "").lower()
    combined_text = f"{chunk_text}\n{context_text}"
    section_path = " > ".join(chunk.section_path or []).lower()

    pdf_match = not case.expected_pdf_ids or pdf_id in case.expected_pdf_ids
    page_match = (
        not case.expected_pages
        or (pdf_match and chunk.page_number in case.expected_pages)
    )
    text_match = (
        not case.expected_text_contains
        or any(expected in combined_text for expected in case.expected_text_contains)
    )
    section_match = (
        not case.expected_section_contains
        or any(expected in section_path for expected in case.expected_section_contains)
        or any(expected in combined_text for expected in case.expected_section_contains)
    )
    evidence_match = pdf_match and page_match and text_match
    strict_match = evidence_match and section_match
    return {
        "pdf": pdf_match,
        "page": page_match,
        "text": text_match,
        "section": section_match,
        "evidence": evidence_match,
        "strict": strict_match,
        "all": evidence_match,
    }


def _reciprocal_rank(matches: list[bool]) -> float:
    for idx, matched in enumerate(matches, 1):
        if matched:
            return 1.0 / idx
    return 0.0


def _write_reports(output_dir: Path, report: dict) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    json_path = output_dir / f"rag_eval_{timestamp}.json"
    md_path = output_dir / f"rag_eval_{timestamp}.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# RAG Evaluation Report",
        "",
        "## Summary",
        "",
    ]
    for key, value in report["summary"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend([
        "",
        "## Metric Notes",
        "",
        "- `hit_at_k`: expected PDF + expected page when provided + expected text match.",
        "- `strict_hit_at_k`: `hit_at_k` plus expected section match.",
        "- `page_hit_at_k`: page match only counts when the PDF also matches.",
        "",
        "## Cases",
        "",
    ])

    for case in report["cases"]:
        lines.append(f"### {case['id']}")
        lines.append("")
        lines.append(f"- Question: {case['question']}")
        lines.append(f"- Hit@k: {case['hit_at_k']}")
        lines.append(f"- Strict hit@k: {case['strict_hit_at_k']}")
        lines.append(f"- Rank: {case['rank']}")
        lines.append(f"- Strict rank: {case['strict_rank']}")
        lines.append(f"- MRR: {case['mrr']}")
        lines.append(f"- Strict MRR: {case['strict_mrr']}")
        if case.get("notes"):
            lines.append(f"- Notes: {case['notes']}")
        lines.append("")
        lines.append("| Rank | Score | Sources | PDF | Page | Match | Chunk |")
        lines.append("|---:|---:|---|---|---:|---|---|")
        for result in case["results"]:
            chunk_preview = result["chunk_text"].replace("|", "\\|").replace("\n", " ")[:180]
            match = ",".join(k for k, v in result["match"].items() if v)
            sources = ",".join(result.get("retrieval_sources") or [])
            lines.append(
                f"| {result['rank']} | {result['score']} | {sources} | {result['pdf_name']} | "
                f"{result['page_number'] or ''} | {match} | {chunk_preview} |"
            )
        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


async def _resolve_pdf_ids(user_id: str, cases: list[EvalCase]) -> None:
    missing = [case for case in cases if not case.expected_pdf_ids]
    if not missing:
        return
    async with AsyncSessionLocal() as session:
        for case in missing:
            raise ValueError(
                f"Case {case.id} has no expected_pdf_ids. Add exact PDF ids first. "
                "Use scripts/inspect_indexed_pdf.py or query pdf_documents to find ids."
            )


async def run_eval(args: argparse.Namespace) -> dict:
    import_all_models()
    old_retrieval_mode = settings.RAG_RETRIEVAL_MODE
    old_text_weight = settings.RAG_TEXT_WEIGHT
    old_rerank_mode = settings.RAG_RERANK_MODE
    if getattr(args, "retrieval_mode", None):
        settings.RAG_RETRIEVAL_MODE = args.retrieval_mode
    if getattr(args, "text_weight", None) is not None:
        settings.RAG_TEXT_WEIGHT = args.text_weight
    if getattr(args, "rerank_mode", None):
        settings.RAG_RERANK_MODE = args.rerank_mode

    user_id, cases = _load_cases(Path(args.file))
    await _resolve_pdf_ids(user_id, cases)

    case_reports = []
    async with AsyncSessionLocal() as session:
        for case in cases:
            started = time.perf_counter()
            results = await RAGService.similarity_search(
                session=session,
                user_id=user_id,
                query_text=case.question,
                pdf_ids=case.expected_pdf_ids if args.restrict_to_expected_pdfs else None,
                top_k=args.top_k,
            )
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)

            result_reports = []
            evidence_matches = []
            strict_matches = []
            pdf_matches = []
            page_matches = []
            for rank, result in enumerate(results, 1):
                chunk = result["chunk"]
                match = _match_expected(result, case)
                evidence_matches.append(match["evidence"])
                strict_matches.append(match["strict"])
                pdf_matches.append(match["pdf"])
                page_matches.append(match["page"])
                result_reports.append(
                    {
                        "rank": rank,
                        "score": result["score"],
                        "pdf_id": str(result["pdf_id"]),
                        "pdf_name": result["pdf_name"],
                        "chunk_id": str(chunk.id),
                        "parent_id": str(chunk.parent_id) if chunk.parent_id else None,
                        "page_number": chunk.page_number,
                        "section_path": chunk.section_path,
                        "source_block_type": chunk.source_block_type,
                        "chunk_text": chunk.chunk_text,
                        "retrieval_sources": result.get("retrieval_sources", []),
                        "dense_rank": result.get("dense_rank"),
                        "dense_score": result.get("dense_score"),
                        "text_rank": result.get("text_rank"),
                        "text_score": result.get("text_score"),
                        "pre_rerank_rank": result.get("pre_rerank_rank"),
                        "pre_rerank_score": result.get("pre_rerank_score"),
                        "rerank_score": result.get("rerank_score"),
                        "lexical_score": result.get("lexical_score"),
                        "phrase_score": result.get("phrase_score"),
                        "section_score": result.get("section_score"),
                        "match": match,
                    }
                )

            rank = next((idx for idx, matched in enumerate(evidence_matches, 1) if matched), None)
            strict_rank = next((idx for idx, matched in enumerate(strict_matches, 1) if matched), None)
            case_reports.append(
                {
                    "id": case.id,
                    "question": case.question,
                    "notes": case.notes,
                    "expected_pdf_ids": [str(pid) for pid in case.expected_pdf_ids],
                    "expected_pages": case.expected_pages,
                    "expected_text_contains": case.expected_text_contains,
                    "expected_section_contains": case.expected_section_contains,
                    "elapsed_ms": elapsed_ms,
                    "hit_at_k": any(evidence_matches),
                    "strict_hit_at_k": any(strict_matches),
                    "pdf_hit_at_k": any(pdf_matches),
                    "page_hit_at_k": any(page_matches) if case.expected_pages else None,
                    "rank": rank,
                    "strict_rank": strict_rank,
                    "mrr": round(_reciprocal_rank(evidence_matches), 4),
                    "strict_mrr": round(_reciprocal_rank(strict_matches), 4),
                    "results": result_reports,
                }
            )

    total = len(case_reports)
    report = {
        "config": {
            "top_k": args.top_k,
            "restrict_to_expected_pdfs": args.restrict_to_expected_pdfs,
            "input_file": str(args.file),
            "retrieval_mode": settings.RAG_RETRIEVAL_MODE,
            "text_weight": settings.RAG_TEXT_WEIGHT,
            "rerank_mode": settings.RAG_RERANK_MODE,
        },
        "summary": {
            "cases": total,
            "hit_at_k": round(sum(1 for c in case_reports if c["hit_at_k"]) / total, 4) if total else 0,
            "strict_hit_at_k": round(sum(1 for c in case_reports if c["strict_hit_at_k"]) / total, 4) if total else 0,
            "pdf_hit_at_k": round(sum(1 for c in case_reports if c["pdf_hit_at_k"]) / total, 4) if total else 0,
            "page_hit_at_k": round(
                sum(1 for c in case_reports if c["page_hit_at_k"])
                / max(1, sum(1 for c in case_reports if c["page_hit_at_k"] is not None)),
                4,
            ),
            "mrr": round(sum(c["mrr"] for c in case_reports) / total, 4) if total else 0,
            "strict_mrr": round(sum(c["strict_mrr"] for c in case_reports) / total, 4) if total else 0,
            "avg_latency_ms": round(sum(c["elapsed_ms"] for c in case_reports) / total, 2) if total else 0,
        },
        "cases": case_reports,
    }
    _write_reports(Path(args.output_dir), report)
    settings.RAG_RETRIEVAL_MODE = old_retrieval_mode
    settings.RAG_TEXT_WEIGHT = old_text_weight
    settings.RAG_RERANK_MODE = old_rerank_mode
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate RAG retrieval quality.")
    parser.add_argument("--file", required=True, help="Path to eval JSON file.")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--output-dir", default="reports/rag_eval")
    parser.add_argument("--retrieval-mode", choices=["dense", "hybrid"], default=None)
    parser.add_argument("--text-weight", type=float, default=None)
    parser.add_argument("--rerank-mode", choices=["none", "heuristic"], default=None)
    parser.add_argument(
        "--restrict-to-expected-pdfs",
        action="store_true",
        help="Search only inside expected PDFs. Useful for chunking tests, less useful for global retrieval tests.",
    )
    args = parser.parse_args()
    report = asyncio.run(run_eval(args))
    print(json.dumps(report["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
