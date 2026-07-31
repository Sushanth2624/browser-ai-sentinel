import { Fragment, useState } from "react";
import { api, type EndpointRow } from "../api";
import { usePolling } from "../usePolling";
import EndpointActivity from "./EndpointActivity";

const AVATAR_COLORS = ["#2a78d6", "#4a3aa7", "#eda100", "#e34948", "#1baf7a", "#e87ba4"];

function initials(name: string): string {
  const parts = name.split(/[.\s]/).filter(Boolean);
  return (parts[0]?.[0] ?? "?").toUpperCase() + (parts[1]?.[0] ?? "").toUpperCase();
}

function colorFor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) >>> 0;
  return AVATAR_COLORS[hash % AVATAR_COLORS.length];
}

export default function EndpointTable() {
  const { data, error } = usePolling<EndpointRow[]>(api.endpoints);
  const [expanded, setExpanded] = useState<string | null>(null);

  if (error) return <p className="error-note">Endpoint load failed: {error}</p>;
  if (!data) return <p className="loading-note">Loading…</p>;

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Endpoint</th>
            <th>Injection alerts</th>
            <th>DLP flagged</th>
            <th>Platforms seen</th>
            <th>AI accounts seen</th>
            <th>Last seen</th>
          </tr>
        </thead>
        <tbody>
          {data.map((ep) => (
            <Fragment key={ep.id}>
              <tr className="clickable" onClick={() => setExpanded(expanded === ep.id ? null : ep.id)}>
                <td className="who">
                  <span className="avatar" style={{ background: colorFor(ep.os_user) }}>{initials(ep.os_user)}</span>
                  <span className="who-text">
                    <span className="user">{ep.os_user}</span>
                    <span className="host mono">{ep.hostname}</span>
                  </span>
                </td>
                <td className="mono">
                  {ep.injection_alert_count > 0 ? <span className="pill flagged">{ep.injection_alert_count}</span> : <span className="pill clean">0</span>}
                </td>
                <td className="mono">
                  {ep.dlp_flagged_count > 0 ? <span className="pill flagged">{ep.dlp_flagged_count}</span> : <span className="pill clean">0</span>}
                </td>
                <td className="mono">{ep.platforms_seen}</td>
                <td className="mono">{ep.ai_accounts_seen}</td>
                <td className="mono" style={{ fontSize: 11.5 }}>{new Date(ep.last_seen).toLocaleString()}</td>
              </tr>
              {expanded === ep.id && (
                <tr key={`${ep.id}-activity`}>
                  <td colSpan={6} style={{ background: "var(--surface-sunken)", textAlign: "left" }}>
                    <EndpointActivity endpointId={ep.id} />
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}
