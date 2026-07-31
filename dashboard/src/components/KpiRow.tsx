import { api, type KPISummary } from "../api";
import { usePolling } from "../usePolling";

export default function KpiRow() {
  const { data, error } = usePolling<KPISummary>(api.kpis);

  if (error) return <p className="error-note">KPI load failed: {error}</p>;
  if (!data) return <p className="loading-note">Loading…</p>;

  return (
    <div className="kpi-row">
      <div className="kpi-tile critical">
        <span className="label">Open injection alerts</span>
        <span className="value mono">{data.open_injection_alerts}</span>
      </div>
      <div className="kpi-tile accent">
        <span className="label">Endpoints monitored</span>
        <span className="value mono">{data.endpoints_monitored}</span>
      </div>
      <div className="kpi-tile warn">
        <span className="label">Shadow-AI candidates</span>
        <span className="value mono">{data.shadow_ai_candidates}</span>
      </div>
      <div className="kpi-tile critical">
        <span className="label">DLP flagged</span>
        <span className="value mono">{data.dlp_flagged}</span>
      </div>
      <div className="kpi-tile warn">
        <span className="label">DLP pending approval</span>
        <span className="value mono">{data.dlp_pending_approval}</span>
      </div>
    </div>
  );
}
