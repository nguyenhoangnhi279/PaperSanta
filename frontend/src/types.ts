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
}

export interface Citation {
  chunk_id: string;
  chunk_text: string;
  score: number;
  pdf_id: string;
  pdf_name: string;
  page_number?: number;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  ts: string;
  tokens?: { prompt: number; completion: number };
  citations?: Citation[];
}

export interface ChatSession {
  id: string;
  title: string;
  created_at: string;
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
export type ActiveView = 'dashboard' | 'reader' | 'comparison' | 'discovery';
