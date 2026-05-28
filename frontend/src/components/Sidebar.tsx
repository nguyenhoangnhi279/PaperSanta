import {
  LayoutDashboard,
  MessageSquare,
  Search,
  BarChart2,
  History,
  LogOut,
  LogIn,
  User,
} from 'lucide-react';
import { cn } from '../lib/utils';
import { useAuth } from '../context/AuthContext';
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

  return (
    <aside className="w-64 border-r border-[#eee] h-screen flex flex-col bg-[#F9FAFB] shrink-0">
      {/* User Header */}
      <div className="p-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 font-bold overflow-hidden">
            {user?.photoURL ? (
              <img src={user.photoURL} alt="" referrerPolicy="no-referrer" className="w-full h-full object-cover" />
            ) : (
              <User size={16} />
            )}
          </div>
          <span className="font-bold text-sm truncate">{user?.displayName || 'Guest'}</span>
        </div>
      </div>

      {/* Global Search */}
      <div className="px-4 mb-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={14} />
          <input
            type="text"
            placeholder="Search for files..."
            className="w-full bg-white border border-gray-200 rounded-lg py-2 pl-9 pr-4 text-xs focus:ring-1 focus:ring-blue-500 outline-none"
          />
        </div>
      </div>

      {/* Main Navigation */}
      <div className="px-3 space-y-1">
        <p className="px-4 text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-1 mt-2">Tools</p>
        {menuItems.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={cn(
                'w-full flex items-center gap-3 px-4 py-2.5 rounded-lg transition-all text-xs font-semibold',
                activeTab === item.id
                  ? 'bg-blue-600 text-white shadow-md shadow-blue-200'
                  : 'text-gray-600 hover:bg-white hover:shadow-sm'
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
            <p className="px-4 text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-1 flex items-center gap-1.5">
              <History size={10} /> Recent
            </p>
            {recentItems.map((item) => (
              <button
                key={item.id}
                onClick={() => onSelectItem?.(item.id)}
                className="w-full text-left px-4 py-2 text-[11px] text-gray-500 hover:text-gray-900 truncate rounded-md hover:bg-white transition-colors"
              >
                {item.title}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Bottom Actions */}
      <div className="p-4 space-y-2 border-t border-gray-100">
        {/* Auth */}
        {user ? (
          <button
            onClick={logout}
            className="w-full flex items-center gap-3 px-4 py-2 text-xs font-bold text-red-500 hover:bg-red-50 rounded-lg transition-colors"
          >
            <LogOut size={14} /> Sign Out
          </button>
        ) : (
          <button
            onClick={signIn}
            className="w-full flex items-center gap-3 px-4 py-2 text-xs font-bold text-blue-600 hover:bg-blue-50 rounded-lg transition-colors border border-blue-100"
          >
            <LogIn size={14} /> Sign In
          </button>
        )}
      </div>
    </aside>
  );
}
