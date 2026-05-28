import type { AnalysisType } from '../types';

const API_BASE = '/api/analyze';

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

export async function runAnalysis(
  pdfIds: string[],
  analysisType: AnalysisType,
  token?: string | null,
  customPrompt?: string | null,
): Promise<{
  id: string;
  analysis_type: string;
  result_json: any;
  pdf_names: string[];
  created_at: string;
}> {
  const res = await fetch(`${API_BASE}/run`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(token),
    },
    body: JSON.stringify({
      pdf_ids: pdfIds,
      analysis_type: analysisType,
      custom_prompt: customPrompt || null,
    }),
  });
  return parseResponse(res);
}

export async function fetchAnalyses(
  token?: string | null,
  skip = 0,
  limit = 20,
): Promise<{ analyses: any[]; total: number }> {
  const res = await fetch(`${API_BASE}/history?skip=${skip}&limit=${limit}`, {
    headers: authHeaders(token),
  });
  return parseResponse(res);
}

export async function fetchAnalysis(
  analysisId: string,
  token?: string | null,
): Promise<any> {
  const res = await fetch(`${API_BASE}/history/${analysisId}`, {
    headers: authHeaders(token),
  });
  return parseResponse(res);
}

export async function deleteAnalysis(
  analysisId: string,
  token?: string | null,
): Promise<any> {
  const res = await fetch(`${API_BASE}/history/${analysisId}`, {
    method: 'DELETE',
    headers: authHeaders(token),
  });
  return parseResponse(res);
}
