# TODO — PaperSanta

## ✅ Done

- [x] Auto-trigger extraction on upload
- [x] Fix infinite loop chunk_pdf
- [x] Validate extracted_text / chunks / model before processing
- [x] session.commit() trong process_pdf + delete + chat
- [x] Cascade delete chunks → embeddings
- [x] Status badge + polling + toast + retry
- [x] Fix MissingGreenlet list_sessions
- [x] Xoá embedding_router thừa + schemas chết
- [x] Vector dimension 1536 → 384
- [x] page_number thật trong chunk
- [x] Chat JSONB migration (messages + pdf_ids)
- [x] opencode.json config
- [x] Paragraph-aware + parent-child chunking
- [x] Embed chỉ children, search child → trả parent context
- [x] POST /{id}/summarize (TL;DR via DeepSeek)
- [x] Summarize button trong Reader
- [x] Prompt quality: system prompt PaperSanta persona + temperature 0.7 + max_tokens 4096
- [x] Garbage filter cho chunk (trên 50 chars, bỏ page num/url/symbols)

---

## 🔴 Sprint tới — Multi-turn + Query Reformulation

### 1. Multi-turn context (Context Amnesia)
- [ ] Lấy N turns gần nhất từ `chat_session.messages`
- [ ] Nhét history vào prompt trước context chunks
- [ ] Config: `RAG_HISTORY_TURNS: int = 3`

### 2. Query Reformulation (Naive RAG)
- [ ] Trước khi embed + search, gọi LLM reformulate câu hỏi:
      "Lịch sử: {history} → Câu hỏi mới: {query} → Câu hỏi độc lập"
- [ ] Dùng câu đã reformulate để embed + search
- [ ] Vẫn dùng câu gốc + history trong prompt cho LLM generate

### 3. Sliding window
- [ ] Dùng `history_char_count` đã có
- [ ] Pop messages cũ khi vượt 6000 chars
- [ ] Giữ ít nhất 2 turns gần nhất

---

## 🟡 Về sau

### Chunk Quality
- [ ] PyMuPDF thay pypdf (bbox, paragraph structure, table detection)
- [ ] Chunk quality scoring

### PDF Ingestion
- [ ] OCR fallback (Tesseract/PaddleOCR) cho scanned PDF
- [ ] Password detection → FAILED sớm
- [ ] Encoding check (CID font)

### Citation Linking
- [ ] Đổi iframe → PDF.js
- [ ] Lưu bbox vào chunk
- [ ] Click badge → scroll + highlight

### Frontend
- [ ] Fix load chat cũ (format mismatch)
- [ ] Smart Reader layout (chat trái, PDF phải)

### Answer Faithfulness
- [ ] Confidence score từ top-k scores
- [ ] Verify claim sau khi LLM sinh

### Research Gap Detection
- [ ] Multi-paper retrieval
- [ ] Structured output (gaps, themes, conflicts)

---
