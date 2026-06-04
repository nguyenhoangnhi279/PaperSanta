import { useCallback, useEffect, useRef, useState } from 'react';
import { ZoomIn, ZoomOut } from 'lucide-react';
import {
  GlobalWorkerOptions,
  TextLayer,
  getDocument,
  type PDFDocumentProxy,
  type PDFPageProxy,
  type RenderTask,
} from 'pdfjs-dist';
import pdfWorkerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import 'pdfjs-dist/web/pdf_viewer.css';
import './PDFViewer.css';

GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

interface PDFViewerProps {
  url: string;
  targetPage?: number | null;
  targetText?: string | null;
  onExplainSelection?: (payload: { text: string; pageNumber?: number | null; surroundingText?: string | null }) => void;
}

interface SelectionMenu {
  text: string;
  x: number;
  y: number;
  pageNumber?: number | null;
  surroundingText?: string | null;
}

interface PDFPageProps {
  pageNumber: number;
  pdfDocument: PDFDocumentProxy;
  containerWidth: number;
  zoom: number;
  registerPageRef: (pageNumber: number, element: HTMLDivElement | null) => void;
}

const MIN_ZOOM = 0.6;
const MAX_ZOOM = 2.5;
const ZOOM_STEP = 0.2;

function PDFPage({ pageNumber, pdfDocument, containerWidth, zoom, registerPageRef }: PDFPageProps) {
  const pageRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const textLayerRef = useRef<HTMLDivElement>(null);
  const renderTaskRef = useRef<RenderTask | null>(null);
  const textLayerTaskRef = useRef<TextLayer | null>(null);
  const [pageSize, setPageSize] = useState<{ width: number; height: number } | null>(null);

  useEffect(() => {
    registerPageRef(pageNumber, pageRef.current);
    return () => registerPageRef(pageNumber, null);
  }, [pageNumber, registerPageRef]);

  useEffect(() => {
    let canceled = false;
    let page: PDFPageProxy | null = null;

    const renderPage = async () => {
      const canvas = canvasRef.current;
      const textLayerElement = textLayerRef.current;
      if (!canvas || !textLayerElement || containerWidth <= 0) return;

      renderTaskRef.current?.cancel();
      textLayerTaskRef.current?.cancel();
      textLayerElement.replaceChildren();

      page = await pdfDocument.getPage(pageNumber);
      if (canceled) return;

      const baseViewport = page.getViewport({ scale: 1 });
      const scale = Math.min(containerWidth / baseViewport.width, 2) * zoom;
      const viewport = page.getViewport({ scale });
      const pixelRatio = window.devicePixelRatio || 1;
      const context = canvas.getContext('2d');
      if (!context) return;

      canvas.width = Math.floor(viewport.width * pixelRatio);
      canvas.height = Math.floor(viewport.height * pixelRatio);
      canvas.style.width = `${viewport.width}px`;
      canvas.style.height = `${viewport.height}px`;

      if (pageRef.current) {
        pageRef.current.style.width = `${viewport.width}px`;
        pageRef.current.style.height = `${viewport.height}px`;
      }
      setPageSize({ width: viewport.width, height: viewport.height });

      textLayerElement.style.setProperty('--total-scale-factor', String(scale));
      textLayerElement.style.width = `${viewport.width}px`;
      textLayerElement.style.height = `${viewport.height}px`;

      renderTaskRef.current = page.render({
        canvas,
        canvasContext: context,
        viewport,
        transform: pixelRatio !== 1 ? [pixelRatio, 0, 0, pixelRatio, 0, 0] : undefined,
      });

      const textContent = await page.getTextContent();
      if (canceled) return;

      const textLayer = new TextLayer({
        container: textLayerElement,
        textContentSource: textContent,
        viewport,
      });
      textLayerTaskRef.current = textLayer;

      await Promise.all([renderTaskRef.current.promise, textLayer.render()]);
    };

    renderPage().catch((error) => {
      if (error?.name !== 'RenderingCancelledException') {
        console.error('PDF page render failed', error);
      }
    });

    return () => {
      canceled = true;
      renderTaskRef.current?.cancel();
      textLayerTaskRef.current?.cancel();
      page?.cleanup();
    };
  }, [containerWidth, pageNumber, pdfDocument, zoom]);

  return (
    <div
      ref={pageRef}
      className="pdf-page relative mx-auto mb-4 bg-white shadow-lg"
      data-page-number={pageNumber}
      style={
        pageSize
          ? { width: pageSize.width, height: pageSize.height }
          : { minHeight: 240 }
      }
    >
      <canvas ref={canvasRef} className="pdf-page-canvas block" />
      <div ref={textLayerRef} className="textLayer pdf-page-text-layer" />
    </div>
  );
}

function normalizeForHighlight(text: string) {
  return text
    .replace(/\[Section:[^\]]+\]/gi, ' ')
    .replace(/[^\p{L}\p{N}\s.-]/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();
}

function highlightTokens(text: string) {
  const stop = new Set([
    'the', 'and', 'for', 'that', 'with', 'this', 'from', 'into', 'paper', 'section',
    'model', 'method', 'results', 'table', 'figure',
  ]);
  const tokens = normalizeForHighlight(text)
    .split(/\s+/)
    .map((token) => token.replace(/^[^a-z0-9]+|[^a-z0-9]+$/gi, ''))
    .filter((token) => token.length >= 4 && !stop.has(token));
  return Array.from(new Set(tokens)).slice(0, 18);
}

export default function PDFViewer({ url, targetPage, targetText, onExplainSelection }: PDFViewerProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const pagesRef = useRef<Map<number, HTMLDivElement>>(new Map());
  const [pdfDocument, setPdfDocument] = useState<PDFDocumentProxy | null>(null);
  const [pageCount, setPageCount] = useState(0);
  const [containerWidth, setContainerWidth] = useState(0);
  const [selectionMenu, setSelectionMenu] = useState<SelectionMenu | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);

  useEffect(() => {
    const scrollElement = scrollRef.current;
    if (!scrollElement) return;

    const observer = new ResizeObserver(([entry]) => {
      const nextWidth = Math.max(0, Math.min(entry.contentRect.width - 32, 980));
      setContainerWidth(nextWidth);
    });
    observer.observe(scrollElement);

    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    let canceled = false;
    setError(null);
    setPdfDocument(null);
    setPageCount(0);
    setSelectionMenu(null);
    pagesRef.current.clear();

    const loadingTask = getDocument({ url });
    loadingTask.promise
      .then((document) => {
        if (canceled) {
          document.cleanup();
          return;
        }
        setPdfDocument(document);
        setPageCount(document.numPages);
      })
      .catch((loadError) => {
        if (!canceled) {
          setError(loadError?.message || 'Unable to load PDF.');
        }
      });

    return () => {
      canceled = true;
      loadingTask.destroy();
    };
  }, [url]);

  useEffect(() => {
    if (!targetPage) return;
    const pageElement = pagesRef.current.get(targetPage);
    pageElement?.scrollIntoView({ behavior: 'smooth', block: 'start' });

    document.querySelectorAll('.pdf-citation-highlight').forEach((element) => {
      element.classList.remove('pdf-citation-highlight');
    });

    if (!pageElement || !targetText) return;
    const tokens = highlightTokens(targetText);
    if (tokens.length === 0) return;

    window.setTimeout(() => {
      const spans = Array.from(pageElement.querySelectorAll<HTMLSpanElement>('.pdf-page-text-layer span'));
      let matched = 0;
      for (const span of spans) {
        const text = normalizeForHighlight(span.textContent || '');
        if (!text) continue;
        if (tokens.some((token) => text.includes(token) || token.includes(text))) {
          span.classList.add('pdf-citation-highlight');
          matched += 1;
        }
        if (matched >= 80) break;
      }
    }, 250);
  }, [targetPage, targetText, pageCount]);

  const registerPageRef = useCallback((pageNumber: number, element: HTMLDivElement | null) => {
    if (element) {
      pagesRef.current.set(pageNumber, element);
    } else {
      pagesRef.current.delete(pageNumber);
    }
  }, []);

  const clearSelection = useCallback(() => {
    document.getSelection()?.removeAllRanges();
    setSelectionMenu(null);
  }, []);

  const updateSelectionMenu = useCallback(() => {
    const wrapper = scrollRef.current;
    const selection = document.getSelection();
    if (!wrapper || !selection || selection.rangeCount === 0) {
      setSelectionMenu(null);
      return;
    }

    const selectedText = selection.toString().trim();
    const anchorNode = selection.anchorNode;
    const focusNode = selection.focusNode;
    if (
      !selectedText ||
      !anchorNode ||
      !focusNode ||
      !wrapper.contains(anchorNode) ||
      !wrapper.contains(focusNode)
    ) {
      setSelectionMenu(null);
      return;
    }

    const rangeRect = selection.getRangeAt(0).getBoundingClientRect();
    const wrapperRect = wrapper.getBoundingClientRect();
    const x = Math.min(
      Math.max(rangeRect.left + rangeRect.width / 2 - wrapperRect.left + wrapper.scrollLeft, 88),
      wrapper.scrollWidth - 88,
    );
    const y = Math.max(
      rangeRect.top - wrapperRect.top + wrapper.scrollTop - 12,
      wrapper.scrollTop + 16,
    );

    const pageElement = (selection.anchorNode instanceof Element
      ? selection.anchorNode
      : selection.anchorNode?.parentElement
    )?.closest<HTMLElement>('.pdf-page');
    const pageNumber = pageElement?.dataset.pageNumber
      ? Number(pageElement.dataset.pageNumber)
      : null;
    const pageText = pageElement?.textContent || '';
    const selectedOffset = pageText.indexOf(selectedText);
    const surroundingText = selectedOffset >= 0
      ? pageText.slice(Math.max(0, selectedOffset - 500), selectedOffset + selectedText.length + 500)
      : pageText.slice(0, 1200);

    setSelectionMenu({ text: selectedText, x, y, pageNumber, surroundingText });
  }, []);

  const handleExplain = () => {
    if (!selectionMenu) return;
    onExplainSelection?.({
      text: selectionMenu.text,
      pageNumber: selectionMenu.pageNumber,
      surroundingText: selectionMenu.surroundingText,
    });
    clearSelection();
  };

  const zoomOut = () => {
    setZoom((current) => Math.max(MIN_ZOOM, Number((current - ZOOM_STEP).toFixed(2))));
    clearSelection();
  };

  const zoomIn = () => {
    setZoom((current) => Math.min(MAX_ZOOM, Number((current + ZOOM_STEP).toFixed(2))));
    clearSelection();
  };

  const resetZoom = () => {
    setZoom(1);
    clearSelection();
  };

  return (
    <div className="relative h-full w-full bg-[#525659]">
      <div className="pdf-zoom-toolbar absolute right-4 top-4 z-30 flex w-fit items-center overflow-hidden rounded-lg border border-black/10 bg-white text-xs font-semibold shadow-lg">
        <button
          type="button"
          onClick={zoomOut}
          disabled={zoom <= MIN_ZOOM}
          title="Zoom out"
          className="flex h-8 w-8 items-center justify-center text-[var(--color-ink)] hover:bg-[var(--color-surface-hover)] disabled:opacity-40"
        >
          <ZoomOut size={16} />
        </button>
        <button
          type="button"
          onClick={resetZoom}
          title="Reset zoom"
          className="h-8 min-w-14 border-x border-[var(--color-line)] px-2 text-[var(--color-ink)] hover:bg-[var(--color-surface-hover)]"
        >
          {Math.round(zoom * 100)}%
        </button>
        <button
          type="button"
          onClick={zoomIn}
          disabled={zoom >= MAX_ZOOM}
          title="Zoom in"
          className="flex h-8 w-8 items-center justify-center text-[var(--color-ink)] hover:bg-[var(--color-surface-hover)] disabled:opacity-40"
        >
          <ZoomIn size={16} />
        </button>
      </div>

      <div
        ref={scrollRef}
        className="pdf-viewer-scroll relative h-full w-full overflow-auto p-4 pt-14"
        onMouseUp={() => window.setTimeout(updateSelectionMenu, 0)}
        onKeyUp={() => window.setTimeout(updateSelectionMenu, 0)}
      >
        {error && (
          <div className="mx-auto mt-8 max-w-md rounded-lg border border-[var(--color-danger-subtle)] bg-[var(--color-surface)] p-4 text-xs text-[var(--color-danger)] shadow">
            {error}
          </div>
        )}

        {!error && !pdfDocument && (
          <div className="mt-8 text-center text-xs text-white/80">Loading PDF...</div>
        )}

        {pdfDocument && containerWidth > 0 && (
          <div className="min-w-fit">
            {Array.from({ length: pageCount }, (_, index) => (
              <PDFPage
                key={`${url}-${index + 1}`}
                pageNumber={index + 1}
                pdfDocument={pdfDocument}
                containerWidth={containerWidth}
                zoom={zoom}
                registerPageRef={registerPageRef}
              />
            ))}
          </div>
        )}

        {selectionMenu && (
          <div
            className="absolute z-20 flex -translate-x-1/2 -translate-y-full overflow-hidden rounded-lg border border-[var(--color-line)] bg-[var(--color-surface)] text-xs font-semibold shadow-lg"
            style={{ left: selectionMenu.x, top: selectionMenu.y }}
            onMouseDown={(event) => event.preventDefault()}
          >
            <button
              type="button"
              onClick={handleExplain}
              className="px-3 py-2 text-[var(--color-accent)] hover:bg-[var(--color-accent-subtle)]"
            >
              Explain
            </button>
            <button
              type="button"
              onClick={clearSelection}
              className="border-l border-[var(--color-line)] px-3 py-2 text-[var(--color-ink-secondary)] hover:bg-[var(--color-surface-hover)]"
            >
              Cancel
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
