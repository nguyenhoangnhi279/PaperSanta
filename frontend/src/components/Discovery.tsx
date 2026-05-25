import { useState } from 'react';
import { Search, ExternalLink, BookOpen, Loader2 } from 'lucide-react';
import { searchPapers } from '../api/search';
import { useAuth } from '../context/AuthContext';
import type { SearchResult } from '../types';

export default function Discovery() {
  const { session } = useAuth();
  const token = session?.access_token;

  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [total, setTotal] = useState(0);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setSearching(true);
    setError(null);
    try {
      const res = await searchPapers(query.trim(), token);
      setResults(res.papers);
      setTotal(res.total);
    } catch (e: any) {
      setError(e.message || 'Search failed');
      setResults([]);
    } finally {
      setSearching(false);
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

        {/* Error */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl p-4">
            {error}
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
