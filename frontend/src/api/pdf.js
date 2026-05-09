const API_BASE = '/api/pdf';

function getAuthHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function parseResponse(response) {
  const contentType = response.headers.get('content-type') || '';
  const data = contentType.includes('application/json')
    ? await response.json()
    : null;

  if (response.ok) {
    return data;
  }

  const message = data?.detail || data?.message || response.statusText;
  throw new Error(message || 'Lỗi khi gọi API');
}

export async function fetchPdfs(token) {
  const response = await fetch(`${API_BASE}/`, {
    headers: getAuthHeaders(token),
  });
  return parseResponse(response);
}

export async function uploadPdfFile(file, token) {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE}/upload`, {
    method: 'POST',
    body: formData,
    headers: getAuthHeaders(token),
  });

  return parseResponse(response);
}

export async function deletePdfById(id, token) {
  const response = await fetch(`${API_BASE}/${id}`, {
    method: 'DELETE',
    headers: getAuthHeaders(token),
  });
  return parseResponse(response);
}

export async function getPdfFileUrl(id, token) {
  const response = await fetch(`${API_BASE}/${id}/file?redirect=false`, {
    headers: getAuthHeaders(token),
  });
  return parseResponse(response);
}
