# Kernel Boundary

> What belongs in the Kernel, what belongs in Plugins, and what belongs elsewhere. This is the definitive boundary document for Zelos architecture.

---

## Document Status

| Status  | Author                     | Date       |
|---------|----------------------------|------------|
| New     | Zelos Architecture Team  | 2026-07-19 |

---

## 1. The Boundary Principle

The Kernel is the irreducible core of Zelos. It contains only what is necessary for multi-agent orchestration. Everything else is a Plugin, an Adapter, a future concern, or simply out of scope.

### Decision Rule

A component belongs in the Kernel if and only if:

1. **Removing it would break the ability to orchestrate multiple agents.**
2. **It cannot be implemented as a replaceable plugin without violating Invariants.**

If a component fails either test, it does not belong in the Kernel.

---

## 2. What is IN the Kernel

### 2.1 Event Bus

**Why in Kernel:** The Event Bus is the sole communication mechanism. Every component depends on it. If it were a plugin, a plugin failure would break all communication — an unacceptable architectural risk.

**Responsibilities:**
- Publish events
- Subscribe to events (by type, pattern, correlation)
- Deliver events to subscribers
- Persist events to Event Store
- Support event replay for recovery

**Boundary:** The Event Bus owns event routing. The Event Store backend is a Plugin (Storage Backend).

---

### 2.2 Capability Registry

**Why in Kernel:** The Runtime must be able to match Tasks to Agents without depending on any plugin. Capability-based dispatch is a core invariant. If the Registry were a plugin, every Scheduling decision would depend on a plugin being healthy.

**Responsibilities:**
- Accept Capability registrations from Agents
- Index Capabilities by name, version, tag, provider
- Answer queries: "which Agents provide Capability X?"
- Track Capability lifecycle (available, unavailable, deprecated)

**Boundary:** The Registry owns the index. How the index is stored is the Storage Backend's concern.

---

### 2.3 Task Graph Engine

**Why in Kernel:** The Task state machine and dependency resolution are fundamental to execution ordering. If this were a plugin, a plugin could introduce cycles, violate dependency invariants, or corrupt task state.

**Responsibilities:**
- Manage Task state machine (Created → Ready → ... → Terminal)
- Resolve dependencies (determine when a Task becomes Ready)
- Validate DAG acyclicity
- Propagate failures through the dependency graph
- Provide progress queries

**Boundary:** The Task Graph Engine owns the graph. The Planner (a Plugin) decides which Tasks exist.

---

### 2.4 Scheduler

**Why in Kernel:** The Scheduler decides which Agent executes which Task. This is the core orchestration decision. If it were a plugin, the Runtime would lose control over execution optimization, policy enforcement, and global scheduling fairness.

**Responsibilities:**
- Match Ready Tasks to available Agents by Capability
- Score and rank provider candidates
- Enforce scheduling constraints
- Evaluate retry policy for failed Tasks
- Respect global and per-Goal concurrency limits

**Boundary:** The Scheduler selects providers. The Execution Engine dispatches. The Policy plugin may Allow or Reject scheduling decisions after the fact.

---

### 2.5 Execution Engine

**Why in Kernel:** The Execution Engine is the bridge between the Runtime and Agents. It enforces timeouts, monitors heartbeats, and manages task lifecycle during execution. Without it, there is no reliable dispatch.

**Responsibilities:**
- Dispatch Tasks to assigned Agents
- Monitor Task execution lifecycle
- Track Agent heartbeats
- Enforce Task timeouts
- Handle cancellation signals
- Collect Artifacts from Agents
- Detect and handle Agent disconnection

**Boundary:** The Execution Engine manages the Agent connection. The Agent implementation is external.

---

### 2.6 Plugin Lifecycle Manager

**Why in Kernel:** The Kernel must be able to load and manage plugins reliably. If plugin management were itself a plugin, there would be a bootstrap problem.

**Responsibilities:**
- Discover plugins (from configuration, filesystem, registry)
- Load plugin code/processes
- Validate plugin compatibility
- Initialize and start plugins in dependency order
- Health-check plugins
- Restart failed plugins per policy
- Stop and unload plugins

**Boundary:** The PLM manages plugin lifecycle. What each plugin does is opaque to the Kernel.

---

## 3. What is in PLUGINS

### 3.1 Planner

**Why Plugin:** Different Goals require different planning strategies. An LLM-based planner, a template-based planner, and a human-in-the-loop planner are all valid. The Kernel should not prescribe one strategy.

**Plugin Interface:**
```
plan(goal: Goal, context: Context) → ExecutionPlan
replan(goal: Goal, current: ExecutionPlan, events: [Event]) → ExecutionPlan
```

---

### 3.2 Verifier

**Why Plugin:** Verification criteria vary by domain. A code review verifier, a security scanner, and a schema validator have nothing in common except their interface. The Kernel should not know about verification logic.

**Plugin Interface:**
```
verify(artifact: Artifact, criteria: VerificationCriteria) → Verdict
```

---

### 3.3 Policy

**Why Plugin:** Policies are domain-specific rules. A cost limit policy, a rate limit policy, and a compliance policy share no logic. The Kernel provides enforcement points; plugins provide rules.

**Plugin Interface:**
```
evaluate(event: Event, context: Context) → PolicyDecision
// PolicyDecision ∈ {Allow, Reject, Delay, Retry}
```

**Invariant**: [Invariant 15](../architecture/invariants.md#invariant-15-policies-never-change-business-logic) — Policies may only Allow, Reject, Delay, or Retry.

---

### 3.4 Scoring Strategy

**Why Plugin:** Different organizations have fundamentally different selection criteria. A fintech prioritizes compliance, a startup prioritizes cost, and a latency-sensitive application prioritizes speed. A single hardcoded scoring formula cannot serve all. The Kernel owns the scheduling pipeline (Order → Filter → Score → Policy → Select); the Scoring Strategy plugin owns only the scoring formula in Phase 3.

**Plugin Interface:**
```
score(task: Task, candidates: [AgentCandidate]) → [ScoredCandidate]
// Returns candidates with scores [0, 1], sorted best-first.
// score=0 means excluded from this scheduling round.
```

**Phase 1:** Scoring Strategy is a first-class Plugin type. The default implementation (`DefaultScoringStrategy`) uses the existing weighted formula with configurable weights. Custom strategies can replace it entirely.

---

### 3.6 Memory Provider

**Why Plugin:** Different memory backends serve different needs. In-memory for development, Redis for speed, vector DB for semantic search, PostgreSQL for durability. The Kernel needs memory; it doesn't need to know the storage engine.

**Plugin Interface:**
```
store(layer: MemoryLayer, key: String, value: Any) → Result
retrieve(layer: MemoryLayer, key: String) → Any
update(layer: MemoryLayer, key: String, value: Any) → Result
search(layer: MemoryLayer, query: String) → [MemoryEntry]
delete(layer: MemoryLayer, key: String) → Result
```

---

### 3.7 Storage Backend

**Why Plugin:** The Event Store and State Store need different backends for different scales. In-memory for Phase 1, PostgreSQL for Phase 2, Kafka+etcd for Phase 3. The Kernel just needs append/read/snapshot.

**Plugin Interface:**
```
append(stream: String, events: [Event]) → Result
read(stream: String, from: Int64, count: Int) → [Event]
snapshot(stream: String, state: State) → Result
restore(stream: String) → State
```

---

### 3.8 Protocol Adapter

**Why Plugin:** New protocols emerge. The Kernel's Runtime API must remain stable while adapters translate external protocols. Adding a new protocol should never require Kernel changes.

**Plugin Interface:**
```
translate(request: ExternalRequest) → RuntimeAPICall
translate(response: RuntimeAPIResponse) → ExternalResponse
```

**See:** [ADR-0005](../adr/ADR-0005-protocol-adapter-architecture.md) for the full rationale.

---

## 4. What is in SDK

SDKs are language-specific libraries that wrap the Runtime API for developer convenience. They are NOT part of the Runtime.

| Concern | Location |
|---------|----------|
| Runtime API definition | Kernel (API Layer) |
| HTTP/gRPC wire protocol | Protocol Adapter (Plugin) |
| Python client library | Python SDK |
| TypeScript client library | TypeScript SDK |
| Go client library | Go SDK |
| Agent base class | SDK |
| Goal submission helper | SDK |
| CLI tool | SDK or separate tool |

---

## 5. What is in ADAPTERS

Adapters translate external protocols. They contain zero business logic.

| Adapter | Protocol | Status |
|---------|----------|--------|
| HTTP Adapter | HTTP/1.1, HTTP/2 → Runtime API | Phase 1 |
| gRPC Adapter | gRPC → Runtime API | Phase 2 |
| MCP Adapter | MCP → Runtime API | Phase 2 |
| A2A Adapter | A2A → Runtime API | Phase 2 |
| WebSocket Adapter | WS → Runtime API | Phase 2 |

---

## 6. What is FUTURE

These are explicitly NOT in scope for Phase 1 or 2. They may exist in Phase 3 or as ecosystem projects.

| Concern | Status | Why Not Now |
|---------|--------|-------------|
| Multi-tenancy | Phase 3 | Requires distributed deployment |
| Agent Marketplace | Ecosystem | Not Runtime infrastructure |
| Visual Workflow Editor | Ecosystem | Not Runtime infrastructure |
| Cloud SaaS | Ecosystem | Not open-source Runtime |
| Billing | Ecosystem | Not Runtime infrastructure |
| Cross-Runtime Federation | Phase 3 | Requires A2A maturity |
| Agent Code Generation | Out of scope | SDK concern, not Runtime |

---

## 7. Boundary Enforcement

### 7.1 Compile-Time (or Load-Time) Enforcement

- Kernel modules must not import Plugin modules
- Plugin modules may import Kernel API interfaces (not Kernel internals)
- Adapters must not import business logic modules

### 7.2 Runtime Enforcement

- Plugin failure must not crash the Kernel
- Kernel API is the only interface exposed to Plugins
- Plugin-to-Plugin communication goes through Events (never direct)

---

## 8. Summary Matrix

| Component | Kernel | Plugin | SDK | Adapter | Future |
|-----------|--------|--------|-----|---------|--------|
| Event Bus | ✓ | | | | |
| Capability Registry | ✓ | | | | |
| Task Graph Engine | ✓ | | | | |
| Scheduler | ✓ | | | | |
| Execution Engine | ✓ | | | | |
| Plugin Lifecycle Manager | ✓ | | | | |
| Planner | | ✓ | | | |
| Verifier | | ✓ | | | |
| Policy | | ✓ | | | |
| Scoring Strategy | | ✓ | | | |
| Memory Provider | | ✓ | | | |
| Storage Backend | | ✓ | | | |
| Agent | | ✓ | | | |
| HTTP → Runtime API | | | | ✓ | |
| gRPC → Runtime API | | | | ✓ | |
| MCP → Runtime API | | | | ✓ | |
| A2A → Runtime API | | | | ✓ | |
| Python SDK | | | ✓ | | |
| TypeScript SDK | | | ✓ | | |
| Go SDK | | | ✓ | | |
| CLI Tool | | | ✓ | | |
| Multi-tenancy | | | | | ✓ |
| Marketplace | | | | | ✓ |
| SaaS | | | | | ✓ |

---

## 9. References

- [Architecture Invariants](../architecture/invariants.md) — Invariants 1, 6, 10 govern the Kernel boundary
- [Domain Model](./domain-model.md) — Entity definitions
- [Execution Model](./execution-model.md) — How the Kernel executes Goals
- [Scheduler](./scheduler.md) — Scheduling in the Kernel
- [Execution Engine](./execution-engine.md) — Dispatch and lifecycle
- [Event Bus](./event-bus.md) — Kernel communication backbone
- [Plugin Architecture](./plugin-architecture.md) — Plugin system design
- [Runtime API](./runtime-api.md) — Stable API contract
