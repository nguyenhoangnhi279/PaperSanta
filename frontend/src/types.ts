export interface PDFDocument {
  id: string;
  user_id: string;
  original_name: string;
  file_size: number;
  page_count?: number;
  status: 'pending' | 'extracted' | 'indexed' | 'failed';
  extracted_text?: string;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  timestamp?: number;
}

export interface Citation {
  pdf_name: string;
  chunk_text: string;
  score: number;
  page_number?: number;
}

export interface ChatSession {
  id: string;
  title: string;
  created_at: string;
  message_count?: number;
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
