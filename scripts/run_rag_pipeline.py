"""
One-shot RAG eval pipeline: migrate → re-index → eval → compare.

Examples:
  # Full pipeline với config mặc định (medium)
  python scripts/run_rag_pipeline.py --pdf-id <uuid>

  # Dry run: migrate + inspect PDF cũ (không re-index)
  python scripts/run_rag_pipeline.py --pdf-id <uuid> --dry-run

  # Chạy với config khác
  python scripts/run_rag_pipeline.py --pdf-id <uuid> --parent-size 1800 --child-size 350 --overlap 80

  # Chạy so sánh 3 configs
  python scripts/run_rag_pipeline.py --pdf-id <uuid> --compare

  # Skip migration step
  python scripts/run_rag_pipeline.py --pdf-id <uuid> --skip-migration
"""
import argparse
import asyncio
import json
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine, import_all_models
from app.models.pdf_document import PDFDocument, ProcessingStatus
from app.services.pdf_service import PDFService
from sqlalchemy import text, update


# ── Configs để so sánh ──────────────────────────────────────────
COMPARE_CONFIGS = [
    {"parent_size": 1800, "child_size": 350, "child_overlap": 80, "label": "small"},
    {"parent_size": 2800, "child_size": 450, "child_overlap": 120, "label": "medium"},
    {"parent_size": 3500, "child_size": 600, "child_overlap": 150, "label": "large"},
]


# ── Helpers ─────────────────────────────────────────────────────
def _bold(s):
    return f"\033[1m{s}\033[0m"


def _print_step(title):
    print(f"\n{'='*60}")
    print(f"{_bold(title)}")
    print(f"{'='*60}")


# ── Steps ───────────────────────────────────────────────────────
async def step_migrate():
    from scripts.migrate_rag_schema import STATEMENTS

    _print_step("STEP: Schema migration")
    async with engine.begin() as conn:
        for stmt in STATEMENTS:
            await conn.execute(text(stmt))
    print("Done.")


async def step_inspect(pdf_id: uuid.UUID):
    _print_step("STEP: Inspect PDF")
    from sqlalchemy import func, select
    from app.models.embedding import PDFChunk
    from app.models.pdf_block import PDFBlock
    from app.models.pdf_document import PDFDocument

    async with AsyncSessionLocal() as session:
        doc = await session.get(PDFDocument, pdf_id)
        if not doc:
            print(f"PDF not found: {pdf_id}")
            return

        print(f"  Name:   {doc.original_name}")
        print(f"  ID:     {doc.id}")
        print(f"  Status: {doc.status.value}")
        print(f"  Pages:  {doc.page_count}")

        block_count = await session.scalar(
            select(func.count()).select_from(PDFBlock).where(PDFBlock.pdf_id == pdf_id)
        )
        parent_count = await session.scalar(
            select(func.count()).select_from(PDFChunk).where(
                PDFChunk.pdf_id == pdf_id, PDFChunk.chunk_type == "parent"
            )
        )
        child_count = await session.scalar(
            select(func.count()).select_from(PDFChunk).where(
                PDFChunk.pdf_id == pdf_id, PDFChunk.chunk_type == "child"
            )
        )
        print(f"  Blocks: {block_count}")
        print(f"  Parents: {parent_count}")
        print(f"  Children: {child_count}")

        if block_count:
            blocks = (
                (await session.execute(
                    select(PDFBlock)
                    .where(PDFBlock.pdf_id == pdf_id)
                    .order_by(PDFBlock.page_number, PDFBlock.order_index)
                    .limit(10)
                ))
                .scalars()
                .all()
            )
            print(f"\n  First {len(blocks)} blocks:")
            for b in blocks:
                section = " > ".join(b.section_path or [])
                print(f"    page={b.page_number} type={b.block_type} chars={len(b.content_markdown or '')} section={section}")


async def step_reindex(pdf_id: uuid.UUID, parent_size: int | None, child_size: int | None, overlap: int | None) -> float:
    """Re-index PDF with optional chunk config override. Returns elapsed seconds."""
    _print_step(f"STEP: Re-index PDF (parent={parent_size or 'default'} child={child_size or 'default'} overlap={overlap or 'default'})")

    async with AsyncSessionLocal() as session:
        await session.execute(
            update(PDFDocument)
            .where(PDFDocument.id == pdf_id)
            .values(status=ProcessingStatus.PENDING)
        )
        await session.commit()

    # Override settings temporarily
    olds = (
        settings.CHUNK_PARENT_SIZE_CHARS,
        settings.CHUNK_CHILD_SIZE_CHARS,
        settings.CHUNK_CHILD_OVERLAP_CHARS,
    )
    if parent_size is not None:
        settings.CHUNK_PARENT_SIZE_CHARS = parent_size
    if child_size is not None:
        settings.CHUNK_CHILD_SIZE_CHARS = child_size
    if overlap is not None:
        settings.CHUNK_CHILD_OVERLAP_CHARS = overlap

    start = time.perf_counter()
    await PDFService.process_pdf(pdf_id)
    elapsed = round(time.perf_counter() - start, 2)

    # Restore
    settings.CHUNK_PARENT_SIZE_CHARS, settings.CHUNK_CHILD_SIZE_CHARS, settings.CHUNK_CHILD_OVERLAP_CHARS = olds
    print(f"Re-index done in {elapsed}s")
    return elapsed


async def step_eval(eval_file: str = "eval/rag_eval_sample.json", top_k: int = 10) -> dict:
    _print_step(f"STEP: RAG eval (top_k={top_k})")
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "rag_eval", str(Path(__file__).resolve().parent / "rag_eval.py")
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["rag_eval"] = mod
    spec.loader.exec_module(mod)

    import argparse
    args = argparse.Namespace(
        file=eval_file,
        top_k=top_k,
        output_dir="reports/rag_eval",
        restrict_to_expected_pdfs=False,
    )
    report = await mod.run_eval(args)
    summary = report["summary"]
    print(
        f"  hit@k={summary['hit_at_k']}  strict_hit@k={summary['strict_hit_at_k']}  "
        f"page_hit@k={summary['page_hit_at_k']}  MRR={summary['mrr']}  "
        f"latency={summary['avg_latency_ms']}ms"
    )
    return summary


# ── Main ────────────────────────────────────────────────────────
async def main():
    import_all_models()
    parser = argparse.ArgumentParser(description="RAG eval pipeline")
    parser.add_argument("--pdf-id", type=uuid.UUID, required=True, help="PDF UUID to (re-)index")
    parser.add_argument("--eval-file", default="eval/rag_eval_sample.json", help="Eval JSON path")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--skip-migration", action="store_true", help="Skip schema migration")
    parser.add_argument("--skip-inspect", action="store_true", help="Skip inspection step")
    parser.add_argument("--dry-run", action="store_true", help="Only migrate + inspect, no re-index/eval")
    parser.add_argument("--compare", action="store_true", help="Run all 3 chunk configs and compare")
    parser.add_argument("--parent-size", type=int, default=None, help="Parent chunk size (chars)")
    parser.add_argument("--child-size", type=int, default=None, help="Child chunk size (chars)")
    parser.add_argument("--overlap", type=int, default=None, help="Child overlap (chars)")
    args = parser.parse_args()

    # ── 1. Migration ──
    if not args.skip_migration:
        await step_migrate()
    else:
        print("[skip] migration")

    # ── 2. Inspect (trước khi re-index) ──
    if not args.skip_inspect:
        await step_inspect(args.pdf_id)

    if args.dry_run:
        return

    # ── 3. Re-index + Eval ──
    results = []

    if args.compare:
        _print_step("COMPARISON MODE: running 3 configs")
        for cfg in COMPARE_CONFIGS:
            print(f"\n--- Config: {cfg['label']} (parent={cfg['parent_size']}, child={cfg['child_size']}, overlap={cfg['child_overlap']}) ---")
            elapsed = await step_reindex(args.pdf_id, cfg["parent_size"], cfg["child_size"], cfg["child_overlap"])
            summary = await step_eval(args.eval_file, args.top_k)
            summary["config"] = cfg
            summary["reindex_seconds"] = elapsed
            results.append(summary)

        # Print comparison table
        print(f"\n{_bold('COMPARISON RESULTS')}")
        print(f"{'Label':>8s} | {'Parent':>6s} {'Child':>5s} {'Overlap':>7s} | "
              f"{'hit@k':>6s} {'strict':>7s} {'pdf_hit':>7s} {'page_hit':>8s} {'MRR':>6s} {'Lat(ms)':>7s}")
        print("-" * 90)
        for r in results:
            c = r["config"]
            print(f"{c['label']:>8s} | {c['parent_size']:6d} {c['child_size']:5d} {c['child_overlap']:7d} | "
                  f"{r['hit_at_k']:6.2f} {r['strict_hit_at_k']:7.2f} {r['pdf_hit_at_k']:7.2f} {r['page_hit_at_k']:8.2f} "
                  f"{r['mrr']:6.4f} {r['avg_latency_ms']:7.2f}")
    else:
        elapsed = await step_reindex(args.pdf_id, args.parent_size, args.child_size, args.overlap)
        summary = await step_eval(args.eval_file, args.top_k)
        summary["config"] = {
            "parent_size": args.parent_size or settings.CHUNK_PARENT_SIZE_CHARS,
            "child_size": args.child_size or settings.CHUNK_CHILD_SIZE_CHARS,
            "overlap": args.overlap or settings.CHUNK_CHILD_OVERLAP_CHARS,
        }
        summary["reindex_seconds"] = elapsed
        results.append(summary)

    # ── Save report ──
    output = Path("reports/rag_eval/pipeline_report.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nReport saved to {output}")


if __name__ == "__main__":
    asyncio.run(main())
