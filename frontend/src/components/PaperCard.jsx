function PaperCard({ title, messageCount, timeAgoText, onSimilar, onClick, isActive }) {
  return (
    <div
      className={`paper-card ${isActive ? 'active' : ''}`}
      onClick={onClick}
    >
      <div className="paper-card-title">{title}</div>
      <div className="paper-card-actions">
        <div className="paper-card-stat">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <rect x="1" y="1" width="12" height="12" rx="2" stroke="#666F8D" strokeWidth="1.3"/>
          </svg>
          <span>{messageCount}</span>
        </div>
        <div className="paper-card-stat">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <circle cx="7" cy="7" r="6" stroke="#666F8D" strokeWidth="1.3"/>
          </svg>
          <span>{timeAgoText}</span>
        </div>
        {onSimilar && (
          <button
            className="btn-similar"
            onClick={(e) => {
              e.stopPropagation();
              onSimilar();
            }}
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <rect x="1" y="1" width="10" height="10" rx="2" stroke="white" strokeWidth="1.2"/>
            </svg>
            Similar
          </button>
        )}
      </div>
    </div>
  );
}

export default PaperCard;
