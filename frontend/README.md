# PaperSanta Frontend

Frontend React app cho PaperSanta PDF Manager, sử dụng Vite để build và FastAPI làm backend.

## Cài đặt

```bash
cd frontend
npm install
```

## Chạy Development

```bash
npm run dev
```

App sẽ chạy tại `http://localhost:5173/static/` với hot reload (do `base: '/static/'` trong Vite config).

## Build Production

```bash
npm run build
```

Output sẽ được tạo trong `dist/` folder. FastAPI sẽ serve từ đây.

## Cấu trúc Project

```
frontend/
├── src/
│   ├── api/           # API calls đến backend
│   ├── components/    # React components
│   ├── utils/         # Helper functions
│   ├── App.jsx        # Main app component
│   ├── main.jsx       # Entry point
│   └── index.css      # Global styles
├── index.html         # Vite entry template
├── package.json       # Dependencies & scripts
└── vite.config.js     # Vite config
```

## Cách mở rộng

### Thêm Component mới

1. Tạo file trong `src/components/`
2. Import và sử dụng trong `App.jsx`

Ví dụ: Thêm component `ChatBox`

```jsx
// src/components/ChatBox.jsx
import { useState } from 'react';

function ChatBox({ sessionId }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');

  const sendMessage = async () => {
    // Gọi API chat với session
    const response = await fetch(`/api/chat/${sessionId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: input })
    });
    const data = await response.json();
    setMessages([...messages, { text: input, type: 'user' }, { text: data.reply, type: 'bot' }]);
    setInput('');
  };

  return (
    <div className="chat-box">
      <div className="messages">
        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.type}`}>
            {msg.text}
          </div>
        ))}
      </div>
      <input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
        placeholder="Nhập tin nhắn..."
      />
      <button onClick={sendMessage}>Gửi</button>
    </div>
  );
}

export default ChatBox;
```

### Thêm API Call

Thêm function trong `src/api/`

```js
// src/api/chat.js
export async function sendChatMessage(sessionId, message) {
  const response = await fetch(`/api/chat/${sessionId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message })
  });
  return response.json();
}
```

### Thêm State Management

Sử dụng React hooks hoặc thêm thư viện như Redux/Zustand nếu cần.

Ví dụ: Thêm session state

```jsx
// src/App.jsx
import { useState } from 'react';

function App() {
  const [currentSession, setCurrentSession] = useState(null);

  // ... existing code ...

  return (
    <div className="app-shell">
      {/* ... existing components ... */}
      {currentSession && <ChatBox sessionId={currentSession.id} />}
    </div>
  );
}
```

### Thêm Route (nếu cần)

Nếu app lớn hơn, thêm React Router:

```bash
npm install react-router-dom
```

```jsx
// src/App.jsx
import { BrowserRouter, Routes, Route } from 'react-router-dom';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/chat/:sessionId" element={<ChatPage />} />
      </Routes>
    </BrowserRouter>
  );
}
```

### Thêm Styling

- Sửa `src/index.css` cho global styles
- Hoặc dùng CSS modules/component-scoped CSS

### Backend Integration

- API calls trong `src/api/` gọi đến FastAPI endpoints
- CORS đã được config trong backend
- Sử dụng `/api/*` paths

### Ví dụ mở rộng: Chatbox theo Session

1. **Backend**: Thêm endpoint `/api/chat/{session_id}` trong FastAPI
2. **Frontend**: Thêm component `ChatBox` như trên
3. **State**: Track session hiện tại (từ PDF selection)
4. **UI**: Hiển thị chatbox khi có session active

```jsx
// Trong App.jsx
const handleSelectPdf = (doc) => {
  setSelectedDoc(doc);
  setCurrentSession({ id: doc.id, name: doc.original_name });
};
```

## Tips

- Sử dụng React DevTools để debug
- Hot reload giúp phát triển nhanh
- Build production để tối ưu performance
- Test API với backend chạy song song

## Troubleshooting

- Nếu `npm install` lỗi network, thử `npm config set registry https://registry.npmjs.org/`
- Nếu build lỗi, kiểm tra syntax trong JSX
- Nếu API calls fail, đảm bảo backend đang chạy tại `http://localhost:8000`