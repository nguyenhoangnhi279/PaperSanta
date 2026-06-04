# PaperSanta RAG Improvement Notes

## Current System

- Backend extracts text from PDFs with `pypdf`.
- Text is chunked into parent/child chunks.
- Child chunks are embedded and searched with pgvector cosine distance.
- Parent chunks are used as LLM context.
- Answers are generated with DeepSeek and saved in chat sessions with citations.

## Current Embedding Model

The current local embedding model is `all-MiniLM-L6-v2`, with 384-dimensional vectors.

This is lightweight and cheap to run locally, but it limits retrieval quality for academic papers:

- Lower semantic capacity than newer cloud embedding models.
- Weaker multilingual behavior, especially for Vietnamese queries over English papers.
- More likely to miss nuanced method, metric, dataset, and limitation queries.
- Still needs good chunking, hybrid retrieval, and reranking; higher dimensions alone do not fix retrieval quality.

## OpenAI Embedding Migration Option

OpenAI's current small embedding model is `text-embedding-3-small`.

Relevant docs:

- https://developers.openai.com/api/docs/guides/embeddings
- https://developers.openai.com/api/docs/models/text-embedding-3-small

Important properties:

- Default output dimension: 1536.
- Max input: 8192 tokens.
- Supports a `dimensions` parameter to reduce vector size.
- Stronger semantic retrieval than `all-MiniLM-L6-v2` is expected, especially for academic and multilingual queries.

### Impact On This Repo

The current `PDFEmbedding.vector` column is `Vector(384)`.

Migrating to `text-embedding-3-small` with default dimensions requires:

- Change vector column dimension from `384` to `1536`.
- Recreate or migrate existing embeddings.
- Re-index all uploaded PDFs.
- Update `EmbeddingProvider` to call OpenAI instead of `sentence-transformers`.
- Store model name and dimension per embedding batch.
- Add `OPENAI_API_KEY` and embedding model config.

Alternative:

- Use `text-embedding-3-small` with `dimensions=384`.
- This avoids changing the database vector dimension.
- It is easier to migrate but may leave some quality on the table.
- Still requires re-indexing because vectors from different models are not comparable.

## Weak Points In Current RAG

### 1. Dense-Only Retrieval

Current retrieval uses only embedding similarity.

Risk:

- Exact keywords like model names, datasets, metrics, and acronyms can be missed.
- Dense retrieval is often weaker for table-like facts and numerical claims.

Improvement:

- Add hybrid retrieval: pgvector semantic search plus PostgreSQL full-text search.
- Merge scores with a weighted formula or reciprocal rank fusion.

Implemented:

- `RAG_RETRIEVAL_MODE=hybrid` combines dense retrieval and PostgreSQL full-text retrieval.
- Candidate lists are fused with reciprocal-rank fusion.
- Full-text index is added by `scripts/migrate_rag_schema.py`.
- Default text weight is low (`0.02`) so full-text acts as a weak keyword boost instead of overpowering dense semantic ranking.

### 2. Chunking Is Character-Based

Previous defaults:

- Parent chunk: about 800 characters.
- Child chunk: about 150 characters.
- Child overlap: none.

Current improved defaults:

- Parent chunk: 2800 characters.
- Child chunk: 450 characters.
- Child overlap: 120 characters.
- Heading context is prefixed as a full section path where available.
- Table/equation blocks bypass parent splitting so their structure is not broken by the generic character splitter.
- Heading-only and very short child chunks are no longer embedded, although they remain stored in `pdf_chunks`.

Risk:

- Character counts are less stable than token counts.
- Very long logical sections can still be cut by character count instead of true tokens.
- Table/equation quality still depends on whether the extractor correctly emits those block types.

Improvement:

- Switch to token-aware chunking.
- Target child chunks around 250-400 tokens.
- Target parent chunks around 900-1500 tokens.
- Use token overlap instead of character overlap.

### 3. No Reranking

Current default flow sends tuned hybrid retrieval results to the LLM.

Risk:

- The highest embedding matches are not always the best evidence.
- Multi-paper comparison and methodology questions need better ordering.

Implemented hook:

- Optional `RAG_RERANK_MODE=heuristic`.
- Current default remains `RAG_RERANK_MODE=none` because the heuristic did not improve the current 10-case eval set.

Future improvement:

- Retrieve 30-50 candidates.
- Rerank down to 6-10 final chunks.
- Options: cross-encoder reranker, LLM-based reranker, or a lightweight local reranker.

### 4. Prompt Allows Unsupported Knowledge

The current RAG system prompt allows the model to use internal knowledge when chunks are incomplete.

Risk:

- Answers can mix PDF evidence with external knowledge.
- Citations become less trustworthy.

Improvement:

- Require claims from retrieved context when answering about uploaded PDFs.
- If outside knowledge is used, put it in a separate section.
- If evidence is missing, say what is missing.

### 4.1. Prompt Does Not Always Frame Technical Roles Correctly

Observed case: in the OpenPose paper, the retrieved context contained the correct pipeline:

```text
Input image
 -> confidence maps + Part Affinity Fields
 -> bipartite matching / parsing
 -> full body poses for all people
```

The answer still labeled confidence maps and PAFs as the task output. This is not exactly a retrieval miss. The context was relevant, but the model failed to distinguish:

- task/problem input;
- final task output;
- intermediate network/model predictions.

Risk:

- Correctly retrieved chunks can still produce conceptually wrong answers.
- The model may latch onto nearby words like "predict" or "output" and answer at the wrong abstraction level.
- In ML papers, "model output", "intermediate representation", and "task output" are often different things.

Improvement:

- Add prompt rules for task input/output questions.
- Require answers to separate final task output from intermediate model predictions.
- Add eval cases that ask "what is the input/output?" for known papers with pipeline figures.

### 5. No Query Rewriting For Follow-Up Questions

Chat history is saved, but retrieval embeds only the latest user message.

Risk:

- Follow-up questions like "method đó khác gì?" lose context.
- Retrieval can return unrelated chunks.

Improvement:

- Add a query contextualization step.
- Convert follow-up messages into standalone search queries before embedding.

### 5.1. No Chat Intent Router Before Retrieval

Currently, every chat message is treated as a RAG question. This means inputs like `hello`, `thanks`, `ok`, or app-help questions can still trigger embedding and retrieval.

Risk:

- Wastes latency and tokens.
- Retrieves unrelated paper chunks for social/control messages.
- Can produce irrelevant citations for messages that do not need evidence.
- Pollutes logs and future evaluation data.

Improvement:

- Add a lightweight intent router before query rewrite and retrieval.
- Start with rule-based classification, not an LLM classifier.
- Only run retrieval when the intent needs paper evidence.

Initial intent classes:

- `social`: hello, hi, chào, cảm ơn, thanks, ok.
- `app_help`: dùng sao, hỏi được gì, app này làm gì.
- `paper_question`: normal PDF content questions.
- `summarize`: summarize/tóm tắt requests.

Initial reasoning types for paper questions:

- `definition`
- `simple_factual`
- `comparison`
- `aggregation`
- `negation`
- `conditional`
- `general`

Desired flow:

```text
user message
 -> intent router
 -> social/app_help/control: direct response, no retrieval
 -> paper_question: query rewrite, retrieval, RAG answer
```

Future improvement:

- Log `intent`, `reasoning_type`, and `needs_retrieval`.
- Add eval cases for social, app-help, comparison, aggregation, negation, and conditional questions.
- Consider an LLM classifier later only if rule-based routing is too brittle.

### 6. No RAG Evaluation Set

There was no local benchmark for retrieval or answer quality.

Risk:

- Changes to embedding model, chunking, or prompts cannot be measured reliably.

Implemented first step:

- `scripts/rag_eval.py`
- `eval/rag_eval_sample.json`
- Measures retrieval hit@k, expected PDF hit@k, expected page hit@k, MRR, substring/section matches, and latency.
- Writes JSON and Markdown reports to `reports/rag_eval/`.
- Metric semantics:
  - `hit_at_k` is the main retrieval metric: expected PDF + expected page when provided + expected text match.
  - `strict_hit_at_k` adds expected section match, useful for checking heading extraction quality.
  - `page_hit_at_k` only counts when the result is also from the expected PDF.

Still needed:

- Create 20-50 test questions across known PDFs.
- Track expected PDF/page/chunk.
- Add answer usefulness evaluation, likely with rubric-based manual scoring first and optional LLM-as-judge later.

### 7. Extraction Phase Is Too Basic

Current extraction uses `pypdf` page text extraction.

Risk:

- Tables are lost or flattened incorrectly.
- Equations are often dropped, split, or converted into unreadable text.
- Figures are not captured.
- Captions are not linked to figures/tables.
- Multi-column layout can be read in the wrong order.
- Section hierarchy is not preserved.
- Header/footer/page-number noise leaks into chunks.
- Broken line breaks and hyphenation reduce embedding quality.

This is a foundation problem. Better embeddings and reranking cannot recover information that was never extracted or was extracted in the wrong order.

Improvement:

- Replace plain text extraction with structured document extraction.
- Store extracted blocks with type, page, order, section, content, and metadata.
- Chunk based on block type instead of raw page text.

## Recommended Priority

1. Improve extraction into structured blocks.
2. Add block-aware cleaning and chunking.
3. Tighten the RAG prompt to reduce unsupported claims.
4. Add query rewriting for follow-up chat.
5. Improve chunking with token-aware chunks and overlap.
6. Migrate or experiment with stronger embeddings.
7. Add hybrid search.
8. Add reranking.
9. Build a small RAG eval set.

## Extraction Phase Redesign

Extraction should become a first-class pipeline stage:

```text
PDF
 -> parser
 -> structured blocks
 -> cleaner / normalizer
 -> block-aware chunker
 -> embeddings
 -> retrieval
```

Recommended block schema:

```json
{
  "type": "text | heading | table | equation | figure | caption",
  "page_number": 3,
  "order_index": 42,
  "section_path": ["Method", "Architecture"],
  "content_markdown": "...",
  "content_json": {},
  "bbox": [x0, y0, x1, y1],
  "confidence": 0.92,
  "extractor": "pymupdf4llm"
}
```

### Recommended Extractors

#### Phase 1: PyMuPDF4LLM

Use this as the first replacement for `pypdf`.

Why:

- Local and relatively easy to integrate.
- Outputs Markdown suitable for downstream LLM/RAG.
- Better handling for multi-column documents and layout.
- Can expose page chunks and image/table-related options.
- Lower operational complexity than heavier layout models.

Use it to produce:

- page-level Markdown;
- page/block order;
- table-like Markdown;
- image/figure references when available;
- richer page metadata.

#### Phase 2: Docling Or Marker Fallback

Use for difficult PDFs:

- complex tables;
- math-heavy papers;
- scanned pages;
- difficult multi-column layouts;
- figure-heavy papers.

Docling is attractive for structured document conversion and table structure recognition.

Marker is attractive for Markdown/JSON conversion with stronger handling of equations, tables, and figures.

These should be optional fallback extractors because they are heavier than PyMuPDF4LLM.

### Text Cleaning

Before chunking:

- Remove repeated headers and footers.
- Remove standalone page numbers.
- Fix hyphenated line breaks: `trans-\nformer` -> `transformer`.
- Normalize whitespace.
- Preserve section headings.
- Preserve paragraph boundaries.
- Detect and down-rank or separately store References.
- Keep captions adjacent to their figures/tables.
- Keep page numbers and bbox metadata for citations.

### Table Handling

Tables should not be treated as plain paragraphs only.

Store each table as:

- Markdown table for LLM context.
- JSON rows/columns for future structured retrieval.
- Caption and surrounding paragraph.
- `table_id`, page number, and bbox.

Chunking strategy:

- Create one table summary chunk.
- For long tables, create row-group chunks.
- Include column names in every row-group chunk.
- Preserve metric names, dataset names, and units.

### Equation Handling

Preferred:

- Preserve LaTeX or Markdown math when extracted.
- Store equation blocks separately with page/bbox/order metadata.
- Attach equation blocks to surrounding explanatory text.

Fallback:

- If equation is only available as an image/vector, keep bbox/image reference.
- Do not inject low-confidence OCR math directly into text chunks.
- Use surrounding text and caption-like context for retrieval.

### Figure Handling

Minimum useful figure extraction:

- figure image path or bbox;
- caption;
- page number;
- surrounding text;
- figure id if detected.

Initial RAG should embed:

- caption;
- surrounding paragraph;
- optional generated figure description later if a vision model is added.

Do not embed raw image content in the first implementation.

### Proposed Database Additions

Add an extracted-block table instead of relying only on `pdf_documents.extracted_text`:

```text
pdf_blocks
- id
- pdf_id
- page_number
- order_index
- block_type
- section_path
- content_markdown
- content_json
- bbox
- confidence
- extractor
- created_at
```

Then `pdf_chunks` can reference `block_id`:

```text
pdf_chunks
- block_id nullable
- chunk_type: parent | child | table | equation | figure
```

Migration helper:

```bash
# Dry run
python scripts/migrate_rag_schema.py

# Apply
python scripts/migrate_rag_schema.py --apply
```

### Extraction Quality Checks

For each processed PDF, store/report:

- page count;
- extracted character count;
- number of text blocks;
- number of tables;
- number of figures/captions;
- number of equations;
- pages with very low extracted text;
- parser used;
- extraction warnings.

These checks help detect scanned PDFs, broken text order, or failed table extraction before users ask questions.

## Full RAG Improvement Roadmap

### Phase 1: Extraction Foundation

- Add extractor abstraction: `PDFExtractor`.
- Implement `PyMuPDF4LLMExtractor`.
- Store extracted blocks.
- Keep current `extracted_text` as a compatibility summary.
- Add extraction quality metadata.

### Phase 2: Block-Aware Chunking

- Chunk text, tables, equations, and figures differently.
- Switch from character sizes to token-aware sizes.
- Add overlap for text chunks.
- Keep section/page/block metadata on chunks.

### Phase 3: Embedding Experiments

- Use the new embedding provider facade.
- Compare current MiniLM against BGE-M3 or E5.
- Migrate pgvector dimension when needed.
- Re-index after changing model/dimension/prefixes.

### Phase 4: Retrieval Improvements

- Add PostgreSQL full-text search over chunk/block text.
- Combine dense and keyword retrieval.
- Retrieve more candidates than final context needs.
- Add reranking.

### Phase 5: Generation Improvements

- Tighten RAG prompt to separate evidence-based answers from outside knowledge.
- Add query rewriting for follow-up questions.
- Add citation validation rules.

### Phase 6: Evaluation

- Build a small gold test set.
- Measure retrieval hit rate.
- Measure citation correctness.
- Compare extraction/chunking/model variants before adopting them.

## Interactive PDF Product Requirements

The reader should become a high-interaction PDF/RAG workspace, not only a PDF iframe plus chat.

### Citation Link To PDF Source

Current state:

- Chat citations already include `chunk_id`, `chunk_text`, `pdf_id`, `pdf_name`, and `page_number`.
- Frontend can jump to a PDF page with the current iframe viewer.

MVP behavior:

- Click a citation chip.
- Open the cited PDF if the chat used multiple PDFs.
- Jump to the cited page.
- Show the cited excerpt near the chat or source panel.

Better behavior:

- Highlight the exact cited text in the PDF.
- Scroll to the exact block/line, not just the page.
- Support table/equation/figure citations.

Backend/schema requirements:

- MVP only needs existing `chunk_id`, `chunk_text`, `pdf_id`, and `page_number`.
- Exact highlighting needs `block_id`, `bbox`, or reliable `start_char`/`end_char`.
- Structured extraction should store `pdf_blocks`.
- `pdf_chunks` should reference `pdf_blocks.id`.

Frontend requirements:

- The current iframe viewer is enough only for page-level navigation.
- Exact text highlight requires replacing iframe with a PDF.js/react-pdf viewer with text layer control.
- Citation click should call a viewer API like `goToCitation({ pdfId, pageNumber, chunkText, bbox })`.

### Highlight Text And Explain

User behavior:

- User selects a term or phrase in the rendered PDF.
- User right-clicks or clicks an `Explain` floating action.
- System explains the selected text in the context of the current paper.
- The answer can appear in chat or a source-aware side panel.

MVP backend endpoint:

```http
POST /api/rag/explain-selection
```

Request:

```json
{
  "pdf_id": "...",
  "selected_text": "attention mechanism",
  "page_number": 5,
  "surrounding_text": "optional text around the selection"
}
```

Response:

```json
{
  "answer": "...",
  "citations": [
    {
      "chunk_id": "...",
      "chunk_text": "...",
      "score": 0.82,
      "pdf_id": "...",
      "pdf_name": "...",
      "page_number": 5
    }
  ]
}
```

RAG behavior:

- Verify the PDF belongs to the current user.
- Search only inside that PDF.
- Prefer chunks on the same page when `page_number` is provided.
- Use `selected_text` as the main query.
- Use `surrounding_text` as extra context, not as trusted source by itself.
- Prompt should explain both paper-specific meaning and broader meaning if useful.

Schema dependency:

- MVP can work with current chunks and `page_number`.
- Better precision needs `pdf_blocks`, `block_id`, `bbox`, and cleaner extraction.

### Development Order For Interactive Features

1. Add backend `explain-selection` endpoint using current RAG chunks.
2. Ensure citations include enough metadata for page-level navigation.
3. Add `pdf_blocks` and chunk-to-block references for future precise highlights.
4. Replace iframe PDF viewer with PDF.js/react-pdf text layer.
5. Add citation highlight by text/bbox.
6. Add selection toolbar and call `explain-selection`.
7. Upgrade extraction to make table/equation/figure citations precise.

## Suggested OpenAI Migration Path

Phase 1: Low-risk migration

- Add OpenAI embedding provider behind the existing `EmbeddingProvider` interface.
- Use `text-embedding-3-small` with `dimensions=384`.
- Re-index all documents.
- Compare retrieval quality against the local MiniLM model.

Phase 2: Full-quality migration

- Change pgvector column to `Vector(1536)`.
- Use default `text-embedding-3-small` dimensions.
- Re-index all documents.
- Add an explicit embedding schema version to avoid mixing incompatible vectors.

Phase 3: Retrieval quality work

- Add hybrid full-text search.
- Add reranking.
- Add eval metrics.

## Embedding Provider Configuration

The backend now has an embedding provider facade in `app/core/embedding_provider.py`.

Default local config:

```env
EMBEDDING_PROVIDER=sentence-transformers
EMBEDDING_MODEL_NAME=all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
EMBEDDING_DEVICE=cpu
EMBEDDING_QUERY_PREFIX=
EMBEDDING_DOCUMENT_PREFIX=
```

Recommended local BGE-M3 trial:

```env
EMBEDDING_PROVIDER=sentence-transformers
EMBEDDING_MODEL_NAME=BAAI/bge-m3
EMBEDDING_DIMENSION=1024
EMBEDDING_DEVICE=cpu
EMBEDDING_QUERY_PREFIX=
EMBEDDING_DOCUMENT_PREFIX=
```

E5-style trial:

```env
EMBEDDING_PROVIDER=sentence-transformers
EMBEDDING_MODEL_NAME=intfloat/multilingual-e5-large
EMBEDDING_DIMENSION=1024
EMBEDDING_QUERY_PREFIX=query: 
EMBEDDING_DOCUMENT_PREFIX=passage: 
```

Mixedbread-style trial:

```env
EMBEDDING_PROVIDER=sentence-transformers
EMBEDDING_MODEL_NAME=mixedbread-ai/mxbai-embed-large-v1
EMBEDDING_DIMENSION=1024
EMBEDDING_QUERY_PREFIX=Represent this sentence for searching relevant passages: 
EMBEDDING_DOCUMENT_PREFIX=
```

OpenAI trial while keeping the current 384D database:

```env
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL_NAME=text-embedding-3-small
EMBEDDING_DIMENSION=384
OPENAI_EMBEDDING_DIMENSIONS=384
OPENAI_API_KEY=...
```

Important:

- The pgvector column dimension must match `EMBEDDING_DIMENSION`.
- Existing vectors from one model cannot be mixed with vectors from another model.
- After changing model, dimension, or prefixes, delete/recreate embeddings for the affected PDFs.
- Moving from 384D to 1024D or 1536D requires a database migration and full re-index.

Migration helper:

```bash
# Dry run
python scripts/migrate_embedding_dimension.py --dimension 1024

# Apply: clears chunks/embeddings, changes vector dimension, resets PDFs to pending
python scripts/migrate_embedding_dimension.py --dimension 1024 --apply
```

After running the migration, re-index PDFs from the app or with `/api/pdf/{id}/index`.
