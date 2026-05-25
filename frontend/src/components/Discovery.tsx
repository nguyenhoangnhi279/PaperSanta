import { useState } from 'react';
import { Search, ExternalLink, BookOpen } from 'lucide-react';

export default function Discovery() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<any[] | null>(null);
  const [searching, setSearching] = useState(false);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setSearching(true);
    // TODO: integrate with Semantic Scholar / arxiv API
    // For now, show placeholder
    setTimeout(() => {
      setResults([]);
      setSearching(false);
    }, 1000);
  };

  return (
    <div className="flex-1 bg-white overflow-y-auto">
      <div className="max-w-4xl mx-auto p-12 space-y-8">
        <header className="space-y-2">
          <h2 className="text-2xl font-bold tracking-tight">Search Papers</h2>
          <p className="text-gray-400 text-sm">
            Discover academic papers from around the web.
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

        {/* Results */}
        {results && results.length === 0 && (
          <div className="text-center py-20 space-y-4">
            <BookOpen size={48} className="mx-auto text-gray-200" />
            <p className="text-gray-400 text-sm">
              Search results will appear here.
            </p>
            <p className="text-xs text-gray-300">
              Semantic Scholar integration coming soon.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
