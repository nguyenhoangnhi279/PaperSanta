interface AnalyzerGapResultProps {
  result: any;
}

export default function AnalyzerGapResult({ result }: AnalyzerGapResultProps) {
  const title = result?.title || '';

  if (!result || Object.keys(result).length === 0) {
    return <div className="text-gray-400 italic text-xs p-4">No gap analysis data available.</div>;
  }

  const gaps = Array.isArray(result.gaps_found) ? result.gaps_found : [];

  const severityColor = (s: string) => {
    switch ((s || '').toLowerCase()) {
      case 'high': return 'bg-red-100 text-red-800 border-red-200';
      case 'medium': return 'bg-amber-100 text-amber-800 border-amber-200';
      case 'low': return 'bg-green-100 text-green-800 border-green-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  return (
    <div className="space-y-5">
      {title && <h4 className="text-sm font-bold text-gray-800">{title}</h4>}

      {gaps.length > 0 && (
        <div>
          <h5 className="text-xs font-bold text-red-700 uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-red-500 inline-block" />
            Gaps Found ({gaps.length})
          </h5>
          <div className="space-y-3">
            {gaps.map((g: any, i: number) => (
              <div key={i} className={`border rounded-lg p-3 ${severityColor(g.severity)}`}>
                <div className="flex items-start justify-between gap-2">
                  <p className="text-xs font-semibold flex-1">{g.gap}</p>
                  {g.severity && (
                    <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded-full bg-white/60 shrink-0">
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
          <h5 className="text-xs font-bold text-green-700 uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-green-500 inline-block" />
            Opportunities
          </h5>
          <ul className="space-y-1.5">
            {result.opportunities.map((o: string, i: number) => (
              <li key={i} className="text-xs text-gray-700 flex items-start gap-2">
                <span className="text-green-500 font-bold mt-0.5">→</span>
                {o}
              </li>
            ))}
          </ul>
        </div>
      )}

      {Array.isArray(result.recommendations) && result.recommendations.length > 0 && (
        <div>
          <h5 className="text-xs font-bold text-blue-700 uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-blue-500 inline-block" />
            Recommendations
          </h5>
          <ul className="space-y-1.5">
            {result.recommendations.map((r: string, i: number) => (
              <li key={i} className="text-xs text-gray-700 flex items-start gap-2">
                <span className="text-blue-500 font-bold mt-0.5">💡</span>
                {r}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
