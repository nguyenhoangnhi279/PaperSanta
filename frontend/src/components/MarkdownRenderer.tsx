import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';

interface MarkdownRendererProps {
  content: string;
}

export default function MarkdownRenderer({ content }: MarkdownRendererProps) {
  return (
    <div className="prose prose-sm max-w-none leading-relaxed">
      <ReactMarkdown
        remarkPlugins={[remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
          ul: ({ children }) => <ul className="list-disc pl-4 mb-2 space-y-1">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal pl-4 mb-2 space-y-1">{children}</ol>,
          li: ({ children }) => <li className="text-gray-700">{children}</li>,
          strong: ({ children }) => <strong className="font-bold text-gray-900">{children}</strong>,
          code: ({ children }) => (
            <code className="bg-gray-100 px-1.5 py-0.5 rounded text-[11px] font-mono">{children}</code>
          ),
          pre: ({ children }) => (
            <pre className="bg-gray-50 p-3 rounded-lg overflow-x-auto text-[11px] font-mono mb-2">{children}</pre>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
