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

-- Module 2: indirect prompt injection detection
CREATE TABLE IF NOT EXISTS injection_alerts (
    id                  BIGSERIAL PRIMARY KEY,
    endpoint_id         UUID NOT NULL REFERENCES endpoints(id),
    url                 TEXT NOT NULL,
    score               DOUBLE PRECISION NOT NULL,
    indicators_json     JSONB NOT NULL,   -- {"offscreen_css":1,"html_comment":0,"zero_width":1,...}
    atlas_technique_id  TEXT REFERENCES atlas_techniques(id) DEFAULT 'AML.T0051.001',
    ts                  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_injection_alerts_endpoint_ts ON injection_alerts (endpoint_id, ts DESC);

-- Phase 2: shadow-AI discovery. A (ja3, ja4) TLS client fingerprint reused across multiple
-- distinct domains NOT on the known-AI list is a candidate signal for programmatic API traffic
-- (one SDK/HTTP client hitting several LLM-shaped endpoints) rather than organic browsing.
-- This is an honest first-cut heuristic (see agent/internal/sensor), not a calibrated model —
-- Phase 3's labeled dataset is what validates or corrects it.
CREATE TABLE IF NOT EXISTS shadow_ai_clusters (
    ja3               TEXT NOT NULL,
    ja4               TEXT NOT NULL,
    first_seen        TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen         TIMESTAMPTZ NOT NULL DEFAULT now(),
    distinct_domains  JSONB NOT NULL DEFAULT '[]',  -- array of domain strings observed under this fingerprint
    occurrence_count   INT NOT NULL DEFAULT 1,
    confidence        TEXT NOT NULL DEFAULT 'observed',  -- 'observed' -> 'candidate' once distinct_domains >= 2
    PRIMARY KEY (ja3, ja4)
);
