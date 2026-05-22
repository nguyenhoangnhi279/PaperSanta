# PaperSanta

Đồ án AI Research Assistant — PDF Storage với Supabase Auth.

## Kiến trúc Auth

```
Frontend (React + supabase-js)
    │  signInWithOAuth({ provider: "google" })
    │  → Google OAuth → Supabase callback → JWT in localStorage
    │
    │  Mỗi request gửi kèm:
    │  Authorization: Bearer <supabase_jwt>
    │
    ▼
FastAPI (stateless, không cookie, không session)
    │
    ├── get_current_user (dependency)
    │   └── PyJWT decode với SUPABASE_JWT_SECRET
    │       → user_id (uuid) + email
    │
    ├── SQLAlchemy (WHERE user_id = ...)
    └── Supabase Storage (path: {user_id}/{filename})
```

- Backend **stateless** — không quản lý OAuth, không session server-side
- Mỗi user chỉ thấy PDF của mình (filter theo `user_id` từ JWT)
- Storage: 1 bucket `pdfs` chung, path phân biệt `{user_id}/{filename}`

## Setup

### 1. Supabase Project

Tạo project tại [supabase.com](https://supabase.com), sau đó:

**Authentication → Providers → Google:**
- Bật Google provider
- Client ID + Secret từ [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
- Redirect URI: lấy từ Supabase (ví dụ: `https://dtggkrxdqpijfemihzkz.supabase.co/auth/v1/callback`)

**Authentication → Settings:**
- **Site URL:** `http://localhost:5173` (hoặc URL frontend của mày)
- **Redirect URLs:** thêm `http://localhost:5173/**`

**Settings → API:**
- `Project URL` → `SUPABASE_URL`
- `anon public` key → `SUPABASE_KEY` (cho frontend)
- `service_role` key → `SUPABASE_SERVICE_ROLE_KEY` (cho backend storage)
- `JWT Secret` → `SUPABASE_JWT_SECRET` (cho backend verify token)

### 2. Database (chạy 1 lần)

Vì thêm cột `user_id` vào model cũ, cần migrate bằng SQL Editor trong Supabase Dashboard:

```sql
ALTER TABLE pdf_documents ADD COLUMN IF NOT EXISTS user_id VARCHAR(255) NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS ix_pdf_documents_user_id ON pdf_documents(user_id);
```

Nếu chưa có dữ liệu quan trọng, có thể drop bảng cũ và để app tự tạo lại:
```sql
DROP TABLE IF EXISTS pdf_documents;
```

### 3. Env

**Copy file `.env` từ notion, thêm 2 field mới:**

```env
# Supabase Auth
SUPABASE_JWT_SECRET=<lấy từ Settings → API → JWT Secret>
SUPABASE_SERVICE_ROLE_KEY=<lấy từ Settings → API → service_role key>
```

**Frontend env** (`frontend/.env` — đã có sẵn, kiểm tra lại nếu cần):
```env
VITE_SUPABASE_URL=<giống SUPABASE_URL>
VITE_SUPABASE_ANON_KEY=<anon public key>
```

### 4. Chạy

```bash
# Backend
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend (terminal riêng)
cd frontend
npm install
npm run dev
```

Mở `http://localhost:5173` → click "Sign in with Google" → xài app.

### 5. Nhiều user

- Bạn bè mở URL trên → sign in Google → mỗi đứa có user riêng
- Mỗi đứa chỉ thấy PDF của mình (backend filter `user_id`)
- Storage path: `{user_id}/{filename}` — không lo đè file

## API

| Method | URL | Auth | Mô tả |
|--------|-----|------|-------|
| POST | /api/pdf/upload | ✅ | Upload PDF |
| GET | /api/pdf/ | ✅ | Danh sách PDF (của user hiện tại) |
| GET | /api/pdf/{id} | ✅ | Chi tiết PDF |
| GET | /api/pdf/{id}/file | ✅ | Serve file |
| DELETE | /api/pdf/{id} | ✅ | Xóa PDF |
| GET | /health | ❌ | Health check |

Tất cả endpoint (trừ health) đều cần `Authorization: Bearer <token>` — nếu không có → 401.

## Security notes

- `.env` chứa credentials thật **đã bị commit** — chạy `git rm --cached .env` để stop tracking, add vào `.gitignore` đã có sẵn
- `SUPABASE_JWT_SECRET` và `SUPABASE_SERVICE_ROLE_KEY` là **secret**, không để lộ
- `SUPABASE_KEY` (anon) là public, an toàn để ở frontend

```
PaperSanta
├─ AGENTS.md
├─ app
│  ├─ api
│  │  ├─ embedding_router.py
│  │  ├─ pdf_router.py
│  │  └─ rag_router.py
│  ├─ core
│  │  ├─ auth.py
│  │  ├─ config.py
│  │  ├─ database.py
│  │  ├─ deepseek_provider.py
│  │  ├─ embedding_provider.py
│  │  └─ __init__.py
│  ├─ models
│  │  ├─ analysis.py
│  │  ├─ chat.py
│  │  ├─ embedding.py
│  │  └─ pdf_document.py
│  ├─ schemas
│  │  ├─ chat_schema.py
│  │  ├─ embedding_schema.py
│  │  └─ pdf_schema.py
│  ├─ services
│  │  ├─ embedding_service.py
│  │  ├─ pdf_service.py
│  │  └─ rag_service.py
│  └─ __init__.py
├─ fix_log_2026-05-14.txt
├─ frontend
│  ├─ FRONTEND.md
│  ├─ index.html
│  ├─ package-lock.json
│  ├─ package.json
│  ├─ README.md
│  ├─ src
│  │  ├─ api
│  │  │  ├─ pdf.js
│  │  │  └─ rag.js
│  │  ├─ App.jsx
│  │  ├─ components
│  │  │  ├─ AppLayout.jsx
│  │  │  ├─ ChatPanel.jsx
│  │  │  ├─ LibraryPanel.jsx
│  │  │  ├─ MainContent.jsx
│  │  │  ├─ NavItem.jsx
│  │  │  ├─ PaperCard.jsx
│  │  │  ├─ PdfList.jsx
│  │  │  ├─ Sidebar.jsx
│  │  │  ├─ SidebarSection.jsx
│  │  │  ├─ ToastContainer.jsx
│  │  │  ├─ UploadZone.jsx
│  │  │  ├─ UserAccount.jsx
│  │  │  ├─ Viewer.jsx
│  │  │  └─ WelcomeCard.jsx
│  │  ├─ context
│  │  │  └─ AuthContext.jsx
│  │  ├─ index.css
│  │  ├─ lib
│  │  │  └─ supabase.js
│  │  ├─ main.jsx
│  │  └─ utils
│  │     └─ format.js
│  └─ vite.config.js
├─ main.py
├─ RAG_RAG
│  ├─ rag_from_scratch_10_and_11.ipynb
│  ├─ rag_from_scratch_12_to_14.ipynb
│  ├─ rag_from_scratch_15_to_18.ipynb
│  ├─ rag_from_scratch_1_to_4.ipynb
│  ├─ rag_from_scratch_5_to_9.ipynb
│  └─ README.md
├─ README.md
├─ requirements.txt
└─ TODO-frontend.md

```