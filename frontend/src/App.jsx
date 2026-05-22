import { useCallback, useEffect, useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import AppLayout from './components/AppLayout';
import ToastContainer from './components/ToastContainer';
import { fetchPdfs, getPdfFileUrl, uploadPdfFile, deletePdfById } from './api/pdf';

function LoginPage({ signInWithGoogle }) {
  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-logo">Paper<span>Santa</span></div>
        <p className="login-desc">PDF Storage & RAG Pipeline</p>
        <button className="login-btn" onClick={signInWithGoogle}>
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
  const { user, session, loading, signInWithGoogle, signOut } = useAuth();
  const token = session?.access_token;

  const [documents, setDocuments] = useState([]);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [pdfUrl, setPdfUrl] = useState('');
  const [statusText, setStatusText] = useState('Checking...');
  const [uploading, setUploading] = useState(false);
  const [toastList, setToastList] = useState([]);
  const [activeView, setActiveView] = useState('library');

  const addToast = (message, type = 'info', duration = 3000) => {
    const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    setToastList((prev) => [...prev, { id, message, type }]);
    window.setTimeout(() => {
      setToastList((prev) => prev.filter((toast) => toast.id !== id));
    }, duration);
  };

  const loadDocuments = useCallback(async () => {
    if (!token) return;
    try {
      const data = await fetchPdfs(token);
      setDocuments(data.documents ?? []);
    } catch (err) {
      addToast('Không kết nối được API', 'error', 5000);
    }
  }, [token]);

  const checkHealth = useCallback(async () => {
    try {
      const response = await fetch('/health');
      setStatusText(response.ok ? 'Online' : 'Offline');
    } catch {
      setStatusText('Offline');
    }
  }, []);

  useEffect(() => {
    if (!loading && !user) return;
    loadDocuments();
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, [loadDocuments, checkHealth, loading, user]);

  useEffect(() => {
    if (!selectedDoc) {
      setPdfUrl('');
      return;
    }
    let canceled = false;
    const loadUrl = async () => {
      try {
        const data = await getPdfFileUrl(selectedDoc.id, token);
        if (!canceled) setPdfUrl(data.url);
      } catch {
        if (!canceled) setPdfUrl('/api/pdf/' + selectedDoc.id + '/file');
      }
    };
    loadUrl();
    return () => { canceled = true; };
  }, [selectedDoc, token]);

  const handleUpload = async (file) => {
    setUploading(true);
    try {
      const result = await uploadPdfFile(file, token);
      addToast('Upload thành công: ' + result.original_name, 'success');
      await loadDocuments();
    } catch (err) {
      addToast(err.message || 'Upload thất bại', 'error', 5000);
    } finally {
      setUploading(false);
    }
  };

  const handleSelect = (doc) => {
    setSelectedDoc(doc);
    setActiveView('library');
  };

  const handleDelete = async (doc) => {
    if (!window.confirm('Xóa "' + doc.original_name + '"?')) return;
    try {
      await deletePdfById(doc.id, token);
      addToast('Đã xóa: ' + doc.original_name, 'success');
      if (selectedDoc?.id === doc.id) setSelectedDoc(null);
      await loadDocuments();
    } catch (err) {
      addToast(err.message || 'Xóa thất bại', 'error', 5000);
    }
  };

  const handleViewPdf = (doc) => {
    setSelectedDoc(doc);
    setActiveView('library');
  };

  const handleCloseViewer = () => {
    setSelectedDoc(null);
  };

  const handleSimilar = () => {
    addToast('Similar papers feature coming soon', 'info');
  };

  if (loading) {
    return (
      <div className="login-page">
        <div className="login-card">
          <div className="login-logo">Paper<span>Santa</span></div>
          <p className="login-desc">Loading...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return <LoginPage signInWithGoogle={signInWithGoogle} />;
  }

  return (
    <>
      <AppLayout
        activeView={activeView}
        onNavigate={setActiveView}
        documents={documents}
        selectedDoc={selectedDoc}
        pdfUrl={pdfUrl}
        uploading={uploading}
        userName={user?.user_metadata?.full_name || user?.email?.split('@')[0] || 'User'}
        onUpload={handleUpload}
        onSelectDocument={handleSelect}
        onViewPdf={handleViewPdf}
        onCloseViewer={handleCloseViewer}
        onSimilar={handleSimilar}
      />
      <ToastContainer toasts={toastList} />
    </>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;
