-- Browser AI Sentinel — core schema
-- Standalone Postgres instance for this project (port 5433), independent of capstone 1's DB.

CREATE TABLE IF NOT EXISTS endpoints (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hostname    TEXT NOT NULL,
    os_user     TEXT NOT NULL,
    first_seen  TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (hostname, os_user)
);

CREATE TABLE IF NOT EXISTS atlas_techniques (
    id      TEXT PRIMARY KEY,        -- e.g. 'AML.T0051.001'
    name    TEXT NOT NULL,
    tactic  TEXT NOT NULL,
    verified BOOLEAN NOT NULL DEFAULT false  -- false = not yet confirmed against atlas.mitre.org
);

INSERT INTO atlas_techniques (id, name, tactic, verified) VALUES
    ('AML.T0051.001', 'LLM Prompt Injection: Indirect', 'Initial Access', true),
    ('DLP-MODULE-TODO', 'Outbound sensitive-data disclosure to AI service (ATLAS ID unresolved as of 2026-07 — verify manually on atlas.mitre.org; interim reference OWASP LLM Top 10 LLM02:2025 Sensitive Information Disclosure)', 'Exfiltration', false)
ON CONFLICT (id) DO NOTHING;

-- Module 1: AI-platform / shadow-AI discovery (network sensor, wired in Phase 2)
CREATE TABLE IF NOT EXISTS platform_events (
    id              BIGSERIAL PRIMARY KEY,
    endpoint_id     UUID NOT NULL REFERENCES endpoints(id),
    sni             TEXT,
    ja3             TEXT,
    ja4             TEXT,
    platform_label  TEXT,             -- e.g. 'claude.ai', 'openai', NULL if unclassified
    is_shadow_ai    BOOLEAN NOT NULL DEFAULT false,
    source          TEXT NOT NULL DEFAULT 'domain-stub',  -- 'domain-stub' (Phase 1) | 'zeek-suricata' (Phase 2)
    ts              TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_platform_events_endpoint_ts ON platform_events (endpoint_id, ts DESC);

-- Which AI account identity was observed logged-in per endpoint/platform
CREATE TABLE IF NOT EXISTS ai_account_sightings (
    id                BIGSERIAL PRIMARY KEY,
    endpoint_id       UUID NOT NULL REFERENCES endpoints(id),
    platform          TEXT NOT NULL,
    account_identity  TEXT,           -- best-effort DOM scrape, NULL if not found
    ts                TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_account_sightings_endpoint_ts ON ai_account_sightings (endpoint_id, ts DESC);

-- Module 3: outbound file/PII exfiltration + approval gate
CREATE TABLE IF NOT EXISTS dlp_events (
    id                BIGSERIAL PRIMARY KEY,
    endpoint_id       UUID NOT NULL REFERENCES endpoints(id),
    platform          TEXT NOT NULL,
    verdict           TEXT NOT NULL,      -- 'clean' | 'flagged'
    matched_entities  JSONB,              -- e.g. [{"type":"email","count":2}, {"type":"card","count":1}]
    approved          BOOLEAN,            -- NULL until user decides, then true/false
    atlas_technique_id TEXT REFERENCES atlas_techniques(id),
    ts                TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_dlp_events_endpoint_ts ON dlp_events (endpoint_id, ts DESC);

-- Module 2: indirect prompt injection detection.
-- Every scored page gets a row, not just ones that crossed the flag threshold (needed for
-- Phase 3's A/B/C evaluation to reconstruct true negatives — a benign page that correctly
-- scored low is a result, not an absence of one). a_flagged/b_flagged are the same-request
-- single-indicator baselines ai-engine's /score/injection/baselines returns alongside the
-- multi-indicator score/flagged, stored together so eval never has to recompute them separately
-- and risk drifting from what was actually returned at scoring time.
CREATE TABLE IF NOT EXISTS injection_alerts (
    id                  BIGSERIAL PRIMARY KEY,
    endpoint_id         UUID NOT NULL REFERENCES endpoints(id),
    url                 TEXT NOT NULL,
    score               DOUBLE PRECISION NOT NULL,
    flagged             BOOLEAN NOT NULL DEFAULT false,
    a_flagged           BOOLEAN NOT NULL DEFAULT false,  -- A: keyword-only baseline
    b_flagged           BOOLEAN NOT NULL DEFAULT false,  -- B: visibility-only baseline
    indicators_json     JSONB NOT NULL,   -- {"offscreen_css":1,"html_comment":0,"zero_width":1,...}
    atlas_technique_id  TEXT REFERENCES atlas_techniques(id) DEFAULT 'AML.T0051.001',
    ts                  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_injection_alerts_endpoint_ts ON injection_alerts (endpoint_id, ts DESC);

-- Phase 2/3: shadow-AI discovery. A JA4 TLS client fingerprint reused across multiple distinct
-- domains NOT on the known-AI list is a candidate signal for programmatic API traffic (one
-- SDK/HTTP client hitting several LLM-shaped endpoints) rather than organic browsing. This is an
-- honest first-cut heuristic (see agent/internal/sensor), not a calibrated model — Phase 3's
-- labeled dataset is what validates or corrects it.
--
-- Keyed on JA4 ALONE, not (ja3, ja4) — a real finding from Phase 3's fleet testing: Chrome's
-- GREASE mechanism randomizes reserved cipher/extension values in every ClientHello, which JA3's
-- naive hashing captures as noise (near-unique JA3 per connection, confirmed empirically — 10 of
-- 12 real Chrome connections to the same two mock endpoints each got a distinct JA3). JA4 is
-- specifically designed to strip GREASE before hashing and stayed stable across all of them. A
-- compound (ja3, ja4) key — which is what an earlier version of this schema used — silently
-- defeats the whole clustering rule for any real browser traffic; it only appeared to work in
-- earlier testing because that testing used curl, which doesn't implement GREASE. sample_ja3 is
-- kept for observability/debugging only, explicitly not trustworthy as a match key.
CREATE TABLE IF NOT EXISTS shadow_ai_clusters (
    ja4               TEXT PRIMARY KEY,
    sample_ja3        TEXT,  -- last-seen JA3, informational only — see comment above on GREASE
    first_seen        TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen         TIMESTAMPTZ NOT NULL DEFAULT now(),
    distinct_domains  JSONB NOT NULL DEFAULT '[]',  -- array of domain strings observed under this fingerprint
    occurrence_count   INT NOT NULL DEFAULT 1,
    confidence        TEXT NOT NULL DEFAULT 'observed'  -- 'observed' -> 'candidate' once distinct_domains >= 2
);
