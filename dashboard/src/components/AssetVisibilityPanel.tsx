import { api, type AssetVisibility } from "../api";
import { usePolling } from "../usePolling";

export default function AssetVisibilityPanel() {
  const { data, error } = usePolling<AssetVisibility>(api.assetVisibility);

  if (error) return <p className="error-note">Asset visibility load failed: {error}</p>;
  if (!data) return <p className="loading-note">Loading…</p>;

  return (
    <div>
      <div style={{ marginBottom: 18 }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: "var(--ink-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>
          Known AI platforms
        </div>
        {data.known.length === 0 ? (
          <p className="empty-note">None observed yet.</p>
        ) : (
          data.known.map((row) => (
            <div className="known-row" key={row.platform_label}>
              <span className="name">{row.platform_label}</span>
              <span className="meta mono">{row.endpoint_count} endpoints · {row.event_count} connections</span>
            </div>
          ))
        )}
      </div>

      <div>
        <div style={{ fontSize: 12, fontWeight: 700, color: "var(--ink-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>
          Shadow-AI candidates
          {data.shadow_total > data.shadow.length && (
            <span style={{ fontWeight: 500, textTransform: "none", letterSpacing: "normal" }}> — showing top {data.shadow.length} of {data.shadow_total}</span>
          )}
        </div>
        {data.shadow.length === 0 ? (
          <p className="empty-note">No fingerprint has hit 2+ unlisted domains yet.</p>
        ) : (
          <div className="chip-list">
            {data.shadow.map((row) => (
              <span className="chip" key={row.domain}>
                {row.domain}
                <span className="count">×{row.event_count}</span>
              </span>
            ))}
          </div>
        )}
        <p style={{ fontSize: 11.5, color: "var(--ink-muted)", marginTop: 10, lineHeight: 1.5 }}>
          One TLS fingerprint reused across ≥2 unlisted domains — includes real shadow-AI targets
          alongside ordinary browser/OS background traffic sharing the same client. Triage signal,
          not an automated verdict (see README).
        </p>
      </div>
    </div>
  );
}
