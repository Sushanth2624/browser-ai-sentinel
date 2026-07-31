// Dashboard aggregate queries (Phase 4). Deliberately separate from store.go's Recent* methods,
// which return raw rows for the Phase 1-3 verification endpoints — these compute summaries
// server-side so the dashboard frontend never has to reduce large row sets itself.
package store

import "fmt"

type KPISummary struct {
	OpenInjectionAlerts int `json:"open_injection_alerts"`
	EndpointsMonitored  int `json:"endpoints_monitored"`
	ShadowAICandidates  int `json:"shadow_ai_candidates"`
	DLPFlagged          int `json:"dlp_flagged"`
	DLPPendingApproval  int `json:"dlp_pending_approval"`
}

func (s *Store) KPISummary() (*KPISummary, error) {
	var k KPISummary
	err := s.db.QueryRow(`
		SELECT
			(SELECT count(*) FROM injection_alerts WHERE flagged = true),
			(SELECT count(*) FROM endpoints),
			(SELECT count(*) FROM shadow_ai_clusters WHERE confidence = 'candidate'),
			(SELECT count(*) FROM dlp_events WHERE verdict = 'flagged'),
			(SELECT count(*) FROM dlp_events WHERE verdict = 'flagged' AND approved IS NULL)
	`).Scan(&k.OpenInjectionAlerts, &k.EndpointsMonitored, &k.ShadowAICandidates, &k.DLPFlagged, &k.DLPPendingApproval)
	if err != nil {
		return nil, fmt.Errorf("kpi summary: %w", err)
	}
	return &k, nil
}

// EndpointRollup returns one row per endpoint with counts a real EDR console's "endpoints" view
// would show — sorted by combined injection+DLP flags descending (busiest/riskiest first).
//
// Honest limitation on shadow_ai_involved: network-sensor-derived platform_events (source
// zeek-ja3ja4/suricata-ja3ja4) are attributed to whichever endpoint's daemon is tailing the
// sensor logs — currently only the host, since the Phase 3 fleet containers don't run their own
// sensor (see entrypoint.sh's SENSOR_LOG_DIR). Packet capture alone can't attribute a given TLS
// connection to a specific container/process without deeper host-side correlation, which is out
// of scope here. In this fleet, that means shadow_ai_involved will show true for the host
// endpoint (root) even though it was karan.iyer's container that actually generated the mock-AI
// traffic — real, worth stating plainly rather than letting the dashboard imply per-container
// attribution it doesn't have.
func (s *Store) EndpointRollup() ([]map[string]any, error) {
	// Postgres won't resolve two SELECT-list aliases combined inside an ORDER BY expression
	// directly (confirmed empirically: "column ... does not exist") — wrapping in a subquery
	// and ordering the outer query fixes it.
	return s.queryRows(`
		SELECT * FROM (
			SELECT
				e.id, e.hostname, e.os_user, e.last_seen,
				COALESCE((SELECT count(*) FROM injection_alerts ia WHERE ia.endpoint_id = e.id AND ia.flagged = true), 0) AS injection_alert_count,
				COALESCE((SELECT count(*) FROM dlp_events d WHERE d.endpoint_id = e.id AND d.verdict = 'flagged'), 0) AS dlp_flagged_count,
				COALESCE((SELECT count(DISTINCT platform_label) FROM platform_events p WHERE p.endpoint_id = e.id AND p.platform_label IS NOT NULL AND p.platform_label != ''), 0) AS platforms_seen,
				COALESCE((SELECT count(DISTINCT account_identity) FROM ai_account_sightings a WHERE a.endpoint_id = e.id AND a.account_identity IS NOT NULL), 0) AS ai_accounts_seen,
				COALESCE((SELECT bool_or(is_shadow_ai) FROM platform_events p2 WHERE p2.endpoint_id = e.id), false) AS shadow_ai_involved
			FROM endpoints e
		) rollup
		ORDER BY (injection_alert_count + dlp_flagged_count) DESC, last_seen DESC
	`)
}

// AssetVisibility splits platform_events into the two things worth showing separately (mixing
// them with the huge tail of unclassified single-sighting domains from ordinary browsing would
// just be noise): known AI platforms, and confirmed shadow-AI candidate domains. Shadow domains
// are capped at 20 (real data after a few hours of continuous sensor capture is dozens of
// domains — mostly ordinary browser/OS background traffic, the exact false-positive-precision
// finding documented in the README, not something to dump uncapped into a dashboard panel).
type AssetVisibility struct {
	Known       []map[string]any `json:"known"`
	Shadow      []map[string]any `json:"shadow"`
	ShadowTotal int              `json:"shadow_total"`
}

func (s *Store) AssetVisibility() (*AssetVisibility, error) {
	known, err := s.queryRows(`
		SELECT platform_label, count(DISTINCT endpoint_id) AS endpoint_count, count(*) AS event_count
		FROM platform_events
		WHERE platform_label IS NOT NULL AND platform_label != ''
		GROUP BY platform_label
		ORDER BY event_count DESC
	`)
	if err != nil {
		return nil, fmt.Errorf("asset visibility known: %w", err)
	}

	var shadowTotal int
	if err := s.db.QueryRow(`SELECT count(DISTINCT sni) FROM platform_events WHERE is_shadow_ai = true`).Scan(&shadowTotal); err != nil {
		return nil, fmt.Errorf("asset visibility shadow total: %w", err)
	}

	shadow, err := s.queryRows(`
		SELECT sni AS domain, count(DISTINCT endpoint_id) AS endpoint_count, count(*) AS event_count
		FROM platform_events
		WHERE is_shadow_ai = true
		GROUP BY sni
		ORDER BY event_count DESC
		LIMIT 20
	`)
	if err != nil {
		return nil, fmt.Errorf("asset visibility shadow: %w", err)
	}

	return &AssetVisibility{Known: known, Shadow: shadow, ShadowTotal: shadowTotal}, nil
}

// AtlasCoverage returns every row in atlas_techniques (currently exactly the two this project
// has actually mapped — see db/schema.sql) with a live hit count. Deliberately does not invent
// rows for the rest of the ATLAS matrix; a technique with no events just shows hit_count 0.
func (s *Store) AtlasCoverage() ([]map[string]any, error) {
	return s.queryRows(`
		SELECT
			t.id, t.name, t.tactic, t.verified,
			COALESCE((SELECT count(*) FROM injection_alerts ia WHERE ia.atlas_technique_id = t.id AND ia.flagged = true), 0)
				+ COALESCE((SELECT count(*) FROM dlp_events d WHERE d.atlas_technique_id = t.id AND d.verdict = 'flagged'), 0) AS hit_count
		FROM atlas_techniques t
		ORDER BY hit_count DESC
	`)
}

// EndpointActivity merges the three "something happened" event kinds for one endpoint into a
// single sorted feed — backs the dashboard's per-endpoint expanded timeline.
func (s *Store) EndpointActivity(endpointID string, limit int) ([]map[string]any, error) {
	return s.queryRows(`
		SELECT 'injection' AS kind, url AS detail, score::text AS extra, ts FROM injection_alerts
			WHERE endpoint_id = $1 AND flagged = true
		UNION ALL
		SELECT 'dlp' AS kind, platform AS detail, verdict AS extra, ts FROM dlp_events
			WHERE endpoint_id = $1 AND verdict = 'flagged'
		UNION ALL
		SELECT 'shadow_ai' AS kind, sni AS detail, ja4 AS extra, ts FROM platform_events
			WHERE endpoint_id = $1 AND is_shadow_ai = true
		ORDER BY ts DESC
		LIMIT $2
	`, endpointID, limit)
}
