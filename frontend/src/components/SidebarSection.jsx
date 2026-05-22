function SidebarSection({ title, children, fade }) {
  return (
    <div className={`sidebar-section ${fade ? 'fade' : ''}`}>
      <div className="section-header">
        <span className="section-title">{title}</span>
      </div>
      <div className="section-items">{children}</div>
      {fade && <div className="section-fade" />}
    </div>
  );
}

export default SidebarSection;
