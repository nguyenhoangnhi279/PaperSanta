# Frontend cần làm — Chat RAG

## 1. API client: `frontend/src/api/rag.js`
- `chatQuery(queryText, pdfIds, sessionId?)` → `POST /api/rag/chat`
- `listSessions()` → `GET /api/rag/sessions`
- `getSession(id)` → `GET /api/rag/sessions/{id}`
- `deleteSession(id)` → `DELETE /api/rag/sessions/{id}`

## 2. Component: `ChatBox.jsx`
- Input + nút gửi
- Messages: user + AI
- Citations dưới mỗi AI message (chunk_index, pdf_name, score)

## 3. Sửa `PdfList.jsx` / `App.jsx`
- Thêm checkbox chọn PDFs bên sidebar
- Truyền selected pdf_ids xuống ChatBox

## Backend hiện tại (KHÔNG cần đụng)
- `POST /api/rag/chat` ✅
- `GET /api/rag/sessions` ✅  
- `GET /api/rag/sessions/{id}` ✅
- `DELETE /api/rag/sessions/{id}` ✅
- DeepSeek + pgvector search ✅
- ChatSession + ChatMessage + MessageCitation models ✅

quay lại trạng thái cũ
git checkout backup-current