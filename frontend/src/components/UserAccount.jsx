import { useAuth } from '../context/AuthContext';

function UserAccount() {
  const { user, signOut } = useAuth();

  return (
    <div className="user-account">
      <div className="user-avatar">
        {user?.user_metadata?.avatar_url ? (
          <img src={user.user_metadata.avatar_url} alt="avatar" />
        ) : (
          <div className="avatar-placeholder">
            {(user?.email?.charAt(0) || 'U').toUpperCase()}
          </div>
        )}
      </div>
      <div className="user-name">{user?.user_metadata?.full_name || user?.email?.split('@')[0] || 'User'}</div>
      <button className="signout-btn" onClick={signOut} title="Sign out">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <path d="M5 13H2.33333C1.97971 13 1.64057 12.8595 1.39052 12.6095C1.14048 12.3594 1 12.0203 1 11.6667V2.33333C1 1.97971 1.14048 1.64057 1.39052 1.39052C1.64057 1.14048 1.97971 1 2.33333 1H5M9.66667 10.3333L13 7M13 7L9.66667 3.66667M13 7H5"
            stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </button>
    </div>
  );
}

export default UserAccount;
