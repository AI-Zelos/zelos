// Package client — HTTP client for remote Zelos Runtime access.
//
// Usage:
//   c := client.New("http://localhost:9876", "zk-client-dev")
//   health, _ := c.Health()
//   goal, _ := c.SubmitGoal("Build a landing page")
package client

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// ZelosClient communicates with a remote Zelos Runtime via its REST API.
type ZelosClient struct {
	BaseURL string
	APIKey  string
	HTTP    *http.Client
}

// New creates a new ZelosClient.
func New(baseURL, apiKey string) *ZelosClient {
	return &ZelosClient{
		BaseURL: baseURL,
		APIKey:  apiKey,
		HTTP:    &http.Client{Timeout: 30 * time.Second},
	}
}

func (c *ZelosClient) headers() http.Header {
	h := http.Header{"Content-Type": {"application/json"}}
	if c.APIKey != "" {
		h.Set("Authorization", "Bearer "+c.APIKey)
	}
	return h
}

func (c *ZelosClient) request(method, path string, body any) (map[string]any, error) {
	var r io.Reader
	if body != nil {
		b, _ := json.Marshal(body)
		r = bytes.NewReader(b)
	}
	req, _ := http.NewRequest(method, c.BaseURL+path, r)
	req.Header = c.headers()

	resp, err := c.HTTP.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	var result map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode failed: %w", err)
	}
	if resp.StatusCode >= 400 {
		return result, fmt.Errorf("HTTP %d: %v", resp.StatusCode, result["error"])
	}
	return result, nil
}

// ── Goal API ──

// SubmitGoal submits a Goal to the Runtime.
func (c *ZelosClient) SubmitGoal(description, priority string) (map[string]any, error) {
	return c.request("POST", "/api/v1/goals", map[string]any{
		"description": description,
		"priority":    priority,
	})
}

// GetGoalStatus returns the current status of a Goal.
func (c *ZelosClient) GetGoalStatus(goalID string) (map[string]any, error) {
	return c.request("GET", "/api/v1/goals/"+goalID, nil)
}

// CancelGoal cancels a running Goal.
func (c *ZelosClient) CancelGoal(goalID string) (map[string]any, error) {
	return c.request("DELETE", "/api/v1/goals/"+goalID, nil)
}

// ── Agent API ──

// RegisterAgent registers an Agent with the Runtime.
func (c *ZelosClient) RegisterAgent(name, entrypoint string, caps []map[string]any) (map[string]any, error) {
	return c.request("POST", "/api/v1/agents", map[string]any{
		"name":         name,
		"entrypoint":   entrypoint,
		"capabilities": caps,
	})
}

// ListAgents lists all registered Agents.
func (c *ZelosClient) ListAgents() (map[string]any, error) {
	return c.request("GET", "/api/v1/agents", nil)
}

// ── Admin API ──

// Health checks Runtime health.
func (c *ZelosClient) Health() (map[string]any, error) {
	return c.request("GET", "/api/v1/health", nil)
}

// Metrics returns Runtime metrics.
func (c *ZelosClient) Metrics() (map[string]any, error) {
	return c.request("GET", "/api/v1/admin/metrics", nil)
}
