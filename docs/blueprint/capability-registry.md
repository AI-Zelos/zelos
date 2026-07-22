# Capability Registry

> Complete Capability Registry: namespace, version negotiation, deprecation, aliases, semantic matching, QoS, tags, capacity, ranking, lifecycle.

---

## Document Status

| Status  | Author                     | Date       |
|---------|----------------------------|------------|
| Revised | Zelos Architecture Team  | 2026-07-19 |

---

## 1. Overview

The Capability Registry is the Kernel component that maintains the mapping between Capabilities (what work can be done) and Providers (which Agents can do it). It enables [Invariant 5](../architecture/invariants.md#invariant-5-capability-before-agent): Capability Before Agent.

---

## 2. Capability Namespace

### 2.1 Naming Convention

```
{domain}.{subdomain}[.{specific}...]

Top-Level Domains:
  code-generation      code-review           code-transformation
  research             analysis              design
  automation           communication         reasoning
  verification
```

### 2.2 Namespace Rules

| Rule | Description |
|------|-------------|
| Lowercase only | All names are lowercase |
| Hyphen separator | Multi-word segments use hyphens: `code-generation` |
| Dot hierarchy | Dots separate levels: `code-generation.python` |
| No trailing dot | `code-generation.` is invalid |
| No consecutive dots | `code..python` is invalid |
| Minimum 2 chars per segment | Unambiguous naming |

### 2.3 Prefix Matching

```
Query: "code-generation"
Matches:
  code-generation
  code-generation.python
  code-generation.typescript.react
Does NOT match:
  code-review
  code-generation  (if case-insensitive, this would match too)
```

---

## 3. Versioning

### 3.1 Semantic Versioning

```
MAJOR.MINOR.PATCH

MAJOR: Breaking change to input_schema or output_schema
MINOR: Backward-compatible addition (new optional field)
PATCH: No schema change (QoS update, bug fix, description)
```

### 3.2 Version Requirements in Tasks

```
Task requires version: ">=1.0.0, <2.0.0"
Agent provides version: "1.3.2"
Compatibility check: 1.3.2 >= 1.0.0 AND 1.3.2 < 2.0.0 → TRUE ✓
```

### 3.3 Version Negotiation

At registration time, the Runtime may negotiate:

```
Agent registers: "code-generation.python" v2.0.0
Runtime: "I need v1.x for existing Tasks. Can you also register v1.x?"
Agent: Yes → registers v1.5.0 and v2.0.0
Agent: No → only v2.0.0 available
```

Phase 1: No negotiation. Agents register what they support.

---

## 4. Deprecation

### 4.1 Deprecation Lifecycle

```
Agent announces deprecation of Capability
    │
    ▼
Capability status → Deprecated
    │
    ▼
Scheduler deprioritizes:
  - Still available for Tasks that explicitly require this version
  - Not selected for new Tasks if an alternative exists
    │
    ▼
Deprecation period (configurable: 7 days default)
    │
    ▼
Capability status → Removed
Scheduler excludes entirely
```

### 4.2 Deprecation Events

- `capability.deprecated` — Agent announces intent
- `capability.removed` — Capability is no longer available

---

## 5. Capability Aliases

### 5.1 Purpose

Allow an Agent's capability name to differ from the canonical name while maintaining semantic equivalence.

### 5.2 Alias Registration

```
Agent registers: "write-python" (internal name)
Registry aliases:  "write-python" → "code-generation.python" (canonical)
```

### 5.3 Alias Rules

| Rule | Description |
|------|-------------|
| Aliases are explicit | Registered by Agent or admin |
| Aliases are versioned | Alias applies to a specific version range |
| Aliases are unidirectional | `A → B` does not imply `B → A` |

Phase 1: No aliases. Agents must use canonical names.

---

## 6. Semantic Matching (Future — Phase 3)

### 6.1 Purpose

When exact name matching fails, find semantically similar capabilities.

### 6.2 Approach

```
Task requires: "write-python-code"
Exact match: none found
Semantic match:
  "code-generation.python"     (similarity: 0.92)
  "code-generation"            (similarity: 0.78)
  "code-transformation"        (similarity: 0.45)
Threshold: 0.75 → "code-generation.python" matches
```

### 6.3 Constraints

- Semantic matching is a fallback — exact matching always preferred
- Threshold is configurable (default: 0.75)
- Semantic match results are logged with confidence for auditing

---

## 7. QoS (Quality of Service)

### 7.1 Declared QoS

```
QoS {
    max_latency_ms: 30000       // Maximum expected execution time
    max_cost_per_call: 0.10     // Maximum cost per execution
    availability: 0.999         // Expected uptime fraction
    accuracy: 0.95              // Expected output accuracy (optional)
    throughput: 10.0            // Tasks per second (optional)
}
```

### 7.2 Measured vs Declared

The Runtime **may** measure actual QoS:

| Metric | Measured How |
|--------|-------------|
| Actual latency | `completed_at - started_at` |
| Actual cost | Agent-reported cost in Artifact metadata |
| Actual availability | Connected time / Total time since registration |
| Actual success rate | Completed tasks / Total tasks |

If measured QoS significantly deviates from declared QoS:
- Capability QoS is downgraded (internally)
- Scheduler deprioritizes
- Agent is not explicitly notified (QoS is informational)

---

## 8. Tags

### 8.1 Purpose

Enable cross-cutting capability discovery beyond the name hierarchy.

### 8.2 Tag Categories

| Category | Examples |
|----------|----------|
| Language | `python`, `typescript`, `go`, `rust` |
| Domain | `web`, `mobile`, `data`, `infra` |
| Quality | `fast`, `cheap`, `high-quality`, `production` |
| AI Backend | `claude`, `gpt`, `gemini` (if agent chooses to disclose) |
| Framework | `react`, `fastapi`, `django` |

### 8.3 Tag Matching

```
Task requires tags: ["fast", "python"]
Agent has tags: ["python", "async", "fast", "production"]
Match: tags intersect ["fast", "python"] → True
```

Tags are AND logic: all required tags must be present.

---

## 9. Capacity

### 9.1 Capacity Declaration

```
Capacity {
    max_concurrent_tasks: 5     // Global across all capabilities (Agent-level)
    per_capability: {           // Optional per-capability sub-limits
        "code-generation.python": 3,
        "code-review": 2
    }
}
```

**Concurrency limit hierarchy:**
1. `agent.max_concurrent_tasks` — Agent-level hard cap. The Agent will never have more than this many Tasks in-flight simultaneously.
2. `per_capability[capability_name]` — Capability-level sub-limits within the Agent-level cap. A per-capability limit may be lower than but never higher than `max_concurrent_tasks`. If unset for a capability, the capability shares the remaining Agent-level capacity.

The Scheduler checks both limits: `agent.current_tasks < agent.max_concurrent_tasks` AND `capability_current_tasks < per_capability_limit` (if set). Both must pass for the Agent to be a valid candidate.

### 9.2 Current Load Tracking

The Runtime tracks `current_tasks` per Agent and per capability. Scheduler uses this to enforce capacity limits.

---

## 10. Provider Ranking

Provider ranking for Task dispatch is owned by the **Scheduler**, not the Capability Registry. The Registry provides provider lists and historical metrics; the Scheduler scores and ranks providers per scheduling round using its own weighted scoring formula.

See [Scheduler: Phase 3 - Scoring](./scheduler.md#5-phase-3-scoring) for the authoritative scoring model.

The Registry maintains historical metrics per provider that the Scheduler consumes:

| Metric | Description |
|--------|-------------|
| Historical success rate | `completed_tasks / total_tasks` per provider per capability |
| Average latency | Rolling average of `(completed_at - started_at)` |
| Average cost | Rolling average of Agent-reported cost per execution |
| Uptime | `heartbeating_time / registered_time` |
| Current load | `current_tasks / max_concurrent_tasks` |

---

## 11. Registry API

```
CapabilityRegistry {
    // Registration
    register(agent_id, capabilities: [Capability]) → Result
    
    // Lifecycle
    mark_available(agent_id) → void
    mark_unavailable(agent_id) → void
    deprecate(agent_id, capability_name, version) → Result
    remove(agent_id, capability_name, version) → Result
    
    // Query
    find_by_name(name: String, version_req?: String) → [Capability]
    find_by_prefix(prefix: String) → [Capability]
    find_by_tag(tags: [String]) → [Capability]
    find_providers_for(name: String, version_req?: String) → [Agent]
    get_capability(name: String, version: String) → Capability?
    list_capabilities(filter?: Filter) → [Capability]
    
    // Admin
    get_stats() → RegistryStats
}
```

---

## 12. References

- [Architecture Invariants](../architecture/invariants.md) — Invariants 5, 14
- [Domain Model](./domain-model.md) — Capability, Agent definitions
- [Kernel Boundary](./kernel-boundary.md) — Registry is in Kernel
- [Scheduler](./scheduler.md) — Consumer of Registry queries
- [RFC-0004](../rfc/rfc-0004-capability-semantics.md) — Capability semantics RFC
- [Schema: Capability](../schema/capability.json)
- [Schema: Agent Registration](../schema/agent-registration.json)
