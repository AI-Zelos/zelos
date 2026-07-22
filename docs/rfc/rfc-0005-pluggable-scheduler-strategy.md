# RFC-0005: Pluggable Scheduler Selection Strategy

| Status      | Accepted (Phase 1) |
|-------------|-------|
| **Date**    | 2026-07-19 |
| **Authors** | Zelos Architecture Team |

---

## Problem

The Scheduler is a sealed Kernel component with a fixed 5-phase pipeline and hardcoded scoring weights. In production, different organizations have fundamentally different selection criteria:

- A fintech company values **security compliance** above cost
- A startup values **cost** above everything else
- A latency-sensitive application values **response time** above success rate
- A research lab wants to **round-robin across providers** to benchmark them
- An enterprise may want to **always prefer internal agents over external ones**

A single hardcoded formula cannot satisfy all these use cases. The current Policy plugin (Phase 4: Allow/Reject/Delay/Retry) can block candidates but cannot re-rank them — it's a binary gate, not a selection strategy.

---

## Design Space

Four approaches, from simplest to most radical:

| Approach | Kernel Change | Flexibility | Risk |
|----------|--------------|-------------|------|
| A: Configurable weights | Minimal | Low | Lowest |
| B: Pluggable ScoringStrategy | Moderate | High | Low |
| C: Full Scheduler as Plugin | High | Maximum | Medium |
| D: Strategy Chain | Moderate | High | Medium |

---

## Proposal: Approach B — Pluggable ScoringStrategy (Accepted for Phase 1)

**Replace only Phase 3 (Scoring) with a plugin interface. Everything else stays in Kernel.**

**Decision (2026-07-19):** ScoringStrategy is a first-class Plugin type starting in Phase 1. The default implementation uses the existing weighted formula with configurable weights. Custom strategies can replace it entirely by implementing the `ScoringStrategy` plugin interface and declaring it in `zelos.yaml`.

### Why Phase 3 specifically?

- **Phase 1 (Order)** — priority ordering is universal. Changes rarely.
- **Phase 2 (Filter)** — hard constraints. These are safety rules, not preferences. Must stay in Kernel.
- **Phase 3 (Score)** — THIS is where "what makes a good candidate" varies by organization.
- **Phase 4 (Policy)** — already pluggable. Works well as a binary gate.
- **Phase 5 (Select)** — picks the max score. Trivial. No need to customize.

### The Interface

```python
class ScoringStrategy(Plugin):
    """
    Plugin that scores and ranks Agent candidates for a Task.

    Replaces the default weighted-formula scoring (Phase 3 of the
    Scheduler pipeline). The Kernel provides all candidate data;
    the strategy returns a ranked list.
    """

    def score(
        self,
        task: Task,
        candidates: list[AgentCandidate],
    ) -> list[ScoredCandidate]:
        """
        Score and rank candidates.

        Args:
            task: The Task being scheduled.
            candidates: Agents that passed Filter (Phase 2).
                        Each has: agent_id, success_rate, cost_per_call,
                        avg_latency_ms, availability, current_load,
                        capability_match_score, tags, historical_data.

        Returns:
            Candidates with scores, sorted best-first.
            Candidates with score=0 are excluded.
        """
        ...

@dataclass
class AgentCandidate:
    agent_id: str
    agent_name: str
    capability_name: str
    capability_version: str
    success_rate: float          # [0, 1]
    cost_per_call: float
    avg_latency_ms: float
    availability: float          # [0, 1]
    current_load: float          # current_tasks / max_concurrent_tasks
    tags: list[str]
    total_completed: int
    executed_dependency: bool    # For affinity scoring
    last_used_seconds_ago: float

@dataclass
class ScoredCandidate:
    candidate: AgentCandidate
    score: float                 # [0, 1], higher = better
    reason: str                  # Human-readable explanation
```

### Default Implementation (Ships with Zelos)

```python
class DefaultScoringStrategy(ScoringStrategy):
    """
    The current weighted-formula scoring, exposed as the default strategy.
    Weights are configurable via zelos.yaml.
    """

    def __init__(self, weights: ScoringWeights):
        self.weights = weights  # Default: success=0.30, cost=0.20, ...

    def score(self, task, candidates):
        results = []
        for c in candidates:
            score = (
                c.success_rate         * self.weights.success +
                self._cost_score(c)    * self.weights.cost +
                self._load_score(c)    * self.weights.load +
                self._latency_score(c) * self.weights.latency +
                self._avail_score(c)   * self.weights.availability +
                self._affinity(c)      * self.weights.affinity +
                self._recency(c)       * self.weights.recency
            )
            results.append(ScoredCandidate(
                candidate=c,
                score=clamp(score, 0, 1),
                reason=f"success={c.success_rate:.2f} cost={c.cost_per_call:.3f} ..."
            ))
        return sorted(results, key=lambda r: r.score, reverse=True)
```

### Example: Fintech Custom Strategy

```python
class FintechScoringStrategy(ScoringStrategy):
    """
    Fintech: prioritize security compliance, then success rate, then cost.
    Agents without 'soc2-compliant' tag are excluded (score=0).
    """

    def score(self, task, candidates):
        results = []
        for c in candidates:
            # Hard requirement: SOC2 compliance
            if "soc2-compliant" not in c.tags:
                results.append(ScoredCandidate(c, score=0, reason="Not SOC2 compliant"))
                continue

            # Custom formula: security-first
            score = (
                c.success_rate      * 0.40 +   # Reliability paramount
                self._compliance(c) * 0.25 +   # Compliance score
                self._cost_score(c) * 0.15 +
                c.availability      * 0.10 +
                self._latency(c)    * 0.10
            )
            results.append(ScoredCandidate(c, score=clamp(score, 0, 1),
                reason=f"compliant success={c.success_rate:.2f}"))
        return sorted(results, key=lambda r: r.score, reverse=True)
```

### Example: Cost-First Startup Strategy

```python
class StartupScoringStrategy(ScoringStrategy):
    """Startup: cheapest wins, as long as success rate > 70%."""

    def score(self, task, candidates):
        results = []
        for c in candidates:
            if c.success_rate < 0.70:
                results.append(ScoredCandidate(c, score=0, reason="Below 70% threshold"))
                continue
            # Cost is king: lower cost → higher score
            max_cost = max(x.cost_per_call for x in candidates) or 1
            score = 1.0 - (c.cost_per_call / max_cost)
            results.append(ScoredCandidate(c, score=clamp(score, 0, 1),
                reason=f"cost={c.cost_per_call:.4f}"))
        return sorted(results, key=lambda r: r.score, reverse=True)
```

### Phase 1 Implementation (Accepted)

ScoringStrategy is a **first-class Plugin type** from Phase 1. The default implementation (`DefaultScoringStrategy`) ships with the Runtime and uses the existing weighted formula. Organizations can replace it with a custom strategy by implementing the `ScoringStrategy` interface and declaring it in `zelos.yaml`.

**Default strategy (built-in, weights configurable via `zelos.yaml`):**

```yaml
plugins:
  - id: "default-scoring"
    type: "scoring_strategy"
    version: "0.1.0"
    entrypoint: "zelos.scoring.default.DefaultScoringStrategy"
    config:
      weights:
        success_rate: 0.30
        cost_efficiency: 0.20
        load_distribution: 0.15
        latency: 0.15
        availability: 0.10
        affinity: 0.05
        recency: 0.05
```

**Custom strategy (replace entire scoring logic):**

```yaml
plugins:
  - id: "fintech-scoring"
    type: "scoring_strategy"
    version: "1.0.0"
    entrypoint: "my_org.scoring.fintech.FintechScoringStrategy"
    config:
      require_compliance_tag: "soc2-compliant"
      compliance_weight: 0.25
```

See Plugin Architecture for the full ScoringStrategy plugin specification.

---

## Why Not Approach C (Full Scheduler as Plugin)?

This would make the Scheduler replaceable entirely — like the Planner already is.

**Arguments for:**
- Maximum flexibility — replace the entire scheduling algorithm
- Architectural consistency — Planner is already a plugin, why not Scheduler?

**Arguments against:**
- The Scheduler enforces **safety invariants** — filter constraints, capacity limits, deadline enforcement. Moving this to a replaceable plugin means a buggy plugin can silently skip safety checks.
- The Planner produces a Plan — a data artifact. If it's wrong, the Verifier catches it. The Scheduler makes **operational decisions** — a wrong decision means tasks go to the wrong agent, with no downstream verifier to catch it.
- Planner can be wrong safely. Scheduler must never be wrong.

**Recommendation: keep Filter/Order/Select in Kernel. Only Scoring becomes a plugin.**

---

## Impact on Architecture Invariants

| Invariant | Impact |
|-----------|--------|
| Invariant 10 (Kernel is Plugin-Oriented) | No change. ScoringStrategy is a new Plugin type. Filter/Order/Select remain in Kernel. |
| Invariant 5 (Capability Before Agent) | No change. Filter still enforces capability matching before scoring. |
| Invariant 15 (Policies Never Change Business Logic) | No change. Policy remains Allow/Reject/Delay/Retry. ScoringStrategy replaces the score formula, not policy decisions. |

---

## New Plugin Type

Add to Plugin Architecture:

| Plugin Type | Interface | Role |
|-------------|-----------|------|
| **Scoring Strategy** | `score(task, candidates) → [ScoredCandidate]` | Custom ranking logic (Phase 2+) |

The Scheduler pipeline becomes:

```
Order → Filter → [ScoringStrategy.score()] → Policy → Select
  ❌       ❌               ✅                  ✅       ❌
Kernel   Kernel          Plugin             Plugin   Kernel
```

---

## Implementation Status

| Phase | Feature | Status |
|-------|---------|--------|
| Phase 1 | Pluggable ScoringStrategy | Accepted — first-class Plugin type |
| Phase 1 | Default weighted-formula strategy | Built-in, weights configurable |
| Phase 1 | Custom strategies (any logic) | Via `ScoringStrategy` plugin interface |
| Phase 3 | Strategy chain / ensemble | Future (if needed) |

---

## Open Questions

1. **Should ScoringStrategy be allowed to return score=0 (exclude)?** Recommended: Yes. This allows strategies to enforce their own soft constraints without requiring Policy plugins for every rule. The Kernel treats score=0 as "excluded from this round."

2. **Should the strategy receive raw metrics or only pre-computed scores?** Recommended: Raw metrics (`success_rate`, `cost_per_call`, `avg_latency_ms`, etc.) so the strategy can apply its own transformation.

3. **Multi-capability tasks (Phase 2+) — should the strategy score across capabilities?** Yes, when multi-capability tasks are supported. The strategy receives all candidates across all acceptable capabilities.

---

## Alternatives Considered

### A1: Configurable Weights Only (Phase 1 approach)

Make the 7 weights configurable but keep the formula fixed.

**Rejected as insufficient:** Different organizations need fundamentally different formulas, not just reweighted versions of the same one. A fintech's `success*0.4 + compliance*0.25 + cost*0.15` is not achievable by tuning the 7 default weights.

### A2: Policy as Scoring Proxy

Allow Policy plugins to return a numeric score instead of just Allow/Reject.

**Rejected:** Conflates two concerns. Policy is a safety gate (binary). Scoring is a ranking (continuous). Merging them makes both harder to reason about.

### A3: Full Pipeline as Plugin

Make the entire Scheduler a replaceable plugin.

**Rejected for Phase 1-2:** Safety invariants (filter constraints, capacity enforcement) should not be trust-dependent on plugin code quality. Revisit for Phase 3+ if demand is strong.

---

## References

- [Architecture Invariants](../architecture/invariants.md) — Invariants 5, 10, 15
- [Scheduler Blueprint](../blueprint/scheduler.md)
- [Plugin Architecture](../blueprint/plugin-architecture.md)
- [Kernel Boundary](../blueprint/kernel-boundary.md)
