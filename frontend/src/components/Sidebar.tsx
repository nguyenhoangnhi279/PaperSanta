import {
  LayoutDashboard,
  MessageSquare,
  Search,
  BarChart2,
  History,
  LogOut,
  LogIn,
  User,
  Moon,
  Sun,
} from 'lucide-react';
import { cn } from '../lib/utils';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import type { ActiveView } from '../types';

interface SidebarProps {
  activeTab: ActiveView;
  setActiveTab: (tab: ActiveView) => void;
  recentItems?: { id: string; title: string }[];
  onSelectItem?: (id: string) => void;
}

const menuItems: { id: ActiveView; label: string; icon: typeof LayoutDashboard }[] = [
  { id: 'dashboard', label: 'Library', icon: LayoutDashboard },
  { id: 'reader', label: 'Chats', icon: MessageSquare },
  { id: 'analyzer', label: 'Analyze', icon: BarChart2 },
  { id: 'discovery', label: 'Search papers', icon: Search },
];

export default function Sidebar({
  activeTab,
  setActiveTab,
  recentItems = [],
  onSelectItem,
}: SidebarProps) {
  const { user, signIn, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();

  return (
    <aside className="w-64 border-r border-[var(--color-line)] h-screen flex flex-col bg-[var(--color-surface)] shrink-0">
      {/* User Header */}
      <div className="p-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-[var(--color-accent-subtle)] flex items-center justify-center text-[var(--color-accent)] font-bold overflow-hidden">
            {user?.photoURL ? (
              <img src={user.photoURL} alt="" referrerPolicy="no-referrer" className="w-full h-full object-cover" />
            ) : (
              <User size={16} />
            )}
          </div>
          <span className="font-bold text-sm truncate text-[var(--color-ink)]">{user?.displayName || 'Guest'}</span>
        </div>
      </div>

      {/* Global Search */}
      <div className="px-4 mb-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-ink-secondary)]" size={14} />
          <input
            type="text"
            placeholder="Search for files..."
            className="w-full bg-[var(--color-bg)] border border-[var(--color-line)] rounded-lg py-2 pl-9 pr-4 text-xs focus:ring-1 focus:ring-[var(--color-accent)] outline-none text-[var(--color-ink)] placeholder:text-[var(--color-ink-secondary)]"
          />
        </div>
      </div>

      {/* Main Navigation */}
      <div className="px-3 space-y-1">
        <p className="px-4 text-[10px] font-bold text-[var(--color-ink-secondary)] uppercase tracking-widest mb-1 mt-2">Tools</p>
        {menuItems.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={cn(
                'w-full flex items-center gap-3 px-4 py-2.5 rounded-lg transition-all text-xs font-semibold',
                activeTab === item.id
                  ? 'bg-[var(--color-accent)] text-white shadow-md'
                  : 'text-[var(--color-ink-secondary)] hover:bg-[var(--color-surface-hover)] hover:shadow-sm'
              )}
            >
              <Icon size={16} />
              {item.label}
            </button>
          );
        })}
      </div>

      {/* Recent Items */}
      <div className="flex-1 overflow-y-auto mt-4 px-3">
        {recentItems.length > 0 && (
          <div>
            <p className="px-4 text-[10px] font-bold text-[var(--color-ink-secondary)] uppercase tracking-widest mb-1 flex items-center gap-1.5">
              <History size={10} /> Recent
            </p>
            {recentItems.map((item) => (
              <button
                key={item.id}
                onClick={() => onSelectItem?.(item.id)}
                className="w-full text-left px-4 py-2 text-[11px] text-[var(--color-ink-secondary)] hover:text-[var(--color-ink)] truncate rounded-md hover:bg-[var(--color-surface-hover)] transition-colors"
              >
                {item.title}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Bottom Actions */}
      <div className="p-3 space-y-1 border-t border-[var(--color-line)]">
        {/* Theme Toggle */}
        <button
          onClick={toggleTheme}
          className="w-full flex items-center gap-3 px-4 py-2 text-xs font-semibold text-[var(--color-ink-secondary)] hover:text-[var(--color-ink)] hover:bg-[var(--color-surface-hover)] rounded-lg transition-colors"
        >
          {theme === 'light' ? <Moon size={14} /> : <Sun size={14} />}
          {theme === 'light' ? 'Dark mode' : 'Light mode'}
        </button>

        {/* Auth */}
        {user ? (
          <button
            onClick={logout}
            className="w-full flex items-center gap-3 px-4 py-2 text-xs font-bold text-[var(--color-danger)] hover:bg-[var(--color-danger-subtle)] rounded-lg transition-colors"
          >
            <LogOut size={14} /> Sign Out
          </button>
        ) : (
          <button
            onClick={signIn}
            className="w-full flex items-center gap-3 px-4 py-2 text-xs font-bold text-[var(--color-accent)] hover:bg-[var(--color-accent-subtle)] rounded-lg transition-colors border border-[var(--color-accent-subtle)]"
          >
            <LogIn size={14} /> Sign In
          </button>
        )}
      </div>
    </aside>
  );
}
