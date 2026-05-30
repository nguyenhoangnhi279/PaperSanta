import { useState } from 'react';
import { BarChart2, FileText, Check, X } from 'lucide-react';
import { cn } from '../lib/utils';
import type { PDFDocument } from '../types';

interface ComparisonProps {
  papers: PDFDocument[];
}

export default function Comparison({ papers }: ComparisonProps) {
  const [selected, setSelected] = useState<string[]>([]);

  const toggle = (id: string) => {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev]
    );
  };

  const selectedPapers = papers.filter((p) => selected.includes(p.id));

  return (
    <div className="flex-1 bg-[var(--color-surface)] overflow-y-auto">
      <div className="max-w-5xl mx-auto p-12 space-y-8">
        <header className="space-y-2">
          <h2 className="text-2xl font-bold tracking-tight">Paper Comparison</h2>
          <p className="text-[var(--color-ink-secondary)] text-sm">
            Select 2 or more papers to compare their metadata side by side.
          </p>
        </header>

        {/* Paper Selection */}
        <div className="border border-[var(--color-line-subtle)] rounded-2xl overflow-hidden shadow-sm">
          {papers.length === 0 ? (
            <div className="p-12 text-center text-[var(--color-ink-secondary)] italic text-sm">
              No papers to compare. Upload some PDFs first.
            </div>
          ) : (
            <table className="w-full text-left">
              <tbody>
                {papers.map((paper) => (
                  <tr
                    key={paper.id}
                    onClick={() => toggle(paper.id)}
                    className={cn(
                      'border-b border-[var(--color-line-subtle)] last:border-0 transition-colors cursor-pointer',
                      selected.includes(paper.id) ? 'bg-[var(--color-accent-subtle)]/50' : 'hover:bg-[var(--color-surface-hover)]/50'
                    )}
                  >
                    <td className="py-3 pl-6 w-10">
                      <div
                        className={cn(
                          'w-5 h-5 rounded border-2 flex items-center justify-center transition-colors',
                          selected.includes(paper.id)
                            ? 'bg-[var(--color-accent)] border-[var(--color-accent)] text-white'
                            : 'border-[var(--color-line)]'
                        )}
                      >
                        {selected.includes(paper.id) && <Check size={12} />}
                      </div>
                    </td>
                    <td className="py-3 pl-2">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-[var(--color-accent-subtle)] flex items-center justify-center text-[var(--color-accent)] shrink-0">
                          <FileText size={16} />
                        </div>
                        <span className="text-sm font-bold text-[var(--color-ink)]">{paper.original_name}</span>
                      </div>
                    </td>
                    <td className="py-3 pr-6 text-right">
                      <span className="text-xs text-[var(--color-ink-secondary)]">
                        {paper.page_count ? `${paper.page_count} pages` : ''}
                        {paper.file_size ? ` · ${(paper.file_size / 1024).toFixed(0)} KB` : ''}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Comparison Table */}
        {selectedPapers.length >= 2 && (
          <div className="border border-[var(--color-line-subtle)] rounded-2xl overflow-hidden shadow-sm">
            <table className="w-full text-left">
              <thead>
                <tr className="bg-[var(--color-surface-hover)] border-b border-[var(--color-line-subtle)]">
                  <th className="py-3 px-6 text-xs font-bold text-[var(--color-ink-secondary)] uppercase tracking-wider w-40">Field</th>
                  {selectedPapers.map((p) => (
                    <th key={p.id} className="py-3 px-4 text-xs font-bold text-[var(--color-ink)]">
                      {p.original_name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[
                  { label: 'Status', value: (p: PDFDocument) => p.status },
                  { label: 'Pages', value: (p: PDFDocument) => p.page_count?.toString() || 'N/A' },
                  { label: 'Size', value: (p: PDFDocument) => p.file_size ? `${(p.file_size / 1024).toFixed(0)} KB` : 'N/A' },
                  { label: 'Created', value: (p: PDFDocument) => new Date(p.created_at).toLocaleDateString() },
                  { label: 'Indexed', value: (p: PDFDocument) => p.status === 'indexed' ? '✅' : '❌' },
                ].map((row) => (
                  <tr key={row.label} className="border-b border-[var(--color-line-subtle)] last:border-0">
                    <td className="py-3 px-6 text-xs font-bold text-[var(--color-ink-secondary)]">{row.label}</td>
                    {selectedPapers.map((p) => (
                      <td key={p.id} className="py-3 px-4 text-xs text-[var(--color-ink)]">
                        {row.value(p)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {selectedPapers.length === 1 && (
          <div className="text-center py-12 text-[var(--color-ink-secondary)] text-sm">
            Select at least one more paper to compare.
          </div>
        )}
      </div>
    </div>
  );
}
