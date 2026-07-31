# Browser AI Sentinel

Client-side detection of indirect prompt injection and unauthorized data exfiltration in
browser-to-AI interactions, using multi-indicator content analysis. Second capstone project
(MTech Cyber Security, RACE/REVA), standalone from the first (`dns-https-c2-ueba-detection`) —
no shared code, own repo, own infrastructure.

Full design rationale, threat model, and phasing are in
[`/root/.claude/plans/nifty-crafting-acorn.md`](../../.claude/plans/nifty-crafting-acorn.md)
(the approved build plan this repo implements).

## What it does

1. **Prompt-injection detection** — a content script scans the live DOM of *any* page (not just
   AI platforms — injection payloads are planted on arbitrary pages an AI agent might later read)
   for content hidden from a human but present in the document: off-screen CSS, zero-width
   Unicode, suspicious HTML comments, alt/ARIA text, JSON-LD metadata. Multi-indicator scoring
   (noisy-OR combination) flags pages likely to contain instructions targeting an AI agent.
2. **Outbound DLP/exfiltration gate** — on known AI domains, a MAIN-world script intercepts
   `fetch`/`XHR` bodies before they're sent, classifies them for PII/secrets, and holds the
   request pending user approval (via a Chrome notification with Allow/Block buttons) if flagged.
3. **AI-platform / shadow-AI discovery** — a standalone Zeek + Suricata sensor pair (own configs,
   own systemd services, watching this machine's real NIC — see Phase 2 below) extracts real
   SNI/JA3/JA4 per TLS connection. Known AI domains get labeled directly; a TLS fingerprint reused
   across ≥2 distinct *unlisted* domains is flagged as a shadow-AI candidate — the idea being a
   shared client fingerprint hitting several LLM-shaped endpoints looks like programmatic API
   traffic, not organic browsing. The extension's own client-declared domain check (Phase 1) stays
   as an additional, faster signal — both write to the same table, tagged by source.

**Explicitly IDS, not IPS**: the extension can warn the human but cannot block an AI agent that
reads a page via its own privileged channel (e.g. CDP/accessibility tree) rather than the visible
DOM.

## Architecture (Phase 1 + 2)

```
Chrome extension (TypeScript, MV3)
  ├─ content-isolated/injection-scan.js   <all_urls> — DOM indicator scan
  ├─ content-isolated/relay.js            known AI domains — MAIN<->background bridge
  ├─ content-isolated/platform-adapters/  known AI domains — best-effort account-identity scrape
  ├─ content-main/fetch-patch.js          known AI domains, MAIN world — body interception
  ├─ background/service-worker.js         native messaging + approval-gate orchestration
  └─ popup/                               Phase 1 read-only view (superseded by dashboard later)
        │ chrome.runtime.connectNative
        ▼
agent/cmd/nmhost   (ephemeral, Chrome-spawned, stdio<->HTTP shim, no logic of its own)
        │ HTTP :8090
        ▼
agent/cmd/daemon  ◄──── agent/internal/sensor tailers (byte-offset persisted, resume-safe)
   │        ▲                    ▲
   │        │              ssl.log (JSON)         eve.json (JSON, tls events)
   │        │                    │                        │
   │        │             bas-zeek.service          bas-suricata.service
   │        │             (Zeek + ja3/ja4 zkg)       (Suricata, JA3/JA4 native)
   │        │                    └──────────── both watch ens18 (real NIC) ────────┘
   │        │
   │  HTTP :8100                         │ Postgres :5433
   ▼        │                            ▼
ai-engine (Python/FastAPI)          db/ (schema.sql, docker-compose.yml)
  injection_scoring, pii_detection, atlas_mapping     platform_events, shadow_ai_clusters, ...
```

Ports (chosen to avoid collision with the unrelated capstone-1 services already running on this
VM — see the plan for the full list checked via `ss -tlnp`): Postgres `5433`, Go daemon `8090`,
ai-engine `8100`, dashboard (Phase 4) `3000`. The two sensor services don't listen on any port —
they only write to their own log files under `sensor/logs/`.

## Phase 1 setup

```
make setup          # brings up Postgres, ai-engine venv, builds Go binaries, builds extension
make ai-engine-run   # terminal 1 — leave running
make daemon-run       # terminal 2 — leave running
make health          # confirms both are up
```

The native messaging host is already registered for this machine at both
`~/.config/google-chrome/NativeMessagingHosts/com.browseraisentinel.nmhost.json` (user-level) and
`/etc/opt/chrome/native-messaging-hosts/com.browseraisentinel.nmhost.json` (system-wide), pointing
at `agent/bin/nmhost` and scoped to this extension's real ID, `extension/extension_id.txt`
(`infjoghmhbkbhohajodjccgphpgejkip`).

**Two real findings from getting this working end-to-end, worth keeping for the report/viva —
both cost significant debugging time and are exactly the kind of thing a panel might probe:**

1. **`--load-extension` (command-line flag) is not a reliable way to install an unpacked
   extension on this machine's Chrome build (150.0.7871.46).** It spins up *a* service worker,
   but content scripts never actually inject (confirmed via CDP: zero isolated-world execution
   contexts ever appeared) and the extension never shows in `chrome://extensions`'s UI. The
   correct, verified-working install path is the **`Extensions.loadUnpacked` CDP command** (what
   `chrome://extensions`'s "Load unpacked" button itself calls internally) — this is what
   `scripts/register-native-host.sh` and `test-pages/cdp_test.py` both use, and it correctly
   honors `manifest.json`'s pinned `"key"` field, producing the stable ID
   `infjoghmhbkbhohajodjccgphpgejkip` deterministically. (A red herring along the way: a
   Chrome-bundled default component extension happens to expose a target literally named
   `service_worker.js` under ID `fignfifoniblkonapihmkfakmlgkbkcf` in *every* fresh profile —
   easy to mistake for "our extension got a different ID" if you don't check the script path in
   the service-worker URL.)
2. **A Chrome profile launched with a custom `--user-data-dir` does not discover
   user-level (`~/.config/google-chrome/NativeMessagingHosts`) native messaging host
   registrations** — only the system-wide path
   (`/etc/opt/chrome/native-messaging-hosts/`) was reliably found in testing, regardless of which
   profile launched Chrome. Real day-to-day use of the default profile may not hit this, but
   registering both (which the script now does) removes an entire class of "works on my machine"
   failure and is what made `test-pages/cdp_test.py` go from failing with `Specified native
   messaging host not found` to passing.

### Load the extension in real Chrome

1. `chrome://extensions` → enable **Developer mode** → **Load unpacked** → select
   `extension/dist/`. (This is the same install path verified above — do NOT load it via any
   command-line `--load-extension` flag if you're scripting this; it won't actually work.)
2. Confirm the loaded extension's ID matches `extension/extension_id.txt`
   (`infjoghmhbkbhohajodjccgphpgejkip`) — if it doesn't (e.g. the repo was moved to a different
   absolute path, though path shouldn't matter since the ID is key-derived, not path-derived, via
   this install method), run `scripts/register-native-host.sh` again and restart Chrome. A
   mismatch means native messaging will silently fail to connect.
3. Restart Chrome once after loading, so it re-reads `NativeMessagingHosts/`.

### Automated verification

`test-pages/cdp_test.py` (needs the `websocket-client` and `requests` Python packages) already
does this for the injection-detection path, end to end, in a real (headless) Chrome instance: it
installs `extension/dist/` via `Extensions.loadUnpacked`, navigates to
`test-pages/injection-test.html` (served via `python3 -m http.server 8877` from that directory —
start that first), and asserts the warning banner renders. **Passing as of this writing**, with a
real seeded page (six planted indicators — off-screen CSS, zero-width Unicode, a suspicious HTML
comment, hidden alt/ARIA text, JSON-LD metadata, and visible imperative language) scoring 1.00 and
landing correctly in `injection_alerts`. Run it with `python3 test-pages/cdp_test.py` once
`ai-engine` and `daemon` are up.

### Manual verification (Phase 1 "done" criteria from the plan)

**Injection detection**: covered by the automated test above; to try your own page, open a local
test HTML file containing a hidden element (e.g. `display:none` or off-screen positioned) whose
text matches one of the patterns in `extension/src/shared/patterns.ts` (e.g. "ignore all previous
instructions"), repeated with enough surrounding indicators to cross the flag threshold (a single
weak indicator alone won't flag — see the scorer's noisy-OR design). Expect: a red warning banner
injected at the top of the page, and a new row in `injection_alerts` — check via
`curl http://127.0.0.1:8090/api/injection_alerts` or the extension popup.

**DLP/exfiltration gate**: on one of the known AI domains (`claude.ai`, `chatgpt.com`, etc.),
open devtools and run
`fetch('/test-endpoint', {method:'POST', body:'contact me at test@example.com, card 4111 1111 1111 1111'})`.
Expect: a Chrome notification asking Allow/Block; on Block, the fetch call rejects with an
`AbortError`; either way, a new row appears in `dlp_events` with `matched_entities` populated.
Un-acknowledged prompts auto-deny after 30s (fail-closed).

## Phase 2 setup — real network sensor

```
sudo bash deploy/install-sensors.sh   # or: make sensor-up (also needs sudo)
make health                            # now also reports bas-zeek / bas-suricata status
```

This installs and starts `bas-zeek.service`, `bas-zeek-lo.service`, and `bas-suricata.service` —
new, separate systemd units from capstone-1's own (disabled/failed) `suricata.service`, own
configs (`sensor/zeek/bas.zeek`, `sensor/suricata/suricata.yaml`), own log directories
(`sensor/logs/{zeek,zeek-lo,suricata}/`), watching this machine's real primary interface (`ens18`,
confirmed via `ip route get 8.8.8.8`) **and loopback**. The Go daemon tails all three logs
continuously (rebuild it after adding the sensors: `make agent-build`, then restart `daemon-run`).

**Why loopback too, added during Phase 3**: Phase 3's mock "unknown AI" endpoints
(`sensor/mock-ai/`) run on this same host. Same-host traffic to a local address never transits the
physical NIC — confirmed empirically, ens18-only capture saw nothing for it, `-i lo` did. Zeek
only accepts one `-i` per process (hence the separate `bas-zeek-lo` service reusing the same
script), while Suricata's `af-packet` config natively supports multiple interfaces in one process
(just don't pass `-i` on its command line — that silently overrides the config's interface list
down to one, which is exactly what broke this the first time).

**A real bug worth keeping for the report**: `shadow_ai_clusters.confidence`'s column default was
initially (mistakenly) `'candidate'` instead of `'observed'` — every single-domain fingerprint
sighting showed up as a "candidate" immediately, defeating the whole point of the ≥2-distinct-
domains rule. Caught by testing against real ambient traffic (this machine's own background
services — `mail.google.com`, `telemetry.elastic.co` — showed as false candidates on one sighting
each) rather than only testing the happy path. Fixed in `db/schema.sql` and via a one-time
`UPDATE` on the already-running database.

**Verified against real traffic**: a curl client hitting two distinct non-known-AI domains
(`api.github.com`, then `httpbin.org`) correctly triggered `confidence: "candidate"` on the
second sighting — same JA3/JA4 both times since it's the same client — while single sightings of
other domains correctly stayed `"observed"`. A daemon restart mid-stream resumed from the
persisted byte offset with no reprocessing and no gap.

## Phase 3 setup — labeled dataset, mock AI, test fleet, A/B/C evaluation

```
make dataset-gen                       # 70 labeled synthetic pages -> eval/dataset/
make dataset-serve                     # separate terminal, leave running — serves them on :8877
make mock-ai-up                        # two local TLS "unknown AI" endpoints for shadow-AI testing
make endpoints-build                   # builds the one shared endpoint image (Chrome + Go agent + extension)
make endpoints-up                      # brings up 4 containers, each its own OS user/hostname
make endpoints-test                    # runs driver.py inside each, one at a time
make eval-run                          # A/B/C precision/recall/F1 against the labeled dataset
```

**Scope note, decided explicitly rather than following the original sketch literally**: the fleet
does not log into real claude.ai/chatgpt.com accounts — creating multiple accounts on production
third-party services purely to generate test traffic risks their ToS and is often unautomatable
(email/phone verification). Instead: real AI domains' public pages (real SNI/JA3/JA4, no login),
a local self-signed mock endpoint for shadow-AI clustering, a fully synthetic labeled dataset for
injection detection, and the same safe DLP-test pattern already manually verified in Phase 1.

**Four endpoints, varied behavior** (a better dashboard story than four identical runs, and each
represents a distinct OS user + hostname in `endpoints`): `priya.sharma` and `arjun.mehta` are
baseline/normal (dataset pages + known AI domains only); `karan.iyer` additionally visits both
mock AI endpoints, which is what actually triggers shadow-AI clustering — the rule fires on **one
fingerprint hitting ≥2 distinct unlisted domains**, so a single endpoint visiting both mock
domains is sufficient on its own, no cross-endpoint coordination needed (an earlier draft of this
plan implied otherwise — corrected once actually implemented); `divya.rao` additionally runs the
DLP approval-gate test. All four visit the full 70-page dataset, so the A/B/C evaluation has up to
4x coverage per page — which doubles as a determinism check (`eval/evaluate.py` flags it if the
same static page ever gets a different verdict across visits, since detection should be
deterministic).

**Container networking**: `network_mode: host`, not a custom bridge — lets each container reach
the host's already-loopback-bound Postgres (`:5433`) and ai-engine (`:8100`) directly without
binding either to `0.0.0.0`, which would be a real exposure regression for this project's own
database. Trade-off: each container's own Go daemon listens on a distinct port (`8091`-`8094`)
since they share the host's network namespace; each still gets its own hostname (UTS namespace is
independent of network namespace) and OS user for endpoint identity.

**Chrome install note**: `chromium-browser` in Ubuntu 24.04's apt is a snap wrapper and doesn't
function inside a container — confirmed via `apt-cache policy` before writing the Dockerfile.
`endpoints/Dockerfile` installs `google-chrome-stable` from Google's own apt repo instead, and
`endpoints/driver.py` installs the extension the same proven way as `test-pages/cdp_test.py`
(`Extensions.loadUnpacked`, never `--load-extension`).

### A/B/C results — real, from the fleet run

| Detector | Precision | Recall | F1 | TP | FP | TN | FN |
|---|---|---|---|---|---|---|---|
| A — keyword-only | 0.754 | 0.817 | 0.784 | 98 | 32 | 128 | 22 |
| B — visibility-only | 0.854 | 0.975 | 0.911 | 117 | 20 | 140 | 3 |
| **C — multi-indicator** | **0.983** | **0.975** | **0.979** | 117 | **2** | 158 | 3 |

280 matched alert rows (70-page dataset × 4 endpoints, minus a few known-AI/mock-domain visits
that don't match the dataset manifest). C wins on every metric — same C > B > A shape as
capstone 1's A/B/C result. The number that actually validates the whole module's design
argument: **on the 40 hard-negative row-visits (10 pages × 4 endpoints, each carrying exactly one
weak indicator), A false-positived 32 times, B false-positived 20 times, C only 2.** Full numbers
in `eval/results/phase3-injection-eval.json`. Reproduce with `make dataset-gen`,
`make dataset-serve`, `make mock-ai-up`, `make endpoints-build`, `make endpoints-up`,
`make endpoints-test`, `make eval-run`.

**Three real bugs found and fixed while getting this run to actually work — worth keeping for
the report, they're better evidence of rigor than a clean first try would have been:**

1. **The first full fleet run silently produced zero rows.** Every page reported as "visited" by
   the driver, but nothing reached the daemon. Root cause: the container's native-messaging
   registration had the exact same user-level-only gap already found and fixed on the host in
   Phase 1 (a Chrome profile with a custom `--user-data-dir` doesn't discover
   `~/.config/google-chrome/NativeMessagingHosts`, only the system-wide path) — but the fix was
   never carried over into `endpoints/entrypoint.sh`. Compounding it: each container's daemon
   listens on its own port (8091-8094), but `nmhost` defaults to 8090 and nothing told it
   otherwise per-container. Fixed by registering system-wide in `entrypoint.sh` and having
   `driver.py` pass `DAEMON_NM_URL` into Chrome's environment before launch.
2. **Shadow-AI clustering silently never accumulated multi-domain evidence for real browser
   traffic.** The original schema keyed `shadow_ai_clusters` on `(ja3, ja4)` together. Chrome's
   GREASE mechanism randomizes reserved cipher/extension values in every ClientHello, which JA3's
   naive hashing treats as signal — confirmed empirically, 10 of 12 real Chrome connections to the
   same two mock endpoints each got a distinct JA3. JA4 is specifically designed to strip GREASE
   before hashing and stayed identical across all of them. This only looked like it worked in
   earlier manual testing because that testing used `curl`, which doesn't implement GREASE.
   Re-keyed to JA4 alone (`sample_ja3` kept as an informational, non-matched column).
3. **The extension's own DOM scanner skipped benign pages entirely.** `injection-scan.ts` only
   messaged the daemon when at least one indicator was found locally — meaning the 30 pure-benign
   dataset pages never got scored or logged at all, leaving no true-negative data for the eval
   despite the daemon-side "log every score" change. Fixed by removing the early return so every
   scan reports, clean or not.

**A finding from actually running the shadow-AI clustering against real traffic, not a bug but
worth being honest about**: once fixed, the JA4-keyed cluster containing the two mock domains
also pulled in 16 other domains — routine Chrome background traffic (Google service checks,
safebrowsing, update pings, Cloudflare challenges) that all share the same JA4 because it's
literally "generic headless Chrome," not because any of it is AI-related. This is exactly the
false-positive mode already flagged below as a known limitation, now demonstrated with real data
instead of just argued for.

## Phase 4 — EDR-style dashboard

```
make dashboard-setup   # once
make dashboard-dev     # separate terminal — http://127.0.0.1:3000
```

React + TypeScript + Vite, **not** Grafana/Kibana (deliberate — see the plan). The dev server
proxies `/api/*` to the daemon (`vite.config.ts`), so the daemon needed no CORS changes and stays
exactly as loopback-scoped as every other Phase 1-3 service.

Five new daemon endpoints back it (`agent/cmd/daemon/dashboard.go`,
`agent/internal/store/dashboard.go`) — server-side aggregates, not raw-row dumps to the frontend:
KPI summary, per-endpoint rollup, known-vs-shadow-AI asset visibility, real ATLAS technique
coverage, and per-endpoint activity (backs the click-to-expand row, standing in for a separate
always-on timeline view).

**One deliberate scope correction**: "MITRE ATLAS technique heatmap" was originally imagined as a
full ATT&CK-style grid. Real data only populates the two techniques this project has actually
mapped — rendering a big mostly-empty 16-tactic grid would overstate coverage. Built a compact
techniques-observed panel instead: real techniques, real hit counts, nothing invented.

**A real architectural limitation, surfaced rather than hidden**: network-sensor-derived events
(shadow-AI sightings, passive platform detection) are attributed to whichever endpoint's daemon
is tailing the Zeek/Suricata logs — currently only the host, since the Phase 3 fleet containers
don't run their own sensor. Confirmed directly in the data: every `is_shadow_ai=true`
`platform_events` row is attributed to the host endpoint, even the ones `karan.iyer`'s container
actually generated by visiting the mock AI domains. Packet capture alone can't attribute a TLS
connection to a specific container without deeper host-side correlation (out of scope). The
dashboard's endpoint table still shows this honestly rather than pretending per-container
attribution it doesn't have — see `agent/internal/store/dashboard.go`'s comment on
`EndpointRollup`.

**A SQL gotcha worth keeping**: Postgres won't resolve two `SELECT`-list aliases combined inside
an `ORDER BY` expression directly (`ORDER BY (a + b)` where `a`/`b` are themselves aliased
subqueries) — confirmed empirically (`column "..." does not exist`). Fixed by wrapping the query
in a subquery and ordering the outer one.

## Known limitations, stated plainly (don't let a viva panel find these first)

- Account-identity scraping (`content-isolated/platform-adapters/index.ts`) uses one generic
  heuristic, **not verified selectors against live authenticated sessions** on each platform —
  this environment has no way to check real logged-in DOM structure. Expect it to miss accounts
  on UI redesigns.
- The DLP module's MITRE ATLAS technique ID is unresolved (`DLP-MODULE-TODO` in the schema) —
  manually confirm on atlas.mitre.org before citing an ID in the report; OWASP LLM Top 10
  LLM02:2025 is the safe interim citation.
- `injection_scoring`'s indicator weights were a judgment-call starting point; Phase 3's fleet run
  gave them a real (if modest, 70-page) evaluation — see the A/B/C table above — rather than
  leaving them purely theoretical. Still worth a larger corpus before calling them calibrated.
- The shadow-AI clustering rule (a JA4 fingerprint reused across ≥2 distinct non-known domains →
  "candidate") is real and empirically confirmed to fire correctly, but its **precision in
  practice is poor** — see the "finding from actually running" note above: one generic browser
  fingerprint pulls in all of Chrome's own background traffic alongside genuine shadow-AI hits.
  Usable as a triage signal (rank candidates for a human to check), not as an automated verdict,
  without further refinement (e.g. excluding a browser's own well-known telemetry/update domains).
- **A ~5% cross-visit determinism gap found during Phase 3 eval**: `eval/evaluate.py` flags when
  the same static page gets a different flagged/a_flagged/b_flagged verdict across separate
  visits — 14 such cases out of 280 matched rows, mostly on the keyword-only (A) baseline for
  injected pages. Most likely cause: `injection-scan.ts` runs at `document_idle`, which can fire
  before CSS/layout is fully resolved, occasionally letting hidden text leak into the
  `innerText`-based visible-text scan on a race. Documented rather than chased further this
  round — full detail in `eval/results/phase3-injection-eval.json`'s `determinism_issues`.
- **Network-sensor event attribution is host-level, not per-container** (found while building
  the Phase 4 dashboard): shadow-AI/passive-platform events are attributed to whichever endpoint
  runs Zeek/Suricata — only the host, since the Phase 3 fleet containers don't run their own
  sensor. The dashboard's endpoint table reflects this honestly rather than implying
  per-container attribution the system doesn't actually have.
