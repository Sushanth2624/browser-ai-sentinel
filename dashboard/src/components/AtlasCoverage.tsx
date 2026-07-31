import { api, type AtlasRow } from "../api";
import { usePolling } from "../usePolling";

export default function AtlasCoverage() {
  const { data, error } = usePolling<AtlasRow[]>(api.atlas);

  if (error) return <p className="error-note">ATLAS load failed: {error}</p>;
  if (!data) return <p className="loading-note">Loading…</p>;

  return (
    <div className="atlas-list">
      {data.map((t) => (
        <div className="atlas-card" key={t.id}>
          <div>
            <div className="id">{t.id}{!t.verified && <span style={{ color: "var(--warning)", fontWeight: 700 }}> · unverified</span>}</div>
            <div className="name">{t.name}</div>
            <div className="tactic">{t.tactic}</div>
          </div>
          <div className="hits mono">
            {t.hit_count}
            <span className="unit">hits</span>
          </div>
        </div>
      ))}
      <p style={{ fontSize: 11.5, color: "var(--ink-muted)", lineHeight: 1.5 }}>
        Only techniques this project has actually mapped — not the full ATLAS matrix. See
        README for why the DLP module's technique ID is still unresolved.
      </p>
    </div>
  );
}
