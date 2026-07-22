# RFC-0004: Capability Semantics

| Status      | Draft |
|-------------|-------|
| **Date**    | 2026-07-19 |
| **Authors** | Zelos Architecture Team |

---

## Problem

Capabilities are the interface between what Tasks need and what Agents provide. The quality of this interface determines scheduling quality, matchmaking accuracy, and overall multi-agent coordination.

Without precise capability semantics — naming, versioning, matching, QoS, lifecycle — the Scheduler cannot make good decisions, and agents cannot reliably describe what they do.

---

## Proposal

### Naming Convention

Hierarchical: `{domain}.{subdomain}[.{specific}...]`

Top-level domains: code-generation, code-review, code-transformation, research, analysis, design, automation, communication, reasoning, verification.

### Versioning

Semantic Versioning: MAJOR.MINOR.PATCH.
- MAJOR: Breaking schema change
- MINOR: Backward-compatible addition
- PATCH: No schema change

Task version requirements: `>=1.0.0, <2.0.0` — Agent must satisfy the range.

### Matching Algorithm

Level 1: Exact name + compatible version (deterministic, primary)
Level 2: Prefix match (e.g., `code-generation` matches `code-generation.python`)
Level 3: Tag-based match (intersection of required and provided tags)
Level 4: Semantic match (embedding similarity, fallback, Phase 3)

### QoS

Declared by Agent: max_latency_ms, max_cost_per_call, availability, accuracy, throughput. Runtime may measure actuals and downgrade on significant deviation.

### Lifecycle

Registered → Available → Unavailable (agent disconnected) / Deprecated → Removed.

### Deprecation

Agent announces deprecation → deprecated period (7 days) → removed. Scheduler deprioritizes deprecated capabilities.

---

## Compatibility

**Naming**: New top-level domains are additive. Existing names must not change meaning.

**Versioning**: Breaking capability changes require new MAJOR version. Old version remains available during deprecation period.

**Schema evolution**: input_schema and output_schema changes follow JSON Schema compatibility rules.

---

## Migration

Not applicable — establishes initial capability semantics. Future migration concerns:
1. Capability name registry (prevent conflicts as ecosystem grows)
2. Canonical capability definitions (shared schemas for common capabilities)

---

## Open Questions

1. **Semantic matching**: At what phase should embedding-based matching be added? Non-deterministic matching is harder to debug.

2. **Multi-capability Tasks**: Should a Task specify multiple acceptable capabilities? E.g., "code-generation.python OR code-review.python"? **Resolved (2026-07-19): Phase 1: single capability per Task.** The `required_capability` field accepts exactly one capability name. The `fallback_capability` field provides a single alternative (retry only, not OR-matching). Multi-capability OR-matching is deferred to Phase 2.

3. **Dynamic capability discovery**: Can Agents discover new capabilities at runtime (after installing a tool)? Or must all be declared at registration?

4. **QoS verification**: Should the Runtime actively measure and compare against declared QoS?

5. **Capability conflicts**: Can an Agent register conflicting capabilities? E.g., "code-generation" and "code-review" for the same work?

---

## Alternatives Considered

### A1: Flat Capability Names (No Hierarchy)

All capabilities are flat strings: "python-coding", "security-review".

**Rejected**: No grouping, no prefix matching, no domain organization. Hierarchy enables discovery and scheduling flexibility.

### A2: Capability as Free-Form Text

No schema — just a text description. Matching via semantic similarity.

**Rejected**: Non-deterministic, hard to validate. Suitable as enhancement, not as primary mechanism.

### A3: Capability as RPC Method Signature

Capability = function signature with typed inputs/outputs.

**Rejected**: Too rigid for AI agent work. JSON Schema provides flexibility while maintaining structure.

---

## References

- [Architecture Invariants](../architecture/invariants.md) — Invariants 5, 14
- [ADR-0002: Capability First](../adr/ADR-0002-capability-first.md)
- [Blueprint: Capability Registry](../blueprint/capability-registry.md)
- [Blueprint: Scheduler](../blueprint/scheduler.md)
- [Schema: Capability](../schema/capability.json)
