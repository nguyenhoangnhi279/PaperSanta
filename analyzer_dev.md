# Analyzer Feature — Development Notes

## Overview

Analyzer là tính năng Multi-Paper AI Analysis cho PaperSanta.
Cho phép user chọn nhiều PDF, chọn kiểu phân tích, và nhận kết quả từ LLM (DeepSeek) dưới dạng bảng hoặc structured text.

## 3 Modes — 10 Use Cases

### Mode 1: Benchmark Matrix (Tự động lập bảng thông số)
| ID | Use Case | Mục đích |
|----|----------|----------|
| 1 | `benchmark_matrix` | So sánh model (mAP, FPS, Dataset, Backbone) |
| 2 | `hyperparameter_compare` | So sánh thông số train (LR, Batch, Optimizer, Loss, Epochs) |
| 3 | `resource_compare` | So sánh tài nguyên (Params, FLOPs, VRAM) |

### Mode 2: Synthesis Mode (Tổng hợp chiến lược)
| ID | Use Case | Mục đích |
|----|----------|----------|
| 4 | `methodology_mapping` | Tổng hợp Phương pháp & Kiến trúc (backbone, loss, input representation) |
| 5 | `eval_conflicts` | Tranh cãi Thực nghiệm & Hiệu năng (kết quả, metric mismatch) |
| 6 | `paradigm_evolution` | Tiến trình & Xu hướng Công nghệ (quan hệ kế thừa, lineage) |

### Mode 3: Research Gap Detector (Bới móc lỗ hổng)
| ID | Use Case | Mục đích |
|----|----------|----------|
| 7 | `dataset_bias_gap` | Phát hiện bias trong dataset |
| 8 | `domain_gap` | Phát hiện miền ứng dụng bị bỏ ngỏ |
| 9 | `performance_gap` | Phát hiện vấn đề hiệu năng |
| 10 | `cross_domain_idea` | Gợi ý kết hợp chéo lĩnh vực |

## Architecture

### Backend
- `app/schemas/analysis_schema.py` — Pydantic models
- `app/services/analyze_service.py` — Business logic + prompt templates
- `app/api/analyze_router.py` — FastAPI endpoints
- `app/core/config.py` — Constants (temperature, max_tokens, top_k)

### Frontend
- `frontend/src/types.ts` — TypeScript interfaces
- `frontend/src/api/analyze.ts` — API client
- `frontend/src/components/Analyzer.tsx` — Main component
- `frontend/src/components/AnalyzerBenchmarkTable.tsx` — Table renderer
- `frontend/src/components/AnalyzerSynthesisResult.tsx` — Synthesis renderer
- `frontend/src/components/AnalyzerGapResult.tsx` — Gap detection renderer
- `frontend/src/App.tsx` — Wire activeTab
- `frontend/src/components/Sidebar.tsx` — Nav item

## Context Retrieval Strategy

Mỗi analysis type dùng một query khác nhau cho `similarity_search`,
và số lượng chunks (K) khác nhau:

| Type | Query Keywords | K |
|------|---------------|---|
| benchmark_matrix | "architecture, accuracy metrics, mAP, FPS, dataset used, backbone" | 20 |
| hyperparameter_compare | "training configuration, learning rate, batch size, optimizer, loss function, epochs" | 20 |
| resource_compare | "model size, parameters, FLOPs, memory, computational requirements, VRAM" | 20 |
| methodology_mapping | "method, architecture, backbone, loss function, objective, input representation, encoder, decoder" | 30 |
| eval_conflicts | "results, experimental findings, comparison, limitations, discussion, metric, benchmark" | 30 |
| paradigm_evolution | "related work, background, limitations of previous approaches, motivation, improvement upon" | 30 |
| dataset_bias_gap | "limitations, dataset, bias, demographic, ethical, future work" | 40 |
| domain_gap | "limitations, future work, application, domain, language, low-resource" | 40 |
| performance_gap | "future work, limitations, real-time, latency, efficiency, deployment, scalability" | 40 |
| cross_domain_idea | "method, approach, architecture, mechanism, core idea, algorithm" | 30 |

Tại sao không dùng full `extracted_text`?
- extracted_text hiện tại bị thiếu table, math equations (do pypdf giới hạn)
- Dùng top-K chunks cho phép retrieval chính xác hơn theo chủ đề
- Tiết kiệm token (cost) so với full-text
- Khi extracted_text được cải thiện (OCR, table extraction) → nâng cấp lên full-text sau

## Prompt Engineering

### Common System Prompt Prefix
```
Bạn là chuyên gia phân tích tài liệu khoa học (Computer Science, Machine Learning).
NHIỆM VỤ: Phân tích các đoạn trích từ bài báo khoa học và xuất kết quả DƯỚI DẠNG JSON.
TUYỆT ĐỐI KHÔNG chào hỏi, không giải thích dài dòng. Chỉ xuất JSON.
```

### Output Format per Family

**Benchmark Matrix** → `{ "title": "...", "table": [ { "col1": "...", "col2": "..." } ], "notes": "..." }`
  - Mỗi object trong `table` là một model/hàng

**Synthesis** → `{ "title": "...", "consensus": [ { "point": "...", "papers": [1,2] } ], "differences": [ { "aspect": "...", "paper_a": "...", "paper_b": "..." } ], "lineage": [ { "from": "...", "to": "...", "inherited_idea": "...", "improvement": "..." } ] }`

  - 3 sub-types chia sẻ chung format này, chỉ khác trọng tâm:
    - `methodology_mapping`: consensus/differences về architecture, loss, input
    - `eval_conflicts`: conflicts về kết quả, metric, experimental setup
    - `paradigm_evolution`: lineage về quan hệ kế thừa giữa các bài

**Research Gap** → `{ "title": "...", "gaps_found": [ { "gap": "...", "evidence": "...", "severity": "high|medium|low" } ], "opportunities": [ "...", "..." ], "recommendations": [ "...", "..." ] }`

### Temperature per Mode
- Benchmark: 0.2 (cần chính xác, ít sáng tạo)
- Synthesis: 0.4 (cần cân bằng)
- Research Gap: 0.5 (cần sáng tạo hơn để suy luận gap)

## API Endpoints

| Method | Path | Auth | Body/Params | Response |
|--------|------|------|-------------|----------|
| POST | `/api/analyze/run` | Yes | `{ pdf_ids: string[], analysis_type: string, custom_prompt?: string }` | `AnalysisResult` |
| GET | `/api/analyze/history` | Yes | `skip, limit` | `{ analyses: AnalysisResult[], total: number }` |
| GET | `/api/analyze/history/{id}` | Yes | — | `AnalysisResult` |
| DELETE | `/api/analyze/history/{id}` | Yes | — | `{ status: "deleted" }` |

## Frontend Component Structure

```
Analyzer.tsx
  ├── Mode tabs: [Benchmark] [Synthesis] [Gap]
  ├── Sub-mode cards (grid, mỗi card là 1 use case)
  ├── PDF selector (multi-checkbox)
  ├── Custom prompt textarea (optional)
  ├── [Run Analysis] button
  ├── Loading spinner
  └── Result area:
      ├── AnalyzerBenchmarkTable.tsx (nếu mode=benchmark)
      ├── AnalyzerSynthesisResult.tsx (nếu mode=synthesis)
      └── AnalyzerGapResult.tsx (nếu mode=gap)
```

## History Cache

- Kết quả analysis được lưu vào `multi_analyses` table
- Frontend hiển thị history list bên dưới kết quả
- User có thể click vào history để xem lại
- History hiển thị: analysis type + số lượng PDFs + thời gian

## DB Models (đã có, không cần migration)

- `multi_analyses`: id, user_id, analysis_type, result_json (JSONB), created_at
- `analysis_documents`: analysis_id (FK), pdf_id (FK)

## Future Improvements

### 🔲 Section-aware Chunking
Hiện tại chunking theo paragraph (`\n\n`) mù, không biết section (Abstract, Method, Results...).
**Cần làm:**
- Thêm section detection heuristic: regex nhận diện heading keywords (`Abstract`, `I. Introduction`, `3. Method`, `Experimental Results`, `Conclusion`...)
- Gắn `section_type` field vào `PDFChunk` model (enum: abstract, introduction, method, experiment, conclusion, other)
- Khi build context cho LLM, ưu tiên chunks cùng section với câu hỏi
- Fallback: dùng sentence embedding để match section semantics nếu regex không detect được

### 🔲 Terminology Explanation
User highlight 1 thuật ngữ → LLM giải thích trong context của paper đó.
- Endpoint: `POST /api/rag/explain` — body: `{ term: string, pdf_ids: string[], context_window?: number }`
- Retrieve N chunks xung quanh vị trí term xuất hiện (context window)
- Prompt: *"Giải thích thuật ngữ '{term}' dựa trên ngữ cảnh của bài báo. Đưa ra: định nghĩa, vai trò trong paper, liên hệ với các khái niệm khác."*
- Có thể làm dạng inline tooltip hoặc chat mode đặc biệt

### 🔲 Section-aware Summarization
Thay vì summarize toàn bộ extracted_text 200K chars, chia thành các section rồi summarize từng phần → tổng hợp lại.
- Parse sections từ extracted_text
- Gọi LLM summarize từng section
- Gộp thành summary có cấu trúc: Abstract | Method | Results | Conclusion

### 🔲 Full-text analysis
Khi extracted_text được improve (table extraction, math OCR), thay chunks → full-text

### 🔲 Dynamic Context Framing
Đọc abstract/summary của PDFs để tự động detect domain keywords, inject vào prompt cho context chính xác hơn. Dùng existing field (extracted_text hoặc summary) thay vì gọi LLM riêng — embed cosine similarity để detect domain chung.

### 🔲 Hypothetical question filter
Cho user nhập câu hỏi giả định, system tự động reformulate thành query để retrieve chunks — dùng chung cho cả Analyzer và Chat

### 🔲 Multi-LLM support
Cho phép chọn model (DeepSeek, Gemini, Claude)

### 🔲 Download result
Export bảng so sánh ra CSV/Markdown

### 🔲 Citation-aware
Highlight chunk sources trong kết quả

### 🔲 Streaming output
Stream response từ LLM để UX mượt hơn

### 🔲 Feedback loop
User có thể "thích" hoặc sửa kết quả, dùng để fine-tune prompt
