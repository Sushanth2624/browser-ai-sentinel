// Package store wraps the Postgres access the daemon needs. Deliberately thin — no ORM,
// plain database/sql + lib/pq, since the schema is small and fixed (db/schema.sql is the
// single source of truth for table shape).
package store

import (
	"database/sql"
	"encoding/json"
	"fmt"

	_ "github.com/lib/pq"
)

type Store struct {
	db *sql.DB
}

func Open(dsn string) (*Store, error) {
	db, err := sql.Open("postgres", dsn)
	if err != nil {
		return nil, fmt.Errorf("open db: %w", err)
	}
	if err := db.Ping(); err != nil {
		return nil, fmt.Errorf("ping db: %w", err)
	}
	return &Store{db: db}, nil
}

func (s *Store) Close() error { return s.db.Close() }

// EnsureEndpoint returns this endpoint's UUID, creating the row on first run and bumping
// last_seen on every subsequent call. hostname+os_user is the natural key (see schema.sql).
func (s *Store) EnsureEndpoint(hostname, osUser string) (string, error) {
	var id string
	err := s.db.QueryRow(`
		INSERT INTO endpoints (hostname, os_user)
		VALUES ($1, $2)
		ON CONFLICT (hostname, os_user)
		DO UPDATE SET last_seen = now()
		RETURNING id
	`, hostname, osUser).Scan(&id)
	if err != nil {
		return "", fmt.Errorf("ensure endpoint: %w", err)
	}
	return id, nil
}

func (s *Store) InsertPlatformEvent(endpointID, sni, ja3, ja4, platformLabel string, isShadowAI bool, source string) error {
	_, err := s.db.Exec(`
		INSERT INTO platform_events (endpoint_id, sni, ja3, ja4, platform_label, is_shadow_ai, source)
		VALUES ($1, $2, $3, $4, $5, $6, $7)
	`, endpointID, sni, ja3, ja4, platformLabel, isShadowAI, source)
	if err != nil {
		return fmt.Errorf("insert platform event: %w", err)
	}
	return nil
}

// UpsertShadowAICluster records a (ja3, ja4) fingerprint sighting under the given domain and
// returns whether it now qualifies as a shadow-AI "candidate" — i.e. this fingerprint has been
// seen under >=2 distinct domains (see the heuristic's rationale in db/schema.sql). Two
// round trips (upsert the domain set, then re-derive confidence from its length) rather than one
// dense CTE, favoring clarity over cleverness for a piece of logic a mentor/panel will read.
//
// Keyed on ja4 alone — NOT (ja3, ja4). Real finding from Phase 3 fleet testing: Chrome's GREASE
// mechanism randomizes reserved cipher/extension values per ClientHello, making JA3 near-unique
// per connection even from the same client (confirmed: 10 of 12 real Chrome connections to the
// same two mock endpoints each got a distinct JA3). JA4 strips GREASE before hashing and stayed
// stable across all of them. sample_ja3 is stored for observability only, not matched on — see
// db/schema.sql's comment on shadow_ai_clusters for the full story.
func (s *Store) UpsertShadowAICluster(ja3, ja4, domain string) (isCandidate bool, err error) {
	var domainCount int
	err = s.db.QueryRow(`
		INSERT INTO shadow_ai_clusters (ja4, sample_ja3, distinct_domains, occurrence_count)
		VALUES ($1, $2, jsonb_build_array($3::text), 1)
		ON CONFLICT (ja4) DO UPDATE SET
			last_seen = now(),
			sample_ja3 = $2,
			occurrence_count = shadow_ai_clusters.occurrence_count + 1,
			distinct_domains = CASE
				WHEN shadow_ai_clusters.distinct_domains @> jsonb_build_array($3::text)
				THEN shadow_ai_clusters.distinct_domains
				ELSE shadow_ai_clusters.distinct_domains || jsonb_build_array($3::text)
			END
		RETURNING jsonb_array_length(distinct_domains)
	`, ja4, ja3, domain).Scan(&domainCount)
	if err != nil {
		return false, fmt.Errorf("upsert shadow ai cluster: %w", err)
	}

	isCandidate = domainCount >= 2
	if isCandidate {
		if _, err := s.db.Exec(
			`UPDATE shadow_ai_clusters SET confidence = 'candidate' WHERE ja4 = $1`,
			ja4,
		); err != nil {
			return false, fmt.Errorf("update shadow ai cluster confidence: %w", err)
		}
	}
	return isCandidate, nil
}

func (s *Store) InsertAccountSighting(endpointID, platform, accountIdentity string) error {
	_, err := s.db.Exec(`
		INSERT INTO ai_account_sightings (endpoint_id, platform, account_identity)
		VALUES ($1, $2, $3)
	`, endpointID, platform, accountIdentity)
	if err != nil {
		return fmt.Errorf("insert account sighting: %w", err)
	}
	return nil
}

type PIIEntity struct {
	Type  string `json:"type"`
	Count int    `json:"count"`
}

// InsertDLPEvent returns the new row's id so the extension can later report the user's
// approve/deny decision against it via UpdateDLPDecision.
func (s *Store) InsertDLPEvent(endpointID, platform, verdict string, entities []PIIEntity, atlasTechniqueID string) (int64, error) {
	entitiesJSON, err := json.Marshal(entities)
	if err != nil {
		return 0, fmt.Errorf("marshal entities: %w", err)
	}
	var id int64
	err = s.db.QueryRow(`
		INSERT INTO dlp_events (endpoint_id, platform, verdict, matched_entities, atlas_technique_id)
		VALUES ($1, $2, $3, $4, $5)
		RETURNING id
	`, endpointID, platform, verdict, entitiesJSON, atlasTechniqueID).Scan(&id)
	if err != nil {
		return 0, fmt.Errorf("insert dlp event: %w", err)
	}
	return id, nil
}

func (s *Store) UpdateDLPDecision(id int64, approved bool) error {
	_, err := s.db.Exec(`UPDATE dlp_events SET approved = $1 WHERE id = $2`, approved, id)
	if err != nil {
		return fmt.Errorf("update dlp decision: %w", err)
	}
	return nil
}

// InsertInjectionAlert records every scored page (not just flagged ones — see schema.sql's
// comment on injection_alerts: Phase 3's eval needs true negatives, not just positives).
func (s *Store) InsertInjectionAlert(endpointID, url string, score float64, flagged, aFlagged, bFlagged bool, indicators map[string]float64) (int64, error) {
	indicatorsJSON, err := json.Marshal(indicators)
	if err != nil {
		return 0, fmt.Errorf("marshal indicators: %w", err)
	}
	var id int64
	err = s.db.QueryRow(`
		INSERT INTO injection_alerts (endpoint_id, url, score, flagged, a_flagged, b_flagged, indicators_json)
		VALUES ($1, $2, $3, $4, $5, $6, $7)
		RETURNING id
	`, endpointID, url, score, flagged, aFlagged, bFlagged, indicatorsJSON).Scan(&id)
	if err != nil {
		return 0, fmt.Errorf("insert injection alert: %w", err)
	}
	return id, nil
}

// Recent* are read-only helpers used by the Phase-1 verification endpoints and, later, the
// dashboard API.
func (s *Store) RecentPlatformEvents(limit int) ([]map[string]any, error) {
	return s.queryRows(`
		SELECT id, endpoint_id, sni, ja3, ja4, platform_label, is_shadow_ai, source, ts
		FROM platform_events ORDER BY ts DESC LIMIT $1
	`, limit)
}

func (s *Store) RecentShadowAIClusters(limit int) ([]map[string]any, error) {
	return s.queryRows(`
		SELECT ja4, sample_ja3, distinct_domains, occurrence_count, confidence, first_seen, last_seen
		FROM shadow_ai_clusters ORDER BY last_seen DESC LIMIT $1
	`, limit)
}

func (s *Store) RecentInjectionAlerts(limit int) ([]map[string]any, error) {
	return s.queryRows(`
		SELECT id, endpoint_id, url, score, flagged, a_flagged, b_flagged, indicators_json, ts
		FROM injection_alerts ORDER BY ts DESC LIMIT $1
	`, limit)
}

func (s *Store) RecentDLPEvents(limit int) ([]map[string]any, error) {
	return s.queryRows(`
		SELECT id, endpoint_id, platform, verdict, matched_entities, approved, ts
		FROM dlp_events ORDER BY ts DESC LIMIT $1
	`, limit)
}

func (s *Store) queryRows(query string, args ...any) ([]map[string]any, error) {
	rows, err := s.db.Query(query, args...)
	if err != nil {
		return nil, fmt.Errorf("query: %w", err)
	}
	defer rows.Close()

	cols, err := rows.Columns()
	if err != nil {
		return nil, fmt.Errorf("columns: %w", err)
	}

	var results []map[string]any
	for rows.Next() {
		vals := make([]any, len(cols))
		ptrs := make([]any, len(cols))
		for i := range vals {
			ptrs[i] = &vals[i]
		}
		if err := rows.Scan(ptrs...); err != nil {
			return nil, fmt.Errorf("scan: %w", err)
		}
		row := map[string]any{}
		for i, c := range cols {
			row[c] = vals[i]
		}
		results = append(results, row)
	}
	return results, rows.Err()
}
