import { useCallback, useEffect, useRef, useState } from 'react';
import { FileText, Send, AlertCircle, MessageSquare, LayoutDashboard, ChevronRight, Trash2, Sparkles } from 'lucide-react';
import { motion } from 'motion/react';
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

export default function Reader({ paper, allPapers, onBack }: ReaderProps) {
  const { session: authSession } = useAuth();
  const token = authSession?.access_token;

  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [selectedPdfIds, setSelectedPdfIds] = useState<string[]>(() =>
    paper ? [paper.id] : []
  );
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [showSessions, setShowSessions] = useState(false);
  const [showPdfSelector, setShowPdfSelector] = useState(false);
  const [errorVisible, setErrorVisible] = useState<string | null>(null);
  const [summarizing, setSummarizing] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [targetPage, setTargetPage] = useState<number | null>(null);
  const [viewerTarget, setViewerTarget] = useState<{ page: number; text?: string } | null>(null);

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
      if (data.pdf_ids?.length) setSelectedPdfIds(data.pdf_ids);
      setShowSessions(false);
    } catch { /* ignore */ }
  };

  const newChat = () => {
    setMessages([]);
    setSessionId(null);
  };

  const togglePdf = (id: string) => {
    setSelectedPdfIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
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
          citations: result.citations?.map((c: any) => ({
            source_id: c.source_id,
            chunk_id: c.chunk_id || '',
            chunk_text: c.chunk_text || '',
            score: c.score || 0,
            pdf_id: c.pdf_id || '',
            pdf_name: c.pdf_name || '',
            page_number: c.page_number,
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

  const selectedDocs = allPapers.filter((d) => selectedPdfIds.includes(d.id));

  return (
    <div className="flex h-full bg-white overflow-hidden">
      {/* PDF Viewer (left) */}
      <div className="flex-1 border-r border-gray-200 overflow-hidden flex flex-col bg-[#525659]">
        {pdfUrl ? (
          <div className="relative w-full h-full flex flex-col">
            <div className="bg-[#323639] text-white px-4 py-2 flex justify-between items-center text-sm border-b border-black/20 z-10">
              <span className="font-medium flex items-center gap-2 text-xs">
                <FileText size={16} className="text-blue-400" />
                {paper?.original_name || 'PDF Viewer'}
              </span>
              <button onClick={onBack} className="text-[10px] bg-white/10 hover:bg-white/20 px-3 py-1 rounded transition-colors">
                ← Back to Library
              </button>
            </div>
            <div className="relative flex-1">
              <PDFViewer 
                url={pdfUrl} 
                targetPage={viewerTarget?.page} 
                targetText={viewerTarget?.text} 
              />
            </div>
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-400 bg-white">
            <div className="text-center space-y-4">
              <FileText size={48} className="mx-auto opacity-30" />
              <p className="text-sm">No PDF selected. Pick one from the library.</p>
              <button onClick={onBack} className="text-blue-500 underline text-xs font-bold">
                Go to Library
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Chat Sidebar (right) */}
      <div className="w-[500px] flex flex-col h-full bg-[#fcfcfd]">
        {/* Header */}
        <div className="p-4 bg-white border-b border-gray-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 bg-blue-50 text-blue-600 rounded-lg">
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
              className="text-[10px] font-bold text-gray-500 hover:text-gray-700 border border-gray-200 px-2 py-1 rounded-lg"
            >
              History
            </button>
            <button
              onClick={newChat}
              className="text-[10px] font-bold text-blue-600 hover:text-blue-700 border border-blue-200 px-2 py-1 rounded-lg"
            >
              + New
            </button>
          </div>
        </div>

        {/* Sessions sidebar */}
        {showSessions && (
          <div className="border-b border-gray-100 bg-gray-50 max-h-48 overflow-y-auto">
            <div className="px-4 py-2 text-[10px] font-bold text-gray-400 uppercase tracking-wider">Chat History</div>
            {sessions.length === 0 ? (
              <div className="px-4 py-3 text-xs text-gray-400 italic">No chat history</div>
            ) : (
              sessions.map((s) => (
                <div
                  key={s.id}
                  className={cn(
                    'flex items-center justify-between px-4 py-2 text-xs cursor-pointer hover:bg-gray-100 transition-colors',
                    sessionId === s.id && 'bg-blue-50'
                  )}
                  onClick={() => loadExistingSession(s.id)}
                >
                  <span className="truncate flex-1">{s.title || 'Untitled'}</span>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDeleteSession(s.id); }}
                    className="p-1 text-gray-300 hover:text-red-500"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              ))
            )}
          </div>
        )}

        {/* PDF Selector */}
        <div className="px-4 py-2 border-b border-gray-100">
          <button
            onClick={() => setShowPdfSelector(!showPdfSelector)}
            className="flex items-center gap-2 text-xs text-gray-600 hover:text-gray-900"
          >
            <LayoutDashboard size={14} />
            <span>
              {selectedDocs.length === 0
                ? 'Select PDFs to chat...'
                : `${selectedDocs.length} PDF(s) selected`}
            </span>
            <ChevronRight size={12} className={cn('transition-transform', showPdfSelector && 'rotate-90')} />
          </button>
          {showPdfSelector && (
            <div className="mt-2 space-y-1 max-h-40 overflow-y-auto">
              {allPapers.length === 0 ? (
                <div className="text-xs text-gray-400 italic px-2">No PDFs uploaded yet</div>
              ) : (
                allPapers.map((doc) => (
                  <label key={doc.id} className="flex items-center gap-2 px-2 py-1.5 text-xs hover:bg-gray-50 rounded cursor-pointer">
                    <input
                      type="checkbox"
                      checked={selectedPdfIds.includes(doc.id)}
                      onChange={() => togglePdf(doc.id)}
                      className="accent-blue-600"
                    />
                    <span className="truncate flex-1">{doc.original_name}</span>
                  </label>
                ))
              )}
            </div>
          )}
          {selectedDocs.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1">
              {selectedDocs.slice(0, 3).map((d) => (
                <span key={d.id} className="inline-flex items-center gap-1 bg-blue-50 text-blue-700 text-[10px] px-2 py-0.5 rounded-full">
                  {d.original_name}
                  <button onClick={() => togglePdf(d.id)} className="hover:text-red-500">×</button>
                </span>
              ))}
              {selectedDocs.length > 3 && (
                <span className="text-[10px] text-gray-400 px-1">+{selectedDocs.length - 3}</span>
              )}
            </div>
          )}
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-8" ref={scrollRef}>
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-400 space-y-3">
              <MessageSquare size={32} className="opacity-30" />
              <p className="text-xs italic">Select PDFs above and ask a question.</p>
            </div>
          ) : (
            messages.map((m, idx) => (
              <div key={m.ts + '-' + idx} className="flex gap-3">
                <div
                  className={cn(
                    'w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center font-bold text-xs',
                    m.role === 'user' ? 'bg-gray-100 text-gray-600' : 'bg-blue-100 text-blue-600'
                  )}
                >
                  {m.role === 'user' ? 'U' : 'AI'}
                </div>
                <div className="space-y-1 flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-bold text-gray-900">
                      {m.role === 'user' ? 'You' : 'PaperSanta'}
                    </span>
                  </div>
                  <div className="p-4 rounded-2xl text-xs leading-relaxed border bg-white border-gray-100 text-gray-700 shadow-sm">
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
                            if (c.page_number) {
                              setViewerTarget({ page: c.page_number, text: c.chunk_text });
                           }
                          }}
                        className="text-[10px] bg-blue-50 hover:bg-blue-100 border border-blue-200 text-blue-600 px-2 py-1 rounded-full truncate max-w-[180px] transition-colors cursor-pointer flex items-center gap-1 font-medium"
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
              <div className="w-8 h-8 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center text-xs font-bold">AI</div>
              <div className="bg-white border border-gray-100 p-3 rounded-xl text-[10px] text-gray-400 italic">Thinking...</div>
            </div>
          )}
        </div>

        {/* Input */}
        <div className="p-4 bg-white border-t border-gray-100">
          <div className="flex items-center bg-[#F9FAFB] border border-gray-100 rounded-2xl p-1 focus-within:ring-2 focus-within:ring-blue-100 transition-all shadow-inner">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), handleSend())}
              placeholder={
                selectedPdfIds.length === 0
                  ? 'Select PDFs to start chatting...'
                  : 'Ask a question about the selected PDFs...'
              }
              disabled={loading || selectedPdfIds.length === 0}
              className="flex-1 bg-transparent px-4 py-2 text-xs focus:outline-none placeholder:text-gray-400 disabled:opacity-50"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || loading || selectedPdfIds.length === 0}
              className="bg-blue-600 text-white p-2 rounded-xl hover:bg-blue-700 disabled:opacity-50 transition-all shadow-md shadow-blue-100"
            >
              <Send size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
