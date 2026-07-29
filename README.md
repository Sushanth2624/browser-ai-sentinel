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
3. **AI-platform / shadow-AI discovery** — Phase 1 uses a static known-domain list as a stub;
   Phase 2 wires in Zeek/Suricata JA3/JA4 fingerprinting for real network-layer identification,
   including unlisted "shadow AI" services.

**Explicitly IDS, not IPS**: the extension can warn the human but cannot block an AI agent that
reads a page via its own privileged channel (e.g. CDP/accessibility tree) rather than the visible
DOM.

## Architecture (Phase 1)

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
agent/cmd/daemon   (persistent — systemd in later phases; run manually for Phase 1)
        │ HTTP :8100                         │ Postgres :5433
        ▼                                     ▼
ai-engine (Python/FastAPI)          db/ (schema.sql, docker-compose.yml)
  injection_scoring, pii_detection, atlas_mapping
```

Ports (chosen to avoid collision with the unrelated capstone-1 services already running on this
VM — see the plan for the full list checked via `ss -tlnp`): Postgres `5433`, Go daemon `8090`,
ai-engine `8100`, dashboard (Phase 4) `3000`.

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

## What's not built yet (see plan's phasing)

- **Phase 2**: real Zeek/Suricata JA3/JA4 network sensor (currently a domain-list stub —
  `is_shadow_ai` is hardcoded `false`, `source` is tagged `"domain-stub"` in every
  `platform_events` row so this limitation is visible in the data itself).
- **Phase 3**: the 4-5 Docker test endpoints + Playwright scripts + labeled A/B/C eval dataset.
- **Phase 4**: the full EDR-style dashboard (`dashboard/` is currently empty — Phase 1's popup is
  a stand-in).

## Known limitations, stated plainly (don't let a viva panel find these first)

- Account-identity scraping (`content-isolated/platform-adapters/index.ts`) uses one generic
  heuristic, **not verified selectors against live authenticated sessions** on each platform —
  this environment has no way to check real logged-in DOM structure. Expect it to miss accounts
  on UI redesigns.
- The DLP module's MITRE ATLAS technique ID is unresolved (`DLP-MODULE-TODO` in the schema) —
  manually confirm on atlas.mitre.org before citing an ID in the report; OWASP LLM Top 10
  LLM02:2025 is the safe interim citation.
- `injection_scoring`'s indicator weights are a judgment-call starting point, not yet calibrated
  against a labeled corpus — that calibration is Phase 3's job.
