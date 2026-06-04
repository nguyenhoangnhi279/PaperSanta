# Chat Improvements

## Current Assessment

The current chat flow works for single-turn RAG, but it is weak for real conversation.

Current flow:

```text
user question
 -> retrieve chunks from selected PDFs
 -> build one prompt from retrieved parent context
 -> generate answer
 -> append user/assistant messages to ChatSession.messages JSONB
```

## Main Weaknesses

### 1. Chat history is stored but not used

- `ChatSession.messages` stores prior turns.
- Retrieval still uses only the latest `query_text`.
- Follow-up questions like "how is it different?", "what about the second method?", or "summarize that" are ambiguous.
- The model does not see prior user/assistant turns except through the latest query.

### 2. No query rewrite

- Follow-up questions are not rewritten into standalone retrieval queries.
- This hurts retrieval because short pronoun-heavy questions have little semantic signal.

Desired behavior:

```text
history:
  user: What is PIA?
  assistant: ...
new question:
  How is it different from finite-state automata?
standalone retrieval query:
  How is a pebble-intervals automaton (PIA) different from standard finite-state automata in the selected paper?
```

### 3. Prompt is too permissive

- Current system prompt allows internal knowledge when chunks are incomplete.
- For paper QA this can mix PDF-grounded evidence with outside knowledge.
- The answer should separate:
  - information supported by selected PDFs;
  - optional background knowledge.

### 4. Citations need richer metadata

Current citations include:

- `chunk_id`
- `chunk_text`
- `score`
- `pdf_id`
- `pdf_name`
- `page_number`

Needed next:

- `block_id`
- `section_path`
- `source_block_type`
- `retrieval_sources`

This will support better citation display and future PDF highlighting.

### 5. Session lifecycle is too static

- `ChatSession` has `created_at` but no `updated_at`.
- Session list sorts by `created_at`, so continued chats do not move to the top.
- Session title is simply the first question prefix.

### 6. PDF scope is ambiguous

- Frontend sends `pdf_ids` on every turn.
- Backend merges new `pdf_ids` into the session.
- There is no explicit rule about whether a session should be fixed to its original PDFs or allowed to expand.

For now, allow expansion but make retrieval use the current request's `pdf_ids`.

## Implementation Plan

### Phase 1: Backend chat memory

- Load existing `ChatSession` before retrieval when `session_id` is provided.
- Validate ownership of the session.
- Build a compact history window from recent messages.
- Rewrite follow-up questions into standalone retrieval queries.
- Store both:
  - original user question;
  - retrieval query used for RAG.

### Phase 2: Prompt hardening

- Build prompt with:
  - retrieved sources;
  - recent conversation history;
  - current question;
  - standalone retrieval query when it differs.
- Require source-grounded answer.
- Require explicit "Outside the paper" wording for background knowledge.

### Phase 3: Citation metadata

- Add optional fields to citation schema:
  - `block_id`
  - `section_path`
  - `source_block_type`
  - `retrieval_sources`
- Return these fields from chat and explain-selection.

### Phase 4: Session lifecycle

- Add `chat_sessions.updated_at`.
- Update it on every new message pair.
- Sort session list by `updated_at desc`.

## Current Decision

Start with Phase 1 and Phase 3 because they improve chat behavior without changing frontend architecture.

## Progress

### Done

- Added `chat_sessions.updated_at` to the model and migration script.
- Applied the RAG schema migration to the local database.
- Session listing now sorts by `updated_at desc`.
- Chat now loads recent session history before retrieval.
- Follow-up-like questions are rewritten into standalone retrieval queries before vector/full-text search.
- Original question and retrieval query are stored on user and assistant messages.
- Chat response returns `retrieval_query` so the frontend can inspect/debug what was searched.
- Citations now carry optional metadata needed for PDF interaction:
  - `source_id`
  - `block_id`
  - `section_path`
  - `source_block_type`
  - `retrieval_sources`
- Frontend types and chat message mapping now preserve the new citation metadata.
- `explain_selection` citations also include the same richer metadata.
- Cleaned the duplicate chat prompt block in `rag_service.py`.
- Extracted chat context/citation building into a dedicated helper.
- Extracted chat prompt construction into a dedicated helper.
- Chat prompt now branches by scope:
  - single-paper QA for normal Reader chat;
  - multi-paper QA for future multi-PDF chat or backend callers.
- Reader chat is now explicitly single-PDF:
  - no multi-PDF selector in Reader;
  - every chat request sends only the opened PDF;
  - changing the opened PDF resets the active chat;
  - chat history list is filtered to sessions containing the opened PDF.

### Remaining

- Citation action currently jumps to page; add fuzzy text/block highlight next.
- PDF text selection UI now exists in the PDF.js viewer, but it currently routes selected text through normal chat instead of the dedicated `explain_selection` endpoint.
- Wire selected text explain to `/api/rag/explain-selection` and pass:
  - selected text;
  - current page number;
  - surrounding text when available.
- Install/sync frontend dependency `pdfjs-dist`; current build fails if `node_modules` has not been updated.
- Add a small chat regression eval set for multi-turn questions:
  - standalone question
  - pronoun follow-up
  - comparison follow-up
  - citation/page correctness

### Latest Code Review Notes

- New PDF.js viewer is directionally correct and supports text selection, zoom controls, and page jump.
- The selection explain flow should not be implemented as a generic chat prompt long-term; use the backend explain endpoint to preserve PDF/page context.
- Re-check current HEAD for prompt hardening changes. Some earlier prompt changes may have been overwritten or not committed:
  - no `[Chunk X]` citation rule in system prompt;
  - distinguish task final output from intermediate model predictions;
  - prefer `[Paper X, page Y]` citations when page is known.
- Re-check frontend bundle split. Current `vite.config.ts` may not include `manualChunks`, and adding PDF.js can reintroduce large bundle warnings.

## Product Decision: Reader vs Analyzer

Reader is single-PDF chat. It should stay tightly coupled to the PDF currently rendered on the left side.

Analyzer remains the multi-PDF structured-analysis surface. Its hard-coded presets are acceptable for now because it is a guided report generator, not free-form chat. Later improvements should make Analyzer share retrieval/context utilities with chat and return richer evidence metadata, but it should not be merged into Reader chat.
