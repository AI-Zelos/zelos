# Event Bus

> Complete Event Bus specification: event taxonomy, ordering guarantees, delivery semantics, idempotency, correlation, causation, replay, persistence.

---

## Document Status

| Status  | Author                     | Date       |
|---------|----------------------------|------------|
| New     | Zelos Architecture Team  | 2026-07-19 |

---

## 1. Overview

The Event Bus is the central nervous system of Zelos. Every inter-component communication flows through events. No component calls another directly. [Invariant 9](../architecture/invariants.md#invariant-9-contracts-over-implementation).

### 1.1 Position

```
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│ SCHEDULER│  │EXEC ENGINE│ │CAPABILITY│  │TASK GRAPH│
│          │  │           │ │ REGISTRY │  │  ENGINE  │
└────┬─────┘  └─────┬─────┘ └────┬─────┘ └────┬─────┘
     │              │            │             │
     └──────────────┼────────────┼─────────────┘
                    │            │
              ┌─────▼────────────▼─────────┐
              │         EVENT BUS          │
              │                            │
              │  Publish / Subscribe       │
              │  Persist / Replay          │
              └────────────┬───────────────┘
                           │
                    ┌──────▼──────┐
                    │ EVENT STORE │ (append-only log)
                    └─────────────┘
```

---

## 2. Event Structure

```
Event {
    event_id: UUID              // Globally unique
    event_type: String          // domain.entity.action
    source: String              // Publishing component identifier
    timestamp: RFC3339          // Publication time
    correlation_id: UUID        // Groups related events (e.g., same Task)
    causation_id: UUID?         // Event that directly caused this one
    data_version: String        // Schema version of payload
    payload: Object             // Type-specific event data
    metadata: {
        trace_id: String        // OpenTelemetry trace ID
        span_id: String         // OpenTelemetry span ID
    }
}
```

### 2.1 Immutability

**Invariant**: [Invariant 7](../architecture/invariants.md#invariant-7-events-are-immutable). Events are append-only. Never modified. Never deleted.

**Correction pattern:** If an incorrect event was published, publish a corrective event.

---

## 3. Event Taxonomy

### 3.1 Naming Convention

```
{domain}.{entity}.{action}

Domains: runtime | goal | plan | task | agent | capability | artifact | verification | policy | plugin
```

### 3.2 Complete Event Catalog

#### Runtime Domain

| Event Type | Description |
|-----------|-------------|
| `runtime.started` | Runtime entered RUNNING state |
| `runtime.degraded` | Runtime entered DEGRADED state |
| `runtime.recovered` | Runtime returned to RUNNING from DEGRADED |
| `runtime.shutting_down` | Shutdown initiated |
| `runtime.stopped` | Runtime stopped |

#### Goal Domain

| Event Type | Description |
|-----------|-------------|
| `goal.submitted` | Goal received by Runtime |
| `goal.accepted` | Goal validation passed |
| `goal.rejected` | Goal validation failed |
| `goal.planned` | Execution Plan created and validated |
| `goal.executing` | First Task dispatched |
| `goal.completed` | All Tasks completed successfully |
| `goal.failed` | Execution failed beyond recovery |
| `goal.cancelled` | Goal cancelled |

#### Plan Domain

| Event Type | Description |
|-----------|-------------|
| `plan.created` | Planner produced Execution Plan |
| `plan.validated` | Plan passed validation |
| `plan.invalid` | Plan failed validation |
| `plan.executing` | Plan is the active source of truth |
| `plan.modified` | Plan was updated during execution |
| `plan.completed` | All Tasks terminal |
| `plan.abandoned` | Goal cancelled or failed |

#### Task Domain

| Event Type | Description |
|-----------|-------------|
| `task.created` | Task exists in Task Graph |
| `task.ready` | All dependencies satisfied |
| `task.assigned` | Scheduler selected an Agent |
| `task.started` | Agent accepted and began execution |
| `task.completed` | Agent returned artifact, verification passed |
| `task.failed` | Task failed after retry exhaustion, or Agent error |
| `task.cancelled` | Task cancelled |
| `task.timed_out` | Timeout exceeded |

#### Agent Domain

| Event Type | Description |
|-----------|-------------|
| `agent.registered` | Agent registered capabilities |
| `agent.connected` | Agent connection established |
| `agent.disconnected` | Agent connection lost |
| `agent.heartbeat` | Heartbeat received |

#### Capability Domain

| Event Type | Description |
|-----------|-------------|
| `capability.registered` | Capability declared by Agent |
| `capability.available` | Agent connected, capability is available |
| `capability.unavailable` | Agent disconnected |
| `capability.deprecated` | Capability flagged for removal |
| `capability.removed` | Capability no longer available |

#### Artifact Domain

| Event Type | Description |
|-----------|-------------|
| `artifact.created` | Agent produced an Artifact |
| `artifact.validated` | Verifier passed the Artifact |
| `artifact.rejected` | Verifier rejected the Artifact |

#### Verification Domain

| Event Type | Description |
|-----------|-------------|
| `verification.requested` | Verifier invoked |
| `verification.completed` | Verifier returned verdict |
| `verification.needs_review` | Verdict is `needs_review` — human intervention required |

#### Plugin Domain

| Event Type | Description |
|-----------|-------------|
| `plugin.loaded` | Plugin code loaded |
| `plugin.configured` | Plugin configuration applied |
| `plugin.initialized` | Plugin resources initialized |
| `plugin.started` | Plugin entered RUNNING |
| `plugin.failed` | Plugin entered ERROR |
| `plugin.recovered` | Plugin returned to RUNNING |
| `plugin.stopped` | Plugin entered STOPPED |

---

## 4. Ordering Guarantees

| Scope | Guarantee |
|-------|-----------|
| Per event type | **Total order** — events of the same type are ordered by publication time |
| Per correlation ID | **Causal order** — events with the same correlation_id respect happens-before |
| Per entity (e.g., same task_id) | **Total order** — all events for one task are ordered |
| Across types | **No guarantee** — do not rely on inter-type ordering |

---

## 5. Delivery Semantics

### 5.1 Phase 1: At-Least-Once

- Events are delivered to all matching subscribers
- If a subscriber fails, the event is redelivered
- **Subscribers must be idempotent** — they must handle duplicate events safely

### 5.2 Idempotency

Subscribers achieve idempotency by:

```
handle(event):
    if already_processed(event.event_id):
        return  // Skip duplicate
    process(event)
    mark_processed(event.event_id)
```

The `event_id` is the idempotency key.

### 5.3 Future: Delivery Options

| Semantic | Description | Phase |
|----------|-------------|-------|
| At-least-once | Default, idempotent handlers required | Phase 1 |
| At-most-once | Fire and forget, no redelivery | Phase 3 |
| Exactly-once | Transactional produce + consume | Phase 3 (if needed) |

---

## 6. Correlation and Causation

### 6.1 Correlation ID

All events related to the same entity share a `correlation_id`:

```
Goal A submitted:
  goal.submitted         (correlation_id = G1)
  goal.accepted          (correlation_id = G1)
  plan.created           (correlation_id = P1)
  task.created (T1)      (correlation_id = T1)
  task.created (T2)      (correlation_id = T2)
  task.ready (T1)        (correlation_id = T1)
  task.started (T1)      (correlation_id = T1)
  task.completed (T1)    (correlation_id = T1)
  task.ready (T2)        (correlation_id = T2)
  ...
```

### 6.2 Causation Chain

```
task.created (event_id = E1)
  →
task.ready (event_id = E2, causation_id = E1)
  →
task.assigned (event_id = E3, causation_id = E2)
  →
task.started (event_id = E4, causation_id = E3)
  →
task.completed (event_id = E5, causation_id = E4)
```

The causation chain enables debugging: "What happened and why?"

---

## 7. Subscription Model

### 7.1 Subscription Types

```
EventBus {
    // Exact type subscription
    subscribe(event_type: "task.completed", handler) → Subscription
    
    // Pattern subscription
    subscribe_pattern("task.*", handler) → Subscription
    subscribe_pattern("*.failed", handler) → Subscription
    
    // Correlation subscription
    subscribe_correlation(correlation_id, handler) → Subscription
}
```

### 7.2 Handler Contract

```
EventHandler = (event: Event) → HandlerResult

HandlerResult = 
    | Ack       // Event processed successfully
    | Retry     // Processing failed, redeliver
    | Skip      // Event not applicable, don't redeliver
```

---

## 8. Event Persistence

### 8.1 Event Store

All events are appended to the Event Store:

```
Position | event_id | event_type           | correlation_id | timestamp
---------|----------|---------------------|----------------|----------
0        | E1       | runtime.started      | —              | ...
1        | E2       | agent.registered     | A1             | ...
2        | E3       | goal.submitted       | G1             | ...
3        | E4       | goal.accepted        | G1             | ...
4        | E5       | plan.created         | P1             | ...
...
```

### 8.2 Replay

The Event Store supports replay for state reconstruction:

```
// Replay from position
replay(from_position: 0, handler)

// Replay from timestamp
replay_from(ts: "2026-07-19T00:00:00Z", handler)

// Replay for correlation
replay_correlation(correlation_id: G1, handler)
```

Replay is used for:
- Crash recovery: reconstruct state from persisted events
- Debugging: replay a Goal's execution
- New subscriber catch-up: subscriber starts mid-stream, replays to catch up

### 8.3 Event Payload Schemas

Each event type carries a typed `payload` object. The `event.json` schema defines the envelope; this section defines the payload types for core Phase 1 events.

#### 8.3.1 Runtime Domain

```
runtime.started:
  runtime_version: String
  started_at: Timestamp

runtime.stopping:
  reason: "shutdown" | "restart" | "error"
  initiated_by: "admin" | "signal" | "internal"

runtime.stopped:
  uptime_seconds: Float
  reason: String
```

#### 8.3.2 Goal Domain

```
goal.submitted:
  goal_id: UUID
  description: String
  constraints?: { budget?, deadline?, priority? }

goal.accepted:
  goal_id: UUID

goal.rejected:
  goal_id: UUID
  reason: String
  validation_errors: [String]

goal.planned:
  goal_id: UUID
  plan_id: UUID

goal.executing:
  goal_id: UUID
  plan_id: UUID

goal.completed:
  goal_id: UUID
  plan_id: UUID
  completed_at: Timestamp

goal.failed:
  goal_id: UUID
  plan_id: UUID?
  reason: String
  failed_at: Timestamp

goal.cancelled:
  goal_id: UUID
  plan_id: UUID?
  cancelled_at: Timestamp
```

#### 8.3.3 Plan Domain

```
plan.created:
  plan_id: UUID
  goal_id: UUID
  task_count: Int
  planner_id: String
  planner_version: String

plan.validated:
  plan_id: UUID
  goal_id: UUID

plan.invalid:
  plan_id: UUID
  goal_id: UUID
  validation_errors: [String]

plan.executing:
  plan_id: UUID
  goal_id: UUID

plan.modified:
  plan_id: UUID
  goal_id: UUID
  version: Int                  // New revision number
  changes: { added_tasks: Int, removed_tasks: Int, modified_tasks: Int }

plan.completed:
  plan_id: UUID
  goal_id: UUID

plan.abandoned:
  plan_id: UUID
  goal_id: UUID
  reason: "goal_cancelled" | "goal_failed" | "replanned"
```

#### 8.3.4 Task Domain

```
task.created:
  task_id: UUID
  plan_id: UUID
  required_capability: String
  dependencies: [UUID]

task.ready:
  task_id: UUID
  plan_id: UUID

task.assigned:
  task_id: UUID
  plan_id: UUID
  agent_id: UUID
  agent_name: String

task.started:
  task_id: UUID
  plan_id: UUID
  agent_id: UUID

task.completed:
  task_id: UUID
  plan_id: UUID
  agent_id: UUID
  artifact_id: UUID
  verification_status: String
  execution_time_ms: Int
  cost?: { amount: Float, currency: String }

task.failed:
  task_id: UUID
  plan_id: UUID
  agent_id: UUID
  attempt: Int
  error_code: String
  error_message: String

task.timed_out:
  task_id: UUID
  plan_id: UUID
  agent_id: UUID
  timeout_ms: Int

task.cancelled:
  task_id: UUID
  plan_id: UUID
  reason: "goal_cancelled" | "explicit" | "dependency_failed"
```

#### 8.3.5 Agent Domain

```
agent.registered:
  agent_id: UUID
  name: String
  capabilities: [{ name: String, version: String }]
  protocol: String
  protocol_version: String

agent.connected:
  agent_id: UUID
  name: String

agent.heartbeating:
  agent_id: UUID
  operational_state: "idle" | "busy"
  current_tasks: Int

agent.disconnected:
  agent_id: UUID
  name: String
  reason: "heartbeat_lost" | "explicit_shutdown" | "error"

agent.shutdown:
  agent_id: UUID
  name: String
```

#### 8.3.6 Capability Domain

```
capability.registered:
  name: String
  version: String
  agent_id: UUID
  agent_name: String

capability.available:
  name: String
  version: String
  agent_id: UUID

capability.unavailable:
  name: String
  version: String
  agent_id: UUID
  reason: "agent_disconnected" | "deprecated" | "removed"
```

#### 8.3.7 Artifact Domain

```
artifact.created:
  artifact_id: UUID
  task_id: UUID
  agent_id: UUID
  content_type: String
  size_bytes: Int

artifact.validated:
  artifact_id: UUID
  task_id: UUID
  verdict: "passed"

artifact.rejected:
  artifact_id: UUID
  task_id: UUID
  verdict: "failed" | "needs_review"
  issues: [{ severity: String, message: String }]

artifact.accepted:
  artifact_id: UUID
  task_id: UUID
```

#### 8.3.8 Verification Domain

```
verification.requested:
  artifact_id: UUID
  task_id: UUID
  verifier_id: String
  criteria: Object

verification.completed:
  artifact_id: UUID
  task_id: UUID
  verifier_id: String
  verdict: "passed" | "failed" | "needs_review"
  score?: Float
  issues?: [{ severity: String, message: String }]
```

#### 8.3.9 Plugin Domain

```
plugin.loaded:
  plugin_id: String
  plugin_type: String
  version: String

plugin.configured:
  plugin_id: String

plugin.initialized:
  plugin_id: String

plugin.started:
  plugin_id: String

plugin.failed:
  plugin_id: String
  error: String

plugin.recovered:
  plugin_id: String

plugin.stopped:
  plugin_id: String
```

---


---

## 9. Phase 1 Simplifications

| Aspect | Phase 1 | Future |
|--------|---------|--------|
| Transport | In-process function calls | Network (gRPC streaming, Kafka) |
| Persistence | In-memory ring buffer | Disk-backed append-only log |
| Delivery | At-least-once, in-process (no network failure) | Distributed delivery |
| Replay | Full replay from memory | Snapshots + incremental replay |
| Subscriber isolation | Same process | Separate processes/containers |

---

## 10. References

- [Architecture Invariants](../architecture/invariants.md) — Invariants 7, 9
- [Domain Model](./domain-model.md) — Event entity definition
- [Kernel Boundary](./kernel-boundary.md) — Event Bus is in Kernel
- [Runtime Lifecycle](./runtime-lifecycle.md) — Events during startup/shutdown
- [Execution Model](./execution-model.md) — Events during execution
- [RFC-0003](../rfc/rfc-0003-event-bus-specification.md) — Event Bus RFC
- [Schema: Event](../schema/event.json)
