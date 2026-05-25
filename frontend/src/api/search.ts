import type { SearchResponse } from '../types';

const API_BASE = '/api/search';

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

export async function searchPapers(
  query: string,
  token?: string | null,
  limit = 10,
  offset = 0,
  yearFrom?: number | null,
  yearTo?: number | null,
  minCitations?: number | null,
): Promise<SearchResponse> {
  const params = new URLSearchParams({ q: query, limit: String(limit), offset: String(offset) });
  if (yearFrom != null) params.append('year_from', String(yearFrom));
  if (yearTo != null) params.append('year_to', String(yearTo));
  if (minCitations != null) params.append('min_citations', String(minCitations));

  const res = await fetch(`${API_BASE}/papers?${params}`, {
    headers: authHeaders(token),
  });
  return parseResponse<SearchResponse>(res);
}
