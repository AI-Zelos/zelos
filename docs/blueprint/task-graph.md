# Task Graph

> Task Graph Engine: state machine, dependency resolution, DAG validation, dynamic modification, failure propagation.

---

## Document Status

| Status  | Author                     | Date       |
|---------|----------------------------|------------|
| Updated | Zelos Architecture Team  | 2026-07-19 |

---

## 1. Overview

The Task Graph is the Runtime's internal representation of work — a directed acyclic graph (DAG) where nodes are Tasks and edges are Dependencies. Managed by the Task Graph Engine, a Kernel component.

### 1.1 Purpose

- Know what work exists and its state
- Determine which Tasks are ready (dependencies satisfied)
- Handle failure propagation
- Support dynamic modification
- Provide progress visibility

### 1.2 Position

```
Execution Plan (Planner output)
       │
       ▼
┌──────────────────┐
│ TASK GRAPH ENGINE │  ← Kernel
│                  │
│ • State machine  │
│ • DAG validation │
│ • Dependency res │
│ • Progress query │
└────────┬─────────┘
         │
         ├──→ Scheduler (ready_tasks)
         ├──→ Observability (progress)
         └──→ Event Bus (task.* events)
```

---

## 2. Graph Structure

```
TaskGraph = (V, E)
  V = {Task | status ∈ {created, ready, assigned, started, completed, failed, cancelled, timed_out}}
  E = {Dependency | from ∈ V, to ∈ V}
  
  Invariant: Graph must remain acyclic.
```

### 2.1 Node: Task

See [Domain Model: Task](./domain-model.md#23-task) for full definition.

### 2.2 Edge: Dependency

```
Dependency {
    from_task_id: UUID    // Must complete first
    to_task_id: UUID      // Waits for 'from'
    type: "hard" | "soft"
    data_required: bool   // Does 'to' need 'from's Artifact?
}
```

---

## 3. Task State Machine

```
                     ┌──────────┐
                     │ Created  │
                     └────┬─────┘
                          │ dependencies_met()
                     ┌────▼─────┐
                ┌───→│  Ready   │←──────────────┐
                │    └────┬─────┘               │
                │         │ scheduler.assign()  │
                │    ┌────▼─────┐               │
                │    │ Assigned │               │
                │    └────┬─────┘               │
                │         │ agent.accepts()     │
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
                │            │ retry_exhausted
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

### 3.1 Transition Table

| From | To | Trigger | Owner |
|------|----|---------|-------|
| `created` | `ready` | All hard dependencies → `completed` | Task Graph Engine |
| `ready` | `assigned` | Scheduler selects provider | Scheduler |
| `assigned` | `started` | Agent accepts | Execution Engine |
| `assigned` | `ready` | Agent rejects → re-schedule | Scheduler |
| `started` | `completed` | Artifact returned, verification passed | Execution Engine + Verifier |
| `started` | `failed` | Agent error | Execution Engine |
| `started` | `timed_out` | Timeout exceeded | Execution Engine |
| `failed` → `ready` | Retry allowed | Scheduler |
| `timed_out` → `ready` | Retry allowed | Scheduler |
| `failed`/`timed_out` → `failed` | Retry exhausted | Scheduler |
| `*` → `cancelled` | Goal cancelled or explicit | Execution Engine |

---

## 4. Dependency Resolution

```
evaluate_dependencies(task, graph):
    for dep_id in task.dependencies:
        dep = graph.get(dep_id)
        if dep.status != COMPLETED:
            return BLOCKED
    return READY
```

Phase 1: Hard dependencies only. Future: soft (preference), conditional (runtime evaluation).

### Acyclicity Enforcement

Before adding any edge, cycle detection runs. If a cycle would be created, the edge is rejected.

---

## 5. Failure Propagation

When a Task fails and retry is exhausted:

- `task.status = FAILED`
- For each dependent with hard dependency: status → BLOCKED (does not auto-fail)
- Runtime may re-plan: Planner invoked, Plan modified, replacement Tasks added
- If no re-plan: blocked dependents also fail (cascading)

---

## 6. Dynamic Graph Modification

| Operation | Constraint |
|-----------|-----------|
| Add Task | New Task evaluated; becomes Ready when deps met |
| Remove Task | Only unstarted Tasks removable |
| Modify Task | Cannot modify in-flight (`started`) Tasks |
| Add Dependency | Cannot add dependency to completed Task |
| Remove Dependency | Cannot remove hard dep on completed Task |
| All | Must maintain acyclicity |

---

## 7. References

- [Architecture Invariants](../architecture/invariants.md) — Invariants 3, 4
- [Domain Model](./domain-model.md) — Task entity
- [Kernel Boundary](./kernel-boundary.md) — Task Graph Engine is in Kernel
- [Execution Model](./execution-model.md) — Full execution phases
- [Scheduler](./scheduler.md) — Consumer of ready Tasks
- [Schema: Task](../schema/task.json)
- [Schema: Execution Plan](../schema/execution-plan.json)
