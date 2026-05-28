import { useEffect, useState } from 'react';
import { Search, ExternalLink, BookOpen, Loader2 } from 'lucide-react';
import { fetchPdfs } from '../api/pdf';
import { searchPapers, searchRelatedPapers } from '../api/search';
import { useAuth } from '../context/AuthContext';
import type { PDFDocument, SearchResult } from '../types';

export default function Discovery() {
  const { session } = useAuth();
  const token = session?.access_token;

  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [relatedResults, setRelatedResults] = useState<SearchResult[] | null>(null);
  const [total, setTotal] = useState(0);
  const [papers, setPapers] = useState<PDFDocument[]>([]);
  const [selectedPdfId, setSelectedPdfId] = useState('');
  const [searching, setSearching] = useState(false);
  const [relatedSearching, setRelatedSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [relatedError, setRelatedError] = useState<string | null>(null);
  const [yearFrom, setYearFrom] = useState<number | ''>('');
  const [yearTo, setYearTo] = useState<number | ''>('');
  const [minCitations, setMinCitations] = useState<number | ''>('');
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
        minCitations === '' ? undefined : minCitations,
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
    setRelatedError(null);
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
      setRelatedError(e.message || 'Related search failed');
      setRelatedResults([]);
    } finally {
      setRelatedSearching(false);
    }
  };

  return (
    <div className="flex-1 bg-white overflow-y-auto">
      <div className="max-w-4xl mx-auto p-12 space-y-8">
        <header className="space-y-2">
          <h2 className="text-2xl font-bold tracking-tight">Search Papers</h2>
          <p className="text-gray-400 text-sm">
            Discover academic papers from around the web via Semantic Scholar.
          </p>
        </header>

        {/* Search */}
        <div className="space-y-3">
          <div className="relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="Search for papers by topic, title, or author..."
              className="w-full pl-12 pr-4 py-3.5 border border-gray-200 rounded-2xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-400 bg-gray-50/50"
            />
            <button
              onClick={handleSearch}
              disabled={searching || !query.trim()}
              className="absolute right-2 top-1/2 -translate-y-1/2 bg-blue-600 text-white px-4 py-1.5 rounded-xl text-xs font-bold hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {searching ? 'Searching...' : 'Search'}
            </button>
          </div>

          {/* Search Filters */}
          <div className="rounded-2xl border border-gray-100 bg-gray-50/40 p-4">
            <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-3">Filters (optional)</p>
            <div className="flex items-center gap-2 flex-wrap">
              <input
                type="number"
                placeholder="Year from"
                value={yearFrom}
                onChange={(e) => setYearFrom(e.target.value === '' ? '' : Number(e.target.value))}
                className="w-24 px-2 py-1.5 border border-gray-200 rounded-md bg-white text-xs focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
              <input
                type="number"
                placeholder="Year to"
                value={yearTo}
                onChange={(e) => setYearTo(e.target.value === '' ? '' : Number(e.target.value))}
                className="w-24 px-2 py-1.5 border border-gray-200 rounded-md bg-white text-xs focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
              <input
                type="number"
                placeholder="Min citations"
                value={minCitations}
                onChange={(e) => setMinCitations(e.target.value === '' ? '' : Number(e.target.value))}
                className="w-28 px-2 py-1.5 border border-gray-200 rounded-md bg-white text-xs focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
            </div>
          </div>
        </div>

        {/* Related papers */}
        <div className="rounded-2xl border border-gray-100 bg-gray-50/40 p-4 space-y-3">
          <div className="flex items-end gap-3 flex-col sm:flex-row">
            <div className="flex-1 w-full space-y-2">
              <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-widest">
                Search related papers from your library
              </label>
              <select
                value={selectedPdfId}
                onChange={(e) => setSelectedPdfId(e.target.value)}
                className="w-full border border-gray-200 rounded-2xl text-sm px-4 py-3 bg-white focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-400"
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
                    className="w-24 px-2 py-1 border border-gray-200 rounded-md bg-white"
                  />
                  <input
                    type="number"
                    placeholder="Year to"
                    value={relatedYearTo}
                    onChange={(e) => setRelatedYearTo(e.target.value === '' ? '' : Number(e.target.value))}
                    className="w-24 px-2 py-1 border border-gray-200 rounded-md bg-white"
                  />
                  <input
                    type="number"
                    placeholder="Min citations"
                    value={relatedMinCitations}
                    onChange={(e) => setRelatedMinCitations(e.target.value === '' ? '' : Number(e.target.value))}
                    className="w-28 px-2 py-1 border border-gray-200 rounded-md bg-white"
                  />
                  <select
                    value={relatedLimit}
                    onChange={(e) => setRelatedLimit(Number(e.target.value))}
                    className="w-20 px-2 py-1 border border-gray-200 rounded-md bg-white"
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
              className="bg-blue-600 text-white px-4 py-1.5 rounded-xl text-xs font-bold hover:bg-blue-700 disabled:opacity-50 transition-colors h-10"
            >
              {relatedSearching ? 'Searching...' : 'Related papers'}
            </button>
          </div>
          <p className="text-xs text-gray-400">
            Use this button to find Semantic Scholar papers related to one of your uploaded PDFs.
          </p>
        </div>

        {/* Error */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl p-4">
            {error}
          </div>
        )}

        {/* Related Error */}
        {relatedError && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl p-4">
            {relatedError}
          </div>
        )}

        {/* Searching */}
        {searching && (
          <div className="flex items-center justify-center gap-2 py-12 text-gray-400">
            <Loader2 size={20} className="animate-spin" />
            <span className="text-sm">Searching...</span>
          </div>
        )}

        {/* Results */}
        {!searching && results && results.length > 0 && (
          <div className="space-y-3">
            <p className="text-xs text-gray-400">{total} result{total !== 1 ? 's' : ''} for "{query}"</p>
            {results.map((paper) => (
              <PaperCard key={paper.s2_id} paper={paper} />
            ))}
          </div>
        )}

        {/* Empty state */}
        {!searching && results && results.length === 0 && !error && (
          <div className="text-center py-20 space-y-4">
            <BookOpen size={48} className="mx-auto text-gray-200" />
            <p className="text-gray-400 text-sm">
              {query ? 'No results found. Try a different query.' : 'Search results will appear here.'}
            </p>
          </div>
        )}

        {/* Related Results */}
        {!relatedSearching && relatedResults && relatedResults.length > 0 && (
          <div className="space-y-3 pt-4">
            <p className="text-xs text-gray-400">
              Related papers from {papers.find((paper) => paper.id === selectedPdfId)?.original_name || 'selected PDF'}
            </p>
            {relatedResults.map((paper) => (
              <PaperCard key={paper.s2_id} paper={paper} />
            ))}
          </div>
        )}

        {!relatedSearching && relatedResults && relatedResults.length === 0 && !relatedError && selectedPdfId && (
          <div className="text-center py-10 space-y-4">
            <BookOpen size={40} className="mx-auto text-gray-200" />
            <p className="text-gray-400 text-sm">No related papers found for the selected PDF.</p>
          </div>
        )}
      </div>
    </div>
  );
}

function PaperCard({ paper }: { paper: SearchResult }) {
  const link = paper.open_access_pdf || `https://www.semanticscholar.org/paper/${paper.s2_id}`;
  return (
    <div className="border border-gray-100 rounded-xl p-5 space-y-2 hover:border-gray-200 transition-colors">
      <div className="flex items-start justify-between gap-4">
        <h3 className="font-semibold text-sm leading-snug text-gray-900">
          <a href={link} target="_blank" rel="noopener noreferrer" className="hover:text-blue-600 transition-colors">
            {paper.title}
          </a>
        </h3>
        <a href={link} target="_blank" rel="noopener noreferrer" className="shrink-0 text-gray-300 hover:text-blue-500 transition-colors">
          <ExternalLink size={14} />
        </a>
      </div>
      {paper.authors.length > 0 && (
        <p className="text-xs text-gray-500">{paper.authors.join(', ')}</p>
      )}
      <div className="flex items-center gap-3 text-xs text-gray-400">
        {paper.year && <span>{paper.year}</span>}
        {paper.venue && <span className="italic">{paper.venue}</span>}
        <span className="font-medium text-gray-500">{paper.citation_count} citations</span>
      </div>
      {paper.abstract && (
        <p className="text-xs text-gray-400 line-clamp-2">{paper.abstract}</p>
      )}
    </div>
  );
}
