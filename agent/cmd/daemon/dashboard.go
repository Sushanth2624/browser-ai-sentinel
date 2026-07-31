// Phase 4 dashboard API — aggregate endpoints for the React dashboard (dashboard/), separate
// from the raw Recent* endpoints in main.go that back Phase 1-3 verification/the popup.
package main

import "net/http"

func (s *server) handleDashboardKPIs(w http.ResponseWriter, r *http.Request) {
	summary, err := s.db.KPISummary()
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]any{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, summary)
}

func (s *server) handleDashboardEndpoints(w http.ResponseWriter, r *http.Request) {
	rows, err := s.db.EndpointRollup()
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]any{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, jsonSafeRows(rows))
}

func (s *server) handleDashboardAssetVisibility(w http.ResponseWriter, r *http.Request) {
	visibility, err := s.db.AssetVisibility()
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]any{"error": err.Error()})
		return
	}
	visibility.Known = jsonSafeRows(visibility.Known)
	visibility.Shadow = jsonSafeRows(visibility.Shadow)
	writeJSON(w, http.StatusOK, visibility)
}

func (s *server) handleDashboardAtlas(w http.ResponseWriter, r *http.Request) {
	rows, err := s.db.AtlasCoverage()
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]any{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, jsonSafeRows(rows))
}

func (s *server) handleDashboardEndpointActivity(w http.ResponseWriter, r *http.Request) {
	endpointID := r.URL.Query().Get("endpoint_id")
	if endpointID == "" {
		writeJSON(w, http.StatusBadRequest, map[string]any{"error": "missing endpoint_id"})
		return
	}
	limit := parseLimit(r, 30)
	rows, err := s.db.EndpointActivity(endpointID, limit)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]any{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, jsonSafeRows(rows))
}
