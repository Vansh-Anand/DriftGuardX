const API_ORIGIN = (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000').replace(/\/$/, '');
const API_BASE = `${API_ORIGIN}/v1`;

export function apiFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (typeof window !== 'undefined') {
    const token = window.localStorage.getItem('dgx_access_token');
    if (token) headers.set('Authorization', `Bearer ${token}`);
  }
  return fetch(input, { ...init, headers });
}

export interface GraphSnapshot {
  nodes: Array<{ id: string; label: string; type: string }>;
  edges: Array<{ id: string; source: string; target: string; label?: string; type: string }>;
}

export async function fetchGraphSnapshot(runId: string): Promise<GraphSnapshot> {
  const res = await apiFetch(`${API_BASE}/graph/snapshot/${encodeURIComponent(runId)}`, {
    cache: 'no-store',
  });
  if (!res.ok) throw new Error(`Graph request failed with status ${res.status}`);
  return await res.json();
}

export interface Run {
  id: string;
  status: string;
  created_at: string;
  total_latency_ms: number;
  total_cost_usd: number;
  reliability_score: number;
  is_synthetic: boolean;
  total_tokens?: number;
  error_type?: string;
  error_message?: string;
}

export interface TraceSpan {
  span_id: string;
  name: string;
  parent_span_id?: string;
  component_type?: string;
  kind?: string;
  latency_ms?: number;
  status_code: string;
  error_type?: string;
}

export interface TraceResponse {
  total_span_count: number;
  spans: TraceSpan[];
}

export async function fetchRuns(page: number = 1, pageSize: number = 10): Promise<{ runs: Run[], total: number }> {
  try {
    const skip = (page - 1) * pageSize;
    const res = await apiFetch(`${API_BASE}/runs?skip=${skip}&limit=${pageSize}`, { cache: 'no-store' });
    if (!res.ok) throw new Error('Failed to fetch runs');
    return await res.json();
  } catch (err) {
    console.error(err);
    return { runs: [], total: 0 };
  }
}

export async function createRun(
  query: string = "What are the latest safety guidelines?",
  execution_mode: "real" | "controlled" | "synthetic" = "real"
): Promise<Run> {
  const res = await apiFetch(`${API_BASE}/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query,
      seed: 42,
      execution_mode,
      is_synthetic: execution_mode === "synthetic",
      use_experimental_retriever: execution_mode === "controlled",
    }),
  });
  if (!res.ok) throw new Error('Failed to create run');
  return await res.json();
}

export async function fetchRun(id: string): Promise<Run | null> {
  try {
    const res = await apiFetch(`${API_BASE}/runs/${id}`, { cache: 'no-store' });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error(err);
    return null;
  }
}

export async function fetchRunTrace(id: string): Promise<TraceResponse | null> {
  try {
    const res = await apiFetch(`${API_BASE}/runs/${id}/trace`, { cache: 'no-store' });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error(err);
    return null;
  }
}

export async function createReplay(runId: string, seed: number): Promise<any> {
  const res = await apiFetch(`${API_BASE}/runs/${runId}/replays`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ seed })
  });
  if (!res.ok) throw new Error('Failed to create replay');
  return await res.json();
}

export async function fetchTelemetry(): Promise<any> {
  const res = await apiFetch(`${API_BASE}/telemetry/quality`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`Telemetry request failed with status ${res.status}`);
  return await res.json();
}

export async function fetchProviders(): Promise<any> {
  const res = await apiFetch(`${API_BASE}/providers`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`Provider request failed with status ${res.status}`);
  return await res.json();
}
