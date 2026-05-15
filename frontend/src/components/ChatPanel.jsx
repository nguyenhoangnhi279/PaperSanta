import { useState, useEffect, useRef } from 'react';
import { ragChat, fetchSession, fetchSessions, deleteSession } from '../api/rag';
import { useAuth } from '../context/AuthContext';

function ChatPanel({ documents, pdfUrl, onViewPdf }) {
  const { session } = useAuth();
  const token = session?.access_token;

  const [selectedPdfIds, setSelectedPdfIds] = useState([]);
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [sessionId, setSessionId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [expandedPdf, setExpandedPdf] = useState(false);
  const [sessions, setSessions] = useState([]);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [showSessions, setShowSessions] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    loadSessions();
  }, []);

  const loadSessions = async () => {
    if (!token) return;
    setLoadingSessions(true);
    try {
      const data = await fetchSessions(token);
      setSessions(data.sessions || []);
    } catch (err) {
      console.error('[chat] load sessions error:', err);
    } finally {
      setLoadingSessions(false);
    }
  };

  const loadSession = async (sid) => {
    if (!token) return;
    try {
      setLoading(true);
      const data = await fetchSession(sid, token);
      setSessionId(data.id);
      const loaded = (data.messages || []).map((m) => ({
        role: m.role === 'user' ? 'user' : 'assistant',
        content: m.content,
        id: m.id,
      }));
      setMessages(loaded);
      setShowSessions(false);
    } catch (err) {
      console.error('[chat] load session error:', err);
    } finally {
      setLoading(false);
    }
  };

  const startNewChat = () => {
    setMessages([]);
    setSessionId(null);
    setSelectedPdfIds([]);
    setShowSessions(false);
  };

  const togglePdfSelection = (docId) => {
    setSelectedPdfIds((prev) =>
      prev.includes(docId)
        ? prev.filter((id) => id !== docId)
        : [...prev, docId]
    );
  };

  const handleSend = async () => {
    const text = inputText.trim();
    if (!text || loading) return;
    if (selectedPdfIds.length === 0) {
      return;
    }

    const userMessage = { role: 'user', content: text, id: Date.now().toString() };
    setMessages((prev) => [...prev, userMessage]);
    setInputText('');
    setLoading(true);

    try {
      const result = await ragChat(text, selectedPdfIds, token, sessionId);
      setSessionId(result.session_id);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: result.answer,
          id: result.session_id + '-resp',
          citations: result.citations,
        },
      ]);
      loadSessions();
    } catch (err) {
      console.error('[chat] send error:', err);
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `Error: ${err.message}`, id: 'error-' + Date.now() },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteSession = async (sid) => {
    if (!token) return;
    try {
      await deleteSession(sid, token);
      if (sessionId === sid) {
        startNewChat();
      }
      loadSessions();
    } catch (err) {
      console.error('[chat] delete session error:', err);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const selectedDocs = documents.filter((d) => selectedPdfIds.includes(d.id));

  return (
    <div className="chat-panel">
      <div className="chat-toolbar">
        <div className="chat-pdf-selector">
          <button
            className="chat-select-toggle"
            onClick={() => setExpandedPdf(!expandedPdf)}
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <rect x="1" y="1" width="12" height="12" rx="2" stroke="#666F8D" strokeWidth="1.3"/>
            </svg>
            <span>
              {selectedDocs.length === 0
                ? 'Select PDFs to chat...'
                : `${selectedDocs.length} PDF(s) selected`}
            </span>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className={`chevron ${expandedPdf ? 'open' : ''}`}>
              <path d="M3 5L6 8L9 5" stroke="#666F8D" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
          {expandedPdf && (
            <div className="chat-pdf-dropdown">
              {documents.length === 0 ? (
                <div className="chat-pdf-empty">No PDFs uploaded yet</div>
              ) : (
                documents.map((doc) => (
                  <label key={doc.id} className="chat-pdf-option">
                    <input
                      type="checkbox"
                      checked={selectedPdfIds.includes(doc.id)}
                      onChange={() => togglePdfSelection(doc.id)}
                    />
                    <span>{doc.original_name}</span>
                    <button
                      className="chat-pdf-view"
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        onViewPdf(doc);
                      }}
                      title="View PDF"
                    >
                      👁
                    </button>
                  </label>
                ))
              )}
            </div>
          )}
          {selectedDocs.length > 0 && (
            <div className="chat-selected-tags">
              {selectedDocs.slice(0, 3).map((d) => (
                <span key={d.id} className="chat-tag">
                  {d.original_name}
                  <button onClick={() => togglePdfSelection(d.id)}>×</button>
                </span>
              ))}
              {selectedDocs.length > 3 && (
                <span className="chat-tag more">+{selectedDocs.length - 3}</span>
              )}
            </div>
          )}
        </div>

        <div className="chat-actions">
          <button className="btn-sessions-toggle" onClick={() => setShowSessions(!showSessions)}>
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <rect x="1" y="1" width="12" height="12" rx="2" stroke="currentColor" strokeWidth="1.3"/>
            </svg>
            History
          </button>
          <button className="btn-new-chat" onClick={startNewChat}>
            + New chat
          </button>
        </div>
      </div>

      <div className="chat-body">
        {showSessions && (
          <div className="chat-sessions-sidebar">
            <div className="chat-sessions-header">Chat History</div>
            {loadingSessions ? (
              <div className="chat-sessions-loading">Loading...</div>
            ) : sessions.length === 0 ? (
              <div className="chat-sessions-empty">No chat history</div>
            ) : (
              <div className="chat-sessions-list">
                {sessions.map((s) => (
                  <div
                    key={s.id}
                    className={`chat-session-item ${sessionId === s.id ? 'active' : ''}`}
                    onClick={() => loadSession(s.id)}
                  >
                    <div className="chat-session-title">{s.title || 'Untitled'}</div>
                    <button
                      className="chat-session-delete"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteSession(s.id);
                      }}
                      title="Delete"
                    >
                      <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                        <path d="M1 1L9 9M9 1L1 9" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="chat-messages">
          {messages.length === 0 ? (
            <div className="chat-empty">
              <div className="chat-empty-icon">💬</div>
              <h3>Chat with your PDFs</h3>
              <p>Select PDFs above and ask questions about their content.</p>
            </div>
          ) : (
            messages.map((msg) => (
              <div key={msg.id} className={`chat-message ${msg.role}`}>
                <div className="chat-message-content">{msg.content}</div>
                {msg.citations && msg.citations.length > 0 && (
                  <div className="chat-citations">
                    <span className="chat-citations-label">Sources:</span>
                    {msg.citations.map((c, i) => (
                      <span key={i} className="chat-citation" title={c.chunk_text}>
                        {c.pdf_name} (score: {c.score.toFixed(2)})
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))
          )}
          {loading && (
            <div className="chat-message assistant">
              <div className="chat-message-content thinking">Thinking...</div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      <div className="chat-input-bar">
        <input
          type="text"
          placeholder={
            selectedPdfIds.length === 0
              ? 'Select PDFs to start chatting...'
              : 'Ask a question about the selected PDFs...'
          }
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading || selectedPdfIds.length === 0}
        />
        <button
          className="btn-send"
          onClick={handleSend}
          disabled={loading || !inputText.trim() || selectedPdfIds.length === 0}
        >
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path d="M1 9L17 1L9 17L7 11L1 9Z" stroke="white" strokeWidth="1.5" strokeLinejoin="round"/>
          </svg>
        </button>
      </div>
    </div>
  );
}

export default ChatPanel;
