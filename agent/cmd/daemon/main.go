// Command daemon is the always-on, systemd-managed half of the agent (see plan's process-model
// split). Serves the extension's events over HTTP, calls the Python ai-engine for
// scoring/classification, writes to Postgres, and classifies AI platforms two ways: the client
// (extension) declares the domain it's on via handlePlatformCheck (fast, simple, Phase 1), and
// — as of Phase 2 — a pair of background goroutines tail the standalone Zeek/Suricata sensors'
// logs for the authoritative network-layer signal (real SNI/JA3/JA4, plus shadow-AI clustering
// for domains not on the known-AI list). Both paths write to platform_events, tagged by source,
// so neither replaces the other — see db/schema.sql and agent/internal/sensor.
package main

import (
	"encoding/json"
	"log"
	"net/http"
	"os"
	"os/user"
	"strconv"
	"strings"

	"github.com/Sushanth2624/browser-ai-sentinel/agent/internal/aiengine"
	"github.com/Sushanth2624/browser-ai-sentinel/agent/internal/sensor"
	"github.com/Sushanth2624/browser-ai-sentinel/agent/internal/store"
)

// Phase 1 stub — real classification moves to Zeek/Suricata SNI+JA3/JA4 in Phase 2.
var knownAIDomains = map[string]string{
	"claude.ai":                         "Anthropic Claude",
	"api.anthropic.com":                 "Anthropic Claude",
	"chatgpt.com":                       "OpenAI ChatGPT",
	"chat.openai.com":                   "OpenAI ChatGPT",
	"api.openai.com":                    "OpenAI ChatGPT",
	"gemini.google.com":                 "Google Gemini",
	"generativelanguage.googleapis.com": "Google Gemini",
	"perplexity.ai":                     "Perplexity",
	"copilot.microsoft.com":             "Microsoft Copilot",
}

type server struct {
	db         *store.Store
	ai         *aiengine.Client
	endpointID string
}

func main() {
	dsn := envOr("DATABASE_URL", "postgres://aisentinel:changeme-local-dev-only@127.0.0.1:5433/aisentinel?sslmode=disable")
	aiURL := envOr("AI_ENGINE_URL", "http://127.0.0.1:8100")
	listenAddr := envOr("LISTEN_ADDR", "127.0.0.1:8090")

	db, err := store.Open(dsn)
	if err != nil {
		log.Fatalf("db open: %v", err)
	}
	defer db.Close()

	hostname, err := os.Hostname()
	if err != nil {
		log.Fatalf("hostname: %v", err)
	}
	osUser, err := user.Current()
	if err != nil {
		log.Fatalf("os user: %v", err)
	}

	endpointID, err := db.EnsureEndpoint(hostname, osUser.Username)
	if err != nil {
		log.Fatalf("ensure endpoint: %v", err)
	}
	log.Printf("endpoint registered: id=%s hostname=%s os_user=%s", endpointID, hostname, osUser.Username)

	s := &server{db: db, ai: aiengine.NewClient(aiURL), endpointID: endpointID}

	sensorLogDir := envOr("SENSOR_LOG_DIR", "/home/analysis/browser-ai-sentinel/sensor/logs")
	// Two Zeek log paths: bas-zeek (ens18, real internet-bound AI traffic) and bas-zeek-lo (lo —
	// needed because same-host traffic to a local address, like Phase 3's mock-ai endpoints,
	// never transits the physical NIC; confirmed empirically, see sensor/zeek-lo's service unit).
	zeekSSLLogs := []string{sensorLogDir + "/zeek/ssl.log", sensorLogDir + "/zeek-lo/ssl.log"}
	suricataEveLog := sensorLogDir + "/suricata/eve.json"

	for _, path := range zeekSSLLogs {
		path := path
		go func() {
			err := sensor.TailZeekSSL(path, path+".offset", s.ingestSensorEvent)
			log.Fatalf("zeek tailer (%s) exited: %v", path, err)
		}()
	}
	go func() {
		err := sensor.TailSuricataEve(suricataEveLog, suricataEveLog+".offset", s.ingestSensorEvent)
		log.Fatalf("suricata tailer exited: %v", err)
	}()
	log.Printf("sensor tailers started: zeek=%v suricata=%s", zeekSSLLogs, suricataEveLog)

	mux := http.NewServeMux()
	mux.HandleFunc("/health", s.handleHealth)
	mux.HandleFunc("/nm", s.handleNM)
	mux.HandleFunc("/api/injection_alerts", s.handleRecentInjectionAlerts)
	mux.HandleFunc("/api/dlp_events", s.handleRecentDLPEvents)
	mux.HandleFunc("/api/platform_events", s.handleRecentPlatformEvents)
	mux.HandleFunc("/api/shadow_ai_clusters", s.handleRecentShadowAIClusters)

	// Phase 4 dashboard aggregate endpoints — see dashboard.go
	mux.HandleFunc("/api/dashboard/kpis", s.handleDashboardKPIs)
	mux.HandleFunc("/api/dashboard/endpoints", s.handleDashboardEndpoints)
	mux.HandleFunc("/api/dashboard/asset-visibility", s.handleDashboardAssetVisibility)
	mux.HandleFunc("/api/dashboard/atlas", s.handleDashboardAtlas)
	mux.HandleFunc("/api/dashboard/endpoint-activity", s.handleDashboardEndpointActivity)

	log.Printf("daemon listening on %s (ai-engine=%s)", listenAddr, aiURL)
	log.Fatal(http.ListenAndServe(listenAddr, mux))
}

func (s *server) handleHealth(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{
		"status":       "ok",
		"endpoint_id":  s.endpointID,
		"ai_engine_ok": s.ai.Healthy(),
	})
}

// nmMessage is the single relay envelope nmhost forwards verbatim from the extension. Keeping
// nmhost itself dumb (no per-type logic) means all dispatch lives here, in one place.
type nmMessage struct {
	Type    string          `json:"type"`
	Payload json.RawMessage `json:"payload"`
}

func (s *server) handleNM(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var msg nmMessage
	if err := json.NewDecoder(r.Body).Decode(&msg); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]any{"ok": false, "error": err.Error()})
		return
	}

	var (
		result any
		err    error
	)
	switch msg.Type {
	case "injection":
		result, err = s.handleInjection(msg.Payload)
	case "dlp_check":
		result, err = s.handleDLPCheck(msg.Payload)
	case "dlp_decision":
		result, err = s.handleDLPDecision(msg.Payload)
	case "platform_check":
		result, err = s.handlePlatformCheck(msg.Payload)
	case "account_sighting":
		result, err = s.handleAccountSighting(msg.Payload)
	default:
		err = errUnknownType(msg.Type)
	}

	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]any{"ok": false, "error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"ok": true, "result": result})
}

func (s *server) handleInjection(payload json.RawMessage) (any, error) {
	var req struct {
		URL        string         `json:"url"`
		Indicators map[string]int `json:"indicators"`
	}
	if err := json.Unmarshal(payload, &req); err != nil {
		return nil, err
	}
	baselines, err := s.ai.ScoreInjectionBaselines(req.URL, req.Indicators)
	if err != nil {
		return nil, err
	}
	// Every scored page is recorded, not just flagged ones — Phase 3's A/B/C evaluation needs
	// true negatives (a benign page that correctly scored low) as much as true positives.
	if _, err := s.db.InsertInjectionAlert(
		s.endpointID, req.URL, baselines.C.Score, baselines.C.Flagged,
		baselines.AKeywordOnly, baselines.BVisibilityOnly, baselines.C.ContributingIndicators,
	); err != nil {
		log.Printf("insert injection alert: %v", err)
	}
	return baselines.C, nil
}

func (s *server) handleDLPCheck(payload json.RawMessage) (any, error) {
	var req struct {
		Platform string `json:"platform"`
		Text     string `json:"text"`
	}
	if err := json.Unmarshal(payload, &req); err != nil {
		return nil, err
	}
	classified, err := s.ai.ClassifyPII(req.Text)
	if err != nil {
		return nil, err
	}
	entities := make([]store.PIIEntity, len(classified.MatchedEntities))
	for i, e := range classified.MatchedEntities {
		entities[i] = store.PIIEntity{Type: e.Type, Count: e.Count}
	}
	id, err := s.db.InsertDLPEvent(s.endpointID, req.Platform, classified.Verdict, entities, "DLP-MODULE-TODO")
	if err != nil {
		return nil, err
	}
	return map[string]any{
		"dlp_event_id":     id,
		"verdict":          classified.Verdict,
		"matched_entities": classified.MatchedEntities,
	}, nil
}

func (s *server) handleDLPDecision(payload json.RawMessage) (any, error) {
	var req struct {
		DLPEventID int64 `json:"dlp_event_id"`
		Approved   bool  `json:"approved"`
	}
	if err := json.Unmarshal(payload, &req); err != nil {
		return nil, err
	}
	if err := s.db.UpdateDLPDecision(req.DLPEventID, req.Approved); err != nil {
		return nil, err
	}
	return map[string]any{"updated": true}, nil
}

func (s *server) handlePlatformCheck(payload json.RawMessage) (any, error) {
	var req struct {
		Domain string `json:"domain"`
	}
	if err := json.Unmarshal(payload, &req); err != nil {
		return nil, err
	}
	domain := strings.ToLower(req.Domain)
	label, known := knownAIDomains[domain]
	if err := s.db.InsertPlatformEvent(s.endpointID, domain, "", "", label, false, "domain-stub"); err != nil {
		log.Printf("insert platform event: %v", err)
	}
	return map[string]any{
		"platform_label": label,
		"known":          known,
		"is_shadow_ai":   false, // Phase 1 stub cannot determine this — needs Phase 2 JA3/JA4
	}, nil
}

// ingestSensorEvent is the callback wired to both sensor tailers (main()). Classifies against
// the same knownAIDomains map handlePlatformCheck uses, and — for domains NOT on that list —
// runs the shadow-AI clustering heuristic (store.UpsertShadowAICluster): a TLS fingerprint
// reused across >=2 distinct unlisted domains is flagged as a shadow-AI candidate. This is the
// real, network-authoritative counterpart to handlePlatformCheck's client-declared stub.
func (s *server) ingestSensorEvent(e sensor.Event) {
	domain := strings.ToLower(e.SNI)
	label, known := knownAIDomains[domain]

	isShadowAI := false
	if !known && e.JA3 != "" && e.JA4 != "" {
		candidate, err := s.db.UpsertShadowAICluster(e.JA3, e.JA4, domain)
		if err != nil {
			log.Printf("shadow ai cluster upsert: %v", err)
		} else {
			isShadowAI = candidate
		}
	}

	if err := s.db.InsertPlatformEvent(s.endpointID, domain, e.JA3, e.JA4, label, isShadowAI, e.Source); err != nil {
		log.Printf("insert platform event (sensor): %v", err)
	}
}

func (s *server) handleAccountSighting(payload json.RawMessage) (any, error) {
	var req struct {
		Platform        string `json:"platform"`
		AccountIdentity string `json:"account_identity"`
	}
	if err := json.Unmarshal(payload, &req); err != nil {
		return nil, err
	}
	if err := s.db.InsertAccountSighting(s.endpointID, req.Platform, req.AccountIdentity); err != nil {
		return nil, err
	}
	return map[string]any{"recorded": true}, nil
}

func (s *server) handleRecentInjectionAlerts(w http.ResponseWriter, r *http.Request) {
	limit := parseLimit(r, 20)
	rows, err := s.db.RecentInjectionAlerts(limit)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]any{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, jsonSafeRows(rows))
}

func (s *server) handleRecentDLPEvents(w http.ResponseWriter, r *http.Request) {
	limit := parseLimit(r, 20)
	rows, err := s.db.RecentDLPEvents(limit)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]any{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, jsonSafeRows(rows))
}

func (s *server) handleRecentPlatformEvents(w http.ResponseWriter, r *http.Request) {
	limit := parseLimit(r, 20)
	rows, err := s.db.RecentPlatformEvents(limit)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]any{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, jsonSafeRows(rows))
}

func (s *server) handleRecentShadowAIClusters(w http.ResponseWriter, r *http.Request) {
	limit := parseLimit(r, 20)
	rows, err := s.db.RecentShadowAIClusters(limit)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]any{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, jsonSafeRows(rows))
}

func parseLimit(r *http.Request, def int) int {
	if v := r.URL.Query().Get("limit"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			return n
		}
	}
	return def
}

// jsonSafeRows converts []byte JSONB columns (which encoding/json would otherwise base64-encode)
// into json.RawMessage so they render as real nested JSON in API responses.
func jsonSafeRows(rows []map[string]any) []map[string]any {
	for _, row := range rows {
		for k, v := range row {
			if b, ok := v.([]byte); ok {
				if json.Valid(b) {
					row[k] = json.RawMessage(b)
				} else {
					row[k] = string(b)
				}
			}
		}
	}
	return rows
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(v); err != nil {
		log.Printf("write json: %v", err)
	}
}

func envOr(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

type errUnknownType string

func (e errUnknownType) Error() string { return "unknown message type: " + string(e) }
