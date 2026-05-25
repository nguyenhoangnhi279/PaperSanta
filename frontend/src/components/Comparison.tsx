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
    <div className="flex-1 bg-white overflow-y-auto">
      <div className="max-w-5xl mx-auto p-12 space-y-8">
        <header className="space-y-2">
          <h2 className="text-2xl font-bold tracking-tight">Paper Comparison</h2>
          <p className="text-gray-400 text-sm">
            Select 2 or more papers to compare their metadata side by side.
          </p>
        </header>

        {/* Paper Selection */}
        <div className="border border-gray-100 rounded-2xl overflow-hidden shadow-sm">
          {papers.length === 0 ? (
            <div className="p-12 text-center text-gray-400 italic text-sm">
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
                      'border-b border-gray-50 last:border-0 transition-colors cursor-pointer',
                      selected.includes(paper.id) ? 'bg-blue-50/50' : 'hover:bg-gray-50/50'
                    )}
                  >
                    <td className="py-3 pl-6 w-10">
                      <div
                        className={cn(
                          'w-5 h-5 rounded border-2 flex items-center justify-center transition-colors',
                          selected.includes(paper.id)
                            ? 'bg-blue-600 border-blue-600 text-white'
                            : 'border-gray-300'
                        )}
                      >
                        {selected.includes(paper.id) && <Check size={12} />}
                      </div>
                    </td>
                    <td className="py-3 pl-2">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-blue-50 flex items-center justify-center text-blue-500 shrink-0">
                          <FileText size={16} />
                        </div>
                        <span className="text-sm font-bold text-gray-700">{paper.original_name}</span>
                      </div>
                    </td>
                    <td className="py-3 pr-6 text-right">
                      <span className="text-xs text-gray-400">
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
          <div className="border border-gray-100 rounded-2xl overflow-hidden shadow-sm">
            <table className="w-full text-left">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-100">
                  <th className="py-3 px-6 text-xs font-bold text-gray-400 uppercase tracking-wider w-40">Field</th>
                  {selectedPapers.map((p) => (
                    <th key={p.id} className="py-3 px-4 text-xs font-bold text-gray-700">
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
                  <tr key={row.label} className="border-b border-gray-50 last:border-0">
                    <td className="py-3 px-6 text-xs font-bold text-gray-500">{row.label}</td>
                    {selectedPapers.map((p) => (
                      <td key={p.id} className="py-3 px-4 text-xs text-gray-700">
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
          <div className="text-center py-12 text-gray-400 text-sm">
            Select at least one more paper to compare.
          </div>
        )}
      </div>
    </div>
  );
}
