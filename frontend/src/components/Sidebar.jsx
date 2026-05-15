import { useState, useRef, useEffect } from 'react';
import NavItem from './NavItem';
import SidebarSection from './SidebarSection';
import UserAccount from './UserAccount';

const NAV_ITEMS = [
  { key: 'library', label: 'Library', icon: '📚' },
  { key: 'chats', label: 'Chats', icon: '💬' },
  { key: 'analyze', label: 'Analyze', icon: '🔬' },
  { key: 'search', label: 'Search papers', icon: '🔎' },
];

function Sidebar({ activeView, onNavigate, onUploadFile, uploading, documents }) {
  const [sidebarSearch, setSidebarSearch] = useState('');
  const fileInputRef = useRef(null);

  const recentItems = documents.slice(0, 6).map((d) => ({
    key: d.id,
    label: d.original_name,
  }));

  const filteredRecent = recentItems.filter((item) =>
    item.label.toLowerCase().includes(sidebarSearch.toLowerCase())
  );

  return (
    <div className="sidebar">
      <div className="sidebar-scroll">
        <div className="sidebar-logo">PAPERSANTA</div>
        <div className="sidebar-search">
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
            <circle cx="5.5" cy="5.5" r="4.5" stroke="#666F8D" strokeWidth="1.2"/>
            <path d="M9 9L12 12" stroke="#666F8D" strokeWidth="1.2" strokeLinecap="round"/>
          </svg>
          <input
            type="text"
            placeholder="Search for files..."
            value={sidebarSearch}
            onChange={(e) => setSidebarSearch(e.target.value)}
          />
        </div>

        <SidebarSection title="Tools">
          {NAV_ITEMS.map((item) => (
            <NavItem
              key={item.key}
              icon={item.icon}
              label={item.label}
              active={activeView === item.key}
              onClick={() => onNavigate(item.key)}
            />
          ))}
        </SidebarSection>

        <SidebarSection title="Recent" fade>
          {filteredRecent.length > 0 ? (
            filteredRecent.map((item) => (
              <div key={item.key} className="section-item">
                <span>{item.label}</span>
              </div>
            ))
          ) : (
            <div className="section-item empty">
              <span>No recent files</span>
            </div>
          )}
        </SidebarSection>
      </div>

      <div className="sidebar-bottom">
        <button
          className="btn-upload-file"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
        >
          <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
            <path d="M7.5 1V14M1 7.5H14" stroke="white" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          Upload file
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf"
          style={{ display: 'none' }}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) {
              onUploadFile(file);
              e.target.value = '';
            }
          }}
        />
        <UserAccount />
      </div>
    </div>
  );
}

export default Sidebar;
