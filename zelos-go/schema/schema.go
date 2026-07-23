// Package schema — Zelos data types for Go.
// Mirrors Python zelos_sdk/schema.py and TypeScript zelos-ts/src/schema.ts.
package schema

// CapabilityDeclaration is a capability registered by an Agent.
type CapabilityDeclaration struct {
	Name              string            `json:"name"`
	Version           string            `json:"version"`
	Description       string            `json:"description,omitempty"`
	InputSchema       map[string]any    `json:"input_schema,omitempty"`
	OutputSchema      map[string]any    `json:"output_schema,omitempty"`
	QoS               map[string]any    `json:"qos,omitempty"`
	Tags              []string          `json:"tags,omitempty"`
	RequiredResources map[string]any    `json:"required_resources,omitempty"`
	Capacity          int               `json:"capacity,omitempty"`
}

// TaskConstraints for scheduler dispatch.
type TaskConstraints struct {
	PreferredAgentID  string   `json:"preferred_agent_id,omitempty"`
	ExcludedAgentIDs  []string `json:"excluded_agent_ids,omitempty"`
	RequiredTags      []string `json:"required_tags,omitempty"`
	MinSuccessRate    float64  `json:"min_success_rate,omitempty"`
	TimeoutMs         int      `json:"timeout_ms,omitempty"`
	MaxRetries        int      `json:"max_retries,omitempty"`
}

// Task — a single unit of work within an Execution Plan.
type Task struct {
	TaskID               string            `json:"task_id"`
	PlanID               string            `json:"plan_id"`
	Description          string            `json:"description"`
	RequiredCapability   string            `json:"required_capability"`
	Input                map[string]any    `json:"input,omitempty"`
	ExpectedOutputSchema map[string]any    `json:"expected_output_schema,omitempty"`
	Dependencies         []string          `json:"dependencies,omitempty"`
	Constraints          TaskConstraints   `json:"constraints,omitempty"`
	FallbackCapability   string            `json:"fallback_capability,omitempty"`
	Priority             string            `json:"priority,omitempty"`
}

// Artifact produced by an Agent after executing a Task.
type Artifact struct {
	ArtifactID         string         `json:"artifact_id"`
	TaskID             string         `json:"task_id"`
	AgentID            string         `json:"agent_id"`
	ContentType        string         `json:"content_type,omitempty"`
	Content            any            `json:"content,omitempty"`
	ContentRef         string         `json:"content_ref,omitempty"`
	SizeBytes          int64          `json:"size_bytes,omitempty"`
	VerificationStatus string         `json:"verification_status,omitempty"`
	ExecutionMetadata  map[string]any `json:"execution_metadata,omitempty"`
}

// MemoryContext assembled from 6-layer Memory before Task dispatch.
type MemoryContext struct {
	Session   map[string]any `json:"session"`
	Project   map[string]any `json:"project"`
	User      map[string]any `json:"user"`
	Knowledge map[string]any `json:"knowledge"`
	Execution map[string]any `json:"execution"`
	Skill     map[string]any `json:"skill"`
}

// TaskResult returned by Agent.Execute.
type TaskResult struct {
	Status   string            `json:"status"` // "completed" | "failed"
	Artifact *ArtifactResult   `json:"artifact,omitempty"`
	Error    *TaskError        `json:"error,omitempty"`
}

// ArtifactResult within a TaskResult.
type ArtifactResult struct {
	ContentType string `json:"content_type"`
	Content     any    `json:"content"`
}

// TaskError within a TaskResult.
type TaskError struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}
