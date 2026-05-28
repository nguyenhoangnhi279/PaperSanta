interface PDFViewerProps {
  url: string;
  targetPage?: number | null;
}

export default function PDFViewer({ url, targetPage }: PDFViewerProps) {
  const finalUrl = targetPage ? `${url}#page=${targetPage}` : url;

  return (
    <iframe
      key={finalUrl}
      src={finalUrl}
      className="w-full h-full border-none"
      title="PDF Viewer"
    />
  );
}