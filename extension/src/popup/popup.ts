// Phase 1 popup — queries the Go daemon's read endpoints directly (:8090). Superseded by the
// real dashboard (Phase 4); this exists only to make Phase 1 end-to-end verifiable without
// waiting on the full dashboard build.
const DAEMON_BASE = "http://127.0.0.1:8090";

interface InjectionAlertRow {
  id: number;
  url: string;
  score: number;
  ts: string;
}

interface DLPEventRow {
  id: number;
  platform: string;
  verdict: string;
  approved: boolean | null;
  matched_entities: { type: string; count: number }[];
  ts: string;
}

async function loadInjectionAlerts() {
  const el = document.getElementById("injection-list")!;
  try {
    const res = await fetch(`${DAEMON_BASE}/api/injection_alerts?limit=10`);
    const rows: InjectionAlertRow[] = await res.json();
    if (!rows.length) {
      el.textContent = "No injection alerts yet.";
      el.className = "empty";
      return;
    }
    el.className = "";
    el.innerHTML = rows
      .map(
        (r) =>
          `<div class="row"><strong>score ${r.score.toFixed(2)}</strong> — ${escapeHtml(r.url)}<div class="meta">${r.ts}</div></div>`
      )
      .join("");
  } catch {
    el.textContent = "Daemon unreachable (is it running on :8090?)";
    el.className = "empty";
  }
}

async function loadDLPEvents() {
  const el = document.getElementById("dlp-list")!;
  try {
    const res = await fetch(`${DAEMON_BASE}/api/dlp_events?limit=10`);
    const rows: DLPEventRow[] = await res.json();
    if (!rows.length) {
      el.textContent = "No DLP events yet.";
      el.className = "empty";
      return;
    }
    el.className = "";
    el.innerHTML = rows
      .map((r) => {
        const entities = r.matched_entities.map((e) => `${e.type}×${e.count}`).join(", ");
        const decision = r.approved === null ? "pending" : r.approved ? "approved" : "blocked";
        const cls = r.verdict === "clean" ? "clean" : "";
        return `<div class="row ${cls}"><strong>${r.platform}</strong> — ${escapeHtml(entities || "clean")} <em>(${decision})</em><div class="meta">${r.ts}</div></div>`;
      })
      .join("");
  } catch {
    el.textContent = "Daemon unreachable (is it running on :8090?)";
    el.className = "empty";
  }
}

function escapeHtml(s: string): string {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

loadInjectionAlerts();
loadDLPEvents();
