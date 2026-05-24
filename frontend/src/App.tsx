import { useCallback, useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { AuthProvider, useAuth } from './context/AuthContext';
import Sidebar from './components/Sidebar';
import Dashboard from './components/Dashboard';
import Reader from './components/Reader';
import Comparison from './components/Comparison';
import Discovery from './components/Discovery';
import { fetchPdfs, uploadPdfFile } from './api/pdf';
import type { PDFDocument, ActiveView } from './types';

function LoginPage() {
  const { signIn } = useAuth();
  return (
    <div className="h-screen flex items-center justify-center bg-[#F8F9FA]">
      <div className="text-center p-12 bg-white border border-gray-200 rounded-2xl max-w-sm w-[90%] shadow-sm">
        <div className="text-3xl font-bold text-[#1A1A1A] mb-2">
          Paper<span className="text-blue-600">Santa</span>
        </div>
        <p className="text-gray-500 mb-8 text-sm">PDF Storage & RAG Pipeline</p>
        <button
          onClick={signIn}
          className="inline-flex items-center gap-2.5 px-7 py-3 border border-gray-200 rounded-lg bg-white text-sm font-medium hover:border-blue-500 hover:shadow-sm transition-all"
        >
          <svg width="20" height="20" viewBox="0 0 48 48">
            <path fill="#FFC107" d="M43.611 20.083H42V20H24v8h11.303c-1.649 4.657-6.08 8-11.303 8-6.627 0-12-5.373-12-12s5.373-12 12-12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 12.955 4 4 12.955 4 24s8.955 20 20 20 20-8.955 20-20c0-1.341-.138-2.65-.389-3.917z"/>
            <path fill="#FF3D00" d="m6.306 14.691 6.571 4.819C14.655 15.108 18.961 12 24 12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 16.318 4 9.656 8.337 6.306 14.691z"/>
            <path fill="#4CAF50" d="M24 44c5.166 0 9.86-1.977 13.409-5.192l-6.19-5.238A11.91 11.91 0 0 1 24 36c-5.202 0-9.619-3.317-11.283-7.946l-6.522 5.025C9.505 39.556 16.227 44 24 44z"/>
            <path fill="#1976D2" d="M43.611 20.083H42V20H24v8h11.303a12.04 12.04 0 0 1-4.087 5.571l.003-.002 6.19 5.238C36.971 39.205 44 34 44 24c0-1.341-.138-2.65-.389-3.917z"/>
          </svg>
          Sign in with Google
        </button>
      </div>
    </div>
  );
}

function AppContent() {
  const { user, session, loading } = useAuth();
  const token = session?.access_token;

  const [activeTab, setActiveTab] = useState<ActiveView>('dashboard');
  const [papers, setPapers] = useState<PDFDocument[]>([]);
  const [selectedPaper, setSelectedPaper] = useState<PDFDocument | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchPapers = useCallback(async () => {
    if (!token) return;
    try {
      const data = await fetchPdfs(token);
      setPapers(data.documents ?? []);
    } catch (err) {
      console.error('fetch papers error:', err);
    }
  }, [token]);

  useEffect(() => {
    if (!loading) {
      if (user) fetchPapers();
      else setPapers([]);
    }
  }, [user, loading, fetchPapers]);

  const handleUpload = async (file: File) => {
    setUploading(true);
    try {
      await uploadPdfFile(file, token);
      await fetchPapers();
    } catch (err) {
      console.error('upload error:', err);
    } finally {
      setUploading(false);
    }
  };

  const handleSelectPaper = (paper: PDFDocument) => {
    setSelectedPaper(paper);
    setActiveTab('reader');
  };

  const handleSelectRecent = (id: string) => {
    const paper = papers.find((p) => p.id === id);
    if (paper) handleSelectPaper(paper);
  };

  const recentItems = [...papers]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 5)
    .map((p) => ({ id: p.id, title: p.original_name }));

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center bg-[#F8F9FA]">
        <motion.div
          animate={{ scale: [1, 1.1, 1] }}
          transition={{ repeat: Infinity, duration: 2 }}
          className="text-2xl font-bold tracking-tighter"
        >
          PaperSanta
        </motion.div>
      </div>
    );
  }

  if (!user) {
    return <LoginPage />;
  }

  return (
    <div className="flex h-screen bg-[#F8F9FA] overflow-hidden">
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        recentItems={recentItems}
        onSelectItem={handleSelectRecent}
        uploading={uploading}
        fileInputRef={fileInputRef}
      />

      <main className="flex-1 overflow-hidden relative">
        <AnimatePresence mode="wait">
          {activeTab === 'dashboard' && (
            <motion.div
              key="dashboard"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              className="h-full overflow-y-auto"
            >
              <Dashboard
                papers={papers}
                onPaperAdded={fetchPapers}
                onSelectPaper={handleSelectPaper}
                onPaperDeleted={fetchPapers}
              />
            </motion.div>
          )}

          {activeTab === 'reader' && (
            <motion.div
              key="reader"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              className="h-full"
            >
              <Reader
                paper={selectedPaper}
                allPapers={papers}
                onBack={() => { setSelectedPaper(null); setActiveTab('dashboard'); }}
              />
            </motion.div>
          )}

          {activeTab === 'comparison' && (
            <motion.div
              key="comparison"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              className="h-full overflow-y-auto"
            >
              <Comparison papers={papers} />
            </motion.div>
          )}

          {activeTab === 'discovery' && (
            <motion.div
              key="discovery"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              className="h-full overflow-y-auto"
            >
              <Discovery />
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      {/* Hidden file input for sidebar upload */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) {
            handleUpload(file);
            e.target.value = '';
          }
        }}
      />
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
