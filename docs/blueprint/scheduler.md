# Scheduler

> Complete scheduling process: filtering, scoring, policy evaluation, fallback, retry, affinity, anti-affinity, cost, latency, capacity, historical success.

---

## Document Status

| Status  | Author                     | Date       |
|---------|----------------------------|------------|
| Revised | Zelos Architecture Team  | 2026-07-19 |

---

## 1. Overview

The Scheduler is the decision-making core of the Kernel. It answers: **which Agent should execute this Task?**

### 1.1 Position

```
Task Graph Engine        Capability Registry        Policy Engine
      │                        │                        │
      │ ready_tasks            │ matching_providers     │ allow/deny
      │                        │                        │
      └────────────────────────┼────────────────────────┘
                               │
                        ┌──────▼──────┐
                        │  SCHEDULER   │
                        └──────┬───────┘
                               │ assignment
                               ▼
                       Execution Engine
```

### 1.2 Scheduling Trigger

The Scheduler runs when:
- `task.ready` event published (primary, event-driven)
- `agent.connected` / `capability.available` event (new provider available)
- `task.completed` event (potentially unblocks dependent Tasks)
- Fallback polling interval (every `scheduling_interval_ms`, default 1000ms)

---

## 2. Scheduling Process

```
Ready Tasks
    │
    ▼
┌─────────────┐
│ 1. ORDER    │  Sort by priority, deadline, dependents count
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ 2. FILTER   │  Remove candidates that fail hard constraints
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ 3. SCORE    │  Rank remaining candidates by weighted criteria
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ 4. POLICY   │  Apply Policy plugin Allow/Reject decisions
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ 5. SELECT   │  Pick highest-scoring allowed candidate
└──────┬──────┘
       │
       ▼
   Assignment
```

---

## 3. Phase 1: Ordering

Ready Tasks are ordered by:

1. **Priority** (critical > high > medium > low)
2. **Earliest deadline** (within same priority)
3. **Most dependents** (unblock the most downstream work, within same deadline)
4. **FIFO** (`created_at`, within same dependents)

---

## 4. Phase 2: Filtering

### 4.1 Hard Constraints (Disqualify)

| Constraint | Check |
|-----------|-------|
| Capability name match | Agent must provide exact capability name required by Task |
| Version compatibility | Agent version must satisfy Task version requirement (e.g., `>=1.0, <2.0`) |
| Agent alive | Agent status must be `heartbeating` |
| Agent capacity | Agent `current_tasks < max_concurrent_tasks` |
| Runtime capacity | Global `current_tasks < max_concurrent_tasks_runtime` |
| Goal capacity | Goal `current_tasks < max_concurrent_tasks_per_goal` |
| Budget remaining | Estimated task cost ≤ remaining Goal budget |
| Deadline feasible | Agent's declared `max_latency_ms` ≤ remaining time to deadline |
| Excluded agents | Agent not in Task's `excluded_agent_ids` |
| Minimum success rate | Agent's historical success rate ≥ Task's `min_success_rate` (if set) |
| Required tags | Agent has all of Task's `required_tags` (if set) |
| Policy forbid | Policy does not explicitly forbid this Agent |

### 4.2 Filter Outcome

- Candidates ≥ 1 → proceed to Scoring
- Candidates = 0 → check fallback_capability
  - If fallback exists → re-query with fallback capability
  - If no fallback → Task remains `ready`, retry next scheduling round

---

## 5. Phase 3: Scoring

### 5.1 Scoring Strategy Plugin

The Scheduler delegates Phase 3 (candidate ranking) to a **Scoring Strategy Plugin**. This is a first-class Plugin type, loaded at startup. The Kernel provides candidate data; the plugin returns a ranked list.

The default strategy (`DefaultScoringStrategy`) uses a weighted multi-factor formula with configurable weights. Custom strategies can implement any ranking logic — cost-first, compliance-first, round-robin, or ML-based — by replacing the plugin.

**Plugin Interface:**
```
score(task: Task, candidates: [AgentCandidate]) → [ScoredCandidate]
// Returns scored candidates sorted best-first. score=0 means excluded.
```

### 5.2 Default Scoring Formula

| Factor | Weight | Rationale |
|--------|--------|-----------|
| Historical Success Rate | 0.30 | Proven reliability is the strongest signal |
| Cost Efficiency | 0.20 | Lower cost preferred within budget |
| Load Distribution | 0.15 | Prefer less busy agents |
| Latency | 0.15 | Faster agents preferred within deadline |
| Availability | 0.10 | Prefer agents with higher uptime |
| Affinity | 0.05 | Prefer same agent for related Tasks |
| Recency | 0.05 | Small boost for recently used agents (context warmth) |

### 5.3 Scoring Formula

```
score(agent, task) =
    success_score(agent)          * 0.30
  + cost_score(agent, task)       * 0.20
  + load_score(agent)             * 0.15
  + latency_score(agent, task)    * 0.15
  + availability_score(agent)     * 0.10
  + affinity_score(agent, task)   * 0.05
  + recency_score(agent, task)    * 0.05
```

### 5.4 Sub-Score Normalization

All sub-scores normalized to [0, 1]:

```
success_score(agent) =
    agent.historical_success_rate  // already [0, 1]

cost_score(agent, task) =
    1 - (agent.cost_per_call / task.max_cost_per_call)
    clamped to [0, 1]

load_score(agent) =
    1 - (agent.current_tasks / agent.max_concurrent_tasks)
    clamped to [0, 1]

latency_score(agent, task) =
    1 - (agent.avg_latency_ms / task.max_latency_ms)
    clamped to [0, 1]

availability_score(agent) =
    agent.declared_availability  // already [0, 1]

affinity_score(agent, task) =
    1.0 if agent executed a dependency Task of this Task
    0.5 if agent executed any Task in the same Goal
    0.0 otherwise

recency_score(agent, task) =
    1.0 if agent executed a Task within last 60 seconds
    max(0, 1 - (seconds_since_last_use / 300)) otherwise
```

---

## 6. Phase 4: Policy Evaluation

After scoring, each candidate is evaluated by active Policy plugins.

| Policy Decision | Effect |
|----------------|--------|
| `Allow` | Candidate proceeds to selection |
| `Reject` | Candidate removed |
| `Delay` | Candidate deferred to next scheduling round |
| `Retry` | Only applicable for retry decisions (see Retry section) |

**Invariant**: Policies cannot add new candidates, modify scores, or change Task requirements. [Invariant 15](../architecture/invariants.md#invariant-15-policies-never-change-business-logic).

---

## 7. Phase 5: Selection

Highest-scoring allowed candidate is selected.

```
if candidates is empty:
    Task remains Ready (retry next round)
else:
    best = argmax(candidates, score)
    assign(task, best)
```

---

## 8. Retry Policy

### 8.1 Evaluation

When a Task fails (`task.failed` or `task.timed_out`):

```
evaluate_retry(task):
    if task.attempt < task.constraints.max_retries:
        delay = task.constraints.backoff_base_ms * (2 ^ task.attempt) + jitter
        schedule_retry(task, delay)
        task.attempt += 1
        task.status → Ready (after delay)
    elif task.constraints.fallback_capability exists:
        task.required_capability = task.constraints.fallback_capability
        task.attempt = 0
        task.status → Ready
    else:
        task.status → Failed (terminal)
```

### 8.2 Exponential Backoff

```
attempt 0: ~1s delay
attempt 1: ~2s delay
attempt 2: ~4s delay
attempt 3: ~8s delay
attempt 4: ~16s delay
attempt 5: ~32s delay (default max_retries = 3, so likely terminal)
```

Jitter: ±50% of base delay, random, to prevent thundering herd.

### 8.3 Smart Retry (Future Enhancement)

On retry, prefer a **different Agent** to avoid repeating identical failures.

```
retry_candidates = filter(candidates, agent_id != previous_agent_id)
if retry_candidates is not empty:
    use retry_candidates
else:
    use original candidates (no alternative available)
```

---

## 9. Affinity and Anti-Affinity

### 9.1 Affinity

Preference for the same Agent to execute related Tasks.

**Benefits:** Context reuse, lower latency (model context may be warm).

**Mechanism:** `affinity_score` in the scoring formula.

### 9.2 Anti-Affinity

Preference for different Agents to execute related Tasks.

**Benefits:** Diversity of perspectives, error independence.

**Mechanism:** `excluded_agent_ids` constraint on Task.

### 9.3 Per-Task Override

```
task.constraints.affinity = "same_agent" | "different_agent" | "none"
```

Overrides the default affinity scoring.

---

## 10. Cost and Budget Enforcement

### 10.1 Per-Task Cost

```
if agent.estimated_cost_per_call > task.constraints.max_cost_per_call:
    agent disqualified (filtering phase)
```

### 10.2 Cumulative Budget

```
if goal.cumulative_cost + agent.estimated_cost > goal.constraints.budget.max_amount:
    agent disqualified (filtering phase)
```

### 10.3 Budget Exhaustion

If no Agent can execute any remaining Task within budget:
- Goal → `failed` (budget exceeded)

---

## 11. Historical Success Rate

### 11.1 Calculation

```
success_rate(agent, capability) =
    completed_tasks / (completed_tasks + failed_tasks)
    over a sliding window (last N tasks or last T minutes)
```

### 11.2 Cold Start

New Agents (no history) receive a neutral default: `0.5`

This allows exploration while preferring proven Agents.

---

## 12. Concurrency Enforcement

| Limit | Enforced At | Mechanism |
|-------|------------|-----------|
| Per-Agent max concurrent | Filtering phase | `agent.current_tasks < agent.max_concurrent_tasks` |
| Per-Goal max concurrent | Filtering phase | `goal.current_tasks < goal.max_concurrent` |
| Global max concurrent | Filtering phase | `runtime.current_tasks < global_max` |

---

## 13. Observability

| Metric | Type | Description |
|--------|------|-------------|
| `scheduler.rounds_total` | Counter | Scheduling rounds executed |
| `scheduler.tasks_assigned_total` | Counter | Tasks assigned per round |
| `scheduler.tasks_deferred_total` | Counter | Ready tasks that couldn't be assigned |
| `scheduler.candidates_per_query` | Histogram | Provider candidates found per query |
| `scheduler.selection_score` | Histogram | Score of selected provider |
| `scheduler.round_duration_ms` | Histogram | Time per scheduling round |
| `scheduler.retries_total` | Counter | Retry decisions made |

---

## 14. References

- [Architecture Invariants](../architecture/invariants.md) — Invariants 5, 14, 15
- [Domain Model](./domain-model.md) — Task, Capability, Agent definitions
- [Kernel Boundary](./kernel-boundary.md) — Scheduler is in Kernel
- [Capability Registry](./capability-registry.md) — Provider lookup
- [Execution Engine](./execution-engine.md) — Dispatch after scheduling
- [Execution Model](./execution-model.md) — Full execution phases
