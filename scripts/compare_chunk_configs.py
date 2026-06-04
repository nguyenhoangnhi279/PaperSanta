"""
Batch eval: re-index with given chunk config, then run eval.
Usage:
  python scripts/compare_chunk_configs.py
"""
import asyncio
import importlib.util
import json
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import update
from app.core.database import AsyncSessionLocal, import_all_models
from app.models.pdf_document import PDFDocument, ProcessingStatus
from app.services.pdf_service import PDFService
from app.core.config import settings

PDF_ID = "dd079458-5bf4-4efa-9ed6-a9216596e319"
EVAL_FILE = "eval/rag_eval_sample.json"
BASE_DIR = Path(__file__).resolve().parent.parent

CONFIGS = [
    {"parent_size": 1800, "child_size": 350, "child_overlap": 80, "label": "small"},
    {"parent_size": 2800, "child_size": 450, "child_overlap": 120, "label": "medium"},
    {"parent_size": 3500, "child_size": 600, "child_overlap": 150, "label": "large"},
]


def _load_eval_module():
    """Load scripts/rag_eval.py so we can call run_eval directly."""
    spec = importlib.util.spec_from_file_location("rag_eval", str(BASE_DIR / "scripts" / "rag_eval.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["rag_eval"] = mod
    spec.loader.exec_module(mod)
    return mod


async def reset_and_reindex(config: dict) -> float:
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(PDFDocument)
            .where(PDFDocument.id == uuid.UUID(PDF_ID))
            .values(status=ProcessingStatus.PENDING)
        )
        await session.commit()

    old_parent = settings.CHUNK_PARENT_SIZE_CHARS
    old_child = settings.CHUNK_CHILD_SIZE_CHARS
    old_overlap = settings.CHUNK_CHILD_OVERLAP_CHARS

    settings.CHUNK_PARENT_SIZE_CHARS = config["parent_size"]
    settings.CHUNK_CHILD_SIZE_CHARS = config["child_size"]
    settings.CHUNK_CHILD_OVERLAP_CHARS = config["child_overlap"]

    start = time.perf_counter()
    await PDFService.process_pdf(uuid.UUID(PDF_ID))
    elapsed = round(time.perf_counter() - start, 2)

    settings.CHUNK_PARENT_SIZE_CHARS = old_parent
    settings.CHUNK_CHILD_SIZE_CHARS = old_child
    settings.CHUNK_CHILD_OVERLAP_CHARS = old_overlap

    return elapsed


async def main():
    import_all_models()
    eval_mod = _load_eval_module()
    results = []

    for config in CONFIGS:
        label = config["label"]
        print(f"\n{'='*60}")
        print(f"Config: {label} (parent={config['parent_size']}, child={config['child_size']}, overlap={config['child_overlap']})")
        print(f"{'='*60}")

        elapsed = await reset_and_reindex(config)
        print(f"Re-index done in {elapsed}s")

        # Run eval using the loaded module
        import argparse
        args = argparse.Namespace(
            file=str(BASE_DIR / EVAL_FILE),
            top_k=10,
            output_dir=str(BASE_DIR / "reports" / "rag_eval"),
            restrict_to_expected_pdfs=False,
        )
        report = await eval_mod.run_eval(args)
        summary = report["summary"]
        summary["config"] = config
        summary["reindex_seconds"] = elapsed
        results.append(summary)
        print(
            f"Result: hit_at_k={summary['hit_at_k']}, "
            f"strict_hit_at_k={summary['strict_hit_at_k']}, "
            f"page_hit_at_k={summary['page_hit_at_k']}, mrr={summary['mrr']}"
        )

    print(f"\n{'='*60}")
    print("COMPARISON SUMMARY")
    print(f"{'='*60}")
    print(f"{'Label':>8s} | {'Parent':>6s} {'Child':>5s} {'Overlap':>7s} | "
          f"{'hit@k':>6s} {'strict':>7s} {'pdf_hit':>7s} {'page_hit':>8s} {'MRR':>6s} {'Lat(ms)':>7s} {'ReIdx(s)':>8s}")
    print("-" * 90)
    for r in results:
        c = r["config"]
        print(f"{c['label']:>8s} | {c['parent_size']:6d} {c['child_size']:5d} {c['child_overlap']:7d} | "
              f"{r['hit_at_k']:6.2f} {r['strict_hit_at_k']:7.2f} {r['pdf_hit_at_k']:7.2f} {r['page_hit_at_k']:8.2f} "
              f"{r['mrr']:6.4f} {r['avg_latency_ms']:7.2f} {r['reindex_seconds']:8.0f}")

    output = BASE_DIR / "reports" / "rag_eval" / "chunk_config_comparison.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved comparison to {output}")


if __name__ == "__main__":
    asyncio.run(main())
