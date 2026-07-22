# Execution Model

> Complete execution model: Goal → Plan → Task Graph → Schedule → Execute → Verify → Complete. Full state machines for Goal, Plan, Task, and Artifact. Failure paths, cancellation, retry, timeout, recovery.

---

## Document Status

| Status  | Author                     | Date       |
|---------|----------------------------|------------|
| Revised | Zelos Architecture Team  | 2026-07-19 |

---

## 1. Overview

The Execution Model is the primary value of the Runtime. It transforms a Goal (a desired outcome) into completed work through a defined sequence of phases. Every phase has a clear owner, defined state transitions, and emitted events.

---

## 2. Execution Phases

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  GOAL    │───→│   PLAN   │───→│  TASK    │───→│ SCHEDULE │───→│ EXECUTE  │───→│  VERIFY  │
│SUBMISSION│    │CREATION  │    │  GRAPH   │    │          │    │          │    │          │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
     │               │               │               │               │               │
     ▼               ▼               ▼               ▼               ▼               ▼
   Goal           Planner          Task            Scheduler      Execution       Verifier
  Accepted       (Plugin)         Graph           (Kernel)        Engine         (Plugin)
                                  Engine                          (Kernel)
                                  (Kernel)
```

---

## 3. Goal State Machine

```
Submitted ──→ Accepted ──→ Planned ──→ Executing ──→ Completed
   │              │            │            │
   └──→ Rejected  │            │            ├──→ Failed
                  └──→ Failed  │            └──→ Cancelled
                               │
                               ├──→ Cancelled
                               └──→ Failed
```

### 3.1 Transition Table

| From | To | Trigger | Owner |
|------|----|---------|-------|
| `submitted` | `accepted` | Validation passes | API Layer |
| `submitted` | `rejected` | Validation fails | API Layer |
| `accepted` | `planned` | Planner produces valid Plan | Runtime + Planner |
| `accepted` | `failed` | Planner fails beyond recovery | Runtime |
| `planned` | `executing` | First Task → `started` | Task Graph Engine |
| `planned` | `cancelled` | Client cancels before execution | API Layer |
| `planned` | `failed` | All Tasks blocked, no recovery | Scheduler |
| `executing` | `completed` | All terminal Tasks → terminal (all completed) | Task Graph Engine |
| `executing` | `failed` | Critical failure, no recovery | Scheduler |
| `executing` | `cancelled` | Client or system cancels | API Layer / Runtime |

### 3.2 Goal Constraints

| Constraint | Enforcement | Violation |
|-----------|-------------|-----------|
| `deadline` | Scheduler checks on each round | Goal → `failed` (timeout) |
| `budget` | Execution Engine tracks cumulative cost | Goal → `failed` (budget) if exceeded |
| `priority` | Scheduler orders Ready tasks by priority | — |

---

## 4. Execution Plan State Machine

```
Created ──→ Validated ──→ Executing ──→ Completed
   │            │              │             │
   │            │              │             └──→ Abandoned
   └──→ Invalid └──→ Abandoned │
                               │
                    Modified ──┘ (returns to Executing)
```

### 4.1 Transition Table

| From | To | Trigger | Owner |
|------|----|---------|-------|
| `created` | `validated` | Plan passes DAG + schema validation | Task Graph Engine |
| `created` | `invalid` | Plan fails validation | Task Graph Engine |
| `validated` | `executing` | Goal → `executing` | Runtime |
| `validated` | `abandoned` | Goal cancelled | Runtime |
| `executing` | `completed` | All Tasks terminal | Task Graph Engine |
| `executing` | `abandoned` | Goal cancelled / failed | Runtime |
| `executing` | `modified` | Planner adds/removes Tasks | Planner + Task Graph Engine |

### 4.2 Plan Modification Protocol

1. Trigger: Task failed beyond retry, or new work discovered
2. Planner invoked: `replan(goal, current_plan, events)`
3. Planner produces modification: added/removed/modified Tasks
4. Task Graph Engine validates: no cycles, valid capabilities, valid dependencies
5. If valid: `plan.modified` event → `plan.version` incremented → Plan returns to `executing`
6. New Tasks: `created` → evaluated → `ready` when dependencies met
7. Removed Tasks: only unstarted Tasks removable

---

## 5. Task State Machine

```
                         ┌──────────┐
                         │ Created  │
                         └────┬─────┘
                              │ dependencies met
                         ┌────▼─────┐
                    ┌───→│  Ready   │←──────────────┐
                    │    └────┬─────┘               │
                    │         │ scheduler assigns   │
                    │    ┌────▼─────┐               │
                    │    │ Assigned │               │
                    │    └────┬─────┘               │
                    │         │ agent accepts       │
                    │    ┌────▼─────┐               │
                    │    │ Started  │               │
                    │    └────┬─────┘               │
                    │         │                     │
                    │    ┌────┼────────────┐        │
                    │    │    │            │        │
                    │    ▼    ▼            ▼        │
                    │ ┌────┐┌──────┐┌──────────┐   │
                    │ │Comp││Failed││TimedOut  │   │
                    │ └──┬─┘└──┬───┘└────┬─────┘   │
                    │    │     │         │         │
                    │    ▼     ▼         ▼         │
                    │ ┌──────────────────────┐     │
                    │ │   Retry Evaluation   │─────┘
                    │ └──────────┬───────────┘
                    │            │ retry exhausted
                    │            ▼
                    │      ┌──────────┐
                    └──────│  Failed  │ (terminal)
                           └──────────┘

                           ┌──────────┐
                           │Completed │ (terminal)
                           └──────────┘
                           ┌──────────┐
                           │Cancelled │ (terminal)
                           └──────────┘
```

### 5.1 Transition Table

| From | To | Trigger | Owner |
|------|----|---------|-------|
| `created` | `ready` | All hard dependencies → `completed` | Task Graph Engine |
| `ready` | `assigned` | Scheduler selects provider | Scheduler |
| `assigned` | `started` | Agent accepts task | Execution Engine |
| `assigned` | `ready` | Agent rejects → re-schedule | Scheduler |
| `started` | `completed` | Agent returns artifact, verification passes | Execution Engine + Verifier |
| `started` | `failed` | Agent returns error | Execution Engine |
| `started` | `timed_out` | Timeout exceeded | Execution Engine |
| `failed` | `ready` | Retry policy allows retry | Scheduler |
| `timed_out` | `ready` | Retry policy allows retry | Scheduler |
| `ready` | `failed` | No Agent provides Capability > 60s (Tier 2 escalation) | Orchestrator |
| `failed` / `timed_out` | `failed` (terminal) | Retry exhausted | Scheduler |
| `*` | `cancelled` | Goal cancelled or explicit cancellation | Execution Engine |

---

## 6. Artifact State Machine

```
Created ──→ Validating ──→ Validated ──→ Accepted
   │            │              │
   │            └──→ Rejected ─┴──→ (Task retry triggers new Task)
   │
   └──→ Accepted (no verifier configured)
```

| From | To | Trigger | Owner |
|------|----|---------|-------|
| `created` | `validating` | Verifier configured for this Task | Runtime |
| `created` | `accepted` | No verifier configured | Runtime |
| `validating` | `validated` | Verifier returns Passed | Verifier |
| `validating` | `rejected` | Verifier returns Failed | Verifier |

---

## 7. Failure Paths

### 7.1 Task Retry Flow

```
Task fails
    │
    ▼
Scheduler evaluates:
    attempt < max_retries?
    ├── Yes → backoff = base_ms * 2^attempt + jitter
    │         Task → Ready (after backoff)
    │         Scheduler may choose different Agent
    │
    └── No  → fallback_capability exists?
              ├── Yes → change required_capability
              │         attempt = 0
              │         Task → Ready
              │
              └── No  → Task → Failed (terminal)
                        Evaluate dependent Tasks
                        Possibly invoke Planner for re-plan
```

### 7.2 Cancellation Flow

```
Cancel signal received (Goal or Task level)
    │
    ▼
Execution Engine:
    ├── In-flight Tasks: send cancel() to Agent
    │   Wait for cancel_ack (timeout: cancel_timeout_ms)
    │   If no ack: force-fail the Task
    │
    ├── Assigned but not started: Task → Cancelled
    │
    ├── Ready: Task → Cancelled
    │
    └── Created (blocked): Task → Cancelled
        Dependents of cancelled Tasks: re-evaluated
```

### 7.3 Timeout Flow

```
Timeout detected (task.timeout_at < now())
    │
    ▼
Execution Engine:
    ├── Task → TimedOut
    ├── Send cancel() to Agent
    └── Scheduler evaluates retry policy
        ├── Retry allowed → Task → Ready
        └── Retry exhausted → Task → Failed (terminal)
```

---

## 8. Three-Tier Escalation for Stuck READY Tasks

When a Task enters READY state but no Agent provides its required Capability, the Orchestrator Loop applies a three-tier escalation strategy. This prevents Goals from hanging indefinitely and enables graceful degradation.

### 8.1 Tier 1: Wait (0–60 seconds)

**Trigger:** Task is READY, Scheduler finds zero matching Agents.

**Behavior:** The Orchestrator records `stuck_since` (first time seen as unschedulable). As long as `stuck_duration < 60 seconds`, the loop continues retrying on each iteration (every 500ms).

**Rationale:** This is the hot-join window. A new Agent with the required Capability may register at any time. The 60-second window provides ample time for:
- An operator to hot-join a missing Agent
- A delayed Agent process to finish starting up
- A recovering Agent to re-register after a crash

**Normal outcome:** Agent becomes available → Task dispatched → everything normal.

### 8.2 Tier 2: Fail (> 60 seconds)

**Trigger:** `stuck_duration > 60 seconds` and still no matching Agent.

**Behavior:** The Orchestrator transitions the Task: `READY → FAILED` with a clear reason:
```
"no agent provides capability: {task.required_capability}"
```

**Rationale:** After 60 seconds, it is unlikely a matching Agent will spontaneously appear. Rather than letting the Goal hang forever, we terminate the Task. This allows:
- The Goal to reach a terminal state (completed or failed)
- Dependent Tasks to be evaluated (a failed prerequisite may still unblock alternatives)
- The system to surface the capability gap to operators

### 8.3 Tier 3: Trigger Planner Re-plan

**Trigger:** Task transitions to FAILED (either from Tier 2 escalation or from Agent execution failure).

**Behavior:** The Orchestrator calls `Planner.replan(goal_description, current_plan, failed_task_events)`. The LLM Planner receives:
- The original Goal description
- The current ExecutionPlan with all Task states
- The failed Task event including the reason

The Planner can then:
- Find alternative capability paths (e.g., `code-generation.rust` → `code-generation.python` + manual translation)
- Add replacement Tasks that use available capabilities
- Adjust the DAG to work around the failed Task

**Phase 1 scope:** Re-plan runs automatically. If the Planner produces valid new Tasks, they are added to the Task Graph.

### 8.4 Escalation State Machine

```
READY Task + No Agent
    │
    ├── stuck < 60s  → Tier 1: keep retrying each loop iteration
    │
    └── stuck > 60s  → Tier 2: Task → FAILED
                           │
                           └── Tier 3: Planner.replan()
                                    ├── Success: new Tasks added to DAG
                                    └── Failure: Goal continues with remaining Tasks
```

### 8.5 Goal Completion After Escalation

When all Tasks reach terminal states (COMPLETED / FAILED / CANCELLED):
- All COMPLETED → Goal → `completed`
- Any FAILED → Goal → `failed`
- All CANCELLED → Goal → `cancelled`

This guarantees Goals never hang indefinitely — the 60-second escalation window bounds the maximum idle time.

---

## 9. Concurrency Model

| Limit | Scope | Default | Enforced By |
|-------|-------|---------|------------|
| Max concurrent Tasks per Goal | Per Goal | 10 | Scheduler |
| Max concurrent Tasks per Agent | Per Agent | Agent declares | Scheduler |
| Max concurrent Tasks (global) | Runtime | 100 | Scheduler |

Ready Tasks beyond limits are queued. Dispatched as slots free.

---

## 10. Dynamic Plan Modification

### 9.1 Triggers

| Trigger | Action |
|---------|--------|
| Task failed beyond retry, blocking dependents | Planner adds alternative/replacement Tasks |
| Artifact reveals additional work needed | Planner adds new Tasks |
| Budget approaching limit | Planner may simplify or remove low-priority Tasks |
| Policy change during execution | Planner adjusts Plan to comply |

### 9.2 Modification Constraints

- Cannot modify in-flight (`started`) Tasks
- Cannot add dependency TO a completed Task (causality violation)
- Cannot remove hard dependency on a completed Task
- Must maintain DAG acyclicity

---

## 11. References

- [Architecture Invariants](../architecture/invariants.md) — Invariants 1-5, 7, 8, 12
- [Domain Model](./domain-model.md) — Entity definitions
- [Runtime Lifecycle](./runtime-lifecycle.md) — Startup to shutdown
- [Task Graph](./task-graph.md) — Task state machine and DAG
- [Scheduler](./scheduler.md) — Scheduling and retry
- [Execution Engine](./execution-engine.md) — Dispatch and monitoring
- [Event Bus](./event-bus.md) — All events flow through here
