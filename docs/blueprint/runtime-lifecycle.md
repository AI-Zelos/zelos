# Runtime Lifecycle

> Complete Runtime lifecycle: startup, plugin discovery, agent registration, goal execution, shutdown, and recovery. Every step, every event, every state change, every owner.

---

## Document Status

| Status  | Author                     | Date       |
|---------|----------------------------|------------|
| Revised | Zelos Architecture Team  | 2026-07-19 |

---

## 1. Runtime State Machine

```
                  ┌──────────┐
                  │ STOPPED  │
                  └────┬─────┘
                       │ start()
                  ┌────▼─────┐
                  │ STARTING │
                  └────┬─────┘
                       │ all components ready
                  ┌────▼─────┐
         ┌───────→│ RUNNING  │←─────────┐
         │        └────┬─────┘          │
         │             │                │
   plugin_failed  internal_error   shutdown()
         │             │                │
   ┌─────▼─────┐  ┌───▼──────┐   ┌─────▼─────┐
   │ DEGRADED  │  │ STOPPING │   │ STOPPING  │
   └─────┬─────┘  └───┬──────┘   └─────┬─────┘
         │             │                │
   plugin_restored  all_stopped    all_stopped
         │             │                │
         └─────────────┘                │
                       │                │
                  ┌────▼─────┐          │
                  │ STOPPED  │←─────────┘
                  └──────────┘
```

| State | Description |
|-------|-------------|
| `STOPPED` | Runtime is not running |
| `STARTING` | Initializing layers in order |
| `RUNNING` | All components healthy, accepting Goals |
| `DEGRADED` | Running but one or more plugins unhealthy |
| `STOPPING` | Graceful shutdown in progress |

---

## 2. Startup Sequence

### Phase 1: Infrastructure Layer (L1)

| Step | Action | Owner | Event Published |
|------|--------|-------|----------------|
| 1 | Initialize Event Store | Storage Backend | — |
| 2 | Initialize State Store | Storage Backend | — |
| 3 | Initialize Metrics Exporter | Infrastructure | — |
| 4 | Initialize Tracing Exporter | Infrastructure | — |
| 5 | Validate L1 readiness | Runtime | — |

**Failure:** Any L1 failure → Fatal. Runtime cannot start.

### Phase 2: Kernel Layer (L2)

| Step | Action | Owner | Event Published |
|------|--------|-------|----------------|
| 6 | Initialize Event Bus | Event Bus | — |
| 7 | Initialize Plugin Lifecycle Manager | PLM | — |
| 8 | Initialize Capability Registry | Capability Registry | — |
| 9 | Initialize Task Graph Engine | Task Graph Engine | — |
| 10 | Initialize Scheduler | Scheduler | — |
| 11 | Initialize Execution Engine | Execution Engine | — |
| 12 | Validate L2 readiness | Runtime | — |

**Failure:** Any L2 failure → Fatal.

### Phase 3: Plugin Discovery and Load

| Step | Action | Owner | Event Published |
|------|--------|-------|----------------|
| 13 | Discover plugins from configuration | PLM | — |
| 14 | Resolve plugin dependencies (topological sort) | PLM | — |
| 15 | Load Storage Backend plugins | PLM | `plugin.loaded` |
| 16 | Load Memory Provider plugins | PLM | `plugin.loaded` |
| 17 | Configure each plugin | PLM | `plugin.configured` |
| 18 | Initialize each plugin | PLM | `plugin.initialized` |
| 19 | Start plugins in dependency order | PLM | `plugin.started` |

**Failure:** Planner failure → Fatal. Other plugin failures → DEGRADED.

### Phase 4: API Layer (L4)

| Step | Action | Owner | Event Published |
|------|--------|-------|----------------|
| 20 | Initialize Goal API | API Layer | — |
| 21 | Initialize Plan API | API Layer | — |
| 22 | Initialize Agent API | API Layer | — |
| 23 | Initialize Admin API | API Layer | — |

### Phase 5: Protocol Layer (L5)

| Step | Action | Owner | Event Published |
|------|--------|-------|----------------|
| 24 | Start HTTP Adapter | HTTP Adapter | `plugin.started` |
| 25 | Start gRPC Adapter (if configured) | gRPC Adapter | `plugin.started` |
| 26 | Start other adapters | Respective adapters | `plugin.started` |

### Phase 6: Ready

| Step | Action | Owner | Event Published |
|------|--------|-------|----------------|
| 27 | All layers validated | Runtime | `runtime.started` |
| 28 | Runtime enters RUNNING | Runtime | — |

---

## 3. Agent Registration

Occurs anytime after Runtime enters RUNNING.

| Step | Action | Owner | Event Published |
|------|--------|-------|----------------|
| 1 | Agent connects to Runtime API | Agent (initiates) | — |
| 2 | Agent calls `register(capabilities)` | Agent | — |
| 3 | Runtime validates capabilities (schemas, naming) | Capability Registry | — |
| 4 | Runtime assigns `agent_id` | Capability Registry | — |
| 5 | Runtime indexes capabilities | Capability Registry | `capability.registered` |
| 6 | Registration response sent | Capability Registry | — |
| 7 | Agent begins heartbeat loop | Agent | — |
| 8 | Agent marked as `connected` | Execution Engine | `agent.connected` |
| 9 | First heartbeat received | Execution Engine | `agent.heartbeat` |
| 10 | Agent state → `heartbeating` | Execution Engine | — |
| 11 | Capabilities → `available` | Capability Registry | `capability.available` |
| 12 | Agent eligible for Task dispatch | Scheduler | — |

---

## 4. Goal Submission and Execution

### 4.1 Goal Submission

| Step | Action | Owner | Event Published |
|------|--------|-------|----------------|
| 1 | Client submits Goal via API | API Layer | — |
| 2 | Validate Goal (description, constraints, auth) | API Layer | — |
| 3 | Assign `goal_id` | Runtime | `goal.submitted` |
| 4 | Goal state → `accepted` | Runtime | `goal.accepted` |

**If validation fails:** `goal.rejected` published. Goal terminal.

### 4.2 Plan Creation

| Step | Action | Owner | Event Published |
|------|--------|-------|----------------|
| 5 | Runtime invokes Planner | Scheduler / Goal handler | — |
| 6 | Planner produces Execution Plan | Planner | — |
| 7 | Runtime validates Plan (DAG, schemas, capabilities) | Task Graph Engine | — |
| 8 | Plan state → `validated` | Runtime | `plan.created`, `plan.validated` |
| 9 | Task Graph created from Plan | Task Graph Engine | `task.created` (per Task) |
| 10 | Initial dependency evaluation | Task Graph Engine | `task.ready` (for unblocked Tasks) |
| 11 | Goal state → `planned` | Runtime | `goal.planned` |

**If plan validation fails:** `plan.invalid` published. Planner may retry or Goal → `failed`.

### 4.3 Task Execution Loop

For each Ready Task:

| Step | Action | Owner | Event Published |
|------|--------|-------|----------------|
| 12 | Scheduler queries Capability Registry | Scheduler | — |
| 13 | Scheduler filters and scores providers | Scheduler | — |
| 14 | Scheduler applies Policy evaluation | Scheduler → Policy | — |
| 15 | Scheduler selects best provider | Scheduler | — |
| 16 | Task state → `assigned` | Task Graph Engine | `task.assigned` |
| 17 | Execution Engine dispatches Task to Agent | Execution Engine | — |
| 18 | Agent accepts and begins execution | Agent | `task.started` |
| 19 | Goal state → `executing` (on first Task) | Runtime | `goal.executing` |
| 20 | Agent executes, produces Artifact | Agent | — |
| 21 | Artifact received by Runtime | Execution Engine | `artifact.created` |

### 4.4 Verification (Optional)

| Step | Action | Owner | Event Published |
|------|--------|-------|----------------|
| 22 | Runtime checks if verification required | Runtime | — |
| 23 | Runtime invokes Verifier | Runtime | `verification.requested` |
| 24 | Verifier produces Verdict | Verifier | `verification.completed` |
| 25 | If Passed: Artifact → `accepted`, Task → `completed` | Runtime | `task.completed` |
| 26 | If Failed: evaluate retry policy | Scheduler | `artifact.rejected` |
| 27 | If no verifier: Artifact → `accepted`, Task → `completed` | Runtime | `task.completed` |
| 28 | Dependent Tasks evaluated (may become Ready) | Task Graph Engine | `task.ready` |

### 4.5 Completion

| Step | Action | Owner | Event Published |
|------|--------|-------|----------------|
| 29 | All terminal Tasks in terminal state | Task Graph Engine | — |
| 30 | Goal state → `completed` or `failed` | Runtime | `goal.completed` / `goal.failed` |
| 31 | Final Artifacts assembled | Runtime | — |
| 32 | Goal reached terminal state | Runtime | `goal.completed` / `goal.failed` |

---

## 5. Failure and Recovery

### 5.1 Task Failure

| Step | Action | Owner | Event Published |
|------|--------|-------|----------------|
| 1 | Agent returns error or times out | Agent / Execution Engine | `task.failed` / `task.timed_out` |
| 2 | Scheduler evaluates retry policy | Scheduler | — |
| 3a | Retry: backoff → Task → `ready` | Task Graph Engine | `task.ready` |
| 3b | Fallback: change capability → Task → `ready` | Scheduler | — |
| 3c | Exhausted: Task → `failed` (terminal) | Task Graph Engine | — |
| 4 | Dependent Tasks evaluated | Task Graph Engine | — |
| 5 | If blocked dependents → Planner invoked for re-plan | Scheduler | `plan.modified` |

### 5.2 Agent Disconnection

| Step | Action | Owner | Event Published |
|------|--------|-------|----------------|
| 1 | Heartbeat timeout detected | Execution Engine | `agent.disconnected` |
| 2 | Agent capabilities → `unavailable` | Capability Registry | `capability.unavailable` |
| 3 | In-flight Tasks: cancel and reassign or wait (policy) | Execution Engine, Scheduler | `task.cancelled` + `task.ready` |
| 4 | Ready Tasks waiting for this Agent's capabilities: re-evaluate | Scheduler | — |

### 5.3 Runtime Crash Recovery

| Step | Action | Owner |
|------|--------|-------|
| 1 | Runtime restarts | Runtime |
| 2 | Infrastructure layer starts | Infrastructure |
| 3 | Replay Event Store from last snapshot | Event Bus + Storage Backend |
| 4 | Reconstruct Capability Registry state | Capability Registry |
| 5 | Reconstruct Task Graph state | Task Graph Engine |
| 6 | Agents detect connection loss and reconnect | Agents |
| 7 | Agent re-registration restores capabilities | Capability Registry |
| 8 | In-flight Tasks at crash time: Agent will timeout → `task.failed` | Execution Engine |
| 9 | Scheduler evaluates retry for any failed Tasks | Scheduler |
| 10 | Execution resumes | Runtime |

---

## 6. Shutdown Sequence

| Step | Action | Owner | Event Published |
|------|--------|-------|----------------|
| 1 | Stop accepting new Goals (API returns 503) | API Layer | — |
| 2 | Publish shutdown intent | Runtime | `runtime.shutting_down` |
| 3 | Cancel in-flight Goals or wait (per policy) | Execution Engine | `goal.cancelled` (if cancelling) |
| 4 | Send cancel to all Agents with in-flight Tasks | Execution Engine | `task.cancelled` |
| 5 | Wait for Agent acknowledgements (timeout: 30s) | Execution Engine | — |
| 6 | Stop Plugin Layer: Planner, Verifiers, Policies | PLM | `plugin.stopped` |
| 7 | Stop Memory Providers (final flush) | PLM | `plugin.stopped` |
| 8 | Stop Protocol Layer: drain connections, stop adapters | PLM | — |
| 9 | Stop API Layer | API Layer | — |
| 10 | Stop Kernel Layer: Scheduler, Execution Engine | Kernel | — |
| 11 | Flush Task Graph and Capability Registry state | Storage Backend | — |
| 12 | Stop Event Bus | Event Bus | — |
| 13 | Stop Infrastructure Layer: final metrics export | Infrastructure | — |
| 14 | Runtime → `STOPPED` | Runtime | `runtime.stopped` |

**Force shutdown:** If graceful shutdown exceeds timeout (60s), abandon in-flight work and terminate.

---

## 7. References

- [Architecture Invariants](../architecture/invariants.md) — Invariants 1, 7, 12
- [Domain Model](./domain-model.md) — Entity definitions
- [Kernel Boundary](./kernel-boundary.md) — What is in Kernel
- [Execution Model](./execution-model.md) — Execution phases in detail
- [Scheduler](./scheduler.md) — Scheduling details
- [Execution Engine](./execution-engine.md) — Dispatch details
- [Event Bus](./event-bus.md) — Event system
- [Plugin Architecture](./plugin-architecture.md) — Plugin lifecycle
- [Protocol Layer](./protocol-layer.md) — Protocol adapters
