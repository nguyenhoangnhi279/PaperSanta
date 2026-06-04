# RAG Upgrade Progress

Last updated: current working session

## Completed

### Security / Runtime Fixes

- Locked RAG similarity search by `user_id`.
- Verified PDF ownership for `/api/rag/query`.
- Verified PDF ownership for multi-paper analyzer.
- Changed DB startup to fail fast when `init_db()` fails.
- Moved ORM model registration into `import_all_models()` so direct service/script imports do not trip circular imports.
- Changed PDF file access to signed URLs instead of stored public URLs.
- Added missing backend dependencies: `httpx`, `openai`.

### Embedding Provider

- Added configurable embedding provider facade:
  - `sentence-transformers` / local backend.
  - `openai` backend.
- Added config:
  - `EMBEDDING_PROVIDER`
  - `EMBEDDING_MODEL_NAME`
  - `EMBEDDING_DIMENSION`
  - `EMBEDDING_QUERY_PREFIX`
  - `EMBEDDING_DOCUMENT_PREFIX`
  - `OPENAI_API_KEY`
  - `OPENAI_EMBEDDING_DIMENSIONS`
- Split embedding calls into:
  - `embed_query`
  - `embed_documents`
- Added dimension validation so config/model/schema mismatch fails loudly.
- Smoke-tested default MiniLM provider: returns 384-dimensional vectors.

### Embedding Dimension Migration

- Added script: `scripts/migrate_embedding_dimension.py`.
- Purpose:
  - inspect current `pdf_embeddings.vector` dimension;
  - clear old chunks/embeddings;
  - alter vector dimension;
  - reset PDFs to `pending` for re-indexing.
- Dry run:
  ```powershell
  .\.venv\Scripts\python.exe scripts\migrate_embedding_dimension.py --dimension 1024
  ```
- Apply:
  ```powershell
  .\.venv\Scripts\python.exe scripts\migrate_embedding_dimension.py --dimension 1024 --apply
  ```

### Structured Extraction Foundation

- Added `pdf_blocks` ORM model.
- Added `pdf_chunks.block_id`.
- Added chunk metadata:
  - `source_block_type`
  - `section_path`
- Added extractor config:
  - `PDF_EXTRACTOR`
  - `PDF_EXTRACT_WRITE_IMAGES`
- Added extractor abstraction:
  - `PyPDFExtractor`
  - `PyMuPDF4LLMExtractor`
- Updated PDF indexing pipeline:
  - download PDF;
  - extract structured blocks;
  - store `pdf_blocks`;
  - chunk by block;
  - embed child chunks.
- Added dependency: `pymupdf4llm`.

### RAG Schema Migration

- Added script: `scripts/migrate_rag_schema.py`.
- Purpose:
  - create `pdf_blocks`;
  - add chunk block metadata columns;
  - add indexes and foreign key.
- Dry run:
  ```powershell
  .\.venv\Scripts\python.exe scripts\migrate_rag_schema.py
  ```
- Apply:
  ```powershell
  .\.venv\Scripts\python.exe scripts\migrate_rag_schema.py --apply
  ```

### Extraction Quality Comparison

- Added script: `scripts/compare_extractors.py`.
- Purpose:
  - run both `pypdf` and `pymupdf4llm` on the same PDF;
  - compare extracted pages, blocks, characters, heading/table/equation/caption-like blocks;
  - write JSON and Markdown reports.
- Use a local file:
  ```powershell
  .\.venv\Scripts\python.exe scripts\compare_extractors.py --file C:\path\to\paper.pdf
  ```
- Use an uploaded PDF:
  ```powershell
  .\.venv\Scripts\python.exe scripts\compare_extractors.py --pdf-id <pdf_uuid>
  ```
- Output folder:
  ```text
  reports/extraction_quality/
  ```
- Added `--preview-chars` to avoid misleading short previews:
  ```powershell
  .\.venv\Scripts\python.exe scripts\compare_extractors.py --file C:\path\to\paper.pdf --preview-chars 4000
  ```

### Single-Page Extraction Inspection

- Added script: `scripts/inspect_extractor_page.py`.
- Purpose:
  - dump full extracted content for a specific page;
  - compare `pypdf` and `pymupdf4llm` without preview truncation.
- Example:
  ```powershell
  .\.venv\Scripts\python.exe scripts\inspect_extractor_page.py --file C:\path\to\paper.pdf --page 2 --output reports\extraction_quality\page2_dump.md
  ```

### RAG Retrieval Evaluation

- Added script: `scripts/rag_eval.py`.
- Added benchmark template: `eval/rag_eval_sample.json`.
- Current evaluation scope:
  - retrieval hit@k;
  - expected PDF hit@k;
  - expected page hit@k;
  - MRR;
  - optional expected text/section substring checks;
  - latency per question.
- Fixed metric semantics after reading generated reports:
  - `hit_at_k` now means evidence hit: expected PDF + expected page when provided + expected text match;
  - `strict_hit_at_k` additionally requires section match;
  - `page_hit_at_k` only counts page matches inside the expected PDF, so another paper's same page number no longer inflates the score.
- Updated the eval set questions to include the target paper title, because generic questions like "main contributions of the paper" are ambiguous when multiple PDFs are indexed.
- Latest retrieval eval after embedding filter + corrected multi-page expectations:
  ```text
  hit_at_k: 1.0
  strict_hit_at_k: 1.0
  pdf_hit_at_k: 1.0
  page_hit_at_k: 1.0
  mrr: 0.7083
  strict_mrr: 0.6917
  ```
- Interpretation:
  - retrieval evidence is now found for all 10 cases;
  - strict section matching now passes for all 10 cases on the current benchmark;
  - ranking is still not perfect, so hybrid search/reranking remain useful next steps.

### Hybrid Retrieval

- Added configurable retrieval mode:
  - `RAG_RETRIEVAL_MODE=dense`
  - `RAG_RETRIEVAL_MODE=hybrid`
- Default is now `hybrid`.
- Hybrid retrieval combines:
  - dense pgvector search;
  - PostgreSQL full-text search over `pdf_chunks.chunk_text`;
  - reciprocal-rank fusion.
- Added config:
  - `RAG_DENSE_CANDIDATES`
  - `RAG_TEXT_CANDIDATES`
  - `RAG_RRF_K`
  - `RAG_DENSE_WEIGHT`
  - `RAG_TEXT_WEIGHT`
- Default weights:
  - dense: `1.0`
  - text: `0.02`
- Text search is intentionally a weak secondary signal because broad OR keyword matches pulled weaker chunks above stronger dense evidence in the first eval runs.
- Current eval comparison:
  ```text
  dense:  hit_at_k=1.0 strict_hit_at_k=1.0 mrr=0.7083 strict_mrr=0.6917
  hybrid: hit_at_k=1.0 strict_hit_at_k=1.0 mrr=0.7583 strict_mrr=0.7417
  ```

### Lightweight Reranking

- Added optional heuristic reranker:
  - `RAG_RERANK_MODE=none`
  - `RAG_RERANK_MODE=heuristic`
- The heuristic reranker uses:
  - original retrieval rank;
  - query term coverage in context;
  - adjacent query phrase coverage;
  - query term coverage in section path;
  - small bonus when a chunk appears in both dense and text retrieval.
- `scripts/rag_eval.py` now supports:
  ```powershell
  .\.venv\Scripts\python.exe scripts\rag_eval.py --file eval\rag_eval_sample.json --retrieval-mode hybrid --text-weight 0.02 --rerank-mode heuristic
  ```
- Current result:
  - heuristic reranker did not improve the 10-case benchmark over tuned hybrid retrieval;
  - default stays `RAG_RERANK_MODE=none`;
  - keep this hook for later cross-encoder or LLM-based reranking.
- Added migration index:
  ```sql
  CREATE INDEX IF NOT EXISTS ix_pdf_chunks_chunk_text_fts
  ON pdf_chunks
  USING GIN (to_tsvector('english', coalesce(chunk_text, '')))
  ```
- This targets exact keyword/acronym/theorem/metric queries that dense-only retrieval can miss.
- Output folder:
  ```text
  reports/rag_eval/
  ```
- Example:
  ```powershell
  .\.venv\Scripts\python.exe scripts\rag_eval.py --file eval\rag_eval_sample.json --top-k 10
  ```
- For chunking-only experiments, restrict search to expected PDFs:
  ```powershell
  .\.venv\Scripts\python.exe scripts\rag_eval.py --file eval\rag_eval_sample.json --top-k 10 --restrict-to-expected-pdfs
  ```
- This lets us compare old vs new chunking, extractor changes, and embedding models with a repeatable number instead of eyeballing chat answers.

### Extraction Cleaning / Splitting

- Added basic cleanup in `extraction_service.py`:
  - soft hyphen removal;
  - hyphenated line break repair;
  - selected line-wrap spacing fixes, such as `con secutive`, `au tomata`, `peb bles`;
  - `A PIA is` normalization.
- Added `split_markdown_page(...)` for `pymupdf4llm` output.
- The splitter now breaks page-level markdown into smaller blocks:
  - heading block;
  - paragraph/body blocks;
  - long paragraph chunks;
  - table-like sections when detected.
- This reduces the earlier issue where `pymupdf4llm` still produced roughly one block per page.

### Extracted Text Normalization

- Added service: `app/services/text_normalization_service.py`.
- Purpose:
  - keep extraction extensible, but avoid expanding table/equation/figure logic too early;
  - focus now on making extracted plain text cleaner for chunking and RAG.
- Current normalization:
  - Unicode NFKC normalization;
  - common mojibake repair for bullets, math symbols, Greek letters, ligatures;
  - soft hyphen removal;
  - hyphenated line break repair;
  - line-wrap spacing fixes;
  - reference number spacing fixes, e.g. `[4, 3, 10, 2 4]`;
  - list marker normalization;
  - simple math notation spacing fixes.
- Added CLI: `scripts/normalize_extracted_text.py`.
- Example:
  ```powershell
  .\.venv\Scripts\python.exe scripts\normalize_extracted_text.py --input raw.txt --output cleaned.txt
  ```

Current direction:

- Extraction schema stays as a foundation/placeholder for future table/equation/figure work.
- Immediate work focuses on cleaned extracted text and better text blocks for chunking.

### Section-Aware Chunking

- Current chunking still keeps the parent/child model.
- Updated default chunk sizes:
  - parent: `2800` characters;
  - child: `450` characters;
  - child overlap: `120` characters.
- Child chunks now overlap, so adjacent child embeddings keep more semantic continuity.
- Added heading/section context into chunk text:
  - parent chunks are prefixed with `[Section: ...]`;
  - child chunks are also prefixed with `[Section: ...]`;
  - `section_path` is stored on `pdf_chunks`.
- This means embeddings now include heading context, so a child chunk from a section like `2 Pebble-Intervals Automata` is semantically tied to that section.
- `pymupdf4llm` extraction now carries the current heading across later blocks/pages until a new heading appears.
- Heading context is now stored as a full path where extraction can infer it, for example:
  ```text
  [Section: 2 Related Work > 2.1 Multi-Person Pose Estimation]
  ```
- Table/equation chunks now have a bypass rule:
  - do not split the full table/equation block into parent chunks by character count;
  - store the full table/equation as one parent chunk;
  - for Markdown tables, create child chunks by row groups while repeating the table header;
  - for equations, keep the equation block intact as the child context.
- Added embedding candidate filtering:
  - heading-only child chunks are stored but not embedded;
  - very short non-table/non-equation child chunks are stored but not embedded;
  - default minimum is `EMBED_MIN_CHUNK_WORDS=20`;
  - table/equation children bypass this filter so compact structured evidence can still be searched.
- Reason:
  - title/author/heading chunks were ranking above actual evidence when the question included the paper title;
  - filtering them should improve MRR without losing DB traceability.
- Added script: `scripts/preview_chunking.py`.
- Example:
  ```powershell
  .\.venv\Scripts\python.exe scripts\preview_chunking.py --file C:\path\to\paper.pdf --page 2 --extractor pymupdf4llm
  ```
- Added script: `scripts/inspect_indexed_pdf.py`.
- Purpose:
  - inspect actual stored `pdf_blocks`;
  - inspect actual stored `pdf_chunks`;
  - verify page, block type, section path, parent/child chunk content.
- Example:
  ```powershell
  .\.venv\Scripts\python.exe scripts\inspect_indexed_pdf.py --pdf-id <pdf_uuid> --page 2 --limit 30 --chars 1200
  ```

Current behavior:

```text
PDF page/block
 -> section_path from heading
 -> parent chunks with section prefix
 -> child chunks with section prefix
 -> embeddings from child chunks
 -> LLM context from parent chunks
```

Still not done:

- multi-level section hierarchy is simple for now;
- heading detection is Markdown-based;
- chunk sizes are still character-based;
- token-aware chunking is still pending.

### Explain Selection Backend

- Added API schema:
  - `ExplainSelectionRequest`
  - `ExplainSelectionResponse`
- Added endpoint:
  ```http
  POST /api/rag/explain-selection
  ```
- Endpoint behavior:
  - verifies PDF belongs to current user;
  - searches only inside that PDF;
  - optionally prioritizes same-page chunks;
  - explains selected text using paper context;
  - returns answer and citations.
- Added frontend API client function:
  - `explainSelection(...)`

### Documentation

- Added `RAG_IMPROVEMENT_NOTES.md`.
- Covered:
  - extraction weaknesses;
  - embedding model options;
  - database schema direction;
  - interactive PDF requirements;
  - citation link behavior;
  - highlight-to-explain behavior;
  - full RAG improvement roadmap.

## Verified

- Backend compile:
  ```powershell
  .\.venv\Scripts\python.exe -m compileall app scripts main.py
  ```
  Result: pass.

- SQLAlchemy metadata includes:
  - `pdf_blocks`
  - `pdf_chunks`
  - `pdf_embeddings`
  - `pdf_documents`
  - chat and analysis tables

- Frontend build:
  ```powershell
  npm.cmd run build
  ```
  Result: pass.

Known warning:

- Frontend bundle is still large, around 1 MB minified JS.
- This is a performance warning, not a build failure.

## Not Done Yet

### Database Apply

The migration scripts were created but not applied to the real database.

Next command:

```powershell
.\.venv\Scripts\python.exe scripts\migrate_rag_schema.py --apply
```

If changing embedding dimension:

```powershell
.\.venv\Scripts\python.exe scripts\migrate_embedding_dimension.py --dimension 1024 --apply
```

### Re-indexing

After schema migration or embedding model change, PDFs must be re-indexed.

Options:

- Use app endpoint:
  ```http
  POST /api/pdf/{id}/index
  ```
- Or add a new bulk re-index script later.

### Frontend Interactive PDF

Current viewer has been changed from an iframe to a PDF.js text-layer viewer.

Implemented in the new code:

- PDF rendering via `pdfjs-dist`.
- Text layer support for selecting text.
- Selection menu with `Explain` and `Cancel`.
- Zoom in/out/reset controls.
- Page-level citation jump via `targetPage`.

Issues to fix:

- Frontend build currently fails until `pdfjs-dist` is installed in `node_modules`.
- `Reader` still sends selected text through normal `ragChat(...)` instead of the dedicated `/api/rag/explain-selection` endpoint.
- Selection explain does not pass `page_number` or `surrounding_text`, so context can be weaker than intended.
- PDF.js viewer renders all pages at once; long PDFs may need page virtualization/lazy rendering.
- Exact citation highlight is still not implemented; current citation action only jumps to page.

Needed next:

- Run `npm install` in `frontend` after pulling the new dependency.
- Wire selection toolbar to `explainSelection(...)`.
- Capture current selected page and nearby text for `ExplainSelectionRequest`.
- Add `highlightText` or fuzzy text highlight for citations.
- Later add bbox-based precise highlight when extraction provides bbox/ranges.

### Precise Citation Highlight

Current citations can provide:

- `chunk_id`
- `chunk_text`
- `pdf_id`
- `pdf_name`
- `page_number`

Still needed for exact source highlighting:

- stable `block_id` in citation response;
- bbox or text range from extraction;
- frontend text/bbox highlight support.

### Extraction Quality

Extractor abstraction exists, but quality pipeline is still early.

Still needed:

- better table detection;
- equation handling;
- figure/caption handling;
- broader header/footer removal;
- broader hyphenation/line-wrap cleanup;
- section hierarchy tracking;
- extraction quality stats surfaced in API/UI.

### Retrieval Quality

Still needed:

- token-aware chunking;
- hybrid dense + full-text search;
- reranking;
- query rewrite for follow-up chat;
- chat intent router before retrieval;
- stricter anti-hallucination RAG prompt;
- answer-quality evaluation beyond retrieval metrics.

### Embedding Startup Preload

Implemented:

- Added startup embedding preload/warm-up in FastAPI lifespan.
- Added config flags:
  - `EMBEDDING_PRELOAD_ON_STARTUP=true`
  - `EMBEDDING_PRELOAD_FAIL_FAST=false`
  - `EMBEDDING_WARMUP_TEXT="PaperSanta embedding warmup"`
- Added `EmbeddingProvider.warmup()` to load the backend and run one small query embedding.
- `/health` now includes embedding warm-up status from app state.

Operational notes:

- With local sentence-transformers, the first startup may still take time because the model is loaded into RAM during server boot.
- With `uvicorn --reload`, every reload starts a new process, so the model will be loaded again.
- Set `EMBEDDING_PRELOAD_FAIL_FAST=true` for demos if the server must refuse to start when embedding preload fails.
- Set `EMBEDDING_PRELOAD_ON_STARTUP=false` if using a cloud embedding provider and startup API calls are undesirable.

### Planned: Chat Intent Router

Decision: add a lightweight layer before query rewrite/retrieval, but not implemented yet.

Purpose:

- avoid retrieval for `hello`, `thanks`, `ok`, and app-help messages;
- reduce irrelevant citations;
- prepare routing for comparison, aggregation, negation, and conditional questions.

Initial approach:

- rule-based first;
- direct response for `social` and `app_help`;
- RAG only for `paper_question`;
- log `intent`, `reasoning_type`, and `needs_retrieval` when implemented.

### Chat Prompt Framing Fix

Observed while testing OpenPose:

- User asked for the paper's task input/output.
- Retrieved context contained the correct pipeline:
  - input image;
  - confidence maps and PAFs;
  - bipartite matching / parsing;
  - final full body poses.
- The model incorrectly described heatmaps/confidence maps and PAFs as the task output.

Applied fix:

- Updated the RAG system prompt to separate final task input/output from intermediate model predictions.
- Updated chat prompt context labels to include page information.
- Updated chat prompt instructions to require `[Paper X, page Y]` citations when possible.
- Added an explicit rule: heatmaps/confidence maps/vector fields can be intermediate predictions, while assembled poses/keypoints/skeletons are the final task output when supported by the source.

Current caveat:

- After the latest code update, some earlier prompt/bundle fixes may not be present in the current HEAD.
- Re-check and re-apply:
  - RAG system prompt that avoids `[Chunk X]` citation instructions;
  - chat prompt rule for task input/output vs intermediate model predictions;
  - `[Paper X, page Y]` citation instruction;
  - frontend `manualChunks` and lazy-loaded views to avoid large bundle warnings.

### Search Fallback Update

New code adds Tavily + Gemini fallback for paper search when Semantic Scholar returns zero results.

Potential benefits:

- Search can return results when Semantic Scholar has no match or is too sparse.

Issues to fix:

- Fallback results use URL as `s2_id`, so `/api/search/papers/{s2_id}` may not work for fallback papers.
- Fallback results are not guaranteed to be scholarly metadata from Semantic Scholar.
- Related-search UI sends filters (`limit`, year range, citations, open access), but the backend `/api/search/related/{pdf_id}` currently does not accept those query params.
- Add a source/provider field if fallback results are shown in UI, so users know whether data came from Semantic Scholar or Tavily.

## Suggested Next Steps

1. Apply `migrate_rag_schema.py --apply` on the DB.
2. Re-index one test PDF with default `pypdf` extractor to verify backward compatibility.
3. Install/use `pymupdf4llm`, set `PDF_EXTRACTOR=pymupdf4llm`, and re-index one PDF.
4. Compare `pdf_blocks` output quality between `pypdf` and `pymupdf4llm`.
5. Use `scripts/compare_extractors.py` to generate a report for the same PDF.
6. Build bulk re-index script.
7. Replace iframe PDF viewer with PDF.js/react-pdf.
8. Add selection toolbar and call `/api/rag/explain-selection`.
9. Add citation highlight by page + fuzzy text first.
10. Later add bbox-based precise highlight.

## Important Cautions

- Do not mix embeddings from different models.
- Do not change `EMBEDDING_DIMENSION` without migrating DB and re-indexing.
- Running embedding dimension migration deletes chunks/embeddings and resets PDFs to pending.
- Running RAG schema migration is additive and should preserve PDF metadata.
- `PDF_EXTRACTOR=pymupdf4llm` may require installing/downloading new dependencies.
- Exact PDF highlighting is not reliable while the viewer remains an iframe.
