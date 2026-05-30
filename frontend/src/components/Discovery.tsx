import { useEffect, useState } from 'react';
import { Search, ExternalLink, BookOpen, Loader2 } from 'lucide-react';
import { fetchPdfs } from '../api/pdf';
import { searchPapers, searchRelatedPapers } from '../api/search';
import { useAuth } from '../context/AuthContext';
import type { PDFDocument, SearchResult } from '../types';

export default function Discovery() {
  const { session } = useAuth();
  const token = session?.access_token;
  
  // State quản lý Tab đang mở
  const [activeTab, setActiveTab] = useState<'topic' | 'related'>('topic');
  
  // State chung
  const [error, setError] = useState<string | null>(null);
  const [papers, setPapers] = useState<PDFDocument[]>([]);
  
  // State cho Topic Search
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [total, setTotal] = useState(0);
  const [searching, setSearching] = useState(false);
  const [yearFrom, setYearFrom] = useState<number | ''>('');
  const [yearTo, setYearTo] = useState<number | ''>('');
  const [minCitations, setMinCitations] = useState<number | ''>('');
  
  // State cho Related Search
  const [selectedPdfId, setSelectedPdfId] = useState('');
  const [relatedResults, setRelatedResults] = useState<SearchResult[] | null>(null);
  const [relatedSearching, setRelatedSearching] = useState(false);
  const [relatedLimit, setRelatedLimit] = useState<number>(10);
  const [relatedYearFrom, setRelatedYearFrom] = useState<number | ''>('');
  const [relatedYearTo, setRelatedYearTo] = useState<number | ''>('');
  const [relatedMinCitations, setRelatedMinCitations] = useState<number | ''>('');
  const [relatedOpenOnly, setRelatedOpenOnly] = useState<boolean>(false);

  useEffect(() => {
    const loadPapers = async () => {
      if (!token) return;
      try {
        const data = await fetchPdfs(token);
        const docs = data.documents ?? [];
        setPapers(docs);
        setSelectedPdfId((prev) => prev || docs[0]?.id || '');
      } catch {
        setPapers([]);
      }
    };

    loadPapers();
  }, [token]);

  // Đổi tab và reset lỗi
  const handleTabChange = (tab: 'topic' | 'related') => {
    setActiveTab(tab);
    setError(null);
  };

  const handleSearch = async () => {
    if (!query.trim()) return;
    setSearching(true);
    setError(null);
    try {
      const res = await searchPapers(
        query.trim(),
        token,
        10,
        0,
        yearFrom === '' ? undefined : yearFrom,
        yearTo === '' ? undefined : yearTo,
        minCitations === '' ? undefined : minCitations
      );
      setResults(res.papers);
      setTotal(res.total);
    } catch (e: any) {
      setError(e.message || 'Search failed');
      setResults([]);
    } finally {
      setSearching(false);
    }
  };

  const handleRelatedSearch = async () => {
    if (!selectedPdfId) return;
    setRelatedSearching(true);
    setError(null);
    try {
      const res = await (searchRelatedPapers as any)(selectedPdfId, token, {
        limit: relatedLimit,
        yearFrom: relatedYearFrom === '' ? undefined : relatedYearFrom,
        yearTo: relatedYearTo === '' ? undefined : relatedYearTo,
        minCitations: relatedMinCitations === '' ? undefined : relatedMinCitations,
        openAccess: relatedOpenOnly,
      });
      setRelatedResults(res.related_papers);
    } catch (e: any) {
      setError(e.message || 'Related search failed');
      setRelatedResults([]);
    } finally {
      setRelatedSearching(false);
    }
  };

  return (
    <div className="flex-1 bg-[var(--color-surface)] overflow-y-auto">
      <div className="max-w-4xl mx-auto p-12 space-y-8">
        <header className="space-y-2">
          <h2 className="text-2xl font-bold tracking-tight">Search Papers</h2>
          <p className="text-[var(--color-ink-secondary)] text-sm">
            Discover academic papers from around the web via Semantic Scholar.
          </p>
        </header>

        {/* Tab Switcher */}
        <div className="flex space-x-4 border-b border-[var(--color-line)] mb-6">
          <button
            onClick={() => handleTabChange('topic')}
            className={`pb-2 text-sm font-medium ${
              activeTab === 'topic' ? 'text-[var(--color-accent)] border-b-2 border-[var(--color-accent)]' : 'text-[var(--color-ink-secondary)] hover:text-[var(--color-ink)]'
            }`}
          >
            Search by Topic
          </button>
          <button
            onClick={() => handleTabChange('related')}
            className={`pb-2 text-sm font-medium ${
              activeTab === 'related' ? 'text-[var(--color-accent)] border-b-2 border-[var(--color-accent)]' : 'text-[var(--color-ink-secondary)] hover:text-[var(--color-ink)]'
            }`}
          >
            Related to Library
          </button>
        </div>

        {/* Khung báo lỗi dùng chung */}
        {error && (
          <div className="bg-[var(--color-danger-subtle)] border border-[var(--color-danger-subtle)] text-[var(--color-danger)] text-sm rounded-xl p-4">
            {error}
          </div>
        )}

        {/* ----------------- PHẦN INPUT (THAY ĐỔI THEO TAB) ----------------- */}
        {activeTab === 'topic' ? (
          <div className="space-y-3">
            <div className="relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-[var(--color-ink-secondary)]" size={18} />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="Search for papers by topic, title, or author..."
                className="w-full pl-12 pr-4 py-3.5 border border-[var(--color-line)] rounded-2xl text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-accent-subtle)] focus:border-[var(--color-accent)] bg-[var(--color-surface-hover)]/50"
              />
              <button
                onClick={handleSearch}
                disabled={searching || !query.trim()}
                className="absolute right-2 top-1/2 -translate-y-1/2 bg-[var(--color-accent)] text-white px-4 py-1.5 rounded-xl text-xs font-bold hover:bg-[var(--color-accent)]/80 disabled:opacity-50 transition-colors"
              >
                {searching ? 'Searching...' : 'Search'}
              </button>
            </div>

            <div className="rounded-2xl border border-[var(--color-line-subtle)] bg-[var(--color-surface-hover)]/40 p-4">
              <p className="text-[10px] font-bold text-[var(--color-ink-secondary)] uppercase tracking-widest mb-3">Filters (optional)</p>
              <div className="flex items-center gap-2 flex-wrap">
                <input
                  type="number"
                  placeholder="Year from"
                  value={yearFrom}
                  onChange={(e) => setYearFrom(e.target.value === '' ? '' : Number(e.target.value))}
                  className="w-24 px-2 py-1.5 border border-[var(--color-line)] rounded-md bg-[var(--color-surface)] text-xs focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)]"
                />
                <input
                  type="number"
                  placeholder="Year to"
                  value={yearTo}
                  onChange={(e) => setYearTo(e.target.value === '' ? '' : Number(e.target.value))}
                  className="w-24 px-2 py-1.5 border border-[var(--color-line)] rounded-md bg-[var(--color-surface)] text-xs focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)]"
                />
                <input
                  type="number"
                  placeholder="Min citations"
                  value={minCitations}
                  onChange={(e) => setMinCitations(e.target.value === '' ? '' : Number(e.target.value))}
                  className="w-28 px-2 py-1.5 border border-[var(--color-line)] rounded-md bg-[var(--color-surface)] text-xs focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)]"
                />
              </div>
            </div>
          </div>
        ) : (
          <div className="rounded-2xl border border-[var(--color-line-subtle)] bg-[var(--color-surface-hover)]/40 p-4 space-y-3">
            <div className="flex items-end gap-3 flex-col sm:flex-row">
              <div className="flex-1 w-full space-y-2">
                <label className="block text-[10px] font-bold text-[var(--color-ink-secondary)] uppercase tracking-widest">
                  Search related papers from your library
                </label>
                <select
                  value={selectedPdfId}
                  onChange={(e) => setSelectedPdfId(e.target.value)}
                  className="w-full border border-[var(--color-line)] rounded-2xl text-sm px-4 py-3 bg-[var(--color-surface)] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent-subtle)] focus:border-[var(--color-accent)]"
                >
                  <option value="">Select a PDF...</option>
                  {papers.map((paper) => (
                    <option key={paper.id} value={paper.id}>
                      {paper.original_name}
                    </option>
                  ))}
                </select>
                <div className="flex items-center gap-2 mt-2 text-xs">
                  <input
                    type="number"
                    placeholder="Year from"
                    value={relatedYearFrom}
                    onChange={(e) => setRelatedYearFrom(e.target.value === '' ? '' : Number(e.target.value))}
                    className="w-24 px-2 py-1 border border-[var(--color-line)] rounded-md bg-[var(--color-surface)]"
                  />
                  <input
                    type="number"
                    placeholder="Year to"
                    value={relatedYearTo}
                    onChange={(e) => setRelatedYearTo(e.target.value === '' ? '' : Number(e.target.value))}
                    className="w-24 px-2 py-1 border border-[var(--color-line)] rounded-md bg-[var(--color-surface)]"
                  />
                  <input
                    type="number"
                    placeholder="Min citations"
                    value={relatedMinCitations}
                    onChange={(e) => setRelatedMinCitations(e.target.value === '' ? '' : Number(e.target.value))}
                    className="w-28 px-2 py-1 border border-[var(--color-line)] rounded-md bg-[var(--color-surface)]"
                  />
                  <select
                    value={relatedLimit}
                    onChange={(e) => setRelatedLimit(Number(e.target.value))}
                    className="w-20 px-2 py-1 border border-[var(--color-line)] rounded-md bg-[var(--color-surface)]"
                  >
                    <option value={5}>5</option>
                    <option value={10}>10</option>
                    <option value={20}>20</option>
                  </select>
                  <label className="ml-2 flex items-center gap-1 text-xs">
                    <input type="checkbox" checked={relatedOpenOnly} onChange={(e) => setRelatedOpenOnly(e.target.checked)} />
                    Open only
                  </label>
                </div>
              </div>
              <button
                onClick={handleRelatedSearch}
                disabled={relatedSearching || !selectedPdfId}
                className="bg-[var(--color-accent)] text-white px-4 py-1.5 rounded-xl text-xs font-bold hover:bg-[var(--color-accent)]/80 disabled:opacity-50 transition-colors h-10"
              >
                {relatedSearching ? 'Searching...' : 'Related papers'}
              </button>
            </div>
            <p className="text-xs text-[var(--color-ink-secondary)]">
              Use this button to find Semantic Scholar papers related to one of your uploaded PDFs.
            </p>
          </div>
        )}

        {/* ----------------- TRẠNG THÁI LOADING (DÙNG CHUNG) ----------------- */}
        {(searching || relatedSearching) && (
          <div className="flex items-center justify-center gap-2 py-12 text-[var(--color-ink-secondary)]">
            <Loader2 size={20} className="animate-spin" />
            <span className="text-sm">Searching...</span>
          </div>
        )}

        {/* ----------------- KẾT QUẢ TOPIC SEARCH ----------------- */}
        {activeTab === 'topic' && !searching && (
          <>
            {results && results.length > 0 && (
              <div className="space-y-3">
                <p className="text-xs text-[var(--color-ink-secondary)]">{total} result{total !== 1 ? 's' : ''} for "{query}"</p>
                {results.map((paper) => (
                  <PaperCard key={paper.s2_id} paper={paper} />
                ))}
              </div>
            )}
            
            {results && results.length === 0 && !error && (
              <div className="text-center py-20 space-y-4">
                <BookOpen size={48} className="mx-auto text-[var(--color-line)]" />
                <p className="text-[var(--color-ink-secondary)] text-sm">
                  {query ? 'No results found. Try a different query.' : 'Search results will appear here.'}
                </p>
              </div>
            )}
          </>
        )}

        {/* ----------------- KẾT QUẢ RELATED SEARCH ----------------- */}
        {activeTab === 'related' && !relatedSearching && (
          <>
            {relatedResults && relatedResults.length > 0 && (
              <div className="space-y-3 pt-4">
                <p className="text-xs text-[var(--color-ink-secondary)]">
                  Related papers from {papers.find((paper) => paper.id === selectedPdfId)?.original_name || 'selected PDF'}
                </p>
                {relatedResults.map((paper) => (
                  <PaperCard key={paper.s2_id} paper={paper} />
                ))}
              </div>
            )}

            {relatedResults && relatedResults.length === 0 && !error && selectedPdfId && (
              <div className="text-center py-10 space-y-4">
                <BookOpen size={40} className="mx-auto text-[var(--color-line)]" />
                <p className="text-[var(--color-ink-secondary)] text-sm">No related papers found for the selected PDF.</p>
              </div>
            )}
          </>
        )}

      </div>
    </div>
  );
}

function PaperCard({ paper }: { paper: SearchResult }) {
  const link = paper.open_access_pdf || `https://www.semanticscholar.org/paper/${paper.s2_id}`;
  return (
    <div className="border border-[var(--color-line-subtle)] rounded-xl p-5 space-y-2 hover:border-[var(--color-line)] transition-colors">
      <div className="flex items-start justify-between gap-4">
        <h3 className="font-semibold text-sm leading-snug text-[var(--color-ink)]">
          <a href={link} target="_blank" rel="noopener noreferrer" className="hover:text-[var(--color-accent)] transition-colors">
            {paper.title}
          </a>
        </h3>
        <a href={link} target="_blank" rel="noopener noreferrer" className="shrink-0 text-[var(--color-ink-secondary)] hover:text-[var(--color-accent)] transition-colors">
          <ExternalLink size={14} />
        </a>
      </div>
      {paper.authors.length > 0 && (
        <p className="text-xs text-[var(--color-ink-secondary)]">{paper.authors.join(', ')}</p>
      )}
      <div className="flex items-center gap-3 text-xs text-[var(--color-ink-secondary)]">
        {paper.year && <span>{paper.year}</span>}
        {paper.venue && <span className="italic">{paper.venue}</span>}
        <span className="font-medium text-[var(--color-ink-secondary)]">{paper.citation_count} citations</span>
      </div>
      {paper.abstract && (
        <p className="text-xs text-[var(--color-ink-secondary)] line-clamp-2">{paper.abstract}</p>
      )}
    </div>
  );
}