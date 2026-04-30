// Tiny fetch wrapper around the HydroSense Flask API.
// Base URL comes from Vite env. In dev defaults to localhost:5001 so
// `npm run dev` + `python api.py` Just Works.
//
// In production (Vercel), set VITE_API_BASE=https://hydrosense-api-jg8i.onrender.com
// in the project env before deploying.

export const API_BASE =
  import.meta.env.VITE_API_BASE || 'http://localhost:5001';

async function get(path) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status} on ${path}`);
  return res.json();
}

// Public endpoints — keep these dumb and 1:1 with backend routes.
export const fetchLatest = (nodeId = 'node_01') =>
  get(`/api/latest?node_id=${encodeURIComponent(nodeId)}`);

export const fetchRecent = (nodeId = 'node_01', hours = 24) =>
  get(`/api/recent?node_id=${encodeURIComponent(nodeId)}&hours=${hours}`);

export const fetchStats = () => get('/api/stats');

export const fetchNodes = () => get('/api/nodes');

export const fetchAlerts = () => get('/api/alerts');

export const fetchHealth = () => get('/api/health');

// Oblast endpoints — Level 2/3 satellite + LSTM data.
export const fetchOblasts          = ()         => get('/api/oblasts');
export const fetchOblast           = (name)     => get(`/api/oblasts/${encodeURIComponent(name)}`);
export const fetchOblastHistory    = (name, m=60) => get(`/api/oblasts/${encodeURIComponent(name)}/history?months=${m}`);
export const fetchOblastForecast   = (name)     => get(`/api/oblasts/${encodeURIComponent(name)}/forecast`);
