function NavItem({ icon, label, active, onClick }) {
  return (
    <div
      className={`nav-item ${active ? 'active' : ''}`}
      onClick={onClick}
    >
      <div className="nav-item-inner">
        <span className="nav-icon">{icon}</span>
        <span className="nav-label">{label}</span>
      </div>
    </div>
  );
}

export default NavItem;
