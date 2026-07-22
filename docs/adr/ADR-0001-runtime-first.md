# ADR-0001: Runtime First

| Status       | Decided |
|--------------|---------|
| **Date**     | 2026-07-19 |
| **Deciders** | Zelos Architecture Team |
| **Depends On** | [ADR-0000](./ADR-0000-why-zelos-exists.md) |

---

## Context

Multi-agent system design faces a fundamental choice: **Agent-Centric** (agents coordinate among themselves; the system is emergent behavior) or **Runtime-Centric** (a central Runtime plans, schedules, and governs; agents are execution plugins).

The Agent-Centric approach is the industry default. Every major framework places agents at the center and adds orchestration as an afterthought. This fails at scale: scheduling is local (no global optimization), memory is inconsistent (each agent manages its own), retry is ad-hoc (per-agent policies), and governance is impossible (no enforcement point).

### Relevant Invariants

- [Invariant 1](../architecture/invariants.md#invariant-1-runtime-owns-orchestration)
- [Invariant 6](../architecture/invariants.md#invariant-6-agent-is-stateless)

---

## Decision

Zelos adopts the **Runtime First** principle.

**Runtime owns:** Goal decomposition, Execution Planning, Task Graph, Scheduling, Dispatch, Retry, Timeout, Memory (all layers), Context Assembly, Event Bus, Policy Enforcement, Verification Orchestration, Observability, Lifecycle Management, Artifact Collection.

**Agent owns:** Receiving Tasks, Executing Tasks, Returning Artifacts, Heartbeat, Shutdown.

**Invariants:** An Agent never invokes another Agent, schedules a Task, manages Memory, retries a Task, knows the workflow topology, or discovers other Agents.

---

## Consequences

### Positive

- Single source of truth for execution state
- Global optimization across all tasks and agents
- Consistent retry, timeout, and governance policies
- Complete observability — every event flows through the Runtime
- Dramatically simpler Agents
- Heterogeneous agents in any language/framework

### Negative

- Runtime is a single point of failure (mitigated by distributed deployment in Phase 3)
- Higher Runtime complexity
- Latency overhead for all communication
- Mental model shift for developers

---

## Alternatives Considered

### A1: Hybrid Model

Some responsibilities Runtime-owned, others Agent-owned. Agents negotiate among themselves for simple cases.

**Rejected**: The boundary between Runtime and Agent responsibility becomes ambiguous, recreating the conflation problem. A clean separation is simpler than a partial one.

### A2: Event-Driven Mesh with Distributed Consensus

No central Runtime. Distributed event mesh with consensus protocols.

**Rejected**: Agent-Centric model with better infrastructure. Still places coordination logic inside agents. Consensus protocols add unnecessary complexity.

---

## Trade-offs

| Trade-off | Choice | Rationale |
|-----------|--------|-----------|
| Central control vs. Agent autonomy | Central control | Governance, observability, and correctness require centralized coordination |
| Runtime complexity vs. Agent complexity | Complex Runtime, simple Agents | Runtime built once; Agents built by thousands — push complexity to the component built once |
| Single point of failure vs. Distributed fragility | Accept SPOF in Phase 1-2 | Distributed deployment in Phase 3; correctness first, distribution second |

---

## References

- [Architecture Invariants](../architecture/invariants.md)
- [ADR-0000: Why Zelos Exists](./ADR-0000-why-zelos-exists.md)
- [ADR-0002: Capability First](./ADR-0002-capability-first.md)
- [Blueprint: Domain Model](../blueprint/domain-model.md)
- [Blueprint: Kernel Boundary](../blueprint/kernel-boundary.md)
- [Blueprint: Runtime Lifecycle](../blueprint/runtime-lifecycle.md)
