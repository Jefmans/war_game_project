const API_BASE =
  import.meta.env.VITE_API_BASE || "http://localhost:8000";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const data = await response.json();
      if (data && data.detail) {
        detail = data.detail;
      }
    } catch (error) {
      // keep default detail
    }
    const err = new Error(detail);
    err.status = response.status;
    throw err;
  }
  return response.json();
}

export function getMatchState(matchId) {
  return request(`/api/matches/${matchId}/state/`);
}

export function getChunk(matchId, chunkQ, chunkR, turnNumber) {
  const params =
    Number.isFinite(turnNumber) && turnNumber > 0
      ? `?turn=${turnNumber}`
      : "";
  return request(`/api/matches/${matchId}/chunks/${chunkQ}/${chunkR}/${params}`);
}

export function getTurnState(matchId, turnNumber) {
  return request(`/api/matches/${matchId}/turns/${turnNumber}/state/`);
}

export function queueOrders(matchId, payload) {
  return request(`/api/matches/${matchId}/queue-orders/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
