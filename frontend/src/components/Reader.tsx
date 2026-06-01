import { useCallback, useEffect, useRef, useState } from 'react';
import { FileText, Send, MessageSquare, Trash2, Sparkles } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { cn } from '../lib/utils';
import { ragChat, fetchSessions, fetchSession, deleteSession } from '../api/rag';
import { getPdfFileUrl, summarizePdf } from '../api/pdf';
import PDFViewer from './PDFViewer';
import MarkdownRenderer from './MarkdownRenderer';
import type { PDFDocument, ChatMessage, ChatSession } from '../types';


interface ReaderProps {
  paper?: PDFDocument | null;
  allPapers: PDFDocument[];
  onBack: () => void;
}

export default function Reader({ paper, onBack }: ReaderProps) {
  const { session: authSession } = useAuth();
  const token = authSession?.access_token;

  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [showSessions, setShowSessions] = useState(false);
  const [summarizing, setSummarizing] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [viewerTarget, setViewerTarget] = useState<{ page: number; text?: string } | null>(null);
  const selectedPdfIds = paper ? [paper.id] : [];

  // Load PDF URL when paper changes
  useEffect(() => {
    if (!paper) {
      setPdfUrl(null);
      return;
    }
    let canceled = false;
    getPdfFileUrl(paper.id, token)
      .then((data) => { if (!canceled) setPdfUrl(data.url); })
      .catch(() => { if (!canceled) setPdfUrl(null); });
    return () => { canceled = true; };
  }, [paper?.id, token]);

  useEffect(() => {
    setMessages([]);
    setSessionId(null);
    setViewerTarget(null);
  }, [paper?.id]);

  // Auto-scroll
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages]);

  // Load sessions
  const loadSessions = useCallback(async () => {
    if (!token) return;
    try {
      const data = await fetchSessions(token);
      setSessions(data.sessions || []);
    } catch { /* ignore */ }
  }, [token]);

  useEffect(() => { loadSessions(); }, [loadSessions]);

  const loadExistingSession = async (sid: string) => {
    if (!token) return;
    try {
      const data = await fetchSession(sid, token);
      setSessionId(data.id);
      setMessages(data.messages || []);
      setShowSessions(false);
    } catch { /* ignore */ }
  };

  const newChat = () => {
    setMessages([]);
    setSessionId(null);
  };

  const handleSend = async () => {
    const text = input.trim();
    if (!text || loading || selectedPdfIds.length === 0) return;

    const userMsg: ChatMessage = {
      role: 'user',
      content: text,
      ts: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const result = await ragChat(text, selectedPdfIds, token, sessionId);
      setSessionId(result.session_id);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: result.answer,
          ts: new Date().toISOString(),
          tokens: { prompt: result.prompt_tokens, completion: result.completion_tokens },
          retrieval_query: result.retrieval_query || undefined,
          citations: result.citations?.map((c: any) => ({
            source_id: c.source_id,
            chunk_id: c.chunk_id || '',
            chunk_text: c.chunk_text || '',
            score: c.score || 0,
            pdf_id: c.pdf_id || '',
            pdf_name: c.pdf_name || '',
            page_number: c.page_number,
            block_id: c.block_id,
            section_path: c.section_path,
            source_block_type: c.source_block_type,
            retrieval_sources: c.retrieval_sources,
          })),
        },
      ]);
      loadSessions();
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `Error: ${err.message}`, ts: new Date().toISOString() },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteSession = async (sid: string) => {
    if (!token) return;
    try {
      await deleteSession(sid, token);
      if (sessionId === sid) newChat();
      loadSessions();
    } catch { /* ignore */ }
  };

  const handleSummarize = async () => {
    if (!token || selectedPdfIds.length === 0) return;
    setSummarizing(true);
    try {
      const result = await summarizePdf(selectedPdfIds[0], token);
      setMessages((prev) => [
        ...prev,
        { role: 'user', content: '📋 Summarize this paper', ts: new Date().toISOString() },
        { role: 'assistant', content: result.summary, ts: new Date().toISOString(),
          citations: [], tokens: { prompt: 0, completion: 0 } },
      ]);
    } catch (err: any) {
      setMessages((prev) => [...prev,
        { role: 'assistant', content: `Summarize failed: ${err.message}`, ts: new Date().toISOString() }
      ]);
    } finally {
      setSummarizing(false);
    }
  };

  const visibleSessions = paper
    ? sessions.filter((s) => s.pdf_ids?.includes(paper.id))
    : sessions;

  return (
    <div className="flex h-full bg-[var(--color-surface)] overflow-hidden">
      {/* PDF Viewer (left) */}
      <div className="flex-1 border-r border-[var(--color-line)] overflow-hidden flex flex-col bg-[#525659]">
        {pdfUrl ? (
          <div className="relative w-full h-full flex flex-col">
            <div className="bg-[#323639] text-white px-4 py-2 flex justify-between items-center text-sm border-b border-black/20 z-10">
              <span className="font-medium flex items-center gap-2 text-xs">
                <FileText size={16} className="text-[var(--color-accent)]" />
                {paper?.original_name || 'PDF Viewer'}
              </span>
              <button onClick={onBack} className="text-[10px] bg-[var(--color-surface)]/10 hover:bg-[var(--color-surface)]/20 px-3 py-1 rounded transition-colors">
                ← Back to Library
              </button>
            </div>
            <div className="relative flex-1">
              <PDFViewer 
                url={pdfUrl} 
                targetPage={viewerTarget?.page} 
              />
            </div>
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center text-[var(--color-ink-secondary)] bg-[var(--color-surface)]">
            <div className="text-center space-y-4">
              <FileText size={48} className="mx-auto opacity-30" />
              <p className="text-sm">No PDF selected. Pick one from the library.</p>
              <button onClick={onBack} className="text-[var(--color-accent)] underline text-xs font-bold">
                Go to Library
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Chat Sidebar (right) */}
      <div className="w-[500px] flex flex-col h-full bg-[#fcfcfd]">
        {/* Header */}
        <div className="p-4 bg-[var(--color-surface)] border-b border-[var(--color-line-subtle)] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 bg-[var(--color-accent-subtle)] text-[var(--color-accent)] rounded-lg">
              <MessageSquare size={16} />
            </div>
            <span className="text-sm font-bold">PaperSanta Chat</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleSummarize}
              disabled={summarizing || selectedPdfIds.length === 0}
              className="flex items-center gap-1 text-[10px] font-bold text-amber-600 hover:text-amber-700 border border-amber-200 px-2 py-1 rounded-lg disabled:opacity-50"
            >
              <Sparkles size={12} />
              {summarizing ? 'Summarizing...' : 'Summarize'}
            </button>
            <button
              onClick={() => setShowSessions(!showSessions)}
              className="text-[10px] font-bold text-[var(--color-ink-secondary)] hover:text-[var(--color-ink)] border border-[var(--color-line)] px-2 py-1 rounded-lg"
            >
              History
            </button>
            <button
              onClick={newChat}
              className="text-[10px] font-bold text-[var(--color-accent)] hover:text-[var(--color-accent)] border border-[var(--color-accent-subtle)] px-2 py-1 rounded-lg"
            >
              + New
            </button>
          </div>
        </div>

        {/* Sessions sidebar */}
        {showSessions && (
          <div className="border-b border-[var(--color-line-subtle)] bg-[var(--color-surface)] max-h-48 overflow-y-auto">
            <div className="px-4 py-2 text-[10px] font-bold text-[var(--color-ink-secondary)] uppercase tracking-wider">Chat History</div>
            {visibleSessions.length === 0 ? (
              <div className="px-4 py-3 text-xs text-[var(--color-ink-secondary)] italic">No chat history</div>
            ) : (
              visibleSessions.map((s) => (
                <div
                  key={s.id}
                  className={cn(
                    'flex items-center justify-between px-4 py-2 text-xs cursor-pointer hover:bg-[var(--color-surface-hover)] transition-colors',
                    sessionId === s.id && 'bg-[var(--color-accent-subtle)]'
                  )}
                  onClick={() => loadExistingSession(s.id)}
                >
                  <span className="truncate flex-1">{s.title || 'Untitled'}</span>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDeleteSession(s.id); }}
                    className="p-1 text-[var(--color-ink-secondary)] hover:text-[var(--color-danger)]"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              ))
            )}
          </div>
        )}

        {/* Active PDF scope */}
        <div className="px-4 py-2 border-b border-[var(--color-line-subtle)]">
          <div className="flex items-center gap-2 text-xs text-[var(--color-ink)]">
            <FileText size={14} className="text-[var(--color-accent)] shrink-0" />
            <span className="truncate">
              {paper ? paper.original_name : 'No PDF selected'}
            </span>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-8" ref={scrollRef}>
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-[var(--color-ink-secondary)] space-y-3">
              <MessageSquare size={32} className="opacity-30" />
              <p className="text-xs italic">Ask a question about the opened PDF.</p>
            </div>
          ) : (
            messages.map((m, idx) => (
              <div key={m.ts + '-' + idx} className="flex gap-3">
                <div
                  className={cn(
                    'w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center font-bold text-xs',
                    m.role === 'user' ? 'bg-[var(--color-surface-hover)] text-[var(--color-ink)]' : 'bg-[var(--color-accent-subtle)] text-[var(--color-accent)]'
                  )}
                >
                  {m.role === 'user' ? 'U' : 'AI'}
                </div>
                <div className="space-y-1 flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-bold text-[var(--color-ink)]">
                      {m.role === 'user' ? 'You' : 'PaperSanta'}
                    </span>
                  </div>
                  <div className="p-4 rounded-2xl text-xs leading-relaxed border bg-[var(--color-surface)] border-[var(--color-line-subtle)] text-[var(--color-ink)] shadow-sm">
                    {m.role === 'user' ? (
                      m.content
                    ) : (
                      <MarkdownRenderer content={m.content} />
                    )}
                  </div>
                  {m.citations && m.citations.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {m.citations.map((c: any, i) => (
                        <button
                          key={i}
                          title={c.chunk_text}
                          onClick={() => {
                            if (c.page_number && c.pdf_id === paper?.id) {
                              setViewerTarget({ page: c.page_number, text: c.chunk_text });
                           }
                          }}
                        className="text-[10px] bg-[var(--color-accent-subtle)] hover:bg-[var(--color-accent-subtle)] border border-[var(--color-accent-subtle)] text-[var(--color-accent)] px-2 py-1 rounded-full truncate max-w-[180px] transition-colors cursor-pointer flex items-center gap-1 font-medium"
                        >
                          📄 [{c.source_id || i + 1}] Trang {c.page_number || 1}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
          {loading && (
            <div className="flex gap-3 animate-pulse">
              <div className="w-8 h-8 rounded-full bg-[var(--color-accent-subtle)] text-[var(--color-accent)] flex items-center justify-center text-xs font-bold">AI</div>
              <div className="bg-[var(--color-surface)] border border-[var(--color-line-subtle)] p-3 rounded-xl text-[10px] text-[var(--color-ink-secondary)] italic">Thinking...</div>
            </div>
          )}
        </div>

        {/* Input */}
        <div className="p-4 bg-[var(--color-surface)] border-t border-[var(--color-line-subtle)]">
          <div className="flex items-center bg-[#F9FAFB] border border-[var(--color-line-subtle)] rounded-2xl p-1 focus-within:ring-2 focus-within:ring-blue-100 transition-all shadow-inner">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), handleSend())}
              placeholder={
                selectedPdfIds.length === 0
                  ? 'Open a PDF to start chatting...'
                  : 'Ask a question about this PDF...'
              }
              disabled={loading || selectedPdfIds.length === 0}
              className="flex-1 bg-transparent px-4 py-2 text-xs focus:outline-none placeholder:text-[var(--color-ink-secondary)] disabled:opacity-50"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || loading || selectedPdfIds.length === 0}
              className="bg-[var(--color-accent)] text-white p-2 rounded-xl hover:bg-[var(--color-accent)]/80 disabled:opacity-50 transition-all shadow-md shadow-[var(--color-accent-subtle)]"
            >
              <Send size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
