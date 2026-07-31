import { useEffect, useState } from "react";
import KpiRow from "./components/KpiRow";
import AssetVisibilityPanel from "./components/AssetVisibilityPanel";
import EndpointTable from "./components/EndpointTable";
import AtlasCoverage from "./components/AtlasCoverage";

export default function App() {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="app-shell">
      <header className="masthead">
        <div>
          <h1>Browser AI Sentinel</h1>
          <div className="sub">Client-side detection of indirect prompt injection and unauthorized data exfiltration in browser-to-AI interactions</div>
        </div>
        <div className="live-badge">
          <span className="dot" />
          Live · {now.toLocaleTimeString()}
        </div>
      </header>

      <section>
        <KpiRow />
      </section>

      <section className="grid-2">
        <div className="panel">
          <div className="panel-head">
            <span className="eyebrow">Modules 1 &amp; 3</span>
            <h2>AI asset visibility</h2>
            <p>Known platforms vs shadow-AI candidates, from real network-sensor telemetry.</p>
          </div>
          <AssetVisibilityPanel />
        </div>

        <div className="panel">
          <div className="panel-head">
            <span className="eyebrow">Coverage</span>
            <h2>MITRE ATLAS techniques observed</h2>
            <p>Real events only — not the full ATLAS matrix.</p>
          </div>
          <AtlasCoverage />
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <span className="eyebrow">All modules</span>
          <h2>Endpoints</h2>
          <p>Click a row to expand its recent flagged activity.</p>
        </div>
        <EndpointTable />
      </section>
    </div>
  );
}
