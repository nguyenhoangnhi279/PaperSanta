import { useState, useEffect, useCallback } from 'react';
import {
  BarChart2, Check, Sparkles, Search, AlertCircle,
  History, Trash2, Brain, GitBranch, Crosshair, Zap,
} from 'lucide-react';
import { cn } from '../lib/utils';
import { useAuth } from '../context/AuthContext';
import { runAnalysis, fetchAnalyses, fetchAnalysis, deleteAnalysis } from '../api/analyze';
import AnalyzerBenchmarkTable from './AnalyzerBenchmarkTable';
import AnalyzerSynthesisResult from './AnalyzerSynthesisResult';
import AnalyzerGapResult from './AnalyzerGapResult';
import type { PDFDocument, AnalysisType } from '../types';

interface AnalyzerProps {
  papers: PDFDocument[];
}

type AnalyzerMode = 'benchmark' | 'synthesis' | 'gap';

interface ModeConfig {
  id: AnalyzerMode;
  label: string;
  icon: typeof BarChart2;
  description: string;
  types: { id: AnalysisType; label: string; description: string; icon: typeof BarChart2 }[];
}

const modes: ModeConfig[] = [
  {
    id: 'benchmark',
    label: 'Benchmark Matrix',
    icon: BarChart2,
    description: 'Compare models, hyperparameters, and resource usage across papers.',
    types: [
      { id: 'benchmark_matrix', label: 'Model Comparison', description: 'Compare YOLO, RT-DETR... side by side', icon: BarChart2 },
      { id: 'hyperparameter_compare', label: 'Hyperparameter Compare', description: 'Training configs: LR, Batch, Optimizer...', icon: Zap },
      { id: 'resource_compare', label: 'Resource Comparison', description: 'Parameters, FLOPs, VRAM requirements', icon: Crosshair },
    ],
  },
  {
    id: 'synthesis',
    label: 'Synthesis',
    icon: GitBranch,
    description: 'Find consensus, conflicts, and evolution across papers.',
    types: [
      { id: 'methodology_mapping', label: 'Methodology Mapping', description: 'Compare architecture, loss, and input representation', icon: Search },
      { id: 'eval_conflicts', label: 'Eval Conflicts', description: 'Find result contradictions and metric mismatches', icon: AlertCircle },
      { id: 'paradigm_evolution', label: 'Paradigm Evolution', description: 'Trace lineage and inheritance between methods', icon: GitBranch },
    ],
  },
  {
    id: 'gap',
    label: 'Research Gap',
    icon: Brain,
    description: 'Identify dataset bias, domain gaps, and performance issues.',
    types: [
      { id: 'dataset_bias_gap', label: 'Dataset Bias Gap', description: 'Find demographic bias in training data', icon: Search },
      { id: 'domain_gap', label: 'Domain Gap', description: 'Uncovered application domains', icon: Crosshair },
      { id: 'performance_gap', label: 'Performance Gap', description: 'Speed vs accuracy bottlenecks', icon: Zap },
      { id: 'cross_domain_idea', label: 'Cross-domain Idea', description: 'Transfer techniques between fields', icon: Brain },
    ],
  },
];

const allTypes = modes.flatMap((m) => m.types);

export default function Analyzer({ papers }: AnalyzerProps) {
  const { session: authSession } = useAuth();
  const token = authSession?.access_token;

  const [mode, setMode] = useState<AnalyzerMode>('benchmark');
  const [selectedType, setSelectedType] = useState<AnalysisType | null>(null);
  const [selectedPdfIds, setSelectedPdfIds] = useState<string[]>([]);
  const [customPrompt, setCustomPrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [showPdfSelector, setShowPdfSelector] = useState(false);

  const loadHistory = useCallback(async () => {
    if (!token) return;
    try {
      const data = await fetchAnalyses(token);
      setHistory(data.analyses || []);
    } catch { /* ignore */ }
  }, [token]);

  useEffect(() => { loadHistory(); }, [loadHistory]);

  const loadExistingAnalysis = async (id: string) => {
    if (!token) return;
    try {
      const data = await fetchAnalysis(id, token);
      const mt = allTypes.find((t) => t.id === data.analysis_type);
      if (mt) {
        const parentMode = modes.find((m) => m.types.some((t) => t.id === data.analysis_type));
        if (parentMode) setMode(parentMode.id);
        setSelectedType(data.analysis_type);
      }
      setResult(data);
      setError(null);
      setShowHistory(false);
    } catch { /* ignore */ }
  };

  const handleDelete = async (id: string) => {
    if (!token) return;
    try {
      await deleteAnalysis(id, token);
      if (result?.id === id) setResult(null);
      loadHistory();
    } catch { /* ignore */ }
  };

  const togglePdf = (id: string) => {
    setSelectedPdfIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const handleRun = async () => {
    if (!token || !selectedType || selectedPdfIds.length < 2) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await runAnalysis(selectedPdfIds, selectedType, token, customPrompt || null);
      setResult(data);
      loadHistory();
    } catch (err: any) {
      setError(err.message || 'Analysis failed');
    } finally {
      setLoading(false);
    }
  };

  const currentModeTypes = modes.find((m) => m.id === mode)?.types || [];
  const selectedDocs = papers.filter((d) => selectedPdfIds.includes(d.id));

  const getTypeName = (type: string) => allTypes.find((t) => t.id === type)?.label || type;

  return (
    <div className="flex-1 bg-white overflow-y-auto">
      <div className="max-w-5xl mx-auto p-8 space-y-6">
        {/* Header */}
        <header className="flex items-center justify-between">
          <div className="space-y-1">
            <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
              <span className="p-1.5 bg-purple-50 text-purple-600 rounded-lg">
                <Brain size={20} />
              </span>
              Analyzer
            </h2>
            <p className="text-gray-400 text-sm">Multi-paper AI analysis</p>
          </div>
          <button
            onClick={() => setShowHistory(!showHistory)}
            className="flex items-center gap-1.5 text-xs font-bold text-gray-500 hover:text-gray-700 border border-gray-200 px-3 py-1.5 rounded-lg transition-colors"
          >
            <History size={14} />
            History
          </button>
        </header>

        {/* Mode tabs */}
        <div className="flex gap-2">
          {modes.map((m) => {
            const Icon = m.icon;
            return (
              <button
                key={m.id}
                onClick={() => { setMode(m.id); setSelectedType(null); setResult(null); setError(null); }}
                className={cn(
                  'flex-1 p-4 rounded-xl border text-left transition-all',
                  mode === m.id
                    ? 'bg-purple-50 border-purple-200 shadow-sm'
                    : 'bg-white border-gray-100 hover:border-gray-200 hover:shadow-sm'
                )}
              >
                <div className={cn(
                  'w-8 h-8 rounded-lg flex items-center justify-center mb-2',
                  mode === m.id ? 'bg-purple-100 text-purple-600' : 'bg-gray-50 text-gray-400'
                )}>
                  <Icon size={16} />
                </div>
                <p className={cn(
                  'text-xs font-bold',
                  mode === m.id ? 'text-purple-800' : 'text-gray-700'
                )}>{m.label}</p>
                <p className="text-[10px] text-gray-400 mt-0.5">{m.description}</p>
              </button>
            );
          })}
        </div>

        {/* Sub-mode cards (analysis types) */}
        <div>
          <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-2">
            Select analysis type
          </p>
          <div className="grid grid-cols-3 gap-2">
            {currentModeTypes.map((t) => {
              const Icon = t.icon;
              const isSelected = selectedType === t.id;
              return (
                <button
                  key={t.id}
                  onClick={() => { setSelectedType(t.id); setResult(null); setError(null); }}
                  className={cn(
                    'p-3 rounded-xl border text-left transition-all',
                    isSelected
                      ? 'bg-blue-50 border-blue-200 shadow-sm'
                      : 'bg-white border-gray-100 hover:border-gray-200 hover:shadow-sm'
                  )}
                >
                  <div className={cn(
                    'w-7 h-7 rounded-lg flex items-center justify-center mb-1.5',
                    isSelected ? 'bg-blue-100 text-blue-600' : 'bg-gray-50 text-gray-400'
                  )}>
                    <Icon size={14} />
                  </div>
                  <p className={cn(
                    'text-xs font-bold leading-tight',
                    isSelected ? 'text-blue-800' : 'text-gray-700'
                  )}>{t.label}</p>
                  <p className="text-[10px] text-gray-400 mt-0.5 leading-tight">{t.description}</p>
                </button>
              );
            })}
          </div>
        </div>

        {/* PDF Selection */}
        <div>
          <div className="flex items-center justify-between">
            <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">
              Select PDFs ({selectedPdfIds.length} selected)
            </p>
            <button
              onClick={() => setShowPdfSelector(!showPdfSelector)}
              className="text-[10px] text-blue-600 hover:text-blue-700 font-bold"
            >
              {showPdfSelector ? 'Collapse' : selectedPdfIds.length < 2 ? 'Select papers...' : 'Change'}
            </button>
          </div>

          {selectedDocs.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-1.5 mb-2">
              {selectedDocs.map((d) => (
                <span key={d.id} className="inline-flex items-center gap-1 bg-blue-50 text-blue-700 text-[10px] px-2 py-0.5 rounded-full border border-blue-100">
                  {d.original_name}
                  <button onClick={() => togglePdf(d.id)} className="hover:text-red-500 font-bold">&times;</button>
                </span>
              ))}
            </div>
          )}

          {showPdfSelector && (
            <div className="mt-1 border border-gray-100 rounded-xl overflow-hidden max-h-48 overflow-y-auto">
              {papers.length === 0 ? (
                <div className="p-4 text-center text-xs text-gray-400 italic">No PDFs uploaded yet</div>
              ) : (
                papers.map((doc) => (
                  <div
                    key={doc.id}
                    onClick={() => togglePdf(doc.id)}
                    className="flex items-center gap-3 px-4 py-2.5 text-xs hover:bg-gray-50 cursor-pointer border-b border-gray-50 last:border-0 transition-colors"
                  >
                    <div
                      className={cn(
                        'w-5 h-5 rounded border-2 flex items-center justify-center shrink-0 transition-colors',
                        selectedPdfIds.includes(doc.id)
                          ? 'bg-blue-600 border-blue-600 text-white'
                          : 'border-gray-300'
                      )}
                    >
                      {selectedPdfIds.includes(doc.id) && <Check size={12} />}
                    </div>
                    <span className="truncate flex-1">{doc.original_name}</span>
                    <span className={cn(
                      'text-[10px] px-1.5 py-0.5 rounded-full',
                      doc.status === 'indexed' ? 'bg-green-100 text-green-700' :
                      doc.status === 'failed' ? 'bg-red-100 text-red-700' :
                      'bg-amber-100 text-amber-700'
                    )}>
                      {doc.status}
                    </span>
                  </div>
                ))
              )}
            </div>
          )}
          {selectedPdfIds.length < 2 && selectedPdfIds.length > 0 && (
            <p className="text-[10px] text-amber-600 mt-1">Select at least 2 papers to run analysis.</p>
          )}
        </div>

        {/* Custom Prompt */}
        <div>
          <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1.5">
            Custom prompt (optional)
          </p>
          <textarea
            value={customPrompt}
            onChange={(e) => setCustomPrompt(e.target.value)}
            placeholder="Override the default prompt with your own question, e.g.: 'Focus only on the training datasets and compare their sizes...'"
            rows={2}
            className="w-full border border-gray-200 rounded-xl p-3 text-xs focus:ring-2 focus:ring-blue-100 focus:border-blue-300 outline-none resize-none placeholder:text-gray-300 bg-gray-50/50"
          />
        </div>

        {/* Run Button */}
        <button
          onClick={handleRun}
          disabled={loading || !selectedType || selectedPdfIds.length < 2}
          className={cn(
            'w-full py-3 rounded-xl text-sm font-bold transition-all flex items-center justify-center gap-2',
            loading || !selectedType || selectedPdfIds.length < 2
              ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
              : 'bg-purple-600 text-white hover:bg-purple-700 shadow-md shadow-purple-200'
          )}
        >
          {loading ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Analyzing...
            </>
          ) : (
            <>
              <Sparkles size={16} />
              {selectedType ? `Run ${allTypes.find((t) => t.id === selectedType)?.label || ''}` : 'Select analysis type'}
            </>
          )}
        </button>

        {/* Error */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3">
            <AlertCircle size={16} className="text-red-500 mt-0.5 shrink-0" />
            <div>
              <p className="text-xs font-bold text-red-800">Analysis failed</p>
              <p className="text-xs text-red-600 mt-0.5">{error}</p>
            </div>
          </div>
        )}

        {/* Result */}
        {result && (
          <div className="border border-gray-200 rounded-2xl overflow-hidden shadow-sm">
            <div className="bg-gray-50 px-5 py-3 border-b border-gray-100 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Sparkles size={14} className="text-purple-500" />
                <span className="text-xs font-bold text-gray-700">
                  {getTypeName(result.analysis_type)}
                </span>
                <span className="text-[10px] text-gray-400">
                  on {result.pdf_names?.join(', ')}
                </span>
              </div>
              <span className="text-[10px] text-gray-400">
                {result.created_at ? new Date(result.created_at).toLocaleString() : ''}
              </span>
            </div>
            <div className="p-5">
              {result.result_json?.error ? (
                <div className="text-xs text-gray-500 italic">{result.result_json.error}</div>
              ) : result.result_json?.raw_output ? (
                <div className="text-xs text-gray-700 whitespace-pre-wrap font-mono bg-gray-50 p-3 rounded-lg">
                  {result.result_json.raw_output}
                </div>
              ) : (
                <>
                  {mode === 'benchmark' && <AnalyzerBenchmarkTable result={result.result_json} />}
                  {mode === 'synthesis' && <AnalyzerSynthesisResult result={result.result_json} />}
                  {mode === 'gap' && <AnalyzerGapResult result={result.result_json} />}
                </>
              )}
            </div>
          </div>
        )}

        {/* History sidebar (dropdown) */}
        {showHistory && (
          <div className="border border-gray-100 rounded-2xl overflow-hidden shadow-sm">
            <div className="px-5 py-3 bg-gray-50 border-b border-gray-100 flex items-center justify-between">
              <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Analysis History</span>
              <button onClick={() => setShowHistory(false)} className="text-[10px] text-gray-400 hover:text-gray-600">&times;</button>
            </div>
            {history.length === 0 ? (
              <div className="p-8 text-center text-xs text-gray-400 italic">No previous analyses</div>
            ) : (
              <div className="max-h-60 overflow-y-auto">
                {history.map((h) => (
                  <div
                    key={h.id}
                    className={cn(
                      'flex items-center justify-between px-5 py-3 text-xs hover:bg-gray-50 cursor-pointer border-b border-gray-50 last:border-0 transition-colors',
                      result?.id === h.id && 'bg-blue-50'
                    )}
                    onClick={() => loadExistingAnalysis(h.id)}
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-6 h-6 rounded-full bg-purple-50 text-purple-500 flex items-center justify-center shrink-0">
                        <Brain size={12} />
                      </div>
                      <div className="min-w-0">
                        <p className="font-bold text-gray-700 truncate">{getTypeName(h.analysis_type)}</p>
                        <p className="text-[10px] text-gray-400 truncate">{h.pdf_names?.join(', ') || 'No papers'}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-[10px] text-gray-400">
                        {h.created_at ? new Date(h.created_at).toLocaleDateString() : ''}
                      </span>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDelete(h.id); }}
                        className="p-1 text-gray-300 hover:text-red-500 transition-colors"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
