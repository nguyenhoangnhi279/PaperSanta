interface PDFViewerProps {
  url: string;
}

export default function PDFViewer({ url }: PDFViewerProps) {
  return (
    <iframe
      src={url}
      className="w-full h-full border-none"
      title="PDF Viewer"
    />
  );
}
