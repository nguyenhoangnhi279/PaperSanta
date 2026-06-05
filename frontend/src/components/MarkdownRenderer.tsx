import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import type { Citation } from '../types';

interface MarkdownRendererProps {
  content: string;
  citations?: Citation[];
  onCitationClick?: (citation: Citation, index: number) => void;
}

function linkCitationMarkers(content: string, citations: Citation[] = []) {
  return content.replace(/\[(\d+)\]/g, (match, rawIndex) => {
    const index = Number(rawIndex) - 1;
    return citations[index] ? `[${rawIndex}](citation://${rawIndex})` : match;
  });
}

export default function MarkdownRenderer({ content, citations = [], onCitationClick }: MarkdownRendererProps) {
  const renderedContent = citations.length > 0 ? linkCitationMarkers(content, citations) : content;

  return (
    <div className="prose prose-sm max-w-none leading-relaxed">
      <ReactMarkdown
        remarkPlugins={[remarkMath]}
        rehypePlugins={[rehypeKatex]}
        urlTransform={(url) => url}
        components={{
          p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
          ul: ({ children }) => <ul className="list-disc pl-4 mb-2 space-y-1">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal pl-4 mb-2 space-y-1">{children}</ol>,
          li: ({ children }) => <li className="text-[var(--color-ink)]">{children}</li>,
          strong: ({ children }) => <strong className="font-bold text-[var(--color-ink)]">{children}</strong>,
          a: ({ href, children }) => {
            if (href?.startsWith('citation://')) {
              const index = Number(href.replace('citation://', '')) - 1;
              const citation = citations[index];
              return (
                <button
                  type="button"
                  onClick={() => citation && onCitationClick?.(citation, index)}
                  className="inline-flex rounded px-1 font-bold text-[var(--color-accent)] hover:bg-[var(--color-accent-subtle)]"
                  title={citation?.chunk_text || `Source ${index + 1}`}
                >
                  {children}
                </button>
              );
            }
            return <a href={href} className="text-[var(--color-accent)] underline">{children}</a>;
          },
          code: ({ children }) => (
            <code className="bg-[var(--color-surface-hover)] px-1.5 py-0.5 rounded text-[11px] font-mono">{children}</code>
          ),
          pre: ({ children }) => (
            <pre className="bg-[var(--color-surface-hover)] p-3 rounded-lg overflow-x-auto text-[11px] font-mono mb-2">{children}</pre>
          ),
        }}
      >
        {renderedContent}
      </ReactMarkdown>
    </div>
  );
}
