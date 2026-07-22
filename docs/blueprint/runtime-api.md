# Runtime API

> The stable, versioned contract between the Runtime Kernel and all Plugins, Protocol Adapters, and SDKs. This is the only interface through which external systems interact with Zelos.

---

## Document Status

| Status  | Author                     | Date       |
|---------|----------------------------|------------|
| New     | Zelos Architecture Team  | 2026-07-19 |

---

## 1. Overview

The Runtime API is the stable contract of Zelos. It is transport-agnostic — defined in terms of data structures and operations, not HTTP status codes or wire formats.

[Invariant 9](../architecture/invariants.md#invariant-9-contracts-over-implementation): Components communicate only through contracts. The Runtime API is the primary contract.

---

## 2. API Groups

```
Runtime API
├── Goal API       (Client → Runtime)
├── Plan API       (Client → Runtime, internal)
├── Agent API      (Runtime ↔ Agent)
├── Admin API      (Operator → Runtime)
└── Plugin API     (Runtime → Plugin, Plugin → Runtime)
```

---

## 3. Goal API

Client-facing API for submitting and managing Goals.

### 3.1 Operations

| Operation | Direction | Description |
|-----------|-----------|-------------|
| `SubmitGoal` | Client → Runtime | Submit a new Goal |
| `GetGoalStatus` | Client → Runtime | Query Goal state and progress |
| `ListGoals` | Client → Runtime | List Goals with optional filters |
| `CancelGoal` | Client → Runtime | Cancel an active Goal |
| `WatchGoal` | Client → Runtime | Stream Goal lifecycle events |

### 3.2 SubmitGoal

```
SubmitGoal(description, constraints?, context?) → GoalResponse

Request:
  description: String (required, non-empty)
  constraints: {
    budget?: { currency: String, max_amount: Float }
    deadline?: Timestamp
    priority?: "low" | "medium" | "high" | "critical"
  }
  context: {
    project_id?: UUID
    user_id?: UUID
    metadata?: Map
  }

Response (Accepted):
  goal_id: UUID
  status: "accepted"
  created_at: Timestamp

Response (Rejected):
  goal_id: UUID
  status: "rejected"
  reason: String
  validation_errors: [String]
```

### 3.3 GetGoalStatus

```
GetGoalStatus(goal_id) → GoalStatusResponse

Response:
  goal_id: UUID
  status: GoalStatus
  plan_id: UUID?
  progress: {
    total_tasks: Int
    completed_tasks: Int
    failed_tasks: Int
    ready_tasks: Int
    in_flight_tasks: Int
    blocked_tasks: Int
    percent_complete: Float
  }
  created_at: Timestamp
  updated_at: Timestamp
  completed_at: Timestamp?
```

### 3.4 CancelGoal

```
CancelGoal(goal_id) → GoalStatusResponse

Response:
  goal_id: UUID
  status: "cancelled" | "cancelling"
  ...
```

---

## 4. Agent API

The protocol between the Runtime and Agents. [RFC-0002](../rfc/rfc-0002-agent-registration-protocol.md).

### 4.1 Operations

| Operation | Direction | Description |
|-----------|-----------|-------------|
| `Register` | Agent → Runtime | Register with declared Capabilities |
| `Heartbeat` | Agent → Runtime | Prove liveness |
| `Execute` | Runtime → Agent | Dispatch a Task for execution |
| `Cancel` | Runtime → Agent | Cancel an in-flight Task |
| `Shutdown` | Agent → Runtime | Graceful disconnection |
| `SubmitResult` | Agent → Runtime | Return Task execution result (Artifact) |

### 4.2 Register

```
Register(name, capabilities, endpoint, protocol_version) → RegistrationResponse

Request:
  name: String
  agent_id?: UUID                 // For re-registration
  capabilities: [Capability]      // At least one required
  endpoint?: URI                  // For network-based agents
  protocol: "http" | "grpc" | "stdio"
  protocol_version: String        // Runtime API version supported
  heartbeat_interval_ms?: Int     // Suggested (Runtime may override)
  max_concurrent_tasks?: Int

Response:
  agent_id: UUID
  status: "registered" | "rejected"
  reason?: String
  heartbeat_interval_ms: Int      // Runtime-assigned interval
  runtime_version: String
```

### 4.3 Heartbeat

```
Heartbeat(agent_id) → HeartbeatResponse

Response:
  status: "ok" | "re-register"
  pending_tasks: Int              // Tasks waiting for this Agent
```

### 4.4 Execute (Runtime → Agent)

```
Execute(task: Task) → ExecuteResponse

Task:
  task_id: UUID
  description: String
  input: Artifact?
  expected_output_schema: JSON Schema
  timeout_ms: Int
  context: {
    goal_description: String
    related_artifacts: [Artifact]
    memory: MemoryContext
  }
  constraints: TaskConstraints

Response:
  status: "accepted" | "rejected"
  reason?: String            // Present if rejected
```

The Agent returns the Artifact asynchronously via `SubmitResult` (see 4.7). The Execution Engine enforces the timeout — if `SubmitResult` is not called within `timeout_ms`, the Task is marked `timed_out`.

### 4.5 Cancel (Runtime → Agent)

```
Cancel(task_id: UUID) → CancelResponse

Response:
  status: "acknowledged" | "already_completed" | "unknown_task"
```

### 4.6 Shutdown

```
Shutdown(agent_id) → void
```

### 4.7 SubmitResult (Agent → Runtime)

```
SubmitResult(task_id: UUID, agent_id: UUID, result: SubmitResultPayload) → SubmitResultResponse

Request:
  task_id: UUID
  agent_id: UUID
  result: {
    status: "completed" | "failed"
    artifact?: Artifact          // Present if completed
    error?: {
      code: String               // Machine-readable: "internal_error", "invalid_input", ...
      message: String            // Human-readable description
      details?: Object
    }                            // Present if failed
  }

Response:
  status: "accepted" | "rejected"
  reason?: String                // Present if rejected (e.g., task unknown, already completed)
```

An Agent calls `SubmitResult` to return the outcome of a Task execution. The Artifact enters the Verifier pipeline before being released to downstream Tasks. If the result status is `"failed"`, the error is recorded and the Task follows its retry policy.

---

## 5. Admin API

Operator-facing API for Runtime management.

### 5.1 Operations

| Operation | Description |
|-----------|-------------|
| `ListAgents` | List all registered Agents |
| `GetAgent` | Get Agent details and status |
| `ListCapabilities` | List all registered Capabilities |
| `GetCapability` | Get Capability details and providers |
| `ListActiveGoals` | List all active Goal executions |
| `GetMetrics` | Get Runtime metrics |
| `GetHealth` | Get Runtime health status |
| `ListPlugins` | List loaded plugins |
| `ConfigurePlugin` | Update plugin configuration |

### 5.2 ListAgents

```
ListAgents(filter?) → ListAgentsResponse

Request (all fields optional):
  filter: {
    status?: "connected" | "disconnected" | "heartbeating"
    capability?: String         // Filter by capability name
    limit?: Int                 // Default 100
    offset?: Int                // Default 0
  }

Response:
  agents: [{
    agent_id: UUID
    name: String
    status: String
    capabilities: [String]      // Capability names
    current_tasks: Int
    max_concurrent_tasks: Int
    registered_at: Timestamp
    last_heartbeat_at: Timestamp?
  }]
  total: Int                    // Total matching agents
```

### 5.3 GetAgent

```
GetAgent(agent_id) → AgentDetailResponse

Response:
  agent_id: UUID
  name: String
  status: "registered" | "connected" | "heartbeating" | "disconnected" | "shutdown"
  operational_state: "idle" | "busy"
  capabilities: [{
    name: String
    version: String
    status: String
  }]
  endpoint: URI?
  protocol: "http" | "grpc" | "stdio"
  protocol_version: String
  current_tasks: [UUID]        // In-flight Task IDs
  max_concurrent_tasks: Int
  registered_at: Timestamp
  last_heartbeat_at: Timestamp?
  heartbeat_interval_ms: Int
  historical_success_rate: Float?
  total_tasks_completed: Int
  total_tasks_failed: Int
```

### 5.4 ListCapabilities

```
ListCapabilities(filter?) → ListCapabilitiesResponse

Request (all fields optional):
  filter: {
    name?: String               // Exact or prefix match
    status?: "available" | "unavailable" | "deprecated"
    limit?: Int                 // Default 100
    offset?: Int                // Default 0
  }

Response:
  capabilities: [{
    name: String
    version: String
    status: "registered" | "available" | "unavailable" | "deprecated" | "removed"
    description: String
    provider_count: Int
    registered_at: Timestamp
  }]
  total: Int
```

### 5.5 GetCapability

```
GetCapability(name, version?) → CapabilityDetailResponse

Response:
  name: String
  version: String
  status: String
  description: String
  input_schema: JSON Schema
  output_schema: JSON Schema
  tags: [String]
  providers: [{
    agent_id: UUID
    agent_name: String
    provider_status: String
    historical_success_rate: Float?
    avg_latency_ms: Float?
    cost_per_call: Float?
    current_load: Int
  }]
  registered_at: Timestamp
  deprecated_at: Timestamp?
```

### 5.6 ListActiveGoals

```
ListActiveGoals(filter?) → ListActiveGoalsResponse

Request (all fields optional):
  filter: {
    status?: String             // Filter by Goal status
    project_id?: UUID
    limit?: Int                 // Default 100
    offset?: Int                // Default 0
  }

Response:
  goals: [{
    goal_id: UUID
    description: String
    status: String
    plan_id: UUID?
    progress: {
      total_tasks: Int
      completed_tasks: Int
      failed_tasks: Int
      percent_complete: Float
    }
    created_at: Timestamp
    updated_at: Timestamp
  }]
  total: Int
```

### 5.7 GetHealth

```
GetHealth() → HealthResponse

Response:
  status: "healthy" | "degraded" | "unhealthy"
  uptime_seconds: Float
  components: {
    kernel: "healthy" | "degraded" | "unhealthy"
    plugins: {
      total: Int
      healthy: Int
      degraded: Int
      error: Int
    }
    agents: {
      total: Int
      connected: Int
      disconnected: Int
    }
  }
  version: String               // Runtime version
```

### 5.8 GetMetrics

```
GetMetrics() → MetricsResponse

Response:
  goals: {
    active: Int
    completed_total: Int
    failed_total: Int
    cancelled_total: Int
  }
  tasks: {
    in_flight: Int
    completed_total: Int
    failed_total: Int
    timed_out_total: Int
    avg_completion_ms: Float
  }
  agents: {
    registered: Int
    connected: Int
    avg_success_rate: Float
    total_tasks_dispatched: Int
  }
  events: {
    published_total: Int
    events_per_second: Float
  }
```

### 5.9 ListPlugins

```
ListPlugins(filter?) → ListPluginsResponse

Request (all fields optional):
  filter: {
    plugin_type?: "planner" | "verifier" | "policy" | "memory" | "storage" | "adapter"
    status?: "running" | "error" | "stopped" | "paused"
  }

Response:
  plugins: [{
    plugin_id: String
    plugin_type: String
    version: String
    display_name: String
    status: String
    uptime_seconds: Float?
    restarts_total: Int
  }]
  total: Int
```

### 5.10 ConfigurePlugin

```
ConfigurePlugin(plugin_id, config) → ConfigurePluginResponse

Request:
  plugin_id: String
  config: Object                // Plugin-specific configuration, validated against plugin's config_schema

Response:
  status: "applied" | "requires_restart" | "rejected"
  reason?: String               // Present if rejected or requires_restart
  applied_at: Timestamp
```

Configuration changes take effect at different times:
- `"applied"`: Configuration applied immediately to running plugin.
- `"requires_restart"`: Plugin must be restarted for config to take effect.
- `"rejected"`: Configuration failed plugin's config_schema validation.


---

## 6. Plugin API

### 6.1 Runtime → Plugin

The Runtime invokes plugins through their type-specific interfaces:

```
Planner:
  plan(goal: Goal, context: Context) → ExecutionPlan
  replan(goal: Goal, current: ExecutionPlan, events: [Event]) → ExecutionPlan

Verifier:
  verify(artifact: Artifact, criteria: VerificationCriteria) → Verdict

Policy:
  evaluate(event: Event, context: Context) → PolicyDecision
  // PolicyDecision ∈ {Allow, Reject, Delay, Retry}

ScoringStrategy:
  score(task: Task, candidates: [AgentCandidate]) → [ScoredCandidate]
  // Returns candidates with scores [0, 1], sorted best-first.
  // score=0 excludes the candidate from this scheduling round.

MemoryProvider:
  store(layer, key, value, metadata?) → Result
  retrieve(layer, key) → MemoryEntry?
  update(layer, key, value) → Result     // Atomic update of existing entry; fails if key does not exist
  search(layer, query, limit?) → [MemoryEntry]
  delete(layer, key) → Result

StorageBackend:
  append(stream, events) → Result
  read(stream, from, count) → [Event]
  snapshot(stream, state) → Result
```

### 6.2 Plugin → Runtime

Plugins communicate with the Runtime by:
1. **Returning values** from their API calls (synchronous)
2. **Publishing Events** to the Event Bus (asynchronous)

Plugins never call Kernel internals.

---

## 7. API Versioning

### 7.1 Version Format

```
v{MAJOR}.{MINOR}
```

- **MAJOR**: Breaking changes. Old versions deprecated but supported for N releases.
- **MINOR**: Additive changes. Fully backward compatible.

### 7.2 Version Lifecycle

```
v1.0  (current, supported)
v1.1  (current, supported — adds new optional fields)
v1.0  → deprecated when v1.1 released, removed after 2 more minor releases
v2.0  (new major — breaking changes, v1.x deprecated)
```

### 7.3 Version Negotiation

At Agent registration:
```
Agent declares: protocol_version = "1.0"
Runtime: API is v1.2, backward compatible with v1.0 → Accept
Runtime: API is v2.0, not compatible with v1.0 → Reject with reason
```

---

## 8. Error Model

### 8.1 Error Structure

```
APIError {
    error_code: String          // Machine-readable: "invalid_input", "not_found"
    message: String             // Human-readable description
    details: Object?            // Error-specific details (validation errors, etc.)
    correlation_id: UUID        // For tracing
}
```

### 8.2 Standard Error Codes

| Error Code | Description |
|-----------|-------------|
| `invalid_input` | Request validation failed |
| `unauthorized` | Authentication required |
| `forbidden` | Authenticated but not authorized |
| `not_found` | Referenced entity does not exist |
| `conflict` | State conflict (e.g., cancel completed Goal) |
| `timeout` | Operation timed out |
| `rate_limited` | Too many requests |
| `internal_error` | Unexpected Runtime error |
| `service_unavailable` | Runtime is starting, stopping, or degraded |
| `plugin_unavailable` | Required plugin is not healthy |
| `capability_unavailable` | No Agent provides required Capability |
| `budget_exceeded` | Goal budget limit reached |
| `deadline_exceeded` | Goal deadline passed |

---

## 9. Transport Mapping

The Runtime API is transport-agnostic. Protocol Adapters map it to specific transports:

| API Call | HTTP | gRPC |
|----------|------|------|
| SubmitGoal | `POST /api/v1/goals` | `Zelos.SubmitGoal` |
| GetGoalStatus | `GET /api/v1/goals/{id}` | `Zelos.GetGoalStatus` |
| CancelGoal | `DELETE /api/v1/goals/{id}` | `Zelos.CancelGoal` |
| Register (Agent) | `POST /api/v1/agents` | `Zelos.Register` |
| Heartbeat | `POST /api/v1/agents/{id}/heartbeat` | `Zelos.Heartbeat` |
| SubmitResult | `POST /api/v1/agents/{id}/tasks/{task_id}/result` | `Zelos.SubmitResult` |
| ListAgents | `GET /api/v1/agents` | `Zelos.ListAgents` |
| GetAgent | `GET /api/v1/agents/{id}` | `Zelos.GetAgent` |
| ListCapabilities | `GET /api/v1/capabilities` | `Zelos.ListCapabilities` |
| GetHealth | `GET /api/v1/health` | `Zelos.GetHealth` |
| GetMetrics | `GET /api/v1/admin/metrics` | `Zelos.GetMetrics` |

---

## 10. References

- [Architecture Invariants](../architecture/invariants.md) — Invariants 9, 11
- [Domain Model](./domain-model.md) — Entity definitions
- [Protocol Layer](./protocol-layer.md) — Protocol adapters use the Runtime API
- [Plugin Architecture](./plugin-architecture.md) — Plugins use the Runtime API
- [RFC-0001](../rfc/rfc-0001-goal-execution-lifecycle.md) — Goal API semantics
- [RFC-0002](../rfc/rfc-0002-agent-registration-protocol.md) — Agent API semantics
