import type { ChatSession } from '../types';

const API_BASE = '/api/rag';

function authHeaders(token?: string | null): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function parseResponse<T>(response: Response): Promise<T> {
  const text = await response.text();
  let data: any;
  try {
    data = JSON.parse(text);
  } catch {
    data = null;
  }

  if (response.ok) {
    return data as T;
  }
  throw new Error(data?.detail || data?.message || response.statusText || 'API error');
}

export async function ragQuery(
  queryText: string,
  token?: string | null,
  pdfId?: string | null,
  topK = 5
): Promise<{ results: any[]; query_time_ms: number }> {
  const res = await fetch(`${API_BASE}/query`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(token),
    },
    body: JSON.stringify({ query_text: queryText, top_k: topK, pdf_id: pdfId }),
  });
  return parseResponse(res);
}

export async function ragChat(
  queryText: string,
  pdfIds: string[],
  token?: string | null,
  sessionId?: string | null,
  topK = 5
): Promise<{ answer: string; session_id: string; citations: any[]; prompt_tokens: number; completion_tokens: number; retrieval_query?: string | null }> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(token),
    },
    body: JSON.stringify({
      query_text: queryText,
      pdf_ids: pdfIds,
      session_id: sessionId,
      top_k: topK,
    }),
  });
  return parseResponse(res);
}

export async function explainSelection(
  payload: {
    pdf_id: string;
    selected_text: string;
    page_number?: number | null;
    surrounding_text?: string | null;
    top_k?: number;
  },
  token?: string | null
): Promise<{ answer: string; citations: any[]; prompt_tokens: number; completion_tokens: number }> {
  const res = await fetch(`${API_BASE}/explain-selection`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(token),
    },
    body: JSON.stringify(payload),
  });
  return parseResponse(res);
}

export async function fetchSessions(
  token?: string | null,
  skip = 0,
  limit = 20
): Promise<{ sessions: ChatSession[]; total: number }> {
  const res = await fetch(`${API_BASE}/sessions?skip=${skip}&limit=${limit}`, {
    headers: authHeaders(token),
  });
  return parseResponse(res);
}

export async function fetchSession(
  sessionId: string,
  token?: string | null
): Promise<ChatSession> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}`, {
    headers: authHeaders(token),
  });
  return parseResponse(res);
}

export async function deleteSession(sessionId: string, token?: string | null): Promise<any> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}`, {
    method: 'DELETE',
    headers: authHeaders(token),
  });
  return parseResponse(res);
}
