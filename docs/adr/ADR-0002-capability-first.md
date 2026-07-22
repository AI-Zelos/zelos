# ADR-0002: Capability First

| Status       | Decided |
|--------------|---------|
| **Date**     | 2026-07-19 |
| **Deciders** | Zelos Architecture Team |
| **Depends On** | [ADR-0001](./ADR-0001-runtime-first.md) |

---

## Context

How does the Runtime decide which Agent should execute a Task? Two approaches exist:

1. **Identity-Based**: Dispatch to a specific Agent by name. The caller knows exactly who.
2. **Capability-Based**: Dispatch by matching the required capability against a registry of providers. The caller specifies what, not who.

Most current systems use identity-based dispatch. This fails at scale: no fallback, no optimization, tight coupling, no multi-vendor support, vendor lock-in, no A/B testing.

### Relevant Invariants

- [Invariant 5](../architecture/invariants.md#invariant-5-capability-before-agent)
- [Invariant 14](../architecture/invariants.md#invariant-14-capability-describes-intent-not-implementation)

---

## Decision

Zelos dispatches all tasks by **Capability**, never by Agent identity.

**Capability**: A named, versioned, schema-described unit of work that an Agent can perform. Describes what — not who or how.

**Dispatch flow**: Task requires Capability → Capability Registry finds providers → Scheduler selects best (cost, latency, QoS, history, policy) → Dispatch.

**Invariants**: Tasks reference capabilities, not agents. Agents register capabilities, not task types. Multiple Agents can provide the same capability. An Agent can provide multiple capabilities.

---

## Consequences

### Positive

- Provider independence — any agent implementing the right capability can serve
- Runtime optimization — best provider selected per real-time conditions
- Resilience — provider failure → fallback to alternatives
- Composability — new agents added without changing orchestration
- Ecosystem potential — third-party agents compete on quality/cost/speed

### Negative

- Capability definition overhead — standardized schema required
- Matching complexity — may require semantic understanding
- Cold start — new agents have no historical data
- Overspecification risk — too-granular capabilities make matching brittle

### Mitigations

- Hierarchical capability taxonomy with well-known base types
- Tag-based and semantic matching as fallback
- Neutral default success rate with exploration budget for new providers
- Capability granularity guidelines in RFCs

---

## Alternatives Considered

### A1: Name-Based Dispatch

Dispatch to agents by name via a routing table.

**Rejected**: Adds indirection without abstraction. Routing table becomes a manual dependency graph. No multi-provider optimization.

### A2: Content-Based Routing (Topic Subscription)

Agents subscribe to task topics. Runtime routes by topic.

**Rejected**: Capability matching by another name, with less structure. Topics lack versioning, schema validation, QoS metadata.

### A3: Semantic Matching Only

No explicit capability names. Embeddings match task descriptions to agent descriptions.

**Rejected**: Non-deterministic, hard to debug. Valuable as fallback, not as primary mechanism.

---

## Trade-offs

| Trade-off | Choice | Rationale |
|-----------|--------|-----------|
| Simple name dispatch vs. Capability-based | Capability-based | Complexity pays for itself in provider independence and optimization |
| Strict typing vs. Flexible matching | Strict typing with fallback | Exact matching for reliability, semantic as enhancement |
| Agent anonymity vs. Agent identity | Anonymous (by capability) | Enables multi-vendor, fallback, marketplace |

---

## References

- [Architecture Invariants](../architecture/invariants.md)
- [ADR-0001: Runtime First](./ADR-0001-runtime-first.md)
- [ADR-0003: Execution Plan First](./ADR-0003-execution-plan-first.md)
- [Blueprint: Capability Registry](../blueprint/capability-registry.md)
- [Blueprint: Scheduler](../blueprint/scheduler.md)
- [RFC-0004: Capability Semantics](../rfc/rfc-0004-capability-semantics.md)
- [Schema: Capability](../schema/capability.json)
