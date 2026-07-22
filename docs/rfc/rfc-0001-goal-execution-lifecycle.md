# RFC-0001: Goal Execution Lifecycle

| Status      | Draft |
|-------------|-------|
| **Date**    | 2026-07-19 |
| **Authors** | Zelos Architecture Team |

---

## Problem

The Goal is the top-level unit of work in Zelos. Its lifecycle — from submission to completion — is the primary execution path that every other component exists to support. Without a clear specification of this lifecycle, components cannot agree on what "done" means, what "failed" means, or how to recover. Currently, the lifecycle is described across multiple documents (execution model, runtime lifecycle, domain model) with potential inconsistencies.

---

## Proposal

Define a single, authoritative Goal Execution Lifecycle that covers:

1. **State Machine**: All Goal states (submitted → accepted → planned → executing → completed/failed/cancelled) with explicit transition triggers and owners.
2. **API Surface**: Submit, Query, Cancel, Watch operations.
3. **Cancellation Semantics**: What happens to in-flight tasks when a Goal is cancelled.
4. **Timeout and Deadline**: How deadlines are enforced and what happens when they expire.
5. **Relationship to Plan Lifecycle**: The Goal and its Execution Plan have coupled but distinct lifecycles.

### State Machine

```
Submitted → Accepted → Planned → Executing → Completed
    │           │          │           │
    └─Rejected  └─Failed   ├─Cancelled ├─Failed
                           └─Failed    └─Cancelled
```

### API

```
SubmitGoal(description, constraints?, context?) → GoalResponse
GetGoalStatus(goal_id) → GoalStatusResponse
ListGoals(filter?) → [Goal]
CancelGoal(goal_id) → GoalStatusResponse
WatchGoal(goal_id) → Stream<Event>
```

### Cancellation

- Goal → `cancelling` (internal transient)
- All in-flight Tasks receive cancel signal
- Agents have `graceful_cancel_timeout_ms` to respond
- All pending Tasks → `cancelled`
- Goal → `cancelled` (terminal)

---

## Compatibility

**Backward compatible**: This is a new specification. No existing implementations to break.

**Forward compatibility**: The state machine may gain states (e.g., `paused`) in future versions. Clients should treat unknown states as terminal-equivalent for safety.

---

## Migration

Not applicable — no existing system to migrate from. This RFC establishes the initial specification.

---

## Open Questions

1. **Partial success**: Should a Goal complete with some Tasks failed (non-critical)? Current: No. All terminal Tasks must complete. This may be too strict for goals with optional or best-effort sub-tasks.

2. **Goal dependencies**: Can one Goal depend on another? Current: Out of scope for Phase 1.

3. **Goal resubmission**: Can a Failed Goal be resubmitted? Reuse existing Plan or re-plan?

4. **Pause vs. Cancel**: Should the state machine distinguish between pause (preserve partial results) and cancel (discard)?

5. **Human-in-the-loop**: Where does human approval of a Plan fit in the state machine? Before `planned` → `executing`? **Resolved (2026-07-19): Deferred to Phase 2.** Phase 1: Plan proceeds directly from `planned` → `executing` without human approval gate. The Verifier's `needs_review` verdict (see artifact.json `pending_review` state) provides the extension point for human-in-the-loop in Phase 2.

---

## Alternatives Considered

### A1: No Explicit Goal Lifecycle

The Goal is just a container for Tasks. It has no independent lifecycle.

**Rejected**: Without a Goal lifecycle, there's no way to know when "the work" is done. The Goal lifecycle provides the top-level success/failure signal.

### A2: Goal as Workflow Instance

Goal lifecycle mirrors Temporal-style workflow execution (scheduled → running → completed/failed).

**Rejected**: Goals are higher-level than workflows. A Goal may involve plan modification, replanning, and dynamic task creation — none of which fit the workflow model.

---

## References

- [Architecture Invariants](../architecture/invariants.md) — Invariants 2, 3, 12
- [ADR-0001: Runtime First](../adr/ADR-0001-runtime-first.md)
- [Blueprint: Execution Model](../blueprint/execution-model.md)
- [Blueprint: Runtime Lifecycle](../blueprint/runtime-lifecycle.md)
- [Blueprint: Domain Model](../blueprint/domain-model.md)
