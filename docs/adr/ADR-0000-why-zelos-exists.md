# ADR-0000: Why Zelos Exists

| Status       | Decided |
|--------------|---------|
| **Date**     | 2026-07-19 |
| **Deciders** | Zelos Architecture Team |
| **Supersedes** | None |

---

## Context

The AI engineering landscape in 2025-2026 is dominated by Agent Frameworks — LangChain, LangGraph, CrewAI, AutoGen — that provide toolkits for constructing agents. These frameworks solve the problem of building an individual agent or a small team.

However, a new class of application is emerging: dozens to hundreds of heterogeneous agents working on long-running, dynamic goals that require governance and observability. Existing frameworks fail here because they conflate agent construction with agent orchestration. When scheduling, memory, retry, and routing logic lives inside agents, the result is tight coupling, no governance, no observability, and compositional failure.

### The Missing Layer

Between the application and the agents, a layer is missing: **the Runtime**. This is the pattern every successful distributed system follows — Linux for processes, Kubernetes for containers, Temporal for workflows. Zelos is that layer for agents.

### Relevant Invariants

- [Invariant 1](../architecture/invariants.md#invariant-1-runtime-owns-orchestration)
- [Invariant 2](../architecture/invariants.md#invariant-2-goal-is-the-first-class-abstraction)
- [Invariant 10](../architecture/invariants.md#invariant-10-kernel-is-plugin-oriented)

---

## Decision

Zelos will be designed and built as a **Runtime** — not a framework, toolkit, or library.

This means:
1. Agents are external processes that register with the Runtime — not imported libraries.
2. The Runtime owns all coordination logic. Agents never coordinate with each other directly.
3. All communication is event-driven through the Event Bus.
4. Dispatch is capability-based — never by agent name.
5. Everything above the Kernel is a replaceable Plugin.

---

## Consequences

### Positive

- **Decoupling**: Agents and Runtime evolve independently
- **Governance**: Policies enforced at the Runtime level
- **Heterogeneity**: Agents in any language, any framework
- **Composability**: Agents from any source can participate in any Goal
- **Observability**: Single source of truth for all execution state
- **Ecosystem potential**: Marketplace, cloud platform, enterprise portal become possible

### Negative

- **Higher initial complexity**: A Runtime is harder to design than a framework
- **Protocol overhead**: All communication goes through the Runtime
- **Adoption friction**: Developers must learn a new paradigm
- **Specification burden**: Runtime API must be stable before anything works

### Mitigations

- Runtime API is intentionally minimal (5 methods per Agent)
- Protocol adapters allow existing agents to integrate without modification
- Plugin Architecture allows incremental adoption

---

## Alternatives Considered

### A1: Extend an Existing Framework

Add scheduling, multi-agent coordination, and governance to LangGraph or CrewAI.

**Rejected**: These frameworks have architectural assumptions (sequential chains, role-based teams) incompatible with the Runtime model. Extension would require breaking changes.

### A2: Build on Temporal

Use Temporal as the execution engine, with agents as Activities.

**Rejected**: Temporal is designed for deterministic workflows. Autonomous agents produce non-deterministic outputs. Strong consistency assumptions mismatch with probabilistic AI agents.

### A3: Pure Event-Driven Mesh (No Central Runtime)

Decentralized event mesh where agents discover and coordinate peer-to-peer.

**Rejected**: No single source of truth for execution state, no governance enforcement point, no capability registry. Same fragmentation that plagues current solutions.

---

## Trade-offs

| Trade-off | Choice | Rationale |
|-----------|--------|-----------|
| Centralized Runtime vs. Decentralized Mesh | Centralized Runtime | Single source of truth, governance, observability > theoretical scalability of mesh |
| Minimal Agent API vs. Rich Agent SDK | Minimal API (5 methods) | Lower barrier to entry; richness belongs in SDKs, not the protocol |
| Build from scratch vs. Extend existing | Build from scratch | No existing system has the Runtime architecture; extending would inherit wrong abstractions |

---

## References

- [Architecture Invariants](../architecture/invariants.md)
- [ADR-0001: Runtime First](./ADR-0001-runtime-first.md)
- [ADR-0002: Capability First](./ADR-0002-capability-first.md)
- [Blueprint: Domain Model](../blueprint/domain-model.md)
- [Blueprint: Kernel Boundary](../blueprint/kernel-boundary.md)
