import type { PDFDocument } from '../types';

const API_BASE = '/api/pdf';

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
  const error = new Error(data?.detail || data?.message || response.statusText || 'API error');
  (error as any).status = response.status;
  throw error;
}

export async function fetchPdfs(token?: string | null): Promise<{ documents: PDFDocument[] }> {
  const res = await fetch(`${API_BASE}/`, { headers: authHeaders(token) });
  return parseResponse(res);
}

export async function uploadPdfFile(file: File, token?: string | null): Promise<PDFDocument> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${API_BASE}/upload`, {
    method: 'POST',
    body: formData,
    headers: authHeaders(token),
  });

  return parseResponse<PDFDocument>(res);
}

export async function indexPdfFile(id: string, token?: string | null): Promise<any> {
  const res = await fetch(`${API_BASE}/${id}/index`, {
    method: 'POST',
    headers: authHeaders(token),
  });
  return parseResponse(res);
}

export async function getPdfStatus(id: string, token?: string | null): Promise<PDFDocument> {
  const res = await fetch(`${API_BASE}/${id}`, {
    headers: authHeaders(token),
  });
  return parseResponse<PDFDocument>(res);
}

export async function deletePdfById(id: string, token?: string | null): Promise<any> {
  const res = await fetch(`${API_BASE}/${id}`, {
    method: 'DELETE',
    headers: authHeaders(token),
  });
  return parseResponse(res);
}

export async function summarizePdf(
  id: string,
  token?: string | null
): Promise<{ summary: string; generated_at: string; cached: boolean }> {
  const res = await fetch(`${API_BASE}/${id}/summarize`, {
    method: 'POST',
    headers: authHeaders(token),
  });
  return parseResponse(res);
}

export async function getPdfFileUrl(id: string, token?: string | null): Promise<{ url: string }> {
  const res = await fetch(`${API_BASE}/${id}/file?redirect=false`, {
    headers: authHeaders(token),
  });
  return parseResponse(res);
}
export async function toggleFavoritePdf(id: string, token: string) {
  const res = await fetch(`${API_BASE}/${id}/favorite`, {
    method: 'PATCH',
    headers: authHeaders(token),
  });
  return parseResponse<{id: string, is_favorite: boolean, message: string}>(res);
}
