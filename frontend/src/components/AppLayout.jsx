import Sidebar from './Sidebar';
import MainContent from './MainContent';

function AppLayout({
  activeView,
  onNavigate,
  documents,
  selectedDoc,
  pdfUrl,
  uploading,
  userName,
  onUpload,
  onSelectDocument,
  onViewPdf,
  onCloseViewer,
  onSimilar,
}) {
  return (
    <div className="app-layout">
      <Sidebar
        activeView={activeView}
        onNavigate={onNavigate}
        onUploadFile={onUpload}
        uploading={uploading}
        documents={documents}
      />
      <MainContent
        activeView={activeView}
        documents={documents}
        selectedDoc={selectedDoc}
        pdfUrl={pdfUrl}
        uploading={uploading}
        userName={userName}
        onUpload={onUpload}
        onSelectDocument={onSelectDocument}
        onViewPdf={onViewPdf}
        onCloseViewer={onCloseViewer}
        onSimilar={onSimilar}
      />
    </div>
  );
}

export default AppLayout;
