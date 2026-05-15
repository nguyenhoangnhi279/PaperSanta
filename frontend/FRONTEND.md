# PaperSanta Frontend

## Tech Stack

- **React 18** (Vite + @vitejs/plugin-react)
- **Vanilla CSS** (no framework — `index.css` chứa toàn bộ styles)
- **Supabase JS** (Auth — Google OAuth)
- **Không router** (state-based routing qua `activeView`)

## Project Structure

```
frontend/
├── src/
│   ├── api/            # API calls tới backend
│   │   ├── pdf.js      # PDF CRUD: list, upload, delete, get file URL
│   │   └── rag.js      # RAG Chat: chat, sessions, similarity query
│   ├── components/     # React components
│   │   ├── AppLayout.jsx    # Layout tổng: Sidebar + MainContent
│   │   ├── ChatPanel.jsx    # Chat với PDF (session history, message list)
│   │   ├── LibraryPanel.jsx # Thư viện PDF (search, sort, card list)
│   │   ├── MainContent.jsx  # State-based router: render view theo activeView
│   │   ├── NavItem.jsx      # Sidebar nav item (icon + label + active)
│   │   ├── PaperCard.jsx    # Card hiển thị 1 PDF (title, stats, Similar)
│   │   ├── PdfList.jsx      # Danh sách PDF cũ (sidebar bottom)
│   │   ├── Sidebar.jsx      # Sidebar trái (logo, search, nav, recent, upload, user)
│   │   ├── SidebarSection.jsx # Section wrapper (title + items + fade)
│   │   ├── ToastContainer.jsx # Toast notification (success/error/info)
│   │   ├── UploadZone.jsx   # Drag-drop upload zone
│   │   ├── UserAccount.jsx  # Avatar + username + sign out
│   │   ├── Viewer.jsx       # PDF viewer (iframe)
│   │   └── WelcomeCard.jsx  # Welcome card (greeting only, no search)
│   ├── context/
│   │   └── AuthContext.jsx   # Auth provider: user, session, signIn/signOut
│   ├── lib/
│   │   └── supabase.js      # Supabase client init
│   ├── utils/
│   │   └── format.js        # formatSize(), timeAgo()
│   ├── App.jsx              # Root: Auth → AppLayout → routing logic
│   ├── index.css            # ALL styles (light theme, ~1400 lines)
│   └── main.jsx             # Entry point (ReactDOM.createRoot)
├── index.html               # Vite entry
├── package.json
├── vite.config.js
└── FRONTEND.md
```

## Layout

```
┌──────── 296px ────────┐───────── flex: 1 ─────────┐
│  Sidebar (#F7F8FA)    │  Main Content (white)      │
│ ─────────────────────  │ ┌──────────────────────┐ │
│  PAPERSANTA            │ │  WelcomeCard          │ │
│  🔍 Search for files..  │ │  UploadZone           │ │
│                        │ │  LibraryPanel         │ │
│  ─── TOOLS ───        │ │  [paper cards]        │ │
│  📚 Library (active)   │ │                       │ │
│  💬 Chats              │ └──────────────────────┘ │
│  🔬 Analyze            │                          │
│  🔎 Search papers      │  Chat view (activeView): │
│                        │  ┌────────────────────┐ │
│  ─── RECENT ───       │  │ Toolbar (PDF select)│ │
│  ...recent PDFs...     │  │ [History] [+New]   │ │
│                        │  ├────────────────────┤ │
│  ┌─[+ Upload file]──┐ │  │ Session sidebar │ Msgs│
│  └──────────────────┘ │  │ (240px)         │     │
│  👤 User       [⇨]    │  ├────────────────────┤ │
└────────────────────────┘  │ Input bar           │
                            └────────────────────┘
```

## Routing (State-based)

`App.jsx` giữ state `activeView`:

| activeView | Nội dung |
|---|---|
| `'library'` | Welcome + LibraryPanel (hoặc Viewer nếu `selectedDoc != null`) |
| `'chats'` | ChatPanel |
| `'analyze'` | Placeholder |
| `'search'` | Placeholder |

Chuyển view qua `onNavigate(key)` → setActiveView. Khi rời `'library'`, `selectedDoc` được clear.

## API Endpoints (Backend calls)

Tất cả gọi qua `src/api/pdf.js` và `src/api/rag.js`.

### PDF (`api/pdf.js`)
```
GET    /api/pdf/           → fetchPdfs(token)
POST   /api/pdf/upload     → uploadPdfFile(file, token)
DELETE /api/pdf/{id}       → deletePdfById(id, token)
GET    /api/pdf/{id}/file  → getPdfFileUrl(id, token)
```

### RAG (`api/rag.js`)
```
POST  /api/rag/query          → ragQuery(text, token, pdfId?, topK?)
POST  /api/rag/chat           → ragChat(text, pdfIds, token, sessionId?, topK?)
GET   /api/rag/sessions       → fetchSessions(token, skip?, limit?)
GET   /api/rag/sessions/{id}  → fetchSession(id, token)
DELETE /api/rag/sessions/{id} → deleteSession(id, token)
```

### Auth
```
Supabase Google OAuth → AuthContext.jsx
Token gửi qua header: Authorization: Bearer <access_token>
```

### System
```
GET /health → health check
```

## Key Logic Flows

### Upload
```
User chọn file (Sidebar Upload / UploadZone / TopBar Upload)
  → App.handleUpload(file)
    → uploadPdfFile(file, token) → POST /api/pdf/upload
    → addToast("Upload thành công")
    → loadDocuments() → re-fetch list
```

### Chat
```
User chọn PDFs → nhập text → gửi
  → ChatPanel.handleSend()
    → ragChat(text, pdfIds, token, sessionId)
      → POST /api/rag/chat
        → backend retrieve chunks → DeepSeek generate → lưu session
    → response: { answer, session_id, citations }
    → messages.push({ role: 'assistant', content, citations })
    → loadSessions() (refresh history)
```

### Session History
```
ChatPanel mount → fetchSessions(token)
  → GET /api/rag/sessions
  → sidebar trái hiện danh sách
Click session → fetchSession(id, token)
  → GET /api/rag/sessions/{id}
  → messages = data.messages
```

## Styling Guide

- **`index.css`**: Single file, ~1400 lines, CSS variables ở đầu
- **Theme**: Light (không hỗ trợ dark mode)
- **CSS Variables**:
  ```css
  --sidebar-bg: #F7F8FA;
  --main-bg: #FFFFFF;
  --card-bg: #FFFFFF;
  --text-dark: #19213D;
  --text-neutral: #666F8D;
  --text-light: #BAC0CC;
  --border: #F0F2F5;
  --border-2: #E3E6EA;
  --accent: #2388FF;
  --accent-gradient: linear-gradient(180deg, #2B7AFB 0%, #2174FD 100%, #213BFD 100%);
  --shadow-sm: 0px 1px 3px rgba(25, 33, 61, 0.10);
  --shadow-md: 0px 2px 4px rgba(25, 33, 61, 0.08);
  --radius: 8px;
  --radius-lg: 16px;
  ```
- **Font**: Inter (Google Fonts)

## Adding a New Feature

1. **Nếu cần view mới**: Thêm case trong `MainContent.renderView()` + thêm nav item trong `Sidebar.NAV_ITEMS`
2. **Nếu cần API mới**: Thêm function trong `api/pdf.js` hoặc `api/rag.js`
3. **Nếu cần component mới**: Tạo file trong `src/components/`, import trong view tương ứng
4. **Style**: Thêm CSS class trong `index.css` (theo thứ tự alphabet của section)
5. **Logging**: Mọi action đều kèm `console.log('[tag] message')` để debug

## Common Fixes

- **"RAG trả lời yếu"**: Tăng `RAG_DEFAULT_TOP_K`, giảm `RAG_MIN_SCORE` trong `app/core/config.py`, hoặc đổi embedding model
- **"Upload không hoạt động"**: Check `handleUpload` trong `App.jsx` — file input ref + `uploadPdfFile` call
- **"Chat không load session"**: Check `fetchSessions` trong `api/rag.js` — token có hợp lệ không
- **"CSS bị vỡ"**: `index.css` là single file — dùng browser DevTools inspect element để tìm selector
