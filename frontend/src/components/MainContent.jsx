import WelcomeCard from './WelcomeCard';
import LibraryPanel from './LibraryPanel';
import ChatPanel from './ChatPanel';
import UploadZone from './UploadZone';
import Viewer from './Viewer';

function MainContent({
  activeView,
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
  const renderView = () => {
    switch (activeView) {
      case 'chats':
        return (
          <ChatPanel
            documents={documents}
            pdfUrl={pdfUrl}
            onViewPdf={onViewPdf}
          />
        );
      case 'analyze':
        return (
          <div className="placeholder-view">
            <div className="placeholder-icon">🔬</div>
            <h2>Analyze</h2>
            <p>PDF analysis coming soon</p>
          </div>
        );
      case 'search':
        return (
          <div className="placeholder-view">
            <div className="placeholder-icon">🔎</div>
            <h2>Search Papers</h2>
            <p>Semantic Scholar integration coming soon</p>
          </div>
        );
      case 'library':
      default:
        if (selectedDoc) {
          return (
            <Viewer
              document={selectedDoc}
              pdfUrl={pdfUrl}
              onClose={onCloseViewer}
            />
          );
        }
        return (
          <>
            <div className="main-greeting-area">
              <WelcomeCard userName={userName} />
              <UploadZone onUpload={onUpload} uploading={uploading} />
            </div>
            <LibraryPanel
              documents={documents}
              onSelectDocument={onSelectDocument}
              onSimilar={onSimilar}
              selectedDocId={selectedDoc?.id}
            />
          </>
        );
    }
  };

  return (
    <div className="main-content">
      <div className="main-body">
        {renderView()}
      </div>
    </div>
  );
}

export default MainContent;
