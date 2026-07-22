# Execution Engine

> Complete Execution Engine: dispatch, lifecycle monitoring, heartbeat tracking, cancellation, timeout enforcement, retry backoff, artifact collection, failure recovery.

---

## Document Status

| Status  | Author                     | Date       |
|---------|----------------------------|------------|
| New     | Zelos Architecture Team  | 2026-07-19 |

---

## 1. Overview

The Execution Engine is the Kernel component that bridges the Runtime and Agents. It dispatches Tasks, monitors their execution, enforces timeouts, tracks heartbeats, and collects Artifacts.

### 1.1 Position

```
Scheduler                    Agent
    │                          │
    │ assignment               │
    ▼                          │
┌──────────────────┐           │
│ EXECUTION ENGINE │───────────┘
│                  │  dispatch, heartbeat, cancel
│ ┌──────────────┐ │
│ │Task Dispatcher│ │
│ ├──────────────┤ │
│ │Lifecycle Mon.│ │
│ ├──────────────┤ │
│ │Heartbeat Trk.│ │
│ └──────────────┘ │
└──────────────────┘
```

---

## 2. Dispatch

### 2.1 Dispatch Flow

```
Scheduler produces assignment (task_id → agent_id)
    │
    ▼
Execution Engine:
    1. Look up Agent endpoint and protocol
    2. Assemble Task payload (description, input, context, constraints)
    3. Call Agent.execute(task) via appropriate protocol
    4. Wait for response (synchronous or callback)
```

### 2.2 Task Payload Assembly

The Execution Engine assembles the full Task payload before dispatch. Context Assembly is the Execution Engine's responsibility — it invokes the Memory Provider to gather relevant Memory entries and assembles the `context.memory` field from Session, Project, User, Knowledge, and Skill layers (see [Memory Architecture](./memory-architecture.md) §5.1).

```
TaskPayload {
    task_id: UUID
    description: String
    input: Artifact?            // From dependency outputs
    expected_output_schema: JSON Schema
    timeout_ms: Int
    context: {
        goal_description: String
        related_artifacts: [Artifact]   // From other dependencies
        memory: MemoryContext           // Assembled by Execution Engine via Memory Provider
    }
    constraints: {
        max_cost_per_call: Float?
        ... (all task.constraints)
    }
}
```

### 2.3 Dispatch Protocol

The Execution Engine communicates with Agents through the Runtime API's `Execute` operation. The transport layer (HTTP, gRPC, etc.) is handled by the Protocol Adapter — the Execution Engine is transport-agnostic.

See [Runtime API §4.4](./runtime-api.md#44-execute-runtime--agent) for the `Execute` operation contract and [Protocol Layer](./protocol-layer.md) for the HTTP/gRPC endpoint mapping.

```
Execute(task: Task) → ExecuteResponse

Response:
  status: "accepted" | "rejected"
  reason?: String
```

On `accepted`: Task → `started`. Publish `task.started`.
On `rejected`: Task → `ready`. Scheduler retries with different Agent.

---

## 3. Lifecycle Monitoring

### 3.1 In-Flight Task Tracking

```
Execution Engine maintains:
  in_flight_tasks: Map<TaskID, InFlightTask>

InFlightTask {
    task_id: UUID
    agent_id: UUID
    started_at: Timestamp
    timeout_at: Timestamp
    status: "running" | "cancelling"
}
```

### 3.2 Completion Handling

```
Agent returns Artifact:
    1. Validate Artifact basic structure (artifact_id, task_id, content_type)
    2. Validate Artifact schema (if expected_output_schema is defined)
    3. Store Artifact
    4. Record execution metadata (time, cost, tokens)
    5. Publish artifact.created
    6. Task → completion pending (waiting for optional verification)
    7. If no verifier: Task → completed, publish task.completed
    8. If verifier configured: invoke verifier, wait for verdict
```

---

## 4. Timeout Enforcement

### 4.1 Timeout Detection

```
Every timeout_check_interval_ms (default: 1000ms):
    for task in in_flight_tasks:
        if now() >= task.timeout_at:
            handle_timeout(task)
```

### 4.2 Timeout Handling

```
handle_timeout(task):
    1. Send cancel(task_id) to Agent
    2. Task → timed_out
    3. Publish task.timed_out
    4. Scheduler evaluates retry policy
```

---

## 5. Cancellation

### 5.1 Cancellation Sources

| Source | Trigger |
|--------|---------|
| Goal cancellation | `goal.cancelled` event |
| Explicit task cancellation | Admin API call |
| Timeout | Timeout exceeded |
| Agent disconnection | Heartbeat timeout |

### 5.2 Cancellation Protocol

```
Execution Engine → Agent: cancel(task_id)
    │
    ▼
Agent: stops work on task_id
    │
    ▼
Agent → Execution Engine: cancel_ack(task_id)
```

### 5.3 Cancellation Timeout

If Agent doesn't acknowledge cancel within `cancel_timeout_ms` (default: 30s):
- Task is force-failed
- Agent may be marked as unresponsive

---

## 6. Heartbeat Tracking

### 6.1 Heartbeat Protocol

```
Agent → Runtime: heartbeat() every heartbeat_interval_ms (default: 30s)

Runtime: update agent.last_heartbeat = now()
Runtime: return { status: "ok", pending_tasks: N }

If now() - last_heartbeat > heartbeat_timeout_ms (3x interval):
    → Agent disconnected
    → All capabilities → unavailable
    → All in-flight tasks → cancel and reassess
```

### 6.2 Heartbeat Failure Handling

```
Agent missed heartbeat:
    1. First miss: log warning
    2. Second miss: log warning, mark agent potentially degraded
    3. Third miss (deadline exceeded):
       a. Publish agent.disconnected
       b. All capabilities → unavailable
       c. For each in-flight task:
          - Policy: cancel and reassign OR wait for reconnect
          - Default: cancel and reassign
```

---

## 7. Retry Backoff

### 7.1 Backoff Implementation

When the Scheduler decides to retry a Task, the Execution Engine handles the timing:

```
schedule_retry(task, delay_ms):
    after delay_ms:
        task.status → ready
        publish task.ready
        // Normal scheduling resumes
```

### 7.2 Backoff Formula

```
delay(base_ms, attempt) = base_ms * (2 ^ attempt) + random(0, base_ms)

Example (base_ms = 1000):
  attempt 0: 1000ms + rand(0, 1000)    = 1000-2000ms
  attempt 1: 2000ms + rand(0, 1000)    = 2000-3000ms
  attempt 2: 4000ms + rand(0, 1000)    = 4000-5000ms
  attempt 3: 8000ms + rand(0, 1000)    = 8000-9000ms
```

---

## 8. Artifact Collection

### 8.1 Small Artifacts

Artifacts under `max_inline_size` (default: 1MB) are stored directly in the Runtime.

### 8.2 Large Artifacts

Artifacts exceeding `max_inline_size`:
- Agent uploads to configured blob storage
- Agent returns `content_ref` (URI) instead of `content`
- Runtime stores the reference

### 8.3 Artifact Validation

```
validate_artifact(artifact, expected_schema):
    if expected_schema is defined:
        validate artifact.content against expected_schema (JSON Schema)
        if invalid: reject, task → failed
        if valid: accept
    else:
        accept
```

---

## 9. Agent Disconnection Recovery

### 9.1 Disconnection Scenario

```
Agent disconnects (crash, network, shutdown):
    │
    ▼
Execution Engine detects (heartbeat timeout or explicit shutdown):
    1. Publish agent.disconnected
    2. Capabilities → unavailable
    3. For each in-flight task from this agent:
       a. Task → timed_out (if timeout not yet exceeded)
       b. Scheduler evaluates retry → task → ready (with new agent)
    4. For each assigned-but-not-started task:
       a. Task → ready (scheduler picks new agent)
```

### 9.2 Agent Reconnection

```
Agent reconnects:
    1. Agent calls register() again
    2. Capabilities → available
    3. Agent resumes heartbeat
    4. Scheduler now considers this Agent for new Tasks
```

---

## 10. Observability

| Metric | Type | Description |
|--------|------|-------------|
| `execution.tasks_dispatched_total` | Counter | Tasks dispatched to Agents |
| `execution.tasks_completed_total` | Counter | Tasks completed successfully |
| `execution.tasks_failed_total` | Counter | Tasks that failed |
| `execution.tasks_timed_out_total` | Counter | Tasks that timed out |
| `execution.tasks_cancelled_total` | Counter | Tasks that were cancelled |
| `execution.in_flight_tasks` | Gauge | Currently executing tasks |
| `execution.dispatch_latency_ms` | Histogram | Time from assignment to Agent acceptance |
| `execution.execution_time_ms` | Histogram | Task execution duration |
| `execution.agents_connected` | Gauge | Number of connected Agents |
| `execution.heartbeat_failures_total` | Counter | Missed heartbeats |

---

## 11. References

- [Architecture Invariants](../architecture/invariants.md) — Invariants 1, 4, 6
- [Domain Model](./domain-model.md) — Task, Agent, Artifact definitions
- [Kernel Boundary](./kernel-boundary.md) — Execution Engine is in Kernel
- [Scheduler](./scheduler.md) — Assignments come from Scheduler
- [Runtime Lifecycle](./runtime-lifecycle.md) — Execution phase in Runtime lifecycle
- [Execution Model](./execution-model.md) — Full execution phases
- [Event Bus](./event-bus.md) — Events published by Execution Engine
