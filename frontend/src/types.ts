export interface PDFDocument {
  id: string;
  user_id: string;
  original_name: string;
  file_size: number;
  page_count?: number;
  status: 'pending' | 'extracted' | 'indexed' | 'failed';
  error_message?: string;
  extracted_text?: string;
  created_at: string;
  updated_at: string;
  is_favorite?: boolean;
  extracted_topics?: string[];
}

export interface Citation {
  source_id?: number;
  chunk_id: string;
  chunk_text: string;
  score: number;
  pdf_id: string;
  pdf_name: string;
  page_number?: number;
  block_id?: string;
  bbox?: number[] | null;
  section_path?: string[];
  source_block_type?: string;
  retrieval_sources?: string[];
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  ts: string;
  tokens?: { prompt: number; completion: number };
  citations?: Citation[];
  retrieval_query?: string;
}

export interface ChatSession {
  id: string;
  title: string;
  created_at: string;
  updated_at?: string;
  pdf_ids: string[];
  messages?: ChatMessage[];
}

export interface User {
  uid: string;
  displayName: string | null;
  email: string | null;
  photoURL?: string | null;
}

export type SortOption = 'newest' | 'oldest' | 'name';
export type ActiveView = 'dashboard' | 'reader' | 'comparison' | 'analyzer' | 'discovery';

export type AnalysisType =
  | 'benchmark_matrix'
  | 'hyperparameter_compare'
  | 'resource_compare'
  | 'methodology_mapping'
  | 'eval_conflicts'
  | 'paradigm_evolution'
  | 'dataset_bias_gap'
  | 'domain_gap'
  | 'performance_gap'
  | 'cross_domain_idea';

export interface AnalysisResultType {
  id: string;
  analysis_type: AnalysisType;
  result_json: any;
  pdf_names: string[];
  created_at: string;
}

export interface AnalysisHistoryType {
  analyses: AnalysisResultType[];
  total: number;
}

export interface SearchResult {
  s2_id: string;
  title: string;
  abstract?: string | null;
  year?: number | null;
  authors: string[];
  venue?: string | null;
  citation_count: number;
  open_access_pdf?: string | null;
}

export interface SearchResponse {
  total: number;
  query: string;
  papers: SearchResult[];
}

export interface RelatedPapersResponse {
  source_pdf_id: string;
  extracted_topics: string[];
  related_papers: SearchResult[];
  method: 'precomputed' | 'title_fallback' | string;
}
