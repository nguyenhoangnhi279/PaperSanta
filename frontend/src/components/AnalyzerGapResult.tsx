interface AnalyzerGapResultProps {
  result: any;
}

export default function AnalyzerGapResult({ result }: AnalyzerGapResultProps) {
  const title = result?.title || '';

  if (!result || Object.keys(result).length === 0) {
    return <div className="text-[var(--color-ink-secondary)] italic text-xs p-4">No gap analysis data available.</div>;
  }

  const gaps = Array.isArray(result.gaps_found) ? result.gaps_found : [];

  const severityColor = (s: string) => {
    switch ((s || '').toLowerCase()) {
      case 'high': return 'bg-[var(--color-danger-subtle)] text-[var(--color-danger)] border-[var(--color-danger-subtle)]';
      case 'medium': return 'bg-[var(--color-warning-subtle)] text-[var(--color-warning)] border-[var(--color-warning-border)]';
      case 'low': return 'bg-[var(--color-success-subtle)] text-[var(--color-success)] border-[var(--color-success-border)]';
      default: return 'bg-[var(--color-surface-hover)] text-[var(--color-ink)] border-[var(--color-line)]';
    }
  };

  return (
    <div className="space-y-5">
      {title && <h4 className="text-sm font-bold text-[var(--color-ink)]">{title}</h4>}

      {gaps.length > 0 && (
        <div>
          <h5 className="text-xs font-bold text-[var(--color-danger)] uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-[var(--color-danger)] inline-block" />
            Gaps Found ({gaps.length})
          </h5>
          <div className="space-y-3">
            {gaps.map((g: any, i: number) => (
              <div key={i} className={`border rounded-lg p-3 ${severityColor(g.severity)}`}>
                <div className="flex items-start justify-between gap-2">
                  <p className="text-xs font-semibold flex-1">{g.gap}</p>
                  {g.severity && (
                    <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded-full bg-[var(--color-surface)]/80 border border-[var(--color-line-subtle)] shrink-0">
                      {g.severity}
                    </span>
                  )}
                </div>
                {g.evidence && <p className="text-[11px] mt-1.5 opacity-80">{g.evidence}</p>}
              </div>
            ))}
          </div>
        </div>
      )}

      {Array.isArray(result.opportunities) && result.opportunities.length > 0 && (
        <div>
          <h5 className="text-xs font-bold text-[var(--color-success)] uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-[var(--color-success)] inline-block" />
            Opportunities
          </h5>
          <ul className="space-y-1.5">
            {result.opportunities.map((o: string, i: number) => (
              <li key={i} className="text-xs text-[var(--color-ink)] flex items-start gap-2">
                <span className="text-[var(--color-success)] font-bold mt-0.5">→</span>
                {o}
              </li>
            ))}
          </ul>
        </div>
      )}

      {Array.isArray(result.recommendations) && result.recommendations.length > 0 && (
        <div>
          <h5 className="text-xs font-bold text-[var(--color-info)] uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-[var(--color-info)] inline-block" />
            Recommendations
          </h5>
          <ul className="space-y-1.5">
            {result.recommendations.map((r: string, i: number) => (
              <li key={i} className="text-xs text-[var(--color-ink)] flex items-start gap-2">
                <span className="text-[var(--color-info)] font-bold mt-0.5">💡</span>
                {r}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
