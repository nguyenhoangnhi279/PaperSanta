# Analyzer Improvements

Last updated: current working session

## Current Goal

Improve the Analyzer without turning Reader chat into multi-PDF chat.

Product decision:

- Reader stays single-PDF and interactive with the rendered PDF.
- Analyzer stays the multi-PDF structured-analysis surface.
- Analyzer presets remain acceptable for now, but retrieval and evidence grounding must be stronger.

## Problems Found

### 1. Analyzer retrieval was too narrow

Each analysis type used one hard-coded query. This is weak for multi-paper analysis because a benchmark comparison needs different evidence angles:

- architecture/method;
- metrics/results;
- speed/latency/resource;
- dataset/evaluation setup.

### 2. Prompt did not force enough grounding

The previous prompt asked for JSON, but it did not strongly require:

- evidence IDs per claim;
- null instead of guessing missing fields;
- separating claims by paper;
- valid JSON without markdown fences.

### 3. Results had no visible evidence trace

The database saved only `result_json`. The UI showed the generated table/themes/gaps, but the user could not see which chunks supported the analysis.

### 4. Frontend bundle warning came back

The new PDF.js viewer pulled heavy PDF.js code into the initial app bundle because `Reader`, `Analyzer`, `Comparison`, and `Discovery` were imported eagerly.

## Changes Implemented

### Backend Analyzer

File: `app/services/analyze_service.py`

- Added per-analysis retrieval query sets.
- Analyzer now retrieves from multiple targeted queries instead of one generic query.
- Added simple reciprocal-rank style fusion across query results.
- Added evidence IDs like `P1-E1`, `P2-E3`.
- Prompt now requires:
  - JSON-only output;
  - no unsupported guessing;
  - `null` for unavailable fields;
  - `Evidence` arrays for important claims.
- Saved extra trace metadata into `result_json`:
  - `_evidence_sources`
  - `_evidence_map`
  - `_retrieval_queries`

No database schema change was needed because `MultiAnalysis.result_json` is JSONB.

### Frontend Analyzer

File: `frontend/src/components/Analyzer.tsx`

- Added an `Evidence Used` section under analyzer results.
- Shows the first evidence excerpts used by backend:
  - evidence ID;
  - PDF name;
  - page number;
  - section path;
  - preview text.

### Frontend Bundle Split

Files:

- `frontend/src/App.tsx`
- `frontend/vite.config.ts`

Changes:

- Lazy-load heavy screens:
  - Reader
  - Analyzer
  - Comparison
  - Discovery
- Added Vite `manualChunks` for:
  - `pdfjs`
  - `katex`
  - `react`
  - `motion`
  - `icons`

Build result:

- Before split: `index` JS was about `1,536 kB` minified and triggered the 500 kB warning.
- After split: initial `index` JS is about `259 kB` minified.
- `pdfjs` is now a separate lazy chunk at about `471 kB`.
- Vite large chunk warning is gone.

### Startup Embedding Warmup

Files:

- `app/core/config.py`
- `app/core/embedding_provider.py`
- `main.py`

Changes:

- Added optional embedding warmup during FastAPI startup.
- `/health` now includes embedding warmup state.
- This shifts the first slow model load from the first user request to server startup.

## Tests Run

### Backend

```powershell
.\.venv\Scripts\python.exe -c "import main; from app.services import analyze_service as s; print('main import ok'); print(len(s.ANALYSIS_RETRIEVAL_QUERIES)); print(len(s.ANALYSIS_SCHEMA_INSTRUCTIONS))"
```

Result:

```text
main import ok
10
10
```

```powershell
.\.venv\Scripts\python.exe -m compileall app main.py
```

Result:

```text
No syntax errors.
```

### Frontend

First build failed because `pdfjs-dist` was declared in `package.json` but not installed locally.

Fixed with:

```powershell
npm.cmd install
```

Then:

```powershell
npm.cmd run build
```

Result:

```text
Build passed.
Large chunk warning removed.
```

## What To Test Manually Next

1. Start backend and frontend.
2. Open Analyzer.
3. Select at least 2 indexed PDFs.
4. Run `Benchmark Matrix`.
5. Check:
   - result is valid table JSON rendered in UI;
   - unsupported values appear as empty/null instead of hallucinated;
   - `Evidence Used` appears under the result;
   - evidence previews point to relevant pages/sections.
6. Run one synthesis mode, such as `Methodology Mapping`.
7. Run one gap mode, such as `Performance Gap`.

## Remaining Risks

- Analyzer still depends on retrieval quality; if important evidence is not retrieved, the LLM cannot analyze it.
- There is no analyzer-specific eval set yet.
- Evidence IDs are visible, but they are not clickable into the PDF viewer yet.
- Prompt can still fail if the LLM returns malformed JSON, though parse fallback now preserves raw output.
- Current multi-query retrieval is heuristic. Later, use a reranker or analyzer-specific eval to tune it.

## Next Recommended Upgrade

Add an analyzer evaluation set:

- 5-10 multi-PDF benchmark questions;
- expected papers/pages/fields;
- checks for:
  - evidence retrieval coverage;
  - JSON parse success;
  - missing-value discipline;
  - citation/evidence correctness.

## External Evaluation Seed

Added script:

```powershell
.\.venv\Scripts\python.exe scripts\build_analyzer_eval_set.py --sources qasper qmsum arxiv_qa --overwrite
```

Purpose:

- download public scientific QA/summarization samples;
- keep raw rows for schema debugging;
- normalize them into local Analyzer seed cases.

Generated files:

- `eval/analyzer_external/qasper_test_raw.jsonl`
- `eval/analyzer_external/qasper_test_cases.json`
- `eval/analyzer_external/qmsum_test_raw.jsonl`
- `eval/analyzer_external/qmsum_test_cases.json`
- `eval/analyzer_external/arxiv_qa_validation_raw.jsonl`
- `eval/analyzer_external/arxiv_qa_validation_cases.json`
- `eval/analyzer_eval_seed.json`

Current seed size after cached rebuild:

```text
QASPER: 99 cases
QMSum: 30 cases
ArXiv-QA: 20 cases
Total: 149 cases
```

Dataset role:

- QASPER is the strongest fit for PaperSanta because it has paper QA plus paragraph-level evidence.
- QMSum is useful for synthesis-style behavior, but it is meeting summarization rather than scientific PDF QA.
- ArXiv-QA is useful for math/CS-style QA, but the selected HuggingFace mirror is text-context QA and not page-local PDF evidence.

Important limitation:

- These are seed cases, not strict local PDF eval cases yet.
- `expected_pdf_ids` and `expected_pages` are intentionally empty until the corresponding papers are indexed in the local PaperSanta database.
- For strict Analyzer scoring, map each source paper to a local `pdf_documents.id` and add expected page/evidence fields.

Next script to add:

- `scripts/analyzer_eval.py`
- It should run Analyzer retrieval on mapped cases and report:
  - evidence hit@k;
  - source coverage per paper;
  - JSON parse success;
  - hallucinated field rate;
- evidence ID validity.

## Evidence Interaction Update

Implemented:

- Analyzer `Evidence Used` cards are now clickable when the evidence PDF exists in the current library.
- Clicking an evidence card opens Reader for that PDF and jumps to the cited page.
- Reader citation chips now use human-readable labels:
  - PDF name;
  - page number;
  - section name when available.
- Backend chat prompt no longer asks the model to cite `[Paper 1]`.
- Chat prompt now asks for citations like:
  - `[paper-name.pdf, page 2]`
  - `[Source 1, page 2]` when the paper name is too long.
- Backend explicitly forbids vague labels like `[Paper 1]` and `[Paper 2]`.

## Direction Change: From Hard-Path Presets To Custom Analyzer

Current issue:

- Analyzer is still hard-path by preset use case.
- Presets decide retrieval queries, prompt shape, and JSON schema ahead of time.
- This is acceptable for a guided demo, but weak for a flexible research analyzer.
- `custom_prompt` currently behaves mostly like a final prompt focus; it does not fully affect retrieval planning, output schema, or evidence grouping.

Decision:

- Keep preset Analyzer modes for stability.
- Add a custom/planner layer so user instructions can drive:
  - retrieval subqueries;
  - section/table/result boosts;
  - evidence grouping;
  - output format;
  - missing-evidence policy.

Target flow:

```text
user analyzer request
 -> AnalyzerPlan
 -> multi-query retrieval
 -> analyzer-specific rerank/group evidence
 -> JSON/table/structured answer generation
 -> evidence validation
 -> saved report
```

Planned `AnalyzerPlan` shape:

```json
{
  "analysis_goal": "string",
  "analysis_type": "preset | custom",
  "subqueries": ["string"],
  "sections_to_boost": ["Methods", "Experiments", "Results"],
  "block_types_to_boost": ["table", "text", "equation"],
  "per_pdf_min_evidence": 2,
  "output_format": "table | themes | gaps | freeform_json",
  "required_fields": ["string"],
  "evidence_policy": "every non-null claim needs evidence"
}
```

## User-Fed PDF Evaluation Plan

Upcoming workflow:

1. User will provide 3 PDFs that cover the required Analyzer features.
2. User will also provide expected answers or expected evidence behavior.
3. PaperSanta will index or re-index those PDFs if needed.
4. Build a local analyzer eval file from the user-provided expectations.
5. Run `scripts/analyzer_eval.py` or a stricter custom eval script against those PDFs.
6. Save reports under:

```text
reports/analyzer_eval/
```

7. Improve Analyzer retrieval/planning/prompt/evidence UX.
8. Run the same eval again and compare before/after.

Expected user-provided test coverage:

- benchmark metrics/table extraction;
- methodology/architecture mapping;
- resource or latency comparison;
- performance gap or limitation extraction;
- cross-paper synthesis;
- evidence citation and page jump/highlight behavior;
- custom prompt behavior, not only preset behavior.

Acceptance target:

- Analyzer should not merely produce plausible output.
- It must retrieve expected evidence, cite it, and show missing evidence honestly when the PDFs do not support a field.

Important note:

- Fuzzy citation highlight can be built from existing `chunk_text` and `page_number`.
- Precise bbox/text-range highlight requires extractor/schema support and then re-indexing.

## Built: Practical PDF Interaction Features

Implemented now:

- Reader selection explain uses the dedicated backend endpoint:
  - `POST /api/rag/explain-selection`
  - passes selected text;
  - passes detected PDF page number;
  - passes surrounding page text when available.
- Selection explain no longer routes through normal chat prompt.
- Citation click now sends both target page and target text to the PDF viewer.
- Analyzer evidence click now sends page and evidence preview to Reader.
- PDF.js viewer performs fuzzy text-layer highlighting:
  - no bbox required;
  - no re-index required if `chunk_text` and `page_number` exist;
  - highlights matching text spans on the cited page.

Verified:

```powershell
npm.cmd run build
.\.venv\Scripts\python.exe -m compileall app main.py scripts\analyzer_eval.py scripts\build_analyzer_eval_set.py
```

Result: pass.

Deferred by decision:

- equation extraction;
- precise bbox/text-range highlighting;
- robust table/cell extraction;
- figure/caption extraction.
