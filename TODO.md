# TODO — PaperSanta

## ✅ Done (Phase 0 + 1)

- [x] Auto-trigger extraction on upload
- [x] Fix infinite loop chunk_pdf
- [x] Validate extracted_text / chunks / model before processing
- [x] session.commit() trong process_pdf + delete
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

---

## 🔴 Problem 1 — Query Understanding

Chưa có xử lý ý định câu hỏi trước khi search.

- [ ] Intent classification: "so sánh" → multi-pdf retrieve, "giải thích" → top-k, "tóm tắt" → summarize endpoint
- [ ] Query expansion: synonym expansion cho câu hỏi ngắn / mơ hồ
- [ ] Coreference resolution: "nó" → resolve về paper/chunk đang nói đến

**Impact:** Medium — cần cho UX tốt hơn nhưng không block core RAG

---

## 🔴 Problem 2 — Chunk Quality

Paragraph-aware đã giải quyết 1 phần (cắt đúng paragraph, filter garbage). Còn thiếu:

- [ ] Chunk quality scoring: mỗi chunk tự đánh giá "có useful không" dựa trên entropy, độ dài, nội dung
- [ ] Bỏ chunk toàn số/ký tự đặc biệt / references (đã có garbage filter sơ bộ)
- [ ] Table/math extraction (PyMuPDF thay pypdf)

**Impact:** Medium — đã cải thiện nhiều so với sliding window cũ

---

## 🟡 Problem 3 — Answer Faithfulness

Kiểm tra câu trả lời có bịa không.

- [ ] Confidence score tổng hợp từ top-k similarity scores
- [ ] Nếu tất cả scores < threshold → "Không đủ thông tin" thay vì hardcode string
- [ ] Verify step: sau khi LLM sinh, check từng claim có trong context không (faithfulness eval nhẹ)

**Impact:** High — ảnh hưởng trực tiếp đến độ tin cậy

---

## 🟡 Problem 4 — Multi-turn Context Coherence

Hội thoại dài bị mất context.

- [ ] Sliding window trên messages (giữ ~4000 chars gần nhất, drop cũ)
- [ ] Conversation summarization: compress messages cũ → 1-2 câu summary
- [ ] Entity tracking: giữ list "đang nói về paper nào, chunk nào" qua các turn

**Impact:** Medium — ảnh hưởng chat dài > 5 turns

---

## 🟠 Problem 5 — PDF Ingestion Failure

PDF xấu không được xử lý đúng.

- [ ] Scanned PDF detection (số trang extract được ít hơn số trang thực tế)
- [ ] OCR fallback (Tesseract / PaddleOCR) cho scanned PDF
- [ ] PDF password protection detection → FAILED sớm
- [ ] PDF encoding check (CID font → garbage text)

**Impact:** Low-Medium — scanned PDF ít gặp trong research papers

---

## 🔵 Problem 6 — Research Gap Detection

USP của PaperSanta nhưng implementation chưa chín.

- [ ] Redesign prompt: structured output (gaps[], themes[], conflicts[])
- [ ] Multi-paper retrieval: lấy parent chunks từ nhiều paper song song
- [ ] Citation mapping: gap nào đến từ paper nào
- [ ] Frontend UI: so sánh side-by-side

**Impact:** Low — feature riêng, không block core

---

## Legend

- 🔴 **Phase 2a** — Cần làm sớm
- 🟡 **Phase 2b** — Quan trọng
- 🟠 **Phase 3** — Có thể làm sau
- 🔵 **Phase 4** — Feature mở rộng
