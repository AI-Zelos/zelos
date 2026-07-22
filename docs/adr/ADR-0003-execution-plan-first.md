# ADR-0003: Execution Plan First

| Status       | Decided |
|--------------|---------|
| **Date**     | 2026-07-19 |
| **Deciders** | Zelos Architecture Team |
| **Depends On** | [ADR-0001](./ADR-0001-runtime-first.md), [ADR-0002](./ADR-0002-capability-first.md) |

---

## Context

When a Goal is submitted, what determines the work to be done? Two approaches:

1. **Reactive Execution**: Agents pull work from a queue. The execution path emerges from agent decisions. No global view.
2. **Plan-First Execution**: A Planner decomposes the Goal into a structured Execution Plan before any Agent is invoked.

Reactive execution is simple but fails at scale: no global optimization, no progress visibility, no completeness guarantee. For complex multi-agent goals, a plan is required.

### Relevant Invariants

- [Invariant 2](../architecture/invariants.md#invariant-2-goal-is-the-first-class-abstraction)
- [Invariant 3](../architecture/invariants.md#invariant-3-execution-plan-is-the-single-source-of-truth)
- [Invariant 4](../architecture/invariants.md#invariant-4-task-is-atomic)

---

## Decision

Zelos requires an **Execution Plan** before any Agent is invoked.

**Execution Plan**: A structured specification containing Tasks, Dependencies, Capability Requirements, Constraints, and Expected Artifacts. Produced by a Planner plugin.

**Planner is a Plugin** — not in the Kernel. Different planners exist for different goal types. The Runtime only cares about the plan output; how it was produced is opaque.

**Dynamic modification**: The Plan is not immutable. It can be modified during execution (Task failure, new information, budget changes) but only through a governed modification protocol.

---

## Consequences

### Positive

- Predictability — Runtime knows all work before starting
- Global optimization — Scheduler can optimize task order and parallelism
- Observability — progress = completed / total tasks
- Governance — Plan can be inspected and approved before execution
- Planner independence — swap planning strategy without affecting execution

### Negative

- Upfront latency — plan generation before any work begins
- Plan brittleness — rigid plans may not adapt well
- Planner quality dependency — poor planner = poor execution
- Overspecification — plans too detailed for simple goals

### Mitigations

- Streaming planning (dispatch tasks as soon as they're ready)
- Dynamic plan modification during execution
- Multiple planner implementations for different goal complexities
- Template-based planners for simple goals (near-zero latency)

---

## Alternatives Considered

### A1: Reactive Execution (No Plan)

Agents pull from a priority queue. An external orchestrator component adds tasks as needed.

**Rejected**: No global view. Cannot optimize. Cannot verify completeness. Debugging is tracing emergent behavior.

### A2: Plan as Suggestion

Planner suggests; agents can deviate.

**Rejected**: Worst of both worlds. Plan gives false confidence; agents retain coordination complexity.

### A3: Pre-Compiled Static Plans

All plans defined ahead of time (like CI/CD pipelines).

**Rejected**: Works for known, repeatable goals. Not for open-ended, creative, or novel goals — the primary use case for AI agents.

---

## Trade-offs

| Trade-off | Choice | Rationale |
|-----------|--------|-----------|
| Plan first vs. Emergent execution | Plan first | Predictability and observability outweigh upfront latency |
| Planner in Kernel vs. Plugins | Plugin | Different goals need different planning strategies |
| Immutable plan vs. Dynamic plan | Dynamic (governed modification) | Real-world execution requires adaptation; governance prevents chaos |

---

## References

- [Architecture Invariants](../architecture/invariants.md)
- [ADR-0001: Runtime First](./ADR-0001-runtime-first.md)
- [ADR-0002: Capability First](./ADR-0002-capability-first.md)
- [ADR-0004: Plugin Architecture](./ADR-0004-plugin-architecture.md)
- [Blueprint: Execution Model](../blueprint/execution-model.md)
- [Blueprint: Task Graph](../blueprint/task-graph.md)
- [Schema: Execution Plan](../schema/execution-plan.json)
