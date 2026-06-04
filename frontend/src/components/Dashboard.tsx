import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, FileText, Search, ArrowUpDown, Trash2, Star, Clock, CheckCircle2, AlertCircle, Loader2, RotateCcw, X } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { useAuth } from '../context/AuthContext';
import { cn } from '../lib/utils';
import { uploadPdfFile, deletePdfById, getPdfStatus, indexPdfFile,toggleFavoritePdf } from '../api/pdf';
import type { PDFDocument, SortOption } from '../types';

interface DashboardProps {
  papers: PDFDocument[];
  onPaperAdded: () => void;
  onSelectPaper: (paper: PDFDocument) => void;
  onPaperDeleted: () => void;
}

const STATUS_LABEL: Record<string, string> = {
  pending: 'Đang xử lý',
  extracted: 'Đang xử lý',
  indexed: 'Hoàn tất',
  failed: 'Thất bại',
};

export default function Dashboard({ papers, onPaperAdded, onSelectPaper, onPaperDeleted }: DashboardProps) {
  const { user, session, signIn } = useAuth();
  const token = session?.access_token;
  const [isUploading, setIsUploading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<SortOption>('newest');
  const [paperToDelete, setPaperToDelete] = useState<{ id: string; title: string } | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [toast, setToast] = useState<{ type: 'success' | 'error'; message: string; pdfId?: string } | null>(null);
  const [retrying, setRetrying] = useState<string | null>(null);

  const pollStatus = useCallback(async (id: string) => {
    const maxAttempts = 60;
    for (let i = 0; i < maxAttempts; i++) {
      await new Promise((r) => setTimeout(r, 2000));
      try {
        const doc = await getPdfStatus(id, token);
        if (doc.status === 'indexed') {
          setToast({ type: 'success', message: `${doc.original_name} đã xử lý xong` });
          setIsUploading(false);
          return;
        }
        if (doc.status === 'failed') {
          setToast({ type: 'error', message: doc.error_message || `${doc.original_name} xử lý thất bại`, pdfId: id });
          setIsUploading(false);
          return;
        }
      } catch {
        // polling
      }
    }
    setToast({ type: 'error', message: 'Xử lý quá lâu, vui lòng thử lại', pdfId: id });
    setIsUploading(false);
  }, [token]);

  const handleRetry = async (id: string) => {
    setRetrying(id);
    try {
      await indexPdfFile(id, token);
      setToast(null);
      pollStatus(id);
    } catch (err: any) {
      setToast({ type: 'error', message: err.message || 'Không thể thử lại' });
    } finally {
      setRetrying(null);
    }
  };

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      if (!user) {
        signIn();
        return;
      }

      const file = acceptedFiles[0];
      if (!file) return;

      setIsUploading(true);
      try {
        const doc = await uploadPdfFile(file, token);
        onPaperAdded();
        if (doc?.id) {
          pollStatus(doc.id);
        } else {
          setIsUploading(false);
        }
      } catch (err: any) {
        setToast({ type: 'error', message: err.message || 'Upload thất bại' });
        setIsUploading(false);
      }
    },
    [user, token, signIn, onPaperAdded, pollStatus]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    multiple: false,
  });
  const handleToggleFavorite = async (e: React.MouseEvent, paper: PDFDocument) => {
    e.stopPropagation(); // Chặn sự kiện bấm vào dòng (mở file)
    if (!token) return;
    
    try {
      await toggleFavoritePdf(paper.id, token);
      
      // Gọi hàm này để báo Component cha fetch lại danh sách mới
      onPaperAdded(); 
      
      setToast({ 
        type: 'success', 
        message: paper.is_favorite ? 'Đã bỏ yêu thích' : 'Đã thêm vào yêu thích' 
      });
    } catch (err: any) {
      setToast({ type: 'error', message: 'Lỗi cập nhật yêu thích' });
    }
  };
  const handleDelete = async () => {
    if (!paperToDelete) return;
    setIsDeleting(true);
    try {
      await deletePdfById(paperToDelete.id, token);
      onPaperDeleted();
      setPaperToDelete(null);
    } catch (err: any) {
      setToast({ type: 'error', message: err.message || 'Delete failed' });
    } finally {
      setIsDeleting(false);
    }
  };

  const confirmDelete = (e: React.MouseEvent, paper: PDFDocument) => {
    e.stopPropagation();
    setPaperToDelete({ id: paper.id, title: paper.original_name });
  };

  const filteredAndSorted = [...papers]
    .filter((p) => p.original_name.toLowerCase().includes(searchQuery.toLowerCase()))
    .sort((a, b) => {
      switch (sortBy) {
        case 'newest':
          return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
        case 'oldest':
          return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
        case 'name':
          return a.original_name.localeCompare(b.original_name);
        default:
          return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      }
    });

  const formatDate = (iso: string) => {
    const diff = Date.now() - new Date(iso).getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    if (days === 0) return 'Today';
    if (days === 1) return 'Yesterday';
    if (days < 7) return `${days}d ago`;
    return new Date(iso).toLocaleDateString();
  };

  return (
    <div className="flex-1 bg-[var(--color-surface)] overflow-y-auto">
      <div className="max-w-5xl mx-auto p-12 space-y-12">
        {/* Welcome */}
        <header className="text-center space-y-2">
          <h2 className="text-2xl font-bold tracking-tight">
            Welcome back, {user?.displayName?.split(' ')[0] || 'Researcher'}
          </h2>
          <p className="text-[var(--color-ink-secondary)] text-sm">Which paper shall we research today?</p>
        </header>

        {/* Upload Zone */}
        <div
          {...getRootProps()}
          className={cn(
            'border-2 border-dashed rounded-3xl p-12 flex flex-col items-center justify-center gap-6 transition-all cursor-pointer bg-[var(--color-surface-hover)]/50',
            isDragActive ? 'border-[var(--color-accent)] bg-[var(--color-accent-subtle)]/30' : 'border-[var(--color-line)] hover:border-[var(--color-accent)]',
            isUploading ? 'opacity-50 pointer-events-none' : ''
          )}
        >
          <input {...getInputProps()} />
          <div className="w-16 h-16 rounded-2xl bg-[var(--color-surface)] shadow-xl shadow-[var(--color-accent-subtle)] flex items-center justify-center text-[var(--color-accent)]">
            {isUploading ? (
              <Loader2 size={32} className="animate-spin" />
              ) : (
              <Upload size={32} />
          )}
          </div>
          <div className="text-center">
            <p className="text-lg font-bold text-[var(--color-ink)]">
              {isUploading ? 'Processing Paper...' : 'Upload your file'}
            </p>
            <p className="text-sm text-[var(--color-ink-secondary)]">Click to browse or drag and drop your PDFs here</p>
          </div>
        </div>

        {/* Library */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-[var(--color-ink-secondary)] uppercase tracking-widest flex items-center gap-2">
              Your Uploaded Library
            </h3>
            <div className="flex items-center gap-4">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-ink-secondary)]" size={14} />
                <input
                  type="text"
                  placeholder="Search for files..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9 pr-4 py-1.5 border border-[var(--color-line)] rounded-lg text-xs text-[var(--color-ink)] placeholder:text-[var(--color-ink-secondary)] focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)] w-48 bg-[var(--color-surface)]"
                />
              </div>
              <div className="flex items-center gap-2 text-xs font-bold text-[var(--color-ink-secondary)] border border-[var(--color-line)] rounded-lg px-2 py-1.5 bg-[var(--color-surface)]">
                <ArrowUpDown size={14} />
                <span>Sort by</span>
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value as SortOption)}
                  className="bg-transparent text-[var(--color-ink)] focus:outline-none cursor-pointer border-none p-0 ml-1"
                >
                  <option value="newest">Newest</option>
                  <option value="oldest">Oldest</option>
                  <option value="name">A-Z</option>
                </select>
              </div>
            </div>
          </div>

          {/* Paper List */}
          <div className="border border-[var(--color-line-subtle)] rounded-2xl overflow-hidden shadow-sm bg-[var(--color-surface)]">
            {filteredAndSorted.length === 0 ? (
              <div className="p-20 text-center text-[var(--color-ink-secondary)] italic text-sm">
                {isUploading ? 'Uploading...' : 'Your research library is currently empty.'}
              </div>
            ) : (
              <table className="w-full text-left">
                <tbody>
                  {filteredAndSorted.map((paper) => (
                    <tr
                      key={paper.id}
                      onClick={() => onSelectPaper(paper)}
                      className="group border-b border-[var(--color-line-subtle)] last:border-0 hover:bg-[var(--color-surface-hover)]/50 transition-colors cursor-pointer"
                    >
                      <td className="py-4 pl-6 w-12">
                        <div className="w-8 h-8 rounded-lg bg-[var(--color-accent-subtle)] flex items-center justify-center text-[var(--color-accent)]">
                          <FileText size={16} />
                        </div>
                      </td>
                      <td className="py-4 px-4">
                        <div className="flex items-center gap-3">
                          <p className="text-sm font-bold text-[var(--color-ink)] truncate max-w-[320px]">
                            {paper.original_name}
                          </p>
                          <span className={cn(
                            'shrink-0 text-[10px] font-bold px-2 py-0.5 rounded-full border',
                            paper.status === 'indexed' && 'text-[var(--color-success)] bg-[var(--color-success-subtle)] border-[var(--color-success-border)]',
                            paper.status === 'failed' && 'text-[var(--color-danger)] bg-[var(--color-danger-subtle)] border-[var(--color-danger-subtle)]',
                            (paper.status === 'pending' || paper.status === 'extracted') && 'text-[var(--color-warning)] bg-[var(--color-warning-subtle)] border-[var(--color-warning-border)]',
                          )}>
                            {paper.status === 'pending' || paper.status === 'extracted' ? (
                              <span className="flex items-center gap-1">
                                <Loader2 size={10} className="animate-spin" />
                                {STATUS_LABEL[paper.status]}
                              </span>
                            ) : paper.status === 'indexed' ? (
                              <span className="flex items-center gap-1">
                                <CheckCircle2 size={10} />
                                {STATUS_LABEL[paper.status]}
                              </span>
                            ) : (
                              <span className="flex items-center gap-1">
                                <AlertCircle size={10} />
                                {STATUS_LABEL[paper.status]}
                              </span>
                            )}
                          </span>
                        </div>
                      </td>
                      <td className="py-4 px-4 text-right">
                        <span className="text-[11px] text-[var(--color-ink-secondary)] font-medium flex items-center gap-1">
                          <Clock size={11} />
                          {formatDate(paper.created_at)}
                        </span>
                      </td>
                      <td className="py-4 px-6 text-right w-20">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={(e) => handleToggleFavorite(e, paper)}
                            className="p-1.5 text-[var(--color-ink-secondary)] hover:text-[var(--color-accent)] hover:bg-[var(--color-accent-subtle)] rounded-md transition-colors"
                            title={paper.is_favorite ? "Bỏ yêu thích" : "Yêu thích"}
                          >
                            <Star 
                              size={14} 
                              className={paper.is_favorite ? "fill-[var(--color-accent)] text-[var(--color-accent)]" : ""} 
                            />
                          </button>
                          <button
                            onClick={(e) => confirmDelete(e, paper)}
                            className="p-1.5 text-[var(--color-ink-secondary)] hover:text-[var(--color-danger)] hover:bg-[var(--color-danger-subtle)] rounded-md transition-colors"
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      <AnimatePresence>
        {paperToDelete && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="bg-[var(--color-surface)] border border-[var(--color-line)] rounded-2xl p-8 max-w-md w-full shadow-2xl space-y-6"
            >
              <div className="flex items-center gap-4 text-[var(--color-danger)]">
                <div className="w-12 h-12 rounded-full bg-[var(--color-danger-subtle)] flex items-center justify-center">
                  <Trash2 size={24} />
                </div>
                <h3 className="text-xl font-bold">Delete Paper?</h3>
              </div>
              <p className="text-[var(--color-ink-secondary)]">
                Are you sure you want to delete{' '}
                <span className="font-bold text-[var(--color-ink)]">"{paperToDelete.title}"</span>? This action cannot be undone.
              </p>
              <div className="flex gap-3 pt-2">
                <button
                  onClick={() => setPaperToDelete(null)}
                  disabled={isDeleting}
                  className="flex-1 px-4 py-3 border border-[var(--color-line)] rounded-xl font-bold hover:bg-[var(--color-surface-hover)] transition-colors disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleDelete}
                  disabled={isDeleting}
                  className="flex-1 px-4 py-3 bg-[var(--color-danger)] text-white rounded-xl font-bold hover:bg-[var(--color-danger)]/80 transition-colors shadow-lg shadow-[var(--color-danger-subtle)] disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {isDeleting ? 'Deleting...' : 'Confirm Delete'}
                </button>
              </div>
            </motion.div>
          </div>
        )}

        {toast && (
          <div className="fixed bottom-8 right-8 z-50">
            <motion.div
              initial={{ x: 100, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: 100, opacity: 0 }}
              className={cn(
                'p-4 rounded-xl shadow-xl flex items-center gap-3 pr-6',
                toast.type === 'success' ? 'bg-green-600 text-white' : 'bg-[var(--color-danger)] text-white'
              )}
            >
              <div className={cn(
                'w-8 h-8 rounded-full flex items-center justify-center shrink-0',
                toast.type === 'success' ? 'bg-white/20' : 'bg-white/20'
              )}>
                {toast.type === 'success' ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
              </div>
              <div className="min-w-0 max-w-xs">
                <p className="font-bold text-sm">{toast.type === 'success' ? 'Hoàn tất' : 'Lỗi'}</p>
                <p className="text-xs opacity-90 truncate">{toast.message}</p>
              </div>
              <div className="flex items-center gap-2 ml-2">
                {toast.type === 'error' && toast.pdfId && (
                  <button
                    onClick={() => handleRetry(toast.pdfId!)}
                    disabled={retrying === toast.pdfId}
                    className="p-1.5 hover:bg-white/20 rounded-lg transition-colors disabled:opacity-50"
                    title="Thử lại"
                  >
                    {retrying === toast.pdfId ? (
                      <Loader2 size={16} className="animate-spin" />
                    ) : (
                      <RotateCcw size={16} />
                    )}
                  </button>
                )}
                <button onClick={() => setToast(null)} className="p-1.5 hover:bg-white/20 rounded-lg transition-colors">
                  <X size={16} />
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
