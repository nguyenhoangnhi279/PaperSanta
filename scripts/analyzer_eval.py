"""
Evaluate Analyzer retrieval against locally indexed PDFs.

This is a local-grounded eval: it builds test cases from chunks already stored in
PaperSanta, then checks whether Analyzer's multi-query retrieval can recover
those expected chunks/pages. It writes JSON and Markdown reports under
reports/analyzer_eval/.
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

from sqlalchemy import func, select

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.database import AsyncSessionLocal, import_all_models
from app.models.embedding import PDFChunk, PDFEmbedding
from app.models.pdf_document import PDFDocument, ProcessingStatus
from app.services import analyze_service


REPORT_DIR = ROOT_DIR / "reports" / "analyzer_eval"


ANALYSIS_CASE_RULES: dict[str, dict] = {
    "benchmark_matrix": {
        "needles": ["accuracy", "ap", "map", "f1", "dataset", "benchmark", "result"],
        "question": "Compare benchmark metrics, datasets, model names, and speed evidence across the selected papers.",
    },
    "hyperparameter_compare": {
        "needles": ["learning rate", "optimizer", "batch", "epoch", "loss", "training"],
        "question": "Compare training hyperparameters and implementation details across the selected papers.",
    },
    "resource_compare": {
        "needles": ["parameters", "flops", "fps", "latency", "runtime", "memory", "vram"],
        "question": "Compare resource usage, speed, latency, model size, and deployment cost across the selected papers.",
    },
    "methodology_mapping": {
        "needles": ["method", "architecture", "pipeline", "model", "input", "loss", "algorithm"],
        "question": "Map the core methodology, architecture, pipeline, and model components across the selected papers.",
    },
    "eval_conflicts": {
        "needles": ["evaluation", "metric", "dataset", "experiment", "ablation", "comparison"],
        "question": "Find evaluation setup differences, metric mismatches, and possible result conflicts across papers.",
    },
    "paradigm_evolution": {
        "needles": ["related work", "previous", "improve", "contribution", "novel", "baseline"],
        "question": "Trace methodological evolution, inherited ideas, and improvements over prior work.",
    },
    "dataset_bias_gap": {
        "needles": ["dataset", "bias", "limitation", "future work", "coverage", "failure"],
        "question": "Identify dataset coverage, bias, limitations, and future work evidence.",
    },
    "domain_gap": {
        "needles": ["domain", "generalization", "application", "limitation", "future work"],
        "question": "Identify domain gaps, generalization limits, and missing application settings.",
    },
    "performance_gap": {
        "needles": ["real-time", "latency", "speed", "accuracy", "tradeoff", "bottleneck", "runtime"],
        "question": "Identify speed, accuracy, runtime, and performance bottleneck gaps.",
    },
    "cross_domain_idea": {
        "needles": ["transfer", "general", "framework", "representation", "architecture", "algorithm"],
        "question": "Find transferable mechanisms and cross-domain research ideas.",
    },
}


@dataclass
class LocalEvalCase:
    id: str
    analysis_type: str
    question: str
    expected_chunk_id: UUID
    expected_pdf_id: UUID
    expected_page: int | None
    expected_text: str
    pdf_ids: list[UUID]
    notes: str


def _chunk_text_score(text: str, needles: list[str]) -> int:
    lower = text.lower()
    return sum(1 for needle in needles if needle in lower)


def _preview(text: str, chars: int = 240) -> str:
    compact = " ".join((text or "").split())
    return compact[:chars]


async def _select_user_and_pdfs(session, user_id: str | None, max_pdfs: int) -> tuple[str, list[PDFDocument]]:
    if user_id:
        selected_user = user_id
    else:
        rows = await session.execute(
            select(PDFDocument.user_id, func.count(PDFDocument.id).label("doc_count"))
            .where(PDFDocument.status == ProcessingStatus.INDEXED)
            .group_by(PDFDocument.user_id)
            .order_by(func.count(PDFDocument.id).desc())
            .limit(1)
        )
        row = rows.first()
        if not row:
            raise RuntimeError("No indexed PDFs found. Index at least one PDF before running analyzer eval.")
        selected_user = row[0]

    docs_result = await session.execute(
        select(PDFDocument)
        .where(
            PDFDocument.user_id == selected_user,
            PDFDocument.status == ProcessingStatus.INDEXED,
        )
        .order_by(PDFDocument.updated_at.desc())
        .limit(max_pdfs)
    )
    docs = list(docs_result.scalars())
    if not docs:
        raise RuntimeError(f"No indexed PDFs found for user_id={selected_user!r}.")
    return selected_user, docs


async def _candidate_chunks(session, pdf_ids: list[UUID], limit: int) -> list[PDFChunk]:
    result = await session.execute(
        select(PDFChunk)
        .join(PDFEmbedding, PDFEmbedding.chunk_id == PDFChunk.id)
        .where(
            PDFChunk.pdf_id.in_(pdf_ids),
            PDFChunk.chunk_type == "child",
            PDFChunk.source_block_type.is_not(None),
            PDFChunk.source_block_type != "heading",
            func.length(PDFChunk.chunk_text) >= 180,
        )
        .order_by(PDFChunk.page_number.asc().nulls_last(), PDFChunk.chunk_index.asc())
        .limit(limit)
    )
    chunks = list(result.scalars())
    if not chunks:
        raise RuntimeError("No embedded child chunks found for selected PDFs.")
    return chunks


def _build_cases(chunks: list[PDFChunk], pdf_ids: list[UUID], cases_per_type: int) -> list[LocalEvalCase]:
    cases: list[LocalEvalCase] = []
    used_chunk_ids: set[UUID] = set()

    for analysis_type, rule in ANALYSIS_CASE_RULES.items():
        scored = [
            (_chunk_text_score(chunk.chunk_text, rule["needles"]), chunk)
            for chunk in chunks
            if chunk.id not in used_chunk_ids
        ]
        scored = [(score, chunk) for score, chunk in scored if score > 0]
        scored.sort(key=lambda item: (item[0], len(item[1].chunk_text)), reverse=True)

        for idx, (score, chunk) in enumerate(scored[:cases_per_type], 1):
            used_chunk_ids.add(chunk.id)
            cases.append(
                LocalEvalCase(
                    id=f"{analysis_type}-{idx:02d}",
                    analysis_type=analysis_type,
                    question=rule["question"],
                    expected_chunk_id=chunk.id,
                    expected_pdf_id=chunk.pdf_id,
                    expected_page=chunk.page_number,
                    expected_text=_preview(chunk.chunk_text, 160),
                    pdf_ids=pdf_ids,
                    notes=f"Local synthetic case from indexed chunk. keyword_score={score}",
                )
            )
    return cases


def _match_result(result: dict, case: LocalEvalCase) -> dict:
    chunk: PDFChunk = result["chunk"]
    context_text = result.get("context_text") or chunk.chunk_text or ""
    expected_words = [word for word in case.expected_text.lower().split()[:12] if len(word) >= 4]
    text_overlap = 0.0
    if expected_words:
        lower_context = context_text.lower()
        text_overlap = sum(1 for word in expected_words if word in lower_context) / len(expected_words)
    return {
        "chunk": chunk.id == case.expected_chunk_id,
        "pdf": result["pdf_id"] == case.expected_pdf_id,
        "page": case.expected_page is None or chunk.page_number == case.expected_page,
        "text_overlap": round(text_overlap, 4),
        "evidence": (
            result["pdf_id"] == case.expected_pdf_id
            and (case.expected_page is None or chunk.page_number == case.expected_page)
            and text_overlap >= 0.35
        ),
    }


def _reciprocal_rank(matches: list[bool]) -> float:
    for idx, matched in enumerate(matches, 1):
        if matched:
            return 1.0 / idx
    return 0.0


def _write_report(report: dict) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    json_path = REPORT_DIR / f"analyzer_eval_{timestamp}.json"
    md_path = REPORT_DIR / f"analyzer_eval_{timestamp}.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Analyzer Local Retrieval Eval",
        "",
        "## Summary",
        "",
    ]
    for key, value in report["summary"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend([
        "",
        "## Scope",
        "",
        "This report evaluates Analyzer retrieval on local indexed chunks. It does not call the LLM and does not judge answer quality.",
        "",
        "## Cases",
        "",
    ])
    for case in report["cases"]:
        lines.append(f"### {case['id']}")
        lines.append("")
        lines.append(f"- Analysis type: `{case['analysis_type']}`")
        lines.append(f"- Question: {case['question']}")
        lines.append(f"- Expected PDF: `{case['expected_pdf_name']}`")
        lines.append(f"- Expected page: `{case['expected_page']}`")
        lines.append(f"- Expected chunk hit: `{case['chunk_hit_at_k']}`")
        lines.append(f"- Evidence hit: `{case['evidence_hit_at_k']}`")
        lines.append(f"- Rank: `{case['rank']}`")
        lines.append(f"- MRR: `{case['mrr']}`")
        lines.append("")
        lines.append("| Rank | Score | Sources | PDF | Page | Match | Preview |")
        lines.append("|---:|---:|---|---|---:|---|---|")
        for result in case["results"]:
            match = ",".join(k for k, v in result["match"].items() if v and k != "text_overlap")
            preview = result["preview"].replace("|", "\\|")
            sources = ",".join(result.get("retrieval_sources") or [])
            lines.append(
                f"| {result['rank']} | {result['score']} | {sources} | {result['pdf_name']} | "
                f"{result['page_number'] or ''} | {match} | {preview} |"
            )
        lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


async def run_eval(args: argparse.Namespace) -> dict:
    import_all_models()
    async with AsyncSessionLocal() as session:
        user_id, docs = await _select_user_and_pdfs(session, args.user_id, args.max_pdfs)
        pdf_ids = [doc.id for doc in docs]
        pdf_name_by_id = {doc.id: doc.original_name for doc in docs}
        chunks = await _candidate_chunks(session, pdf_ids, args.candidate_chunks)
        cases = _build_cases(chunks, pdf_ids, args.cases_per_type)
        if args.max_cases:
            cases = cases[: args.max_cases]
        if not cases:
            raise RuntimeError("Could not build any local analyzer eval cases from indexed chunks.")

        case_reports = []
        for case in cases:
            started = time.perf_counter()
            results = await analyze_service._retrieve_analysis_context(
                db=session,
                user_id=user_id,
                pdf_uuids=case.pdf_ids,
                analysis_type=case.analysis_type,
                fallback_query=ANALYSIS_CASE_RULES[case.analysis_type]["question"],
                top_k=args.top_k,
            )
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)

            result_reports = []
            chunk_matches = []
            evidence_matches = []
            for rank, result in enumerate(results, 1):
                chunk: PDFChunk = result["chunk"]
                match = _match_result(result, case)
                chunk_matches.append(match["chunk"])
                evidence_matches.append(match["evidence"])
                result_reports.append(
                    {
                        "rank": rank,
                        "score": result.get("score"),
                        "analysis_rank_score": result.get("analysis_rank_score"),
                        "pdf_id": str(result["pdf_id"]),
                        "pdf_name": result.get("pdf_name"),
                        "chunk_id": str(chunk.id),
                        "page_number": chunk.page_number,
                        "section_path": chunk.section_path,
                        "source_block_type": chunk.source_block_type,
                        "retrieval_sources": result.get("retrieval_sources", []),
                        "analysis_queries": result.get("analysis_queries", []),
                        "preview": _preview(chunk.chunk_text),
                        "match": match,
                    }
                )

            chunk_hit = any(chunk_matches)
            evidence_hit = any(evidence_matches)
            rank = next((idx for idx, matched in enumerate(chunk_matches, 1) if matched), None)
            evidence_rank = next((idx for idx, matched in enumerate(evidence_matches, 1) if matched), None)
            case_reports.append(
                {
                    "id": case.id,
                    "analysis_type": case.analysis_type,
                    "question": case.question,
                    "expected_pdf_id": str(case.expected_pdf_id),
                    "expected_pdf_name": pdf_name_by_id.get(case.expected_pdf_id, "Unknown"),
                    "expected_page": case.expected_page,
                    "expected_chunk_id": str(case.expected_chunk_id),
                    "expected_text": case.expected_text,
                    "notes": case.notes,
                    "latency_ms": elapsed_ms,
                    "chunk_hit_at_k": chunk_hit,
                    "evidence_hit_at_k": evidence_hit,
                    "rank": rank,
                    "evidence_rank": evidence_rank,
                    "mrr": round(_reciprocal_rank(chunk_matches), 4),
                    "evidence_mrr": round(_reciprocal_rank(evidence_matches), 4),
                    "results": result_reports,
                }
            )

    total = len(case_reports)
    report = {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "user_id": user_id,
        "pdfs": [
            {
                "id": str(doc.id),
                "name": doc.original_name,
                "page_count": doc.page_count,
                "status": str(doc.status.value if hasattr(doc.status, "value") else doc.status),
            }
            for doc in docs
        ],
        "summary": {
            "cases": total,
            "analysis_types": len({case["analysis_type"] for case in case_reports}),
            "top_k": args.top_k,
            "chunk_hit_at_k": round(sum(1 for case in case_reports if case["chunk_hit_at_k"]) / max(1, total), 4),
            "evidence_hit_at_k": round(sum(1 for case in case_reports if case["evidence_hit_at_k"]) / max(1, total), 4),
            "mrr": round(sum(case["mrr"] for case in case_reports) / max(1, total), 4),
            "evidence_mrr": round(sum(case["evidence_mrr"] for case in case_reports) / max(1, total), 4),
            "avg_latency_ms": round(sum(case["latency_ms"] for case in case_reports) / max(1, total), 2),
        },
        "cases": case_reports,
    }
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", default=None)
    parser.add_argument("--max-pdfs", type=int, default=5)
    parser.add_argument("--candidate-chunks", type=int, default=800)
    parser.add_argument("--cases-per-type", type=int, default=2)
    parser.add_argument("--max-cases", type=int, default=20)
    parser.add_argument("--top-k", type=int, default=20)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = asyncio.run(run_eval(args))
    json_path, md_path = _write_report(report)
    print(json.dumps(report["summary"], indent=2, ensure_ascii=False))
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
