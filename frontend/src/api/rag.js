const API_BASE = '/api/rag';

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
  throw new Error(message || 'Lỗi khi gọi API RAG');
}

export async function ragQuery(queryText, token, pdfId = null, topK = 5) {
  console.log(`[rag] query: "${queryText.substring(0, 50)}..." pdfId=${pdfId} topK=${topK}`);
  const response = await fetch(`${API_BASE}/query`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(token),
    },
    body: JSON.stringify({
      query_text: queryText,
      top_k: topK,
      pdf_id: pdfId,
    }),
  });
  const result = await parseResponse(response);
  console.log(`[rag] query done: ${result.results?.length || 0} results in ${result.query_time_ms}ms`);
  return result;
}

export async function ragChat(queryText, pdfIds, token, sessionId = null, topK = 5) {
  console.log(`[rag] chat: "${queryText.substring(0, 50)}..." sessionId=${sessionId} pdfIds=${pdfIds}`);
  const response = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(token),
    },
    body: JSON.stringify({
      query_text: queryText,
      pdf_ids: pdfIds,
      session_id: sessionId,
      top_k: topK,
    }),
  });
  const result = await parseResponse(response);
  console.log(`[rag] chat done: sessionId=${result.session_id} tokens=${result.prompt_tokens}+${result.completion_tokens}`);
  return result;
}

export async function fetchSessions(token, skip = 0, limit = 20) {
  console.log(`[rag] fetchSessions: skip=${skip} limit=${limit}`);
  const response = await fetch(`${API_BASE}/sessions?skip=${skip}&limit=${limit}`, {
    headers: getAuthHeaders(token),
  });
  const result = await parseResponse(response);
  console.log(`[rag] fetchSessions done: ${result.sessions?.length || 0} sessions (total=${result.total})`);
  return result;
}

export async function fetchSession(sessionId, token) {
  console.log(`[rag] fetchSession: id=${sessionId}`);
  const response = await fetch(`${API_BASE}/sessions/${sessionId}`, {
    headers: getAuthHeaders(token),
  });
  const result = await parseResponse(response);
  console.log(`[rag] fetchSession done: ${result.messages?.length || 0} messages`);
  return result;
}

export async function deleteSession(sessionId, token) {
  console.log(`[rag] deleteSession: id=${sessionId}`);
  const response = await fetch(`${API_BASE}/sessions/${sessionId}`, {
    method: 'DELETE',
    headers: getAuthHeaders(token),
  });
  const result = await parseResponse(response);
  console.log(`[rag] deleteSession done`);
  return result;
}
