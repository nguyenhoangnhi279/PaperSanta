interface AnalyzerSynthesisResultProps {
  result: any;
}

export default function AnalyzerSynthesisResult({ result }: AnalyzerSynthesisResultProps) {
  const title = result?.title || '';

  if (!result || Object.keys(result).length === 0) {
    return <div className="text-gray-400 italic text-xs p-4">No synthesis data available.</div>;
  }

  const hasThemes = Array.isArray(result.comparison_themes) && result.comparison_themes.length > 0;
  const hasLineageTracks = Array.isArray(result.lineage_tracks) && result.lineage_tracks.length > 0;
  const hasConflicts = !hasThemes && Array.isArray(result.conflicts) && result.conflicts.length > 0;
  const hasLineage = !hasLineageTracks && Array.isArray(result.lineage) && result.lineage.length > 0;
  const hasConsensus = !hasThemes && Array.isArray(result.consensus) && result.consensus.length > 0;
  const hasDifferences = !hasThemes && Array.isArray(result.differences) && result.differences.length > 0;

  const renderThemeCard = (theme: any, i: number) => {
    const hasThemeConflicts = Array.isArray(theme.conflicts) && theme.conflicts.length > 0;
    return (
      <div key={i} className="border border-gray-200 rounded-xl overflow-hidden">
        <div className="bg-gray-50 px-4 py-2.5 border-b border-gray-100">
          <p className="text-xs font-bold text-gray-700">{theme.theme_name}</p>
        </div>
        <div className="p-4 space-y-3">
          {theme.consensus ? (
            <div className="bg-green-50 border border-green-100 rounded-lg p-3">
              <p className="text-[10px] font-bold text-green-700 uppercase tracking-wider mb-1">Consensus</p>
              <p className="text-xs text-green-800">{theme.consensus}</p>
            </div>
          ) : (
            <div className="bg-gray-50 border border-gray-100 rounded-lg p-3">
              <p className="text-[10px] text-gray-400 italic">No consensus found</p>
            </div>
          )}

          {theme.differences && (
            <div className="bg-orange-50 border border-orange-100 rounded-lg p-3">
              <p className="text-[10px] font-bold text-orange-700 uppercase tracking-wider mb-1">Differences</p>
              <p className="text-xs text-orange-800">{theme.differences}</p>
            </div>
          )}

          {hasThemeConflicts && theme.conflicts.map((c: any, j: number) => (
            <div key={j} className="bg-red-50 border border-red-100 rounded-lg p-3">
              <p className="text-[10px] font-bold text-red-700 uppercase tracking-wider mb-1">Conflict</p>
              <p className="text-xs font-semibold text-red-800">{c.issue}</p>
              <div className="mt-1.5 space-y-1">
                <p className="text-[11px] text-red-700"><span className="font-bold">Paper A: </span>{c.paper_a_claim}</p>
                <p className="text-[11px] text-red-700"><span className="font-bold">Paper B: </span>{c.paper_b_claim}</p>
              </div>
              {c.possible_reason && (
                <p className="text-[11px] text-red-600 mt-1.5 italic">Possible reason: {c.possible_reason}</p>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  };

  const renderLineageTrack = (track: any, i: number) => (
    <div key={i} className="border border-gray-200 rounded-xl overflow-hidden">
      <div className="bg-blue-50 px-4 py-2.5 border-b border-blue-100 flex items-center gap-2">
        <span className="text-xs font-bold text-blue-800">{track.from_paper || track.from}</span>
        <span className="text-blue-400 text-xs">→</span>
        <span className="text-xs font-bold text-blue-800">{track.to_paper || track.to}</span>
      </div>
      <div className="p-4 space-y-3">
        {Array.isArray(track.inherited_points) && track.inherited_points.length > 0 && (
          <div>
            <p className="text-[10px] font-bold text-green-700 uppercase tracking-wider mb-1.5">Inherited</p>
            <ul className="space-y-1">
              {track.inherited_points.map((pt: string, j: number) => (
                <li key={j} className="text-xs text-gray-700 flex items-start gap-2">
                  <span className="text-green-500 mt-0.5 shrink-0">→</span>
                  {pt}
                </li>
              ))}
            </ul>
          </div>
        )}
        {track.inherited_idea && !track.inherited_points && (
          <div className="bg-green-50 border border-green-100 rounded-lg p-3">
            <p className="text-[10px] font-bold text-green-700 uppercase tracking-wider mb-1">Inherited</p>
            <p className="text-xs text-green-800">{track.inherited_idea}</p>
          </div>
        )}

        {Array.isArray(track.improvement_points) && track.improvement_points.length > 0 && (
          <div>
            <p className="text-[10px] font-bold text-blue-700 uppercase tracking-wider mb-1.5">Improvements</p>
            <ul className="space-y-1">
              {track.improvement_points.map((pt: string, j: number) => (
                <li key={j} className="text-xs text-gray-700 flex items-start gap-2">
                  <span className="text-blue-500 mt-0.5 shrink-0">+</span>
                  {pt}
                </li>
              ))}
            </ul>
          </div>
        )}
        {track.improvement && !track.improvement_points && (
          <div className="bg-blue-50 border border-blue-100 rounded-lg p-3">
            <p className="text-[10px] font-bold text-blue-700 uppercase tracking-wider mb-1">Improvement</p>
            <p className="text-xs text-blue-800">{track.improvement}</p>
          </div>
        )}
      </div>
    </div>
  );

  return (
    <div className="space-y-5">
      {title && <h4 className="text-sm font-bold text-gray-800">{title}</h4>}

      {/* New: comparison_themes structure */}
      {hasThemes && (
        <div className="space-y-3">
          {result.comparison_themes.map((theme: any, i: number) => renderThemeCard(theme, i))}
        </div>
      )}

      {/* New: lineage_tracks structure */}
      {hasLineageTracks && (
        <div className="space-y-3">
          {result.lineage_tracks.map((track: any, i: number) => renderLineageTrack(track, i))}
        </div>
      )}

      {/* Fallback: old consensus */}
      {hasConsensus && (
        <div>
          <h5 className="text-xs font-bold text-green-700 uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-green-500 inline-block" />
            Consensus
          </h5>
          <div className="space-y-2">
            {result.consensus.map((c: any, i: number) => (
              <div key={i} className="bg-green-50 border border-green-100 rounded-lg p-3">
                <p className="text-xs font-semibold text-green-800">{c.point || c.technique}</p>
                {c.detail && <p className="text-xs text-green-700 mt-1">{c.detail}</p>}
                {c.papers && <p className="text-[10px] text-green-500 mt-1">Papers: {c.papers.join(', ')}</p>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Fallback: old differences */}
      {hasDifferences && (
        <div>
          <h5 className="text-xs font-bold text-orange-700 uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-orange-500 inline-block" />
            Differences
          </h5>
          <div className="space-y-2">
            {result.differences.map((d: any, i: number) => (
              <div key={i} className="bg-orange-50 border border-orange-100 rounded-lg p-3">
                <p className="text-xs font-semibold text-orange-800">{d.aspect || d.technique}</p>
                {d.paper_a && <p className="text-[11px] text-orange-700 mt-1">Paper A: {d.paper_a}</p>}
                {d.paper_b && <p className="text-[11px] text-orange-700">Paper B: {d.paper_b}</p>}
                {d.implication && <p className="text-[10px] text-orange-600 mt-1 italic">Implication: {d.implication}</p>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Fallback: old conflicts */}
      {hasConflicts && (
        <div>
          <h5 className="text-xs font-bold text-red-700 uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-red-500 inline-block" />
            Conflicts
          </h5>
          <div className="space-y-2">
            {result.conflicts.map((c: any, i: number) => (
              <div key={i} className="bg-red-50 border border-red-100 rounded-lg p-3">
                <p className="text-xs font-semibold text-red-800">{c.issue}</p>
                <div className="mt-1.5 space-y-1">
                  <p className="text-[11px] text-red-700"><span className="font-bold">Paper A: </span>{c.paper_a_claim}</p>
                  <p className="text-[11px] text-red-700"><span className="font-bold">Paper B: </span>{c.paper_b_claim}</p>
                </div>
                {c.possible_reason && <p className="text-[11px] text-red-600 mt-1.5 italic">Possible reason: {c.possible_reason}</p>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Fallback: old lineage */}
      {hasLineage && (
        <div>
          <h5 className="text-xs font-bold text-blue-700 uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-blue-500 inline-block" />
            Lineage / Inheritance
          </h5>
          <div className="space-y-3">
            {result.lineage.map((l: any, i: number) => (
              <div key={i} className="bg-blue-50 border border-blue-100 rounded-lg p-3">
                <div className="flex items-start gap-2">
                  <div className="text-xs font-bold text-blue-800 min-w-0 flex-1">
                    <span className="text-blue-500">← </span>{l.from}
                  </div>
                  <div className="text-xs font-bold text-blue-800 min-w-0 flex-1 text-right">
                    {l.to}<span className="text-blue-500"> →</span>
                  </div>
                </div>
                {l.inherited_idea && <p className="text-[11px] text-blue-700 mt-1.5"><span className="font-bold">Inherited: </span>{l.inherited_idea}</p>}
                {l.improvement && <p className="text-[11px] text-blue-700"><span className="font-bold">Improvement: </span>{l.improvement}</p>}
              </div>
            ))}
          </div>
        </div>
      )}

      {result.recommendation && (
        <div className="bg-blue-50 border border-blue-100 rounded-lg p-3">
          <p className="text-xs font-bold text-blue-800">Recommendation</p>
          <p className="text-xs text-blue-700 mt-1">{result.recommendation}</p>
        </div>
      )}

      {result.summary && (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-3">
          <p className="text-xs font-bold text-gray-700">Summary</p>
          <p className="text-xs text-gray-600 mt-1">{result.summary}</p>
        </div>
      )}

      {result.overall_assessment && (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-3">
          <p className="text-xs font-bold text-gray-700">Overall Assessment</p>
          <p className="text-xs text-gray-600 mt-1">{result.overall_assessment}</p>
        </div>
      )}

      {result.agreements && Array.isArray(result.agreements) && result.agreements.length > 0 && (
        <div>
          <h5 className="text-xs font-bold text-green-700 uppercase tracking-wider mb-2">Agreements</h5>
          <ul className="space-y-1">
            {result.agreements.map((a: string, i: number) => (
              <li key={i} className="text-xs text-gray-700 flex items-start gap-2">
                <span className="text-green-500 mt-0.5">✓</span>
                {a}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
