import { api, type ActivityRow } from "../api";
import { usePolling } from "../usePolling";

function timeAgo(ts: string): string {
  const diffMs = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

const KIND_LABEL: Record<ActivityRow["kind"], string> = {
  injection: "Injection score",
  dlp: "DLP check",
  shadow_ai: "Shadow-AI sighting",
};

export default function EndpointActivity({ endpointId }: { endpointId: string }) {
  const { data, error } = usePolling<ActivityRow[]>(() => api.endpointActivity(endpointId), 8000);

  if (error) return <p className="error-note">Activity load failed: {error}</p>;
  if (!data) return <p className="loading-note">Loading activity…</p>;
  if (data.length === 0) return <p className="empty-note">No flagged activity recorded for this endpoint.</p>;

  return (
    <div>
      {data.map((row, i) => (
        <div className="activity-row" key={i}>
          <span className={`kind-dot ${row.kind}`} />
          <span style={{ flex: "none", width: 128, color: "var(--ink-muted)" }}>{KIND_LABEL[row.kind]}</span>
          <span className="detail mono">{row.detail}{row.extra ? ` · ${row.extra}` : ""}</span>
          <span className="ts mono">{timeAgo(row.ts)}</span>
        </div>
      ))}
    </div>
  );
}
