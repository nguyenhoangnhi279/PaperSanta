interface AnalyzerBenchmarkTableProps {
  result: any;
}

export default function AnalyzerBenchmarkTable({ result }: AnalyzerBenchmarkTableProps) {
  const table = result?.table;
  const notes = result?.notes;
  const title = result?.title || '';

  if (!Array.isArray(table) || table.length === 0) {
    return <div className="text-[var(--color-ink-secondary)] italic text-xs p-4">No table data available.</div>;
  }

  const columns = Object.keys(table[0]);

  return (
    <div className="space-y-4">
      {title && <h4 className="text-sm font-bold text-[var(--color-ink)]">{title}</h4>}
      <div className="overflow-x-auto border border-[var(--color-line)] rounded-xl">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="bg-[var(--color-surface-hover)] border-b border-[var(--color-line)]">
              {columns.map((col) => (
                <th key={col} className="py-3 px-4 font-bold text-[var(--color-ink-secondary)] uppercase tracking-wider whitespace-nowrap">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.map((row: any, i: number) => (
              <tr key={i} className="border-b border-[var(--color-line-subtle)] last:border-0 hover:bg-[var(--color-surface-hover)]/50">
                {columns.map((col) => (
                  <td key={col} className="py-3 px-4 text-[var(--color-ink)] whitespace-nowrap">
                    {row[col] ?? <span className="text-[var(--color-ink-secondary)] italic">N/A</span>}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {notes && (
        <div className="text-xs text-[var(--color-ink-secondary)] bg-[var(--color-surface-hover)] p-3 rounded-lg border border-[var(--color-line-subtle)]">
          <span className="font-bold text-[var(--color-ink)]">Notes: </span>{notes}
        </div>
      )}
    </div>
  );
}
