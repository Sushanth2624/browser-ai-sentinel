// Package aiengine is a thin HTTP client for the Python ai-engine service (:8100). The daemon
// is the only caller — the extension never talks to ai-engine directly (see plan).
package aiengine

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"time"
)

type Client struct {
	baseURL string
	http    *http.Client
}

func NewClient(baseURL string) *Client {
	return &Client{baseURL: baseURL, http: &http.Client{Timeout: 5 * time.Second}}
}

type InjectionScoreResult struct {
	Score                  float64            `json:"score"`
	Flagged                bool               `json:"flagged"`
	ContributingIndicators map[string]float64 `json:"contributing_indicators"`
}

func (c *Client) ScoreInjection(url string, indicators map[string]int) (*InjectionScoreResult, error) {
	body, err := json.Marshal(map[string]any{"url": url, "indicators": indicators})
	if err != nil {
		return nil, err
	}
	var result InjectionScoreResult
	if err := c.postJSON("/score/injection", body, &result); err != nil {
		return nil, err
	}
	return &result, nil
}

// InjectionBaselinesResult is ai-engine's /score/injection/baselines response: the same
// multi-indicator (C) score as ScoreInjection, plus the two single-indicator baselines (A, B)
// used for Phase 3's A/B/C evaluation — see ai-engine/injection_scoring/scorer.py.
type InjectionBaselinesResult struct {
	C               InjectionScoreResult `json:"C_multi_indicator"`
	AKeywordOnly    bool                 `json:"A_keyword_only"`
	BVisibilityOnly bool                 `json:"B_visibility_only"`
}

func (c *Client) ScoreInjectionBaselines(url string, indicators map[string]int) (*InjectionBaselinesResult, error) {
	body, err := json.Marshal(map[string]any{"url": url, "indicators": indicators})
	if err != nil {
		return nil, err
	}
	var result InjectionBaselinesResult
	if err := c.postJSON("/score/injection/baselines", body, &result); err != nil {
		return nil, err
	}
	return &result, nil
}

type PIIEntity struct {
	Type  string `json:"type"`
	Count int    `json:"count"`
}

type PIIClassifyResult struct {
	Verdict         string      `json:"verdict"`
	MatchedEntities []PIIEntity `json:"matched_entities"`
}

func (c *Client) ClassifyPII(text string) (*PIIClassifyResult, error) {
	body, err := json.Marshal(map[string]any{"text": text})
	if err != nil {
		return nil, err
	}
	var result PIIClassifyResult
	if err := c.postJSON("/classify/pii", body, &result); err != nil {
		return nil, err
	}
	return &result, nil
}

func (c *Client) Healthy() bool {
	resp, err := c.http.Get(c.baseURL + "/health")
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	return resp.StatusCode == http.StatusOK
}

func (c *Client) postJSON(path string, body []byte, out any) error {
	resp, err := c.http.Post(c.baseURL+path, "application/json", bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("post %s: %w", path, err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("post %s: status %d", path, resp.StatusCode)
	}
	return json.NewDecoder(resp.Body).Decode(out)
}
