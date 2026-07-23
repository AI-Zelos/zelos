// Package agent — BaseAgent for building Zelos Agents in Go.
//
// Implement the Agent interface and register with the Runtime.
// The Runtime owns planning, scheduling, retry, memory — the Agent only executes.
package agent

import (
	"github.com/zelos/zelos-go/schema"
)

// Agent is the interface every Zelos Agent must implement.
type Agent interface {
	// DeclareCapabilities returns the capabilities this Agent provides.
	DeclareCapabilities() []schema.CapabilityDeclaration
	// Execute runs a Task and returns the result.
	Execute(task schema.Task) (schema.TaskResult, error)
	// ValidateTask is an optional hook to reject tasks this Agent should not handle.
	ValidateTask(task schema.Task) bool
	// OnRegistered is called after successful registration.
	OnRegistered(agentID string)
	// OnShutdown is called before the Agent is shut down.
	OnShutdown()
}

// BaseAgent provides default implementations of optional hooks.
type BaseAgent struct {
	AgentID string
	Config  map[string]any
}

// ValidateTask defaults to accepting all tasks.
func (b *BaseAgent) ValidateTask(task schema.Task) bool { return true }

// OnRegistered stores the agent ID.
func (b *BaseAgent) OnRegistered(agentID string) { b.AgentID = agentID }

// OnShutdown is a no-op by default.
func (b *BaseAgent) OnShutdown() {}

// NewBaseAgent creates a BaseAgent with optional config.
func NewBaseAgent(config map[string]any) *BaseAgent {
	if config == nil {
		config = make(map[string]any)
	}
	return &BaseAgent{Config: config}
}

// DemoAgent is a simple Agent that echoes the task description.
type DemoAgent struct {
	BaseAgent
}

// DeclareCapabilities returns a single Python code generation capability.
func (d *DemoAgent) DeclareCapabilities() []schema.CapabilityDeclaration {
	return []schema.CapabilityDeclaration{
		{
			Name:        "code-generation.python",
			Version:     "1.0.0",
			Description: "Generates Python code from task descriptions",
			Tags:        []string{"python", "demo"},
		},
	}
}

// Execute returns a simple hello-world artifact.
func (d *DemoAgent) Execute(task schema.Task) (schema.TaskResult, error) {
	return schema.TaskResult{
		Status: "completed",
		Artifact: &schema.ArtifactResult{
			ContentType: "text/plain",
			Content:     "# Generated for: " + task.Description + "\ndef hello():\n    return 'Hello from Zelos!'",
		},
	}, nil
}
