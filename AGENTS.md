# Rules

## Logging

Mọi thay đổi trong codebase đều PHẢI kèm log statement (`logger.info/warning/error`). Cụ thể:
- **Sửa logic** → log input params + kết quả / hành động đã làm
- **Thêm feature** → log từng bước xử lý
- **Xử lý lỗi** → log error message + context
- **Background task** → log start + done / fail

## RAG Quality — Future Improvements

### Vấn đề hiện tại (2026-05-15)
DeepSeek trả kết quả yếu hơn Gemini khi hỏi "attention là gì" dù PDF là "Attention Is All You Need".
Nguyên nhân: Vietnamese query → embed bằng `all-MiniLM-L6-v2` (English model) → similarity score thấp
→ `RAG_MIN_SCORE=0.3` filter mất chunks chứa definition.

### Cần làm khi có thời gian

#### 1. Tune params in `app/core/config.py`
```python
RAG_DEFAULT_TOP_K: int = 15   # hiện tại: 5 — quá ít
RAG_MIN_SCORE: float = 0.15   # hiện tại: 0.3 — mất chunks khi cross-lingual
```

#### 2. Improve prompt in `app/services/rag_service.py:127-131`
User prompt hiện tại quá đơn giản. Cần thêm instruction:
- Yêu cầu DeepSeek tổng hợp từ nhiều chunks thành định nghĩa hoàn chỉnh
- Không paraphrase đơn thuần từng chunk
- Nếu chunks có thông tin bổ sung, hãy kết hợp lại

#### 3. Thử embedding model mạnh hơn
- `intfloat/multilingual-e5-large` (hỗ trợ Vietnamese-English)
- `BAAI/bge-m3` (multilingual, 8192 context length)
Cần đổi `EMBEDDING_MODEL_NAME` trong config + re-chunk & re-embed.

#### 4. Smart chunking
Hiện tại chunk_size=1000 chars fixed → không tôn trọng ranh giới câu/đoạn.
Có thể thử:
- `langchain` text splitters (RecursiveCharacterTextSplitter)
- Semantic chunking (dựa vào embedding similarity)

#### 5. Re-ranking
Thêm bước re-rank sau similarity search:
- Dùng cross-encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`) để re-rank top-K chunks
- Chỉ gửi top chunks sau re-rank vào LLM
