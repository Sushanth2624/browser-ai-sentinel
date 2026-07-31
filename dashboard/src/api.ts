// Typed fetch wrappers for the Phase 4 dashboard endpoints (agent/cmd/daemon/dashboard.go).
// All requests go through Vite's dev-server proxy (vite.config.ts) to the Go daemon on :8090 —
// no CORS handling needed, no absolute URLs here.

export interface KPISummary {
  open_injection_alerts: number;
  endpoints_monitored: number;
  shadow_ai_candidates: number;
  dlp_flagged: number;
  dlp_pending_approval: number;
}

export interface EndpointRow {
  id: string;
  hostname: string;
  os_user: string;
  last_seen: string;
  injection_alert_count: number;
  dlp_flagged_count: number;
  platforms_seen: number;
  ai_accounts_seen: number;
  shadow_ai_involved: boolean;
}

export interface AssetRow {
  platform_label?: string;
  domain?: string;
  endpoint_count: number;
  event_count: number;
}

export interface AssetVisibility {
  known: AssetRow[];
  shadow: AssetRow[];
  shadow_total: number;
}

export interface AtlasRow {
  id: string;
  name: string;
  tactic: string;
  verified: boolean;
  hit_count: number;
}

export interface ActivityRow {
  kind: "injection" | "dlp" | "shadow_ai";
  detail: string;
  extra: string;
  ts: string;
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  kpis: () => getJSON<KPISummary>("/api/dashboard/kpis"),
  endpoints: () => getJSON<EndpointRow[]>("/api/dashboard/endpoints"),
  assetVisibility: () => getJSON<AssetVisibility>("/api/dashboard/asset-visibility"),
  atlas: () => getJSON<AtlasRow[]>("/api/dashboard/atlas"),
  endpointActivity: (endpointId: string) =>
    getJSON<ActivityRow[]>(`/api/dashboard/endpoint-activity?endpoint_id=${encodeURIComponent(endpointId)}&limit=30`),
};
