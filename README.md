---
title: Paper Search API
emoji: 🚀
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
---
# PaperSanta

> PaperSanta là một AI Research Assistant hỗ trợ đọc, lưu trữ, tìm kiếm và phân tích bài báo khoa học dạng PDF.

**Phiên bản:** v1.0.0 | **Bắt đầu:** 13/03/2026 | **License:** MIT

---

## Đặc điểm nổi bật

- **Xác thực đa-nền tảng**: Đăng nhập qua Google OAuth với Supabase
- **Quản lý tài liệu**: Upload, xem, xóa các bài báo PDF cá nhân
- **RAG (Retrieval-Augmented Generation)**: Đặt câu hỏi và chat với PDF bằng AI DeepSeek
- **Tìm kiếm semantic**: Tìm các bài báo liên quan dựa trên nội dung
- **Phân tích tài liệu**: Phân tích nội dung PDF, rút trích thông tin quan trọng
- **Bảo mật dữ liệu**: Mỗi user chỉ thấy PDF của mình (filter theo user_id)
- **Stateless Backend**: FastAPI backend không lưu session, dễ scale

---

## Kiến trúc dự án (Architecture)

### Sơ đồ hệ thống

```
Frontend (React 18 + TypeScript + Supabase.js)
         ↓
    Google OAuth (Supabase Auth)
         ↓
    JWT Token (localStorage)
         ↓
Backend (FastAPI)
    ├── Auth: PyJWT verify
    ├── PDF Storage: Supabase Storage ({user_id}/{filename})
    ├── Database: PostgreSQL (PDFs, chat sessions, embeddings)
    ├── Embedding: Sentence-transformers (all-minilm-l6-v2)
    └── RAG Pipeline: Text Extraction → Embedding → Semantic Search → LLM
```

### Cấu trúc thư mục

```
PaperSanta/
├── app/                          # Backend Python
│   ├── api/                      # API routes
│   │   ├── pdf_router.py         # Upload, list, delete PDFs
│   │   ├── rag_router.py         # Chat, RAG endpoints
│   │   ├── analyze_router.py     # Document analysis endpoints
│   │   └── search_router.py      # Paper search & similarity
│   ├── core/                     # Core utilities
│   │   ├── auth.py               # JWT verification
│   │   ├── config.py             # Environment config
│   │   ├── database.py           # DB connection
│   │   ├── deepseek_provider.py  # Embedding provider (Sentence-transformers)
│   │   └── embedding_provider.py # LLM provider integration
│   ├── models/                   # SQLAlchemy models
│   │   ├── pdf_document.py       # PDF document model
│   │   ├── pdf_block.py          # PDF block/chunk model
│   │   ├── chat.py               # Chat session model
│   │   ├── analysis.py           # Document analysis model
│   │   └── embedding.py          # Embedding vector model
│   ├── schemas/                  # Pydantic schemas (request/response)
│   └── services/                 # Business logic
│       ├── pdf_service.py        # PDF operations & extraction
│       ├── rag_service.py        # RAG pipeline
│       ├── embedding_service.py  # Embedding generation & storage
│       ├── analyze_service.py    # Document analysis
│       ├── extraction_service.py # Text extraction from PDF
│       ├── paper_search_service.py # Semantic search
│       └── text_normalization_service.py # Text processing
├── frontend/                     # React + TypeScript frontend
│   ├── src/
│   │   ├── api/                  # Backend API client
│   │   ├── components/           # React components
│   │   ├── context/              # Auth context (Supabase)
│   │   ├── lib/                  # Utility functions
│   │   └── main.tsx              # Entry point
│   └── vite.config.ts            # Vite config
├── main.py                       # FastAPI app entry point
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

---

## Hướng dẫn bắt đầu (Getting Started)

### Yêu cầu hệ thống (Prerequisites)

- **Node.js**: v18+ (cho frontend - TypeScript)
- **Python**: v3.10+ (cho backend - FastAPI)
- **npm**: Node package manager
- **pip**: Python package manager
- **Git**: Version control

### Cài đặt (Installation)

#### 1. Clone repository

```bash
git clone https://github.com/tthanh1223/PaperSanta_TTNN
cd PaperSanta_TTNN
```

#### 2. Tạo virtual environment Python

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python -m venv venv
source venv/bin/activate
```

#### 3. Cài đặt dependencies Backend

```bash
pip install -r requirements.txt
```

#### 4. Cài đặt dependencies Frontend

```bash
cd frontend
npm install
cd ..
```

### Cấu hình (Configuration)

#### 1. Tạo tài khoản Supabase

- Đăng ký tại [supabase.com](https://supabase.com)
- Tạo project mới
- Lấy `Project URL`, `Anon Key`, `Service Role Key` và `JWT Secret`

#### 2. Cấu hình Google OAuth (trong Supabase)

- Đi đến **Authentication → Providers → Google**
- Bật Google provider
- Lấy **Client ID** và **Secret** từ [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
- Nhập vào Supabase

#### 3. Lấy API key từ DeepSeek platform

- Đăng ký tại [platform.deepseek.com](https://platform.deepseek.com)
- Vào **API keys** chọn **Create new API key**
- Nhập tên và lấy DeepSeek API key

#### 4. Cấu hình Environment Variables

**Tạo file `.env` ở thư mục gốc:**

```env
# Database (Supabase/Postgres)
DB_HOST=<Host URL từ Supabase Database Settings>
DB_USER=<Database User>
DB_PASSWORD=<Database Password>

# Supabase Auth & Storage
SUPABASE_URL=<Project URL từ Supabase>
SUPABASE_KEY=<Anon Key từ Supabase>
SUPABASE_SERVICE_ROLE_KEY=<Service Role Key từ Supabase>
SUPABASE_JWT_SECRET=<JWT Secret từ Supabase Settings>

# External APIs
TAVILY_API_KEY=<Tavily API key>
GEMINI_API_KEY=<Gemini API key>
SEMANTIC_SCHOLAR_API_KEY=<Semantic Scholar API key>
DEEPSEEK_API_KEY=<DeepSeek API key>
OPENAI_API_KEY=<OpenAI API key>

# Environment
ENVIRONMENT=development
```

**Tạo file `frontend/.env`:**

```env
VITE_SUPABASE_URL=<Project URL từ Supabase>
VITE_SUPABASE_ANON_KEY=<Anon Key từ Supabase>
```

---

## Hướng dẫn sử dụng (Usage)

### Chạy ứng dụng

```bash
# Terminal 1: Backend
.venv\Scripts\activate  # Windows (hoặc source venv/bin/activate trên Mac/Linux)
uvicorn main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend
npm run build
npm run dev
```

### Truy cập ứng dụng

1. Mở browser: `http://localhost:5173`
2. Click **Sign in with Google**
3. Đăng nhập Google account
4. Bắt đầu upload PDF và chat

### Các tính năng chính

| Tính năng | Mô tả |
|-----------|--------|
| **Upload PDF** | Drag & drop hoặc chọn file PDF để upload |
| **Danh sách PDF** | Xem tất cả PDF của bạn |
| **Chat với PDF** | Đặt câu hỏi về nội dung PDF |
| **Tìm kiếm** | Tìm PDF liên quan theo từ khóa |
| **Xóa PDF** | Xóa PDF khỏi thư viện |

### API Endpoints

| Method | URL | Auth | Mô tả |
|--------|-----|------|-------|
| POST | /api/pdf/upload | ✅ | Upload PDF |
| GET | /api/pdf/ | ✅ | Danh sách PDF (của user hiện tại) |
| GET | /api/pdf/{id} | ✅ | Chi tiết PDF |
| GET | /api/pdf/{id}/file | ✅ | Serve file |
| DELETE | /api/pdf/{id} | ✅ | Xóa PDF |
| POST | /api/pdf/{id}/index | ✅ | Trigger indexing pipeline |
| GET | /api/pdf/{id}/status | ✅ | Check indexing status |
| POST | /api/rag/chat | ✅ | Chat với PDF (RAG) |
| GET | /api/rag/sessions | ✅ | Danh sách chat sessions |
| GET | /api/rag/sessions/{id} | ✅ | Chi tiết session |
| DELETE | /api/rag/sessions/{id} | ✅ | Xóa session |
| POST | /api/embedding/search | ✅ | Tìm kiếm similar documents |
| GET | /health | ❌ | Health check |

**Lưu ý:** Tất cả endpoint (trừ `/health`) cần header `Authorization: Bearer <token>`

---

## Đóng góp (Contributing)

### Quy trình đóng góp

1. **Fork** repository
2. Tạo branch mới: `git checkout -b feature/your-feature`
3. Commit changes: `git commit -am 'Add your feature'`
4. Push to branch: `git push origin feature/your-feature`
5. Tạo **Pull Request** (theo quy chuẩn của dự án)

### Hướng dẫn phát triển

- Tuân thủ PEP 8 cho Python code
- Viết tests cho features mới
- Cập nhật README nếu thêm tính năng mới
- Chạy tests trước khi push: `pytest`

---

## Giấy phép (License)

Dự án này được cấp phép dưới **MIT License**.

**Copyright © 2026 - Nhóm Trí tuệ nhân nhượng (24TNT1)**

Được phép sử dụng, sửa đổi, và phân phối code dưới các điều khoản MIT License.

---

## Liên hệ & Hỗ trợ

- **Tác giả**: Nhóm Trí tuệ nhân nhượng (24TNT1)
- **GitHub Issues**: [Báo cáo lỗi hoặc suggest feature](../../issues)
- **Email**: tthanh1223@gmail.com (hoặc liên hệ tác giả)

---

## Tài liệu bổ sung

- [Frontend README](./frontend/FRONTEND.md) - Hướng dẫn frontend chi tiết (React + TypeScript)
- [RAG Improvement Notes](./RAG_IMPROVEMENT_NOTES.md) - Ghi chú cải thiện RAG pipeline
- [Analyzer Development](./analyzer_dev.md) - Tài liệu phát triển module analyzer

---

**Last Updated**: 12/06/2026
