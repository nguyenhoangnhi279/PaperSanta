import { useState, useMemo } from 'react';
import PaperCard from './PaperCard';
import { formatSize, timeAgo } from '../utils/format';

function LibraryPanel({ documents, onSelectDocument, onSimilar, selectedDocId }) {
  const [searchText, setSearchText] = useState('');
  const [sortBy, setSortBy] = useState('newest');

  const filteredDocs = useMemo(() => {
    let list = [...documents];

    if (searchText) {
      const q = searchText.toLowerCase();
      list = list.filter((d) => d.original_name.toLowerCase().includes(q));
    }

    if (sortBy === 'newest') {
      list.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    } else if (sortBy === 'oldest') {
      list.sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
    } else if (sortBy === 'name') {
      list.sort((a, b) => a.original_name.localeCompare(b.original_name));
    }

    return list;
  }, [documents, searchText, sortBy]);

  return (
    <div className="library-panel">
      <div className="library-header">
        <h2 className="library-title">Your Uploaded Library</h2>
        <div className="library-controls">
          <div className="library-search">
            <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
              <circle cx="5.5" cy="5.5" r="4.5" stroke="#666F8D" strokeWidth="1.2"/>
              <path d="M9 9L12 12" stroke="#666F8D" strokeWidth="1.2" strokeLinecap="round"/>
            </svg>
            <input
              type="text"
              placeholder="Search for files..."
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
            />
          </div>
          <div className="library-sort">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d="M1 3H11M3 6H9M5 9H7" stroke="#666F8D" strokeWidth="1.3" strokeLinecap="round"/>
            </svg>
            <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
              <option value="newest">Newest</option>
              <option value="oldest">Oldest</option>
              <option value="name">Name</option>
            </select>
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M3.5 5.5L7 9L10.5 5.5" stroke="#666F8D" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
        </div>
      </div>

      <div className="library-list">
        {filteredDocs.length > 0 ? (
          filteredDocs.map((doc) => (
            <PaperCard
              key={doc.id}
              title={doc.original_name}
              messageCount={doc.message_count || 0}
              timeAgoText={timeAgo(doc.created_at)}
              isActive={selectedDocId === doc.id}
              onClick={() => onSelectDocument(doc)}
              onSimilar={onSimilar ? () => onSimilar(doc) : null}
            />
          ))
        ) : (
          <div className="library-empty">
            <p>No papers found</p>
            {!searchText && <p className="library-empty-hint">Upload a PDF to get started</p>}
          </div>
        )}
      </div>
    </div>
  );
}

export default LibraryPanel;
