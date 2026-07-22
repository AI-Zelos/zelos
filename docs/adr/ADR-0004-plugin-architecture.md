# ADR-0004: Plugin Architecture

| Status       | Decided |
|--------------|---------|
| **Date**     | 2026-07-19 |
| **Deciders** | Zelos Architecture Team |
| **Depends On** | [ADR-0001](./ADR-0001-runtime-first.md) |

---

## Context

The Runtime Kernel must be minimal, stable, and long-lived. The ecosystem — Planners, Verifiers, Policies, Memory Providers, Agents — must be extensible and replaceable. This is the Kernel vs. Userspace boundary from operating system design.

Where to draw the line? If the Kernel does too much, it becomes large, opinionated, fragile. If too little, it becomes a thin event bus providing insufficient value.

### Relevant Invariants

- [Invariant 10](../architecture/invariants.md#invariant-10-kernel-is-plugin-oriented)

---

## Decision

Zelos adopts a **Plugin Architecture** with a minimal, sealed Kernel.

**Kernel contains (immutable):** Event Bus, Capability Registry, Task Graph Engine, Scheduler, Execution Engine, Plugin Lifecycle Manager.

**Plugins (replaceable):** Planner, Verifier, Policy, Memory Provider, Storage Backend, Protocol Adapter, Agent.

**Boundary rule:** A component belongs in the Kernel only if removing it would break multi-agent orchestration, AND it cannot be implemented as a replaceable plugin without violating invariants.

---

## Consequences

### Positive

- Stable Kernel — thoroughly tested, rarely changed
- Ecosystem — third parties build plugins without modifying Kernel
- Experimentation — new planners, verifiers, policies tested in isolation
- Security boundary — plugin isolation provides natural security
- Independent evolution — each plugin evolves at its own pace

### Negative

- API stability burden — Runtime API must be carefully versioned
- Plugin discovery and compatibility validation overhead
- Performance overhead — process/container boundaries add latency
- Debugging complexity — issues spanning Kernel + plugins are harder to trace

### Mitigations

- Runtime API follows strict semantic versioning
- Plugin compatibility validated at registration
- In-process plugin mode for development and low-latency scenarios
- Distributed tracing spans across Kernel and plugin boundaries

---

## Alternatives Considered

### A1: Monolithic Runtime

All functionality in the Kernel. No plugin system.

**Rejected**: Limits extensibility, creates large fragile codebase, prevents ecosystem growth.

### A2: Microservices Architecture

Every component is an independent service. No Kernel.

**Rejected**: Overhead of service-to-service communication. No single source of truth. Operational complexity appropriate for Phase 3, not Phase 0.

### A3: Scriptable Kernel (Lua/Python embedded)

Kernel minimal but allows scripting for extensibility.

**Rejected**: Embeds plugin logic in Kernel process, breaking isolation. Limits plugin languages. Versioning harder.

---

## Trade-offs

| Trade-off | Choice | Rationale |
|-----------|--------|-----------|
| Monolith vs. Plugin | Plugin Architecture | Extensibility and ecosystem > monolithic simplicity |
| In-process vs. Isolated plugins | Graduated (in-process → container) | Start simple, add isolation as scale demands |
| Rich plugin API vs. Minimal interfaces | Minimal interfaces | Lower barrier to entry; richness in SDKs |

---

## References

- [Architecture Invariants](../architecture/invariants.md)
- [ADR-0001: Runtime First](./ADR-0001-runtime-first.md)
- [ADR-0005: Protocol Adapter Architecture](./ADR-0005-protocol-adapter-architecture.md)
- [Blueprint: Kernel Boundary](../blueprint/kernel-boundary.md)
- [Blueprint: Plugin Architecture](../blueprint/plugin-architecture.md)
