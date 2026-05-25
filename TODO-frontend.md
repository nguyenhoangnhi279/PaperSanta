# Frontend cần làm tiếp

## 1. Hiển thị status PDF trên PaperCard
- Thêm badge nhỏ hiển thị `doc.status` (pending / extracted / indexed / failed)
- Màu sắc: pending=vàng, indexed=xanh, failed=đỏ

## 2. Auto-refresh LibraryPanel sau upload
- Sau khi upload xong, tự động reload danh sách PDF để cập nhật status

## 3. Log trigger index khi upload
- Thêm console.log ở `pdf.js` khi fire-and-forget gọi `indexPdfFile`

## 4. Nút xóa PDF
- PaperCard chưa có nút xóa → cần thêm

## 5. Health/status indicator
- UI mới không hiển thị trạng thái API health (đèn xanh/đỏ)

## 6. Search papers view
- View "Search papers" hiện là placeholder → cần implement

## 7. Analyze view
- View "Analyze" hiện là placeholder → cần implement

## 8. DB migration
- `ALTER TABLE pdf_embeddings ALTER COLUMN vector TYPE vector(384);`
- `ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS prompt_tokens INTEGER;`
- `ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS completion_tokens INTEGER;`

## ✅ Đã xong
- [x] Light theme UI (Inter font, AppLayout, Sidebar, ChatPanel, LibraryPanel)
- [x] RAG chat endpoint
- [x] Pipeline index (auto-trigger sau upload)
- [x] Fix 405 rag_router không được include
- [x] Fix missing config fields (RAG, embedding, DeepSeek)
- [x] Fix vector dimension mismatch (1536 → 384)
- [x] Fix ChatMessage missing prompt_tokens/completion_tokens
- [x] Fix blocking calls (embedding + DeepSeek → asyncio.to_thread)
- [x] Fix N+1 query in rag_router
