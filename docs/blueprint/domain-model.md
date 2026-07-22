# Domain Model

> Complete domain entity definitions. Every concept in Zelos is defined here. All other documents reference these definitions.

---

## Document Status

| Status  | Author                     | Date       |
|---------|----------------------------|------------|
| Revised | Zelos Architecture Team  | 2026-07-19 |

---

## 1. Entity Relationship Diagram

```
                        ┌──────────────┐
                        │    GOAL      │
                        │  (submitted  │
                        │   by client) │
                        └──────┬───────┘
                               │ 1
                               │ produces
                               ▼ 1
                        ┌──────────────┐
                        │  EXECUTION   │
                        │    PLAN      │
                        │ (derived by  │
                        │   Planner)   │
                        └──────┬───────┘
                               │ 1
                               │ contains
                               ▼ *
                        ┌──────────────┐
               ┌───────│     TASK     │───────┐
               │       │  (atomic     │       │
               │       │   unit of    │       │
               │       │   dispatch)  │       │
               │       └──────┬───────┘       │
               │              │               │
               │ requires     │ produces      │ depends on
               │ 1            │ 1             │ *
               ▼              ▼               │
        ┌──────────────┐ ┌──────────┐        │
        │  CAPABILITY  │ │ ARTIFACT │        │
        │  (declared   │ │(immutable│        │
        │   by Agent)  │ │ output)  │        │
        └──────┬───────┘ └──────────┘        │
               │                             │
               │ * provides                  │
               ▼ 1                           │
        ┌──────────────┐                     │
        │    AGENT     │                     │
        │  (stateless  │                     │
        │   executor)  │                     │
        └──────────────┘                     │
                                             │
        ┌────────────────────────────────────┘
        │
        ▼
  ┌──────────┐     ┌──────────┐     ┌──────────┐
  │ SCHEDULER│────▶│CAPABILITY│     │  EVENT   │
  │ (matches │     │ REGISTRY │     │   BUS    │
  │  task→   │     │ (indexes │     │ (all comm│
  │  agent)  │     │  caps)   │     │  via     │
  └──────────┘     └──────────┘     │ events)  │
                                    └──────────┘
  ┌──────────┐     ┌──────────┐
  │EXECUTION │     │  TASK    │
  │  ENGINE  │     │  GRAPH   │
  │(dispatch │     │  ENGINE  │
  │ lifecycle│     │  (DAG)   │
  └──────────┘     └──────────┘
```

---

## 2. Entity Definitions

### 2.1 Goal

| Attribute | Value |
|-----------|-------|
| **Definition** | The highest-level unit of work — a declaration of a desired outcome submitted to the Runtime |
| **Owner** | Client (submits), Runtime (manages full lifecycle) |
| **Identity** | `goal_id` (UUID, assigned by Runtime on acceptance) |

#### Lifecycle

```
Submitted ──→ Accepted ──→ Planned ──→ Executing ──→ Completed
   │              │            │            │
   └──→ Rejected  │            │            ├──→ Failed
                  └──→ Failed  │            └──→ Cancelled
                               │
                               ├──→ Cancelled
                               └──→ Failed
```

| State | Description |
|-------|-------------|
| `submitted` | Goal received by Runtime, not yet validated |
| `accepted` | Goal validated, waiting for planning |
| `rejected` | Goal validation failed (terminal) |
| `planned` | Execution Plan created and validated |
| `executing` | At least one Task has been dispatched |
| `completed` | All terminal Tasks completed successfully (terminal) |
| `failed` | Execution failed beyond recovery (terminal) |
| `cancelled` | Execution cancelled by client or system (terminal). Note: `cancelling` is an internal transient state not exposed as a formal lifecycle state — it represents the window between receiving a cancel signal and all Tasks acknowledging cancellation. |

#### Responsibilities

| Responsibility | Description |
|---------------|-------------|
| Declare intent | The Goal describes WHAT to achieve, not HOW |
| Carry constraints | Budget, deadline, priority, context |
| Anchor execution | All Tasks derive from this Goal |
| Track progress | Goal status reflects aggregate Task status |

#### Relationships

| Target | Cardinality | Description |
|--------|-------------|-------------|
| ExecutionPlan | 1:1 | One active plan per Goal |
| Task | 1:N (via Plan) | Goal contains Tasks through its Plan |

---

### 2.2 Execution Plan

| Attribute | Value |
|-----------|-------|
| **Definition** | A structured decomposition of a Goal into Tasks with dependencies. The single source of truth during execution. |
| **Owner** | Planner (produces), Runtime (validates, manages, modifies) |
| **Identity** | `plan_id` (UUID) |

#### Lifecycle

```
Created ──→ Validated ──→ Executing ──→ Completed
   │            │              │             │
   │            │              └──→ Abandoned│
   └──→ Invalid └──→ Abandoned               │
                    (goal cancelled)          │
                                             │
                    Modified ←────────────────┘
                        │
                        └──→ Executing (continues)
```

| State | Description |
|-------|-------------|
| `created` | Planner produced the plan |
| `validated` | Plan passed structural validation (DAG, schemas) |
| `invalid` | Plan failed validation (terminal) |
| `executing` | Plan is the active source of truth |
| `modified` | Plan was updated during execution (transient, returns to executing) |
| `completed` | All Tasks reached terminal state (terminal) |
| `abandoned` | Goal cancelled or failed (terminal) |

#### Responsibilities

| Responsibility | Description |
|---------------|-------------|
| Define work | List all Tasks needed to achieve the Goal |
| Define order | Specify Task dependencies (DAG edges) |
| Define requirements | Specify Capability requirements per Task |
| Define constraints | Set per-Task and plan-level constraints |
| Track progress | Provide the basis for execution observability |

#### Relationships

| Target | Cardinality | Description |
|--------|-------------|-------------|
| Goal | N:1 | Plan belongs to one Goal |
| Task | 1:N | Plan contains many Tasks |
| Planner | N:1 | Plan is produced by one Planner |

---

### 2.3 Task

| Attribute | Value |
|-----------|-------|
| **Definition** | The atomic unit of dispatch. One Task = one Agent invocation. |
| **Owner** | Runtime (full lifecycle), Agent (execution only) |
| **Identity** | `task_id` (UUID) |

#### Lifecycle

```
                         ┌──────────┐
                         │ Created  │
                         └────┬─────┘
                              │ dependencies_met()
                         ┌────▼─────┐
                    ┌───→│  Ready   │←──────────────┐
                    │    └────┬─────┘               │
                    │         │ scheduler.assign()  │
                    │    ┌────▼─────┐               │
                    │    │ Assigned │               │
                    │    └────┬─────┘               │
                    │         │ agent.accepts()     │
                    │    ┌────▼─────┐               │
                    │    │ Started  │               │
                    │    └────┬─────┘               │
                    │         │                     │
                    │    ┌────┼────────────┐        │
                    │    │    │            │        │
                    │    ▼    ▼            ▼        │
                    │ ┌────┐┌──────┐┌──────────┐   │
                    │ │Comp││Failed││TimedOut  │   │
                    │ └──┬─┘└──┬───┘└────┬─────┘   │
                    │    │     │         │         │
                    │    ▼     ▼         ▼         │
                    │ ┌──────────────┐             │
                    │ │Retry Policy  │─────────────┘
                    │ │Evaluation    │
                    │ └──────┬───────┘
                    │        │ retry_exhausted
                    │        ▼
                    │  ┌──────────┐
                    └──│  Failed  │ (terminal)
                       └──────────┘

                       ┌──────────┐
                       │Completed │ (terminal)
                       └──────────┘
                       ┌──────────┐
                       │Cancelled │ (terminal)
                       └──────────┘
```

| State | Description | Can be Scheduled? |
|-------|-------------|-------------------|
| `created` | Task exists, dependencies not yet met | No |
| `ready` | All dependencies satisfied, waiting for scheduling | Yes |
| `assigned` | Scheduler selected an Agent, waiting for acceptance | No |
| `started` | Agent accepted and is executing | No |
| `completed` | Agent returned Artifact, verification passed (if applicable) | No (terminal) |
| `failed` | Retry exhausted, no recovery | No (terminal) |
| `cancelled` | Task cancelled | No (terminal) |
| `timed_out` | Task exceeded its deadline | No (can transition to Ready on retry) |

#### Responsibilities

| Responsibility | Description |
|---------------|-------------|
| Define work unit | A single, atomic piece of work |
| Declare requirement | Specify which Capability is needed |
| Carry constraints | Timeout, retry policy, budget, priority |
| Declare dependencies | Which other Tasks must complete first |
| Produce (via Agent) | An Artifact as output |

#### Task Constraints

| Constraint | Type | Description |
|-----------|------|-------------|
| `timeout_ms` | Duration | Maximum execution time |
| `max_retries` | Integer | Maximum retry attempts |
| `backoff_base_ms` | Duration | Base interval for exponential backoff |
| `max_cost_per_call` | Float | Cost ceiling per execution |
| `max_latency_ms` | Duration | Latency ceiling |
| `priority` | Enum | low, medium, high, critical |
| `fallback_capability` | CapabilityRef | Alternative if primary capability fails |
| `preferred_agent_id` | UUID | Force specific agent (admin override) |
| `excluded_agent_ids` | [UUID] | Blacklist |
| `min_success_rate` | Float [0,1] | Minimum historical success rate |
| `required_tags` | [String] | Agent must have all tags |

#### Relationships

| Target | Cardinality | Description |
|--------|-------------|-------------|
| ExecutionPlan | N:1 | Task belongs to one Plan |
| Capability | N:1 | Task requires one Capability type |
| Artifact | 1:1 | Task produces one Artifact |
| Agent | N:1 (at a time) | Task is assigned to one Agent |
| Task (dependency) | N:N | Tasks depend on other Tasks |

---

### 2.4 Capability

| Attribute | Value |
|-----------|-------|
| **Definition** | A named, versioned, schema-described unit of work that an Agent can perform |
| **Owner** | Agent (declares), Capability Registry (indexes), Runtime (matches) |
| **Identity** | `(name, version)` tuple |

#### Lifecycle

```
Registered ──→ Available ──→ Deprecated ──→ Removed
                  │
                  └──→ Unavailable (agent disconnected)
                         │
                         └──→ Available (agent reconnected)
```

| State | Description | Scheduler Behavior |
|-------|-------------|-------------------|
| `registered` | Capability declared, agent not yet available | Excluded |
| `available` | Agent connected and heartbeating | Normal consideration |
| `unavailable` | Agent disconnected | Excluded until reconnection |
| `deprecated` | Phasing out | Deprioritized (use only if no alternative) |
| `removed` | No longer offered | Excluded permanently |

#### Capability Naming Convention

```
{domain}.{subdomain}[.{specific}...]

Top-Level Domains:
  code-generation      — Producing source code
  code-review          — Reviewing source code
  code-transformation  — Refactoring, translating, optimizing
  research             — Finding and synthesizing information
  analysis             — Analyzing data, code, or text
  design               — Producing design artifacts
  automation           — Performing automated actions
  communication        — Generating messages, summaries, reports
  reasoning            — Logical reasoning, planning, decision-making
  verification         — Validating correctness of artifacts

Examples:
  code-generation.python
  code-review.security
  research.web-search
  automation.browser
  design.architecture
```

#### Responsibilities

| Responsibility | Description |
|---------------|-------------|
| Describe intent | WHAT work can be done |
| Define contract | Input and output JSON Schema |
| Declare QoS | Latency, cost, availability claims |
| Declare capacity | How many concurrent tasks the agent can handle |

#### Relationships

| Target | Cardinality | Description |
|--------|-------------|-------------|
| Agent | N:1 | Capability is provided by one Agent |
| Task | 1:N | Many Tasks may require this Capability |

---

### 2.5 Agent

| Attribute | Value |
|-------|-----------|
| **Definition** | An external process that registers Capabilities, receives Tasks, executes them, and returns Artifacts |
| **Owner** | Agent developer (builds), Runtime (manages connection lifecycle) |
| **Identity** | `agent_id` (UUID, assigned at registration) |

#### Lifecycle

```
Registered ──→ Connected ──→ Heartbeating ──→ Disconnected
                  │              │       │         │
                  └──→ Shutdown  │       │         │
                                 │       │         │
                    ┌────────────┘       │         │
                    │                    │         │
                    ▼                    ▼         │
                  Idle ←────────────── Busy       │
                    │                    │         │
                    └────────────────────┘         │
                     (operational sub-states)      │
                                                   │
                  Shutdown ←───────────────────────┘
```

| State | Description |
|-------|-------------|
| `registered` | Agent has registered capabilities with the Runtime |
| `connected` | Connection established, not yet heartbeating |
| `heartbeating` | Agent is sending regular heartbeats, eligible for dispatch |
| `disconnected` | Connection lost (heartbeat timeout or network) |
| `shutdown` | Agent voluntarily disconnected (terminal for this session) |

**Operational sub-states of `heartbeating`:**

| Sub-state | Description |
|-----------|-------------|
| `idle` | Agent is heartbeating but has no in-flight Tasks. Ready for immediate dispatch. |
| `busy` | Agent has at least one in-flight Task. May still accept more if `current_tasks < max_concurrent_tasks`. |

These sub-states inform the Scheduler's load-balancing: idle agents are preferred over busy agents (via the `load_score` factor).

#### Contract (Runtime API)

```
register(capabilities)  → RegistrationResponse
heartbeat()             → HeartbeatResponse
execute(task)           → Artifact
cancel(task_id)         → CancelResponse
shutdown()              → void
```

#### Responsibilities

| Responsibility | Description |
|---------------|-------------|
| Register capabilities | Declare what work this Agent can perform |
| Heartbeat | Prove liveness at configured interval |
| Execute tasks | Receive task, perform work, return artifact |
| Handle cancellation | Stop work on a specified task |
| Graceful shutdown | Notify Runtime before disconnecting |

#### What an Agent Must NOT Do

- Schedule tasks
- Invoke other agents
- Manage memory / context
- Retry failed tasks
- Modify the Execution Plan
- Know about other agents
- Know about the Task Graph topology

#### Relationships

| Target | Cardinality | Description |
|--------|-------------|-------------|
| Capability | 1:N | Agent provides many Capabilities |
| Task | 1:N | Agent executes many Tasks over its lifetime |
| Artifact | 1:N | Agent produces many Artifacts |

---

### 2.6 Artifact

| Attribute | Value |
|-----------|-------|
| **Definition** | The structured, immutable output produced by an Agent executing a Task |
| **Owner** | Agent (produces), Runtime (stores, manages lifecycle), Verifier (validates) |
| **Identity** | `artifact_id` (UUID) |

#### Lifecycle

```
Created ──→ Validated (optional) ──→ Accepted
   │              │
   │              └──→ Rejected (triggers retry)
   │
   └──→ Accepted (if no verifier configured)
```

| State | Description |
|-------|-------------|
| `created` | Artifact produced by Agent |
| `validating` | Verifier is evaluating |
| `validated` | Verification passed |
| `rejected` | Verification failed |
| `accepted` | Final state, available for dependent Tasks |

#### Responsibilities

| Responsibility | Description |
|---------------|-------------|
| Carry result | The output of a Task execution |
| Carry metadata | Execution time, cost, tokens used, model used |
| Enable verification | Structured format for Verifier inspection |
| Feed dependents | Input to Tasks that depend on this Task |

#### Relationships

| Target | Cardinality | Description |
|--------|-------------|-------------|
| Task | N:1 | Artifact produced by one Task |
| Agent | N:1 | Artifact produced by one Agent |

---

### 2.7 Event

| Attribute | Value |
|-----------|-------|
| **Definition** | An immutable record of a state transition in the Runtime |
| **Owner** | Event Bus (manages delivery), publishing component (creates) |
| **Identity** | `event_id` (UUID) |

#### Properties

| Property | Description |
|----------|-------------|
| Immutable | Cannot be modified after publication |
| Append-only | New events are appended to the Event Store |
| Typed | Hierarchical type system (domain.entity.action) |
| Timestamped | Publication time recorded |
| Correlated | Events related to the same entity share a correlation_id |
| Causal | Causation chain via causation_id |

#### Event Type Taxonomy

```
runtime.started           runtime.stopped           runtime.degraded
goal.submitted            goal.accepted             goal.rejected
goal.planned              goal.executing            goal.completed
goal.failed               goal.cancelled
plan.created              plan.validated            plan.invalid
plan.executing            plan.modified             plan.completed
plan.abandoned
task.created              task.ready                task.assigned
task.started              task.completed            task.failed
task.cancelled            task.timed_out
artifact.created          artifact.validated        artifact.rejected
agent.registered          agent.connected           agent.disconnected
agent.heartbeat
capability.registered     capability.available      capability.unavailable
capability.deprecated     capability.removed
verification.requested    verification.completed    verification.needs_review
plugin.loaded             plugin.started            plugin.failed
plugin.stopped
```

#### Relationships

| Target | Cardinality | Description |
|--------|-------------|-------------|
| Entity (Goal, Task, etc.) | N:1 | Event records a state transition of an entity |
| Event (causation) | N:1 | Event caused by a previous event |

---

## 3. Kernel Components

### 3.1 Event Bus

| Attribute | Value |
|-----------|-------|
| **Definition** | Central pub/sub message backbone. Sole communication channel between all components. |
| **Owner** | Kernel |
| **Responsibilities** | Publish, subscribe, deliver, persist, replay events |

### 3.2 Capability Registry

| Attribute | Value |
|-----------|-------|
| **Definition** | Index of all registered Capabilities and their Agent providers |
| **Owner** | Kernel |
| **Responsibilities** | Register capabilities, index by name/tag/version, query for matching, track lifecycle |

### 3.3 Task Graph Engine

| Attribute | Value |
|-----------|-------|
| **Definition** | Manages the Task state machine and dependency graph |
| **Owner** | Kernel |
| **Responsibilities** | State transitions, dependency resolution, DAG validation, progress tracking |

### 3.4 Scheduler

| Attribute | Value |
|-----------|-------|
| **Definition** | Matches Ready tasks to available Agents based on capability, constraints, and optimization criteria |
| **Owner** | Kernel |
| **Responsibilities** | Provider selection, scoring, constraint enforcement, retry evaluation |

### 3.5 Execution Engine

| Attribute | Value |
|-----------|-------|
| **Definition** | Dispatches Tasks to Agents, monitors execution, enforces timeouts and heartbeats |
| **Owner** | Kernel |
| **Responsibilities** | Dispatch, lifecycle monitoring, heartbeat tracking, cancellation, artifact collection |

### 3.6 Plugin Lifecycle Manager

| Attribute | Value |
|-----------|-------|
| **Definition** | Loads, configures, health-checks, and manages the lifecycle of all plugins |
| **Owner** | Kernel |
| **Responsibilities** | Plugin discovery, loading, configuration, health monitoring, restart, shutdown |

---

## 4. Plugin Components

| Plugin Type | Interface | Responsibility |
|-------------|-----------|---------------|
| **Planner** | `plan(goal) → ExecutionPlan` | Goal decomposition into Tasks |
| **Verifier** | `verify(artifact, criteria) → Verdict` | Artifact quality validation |
| **Policy** | `evaluate(event, context) → Decision` | Allow / Reject / Delay / Retry |
| **Scoring Strategy** | `score(task, candidates) → [ScoredCandidate]` | Custom Agent ranking for scheduling |
| **Memory Provider** | `store() / retrieve() / search() / update()` | Context storage and retrieval |
| **Storage Backend** | `append() / read() / snapshot()` | Event and state persistence |
| **Protocol Adapter** | `translate(external) → Runtime API` | External protocol translation |
| **Agent** | `register() / heartbeat() / execute() / cancel() / shutdown()` | Async execution provider. Agents are plugins that connect asynchronously rather than being loaded at startup. |

---

## 5. Cross-Cutting Rules

1. All ownership is exclusive. No entity has two owners.
2. All relationships are navigable in one direction (no circular ownership).
3. All lifecycles are finite state machines with defined terminal states.
4. All identity is UUID — no natural keys, no compound keys.
5. All timestamps are RFC 3339.
6. All schemas are versioned JSON Schema (draft 2020-12).

---

## 6. References

- [Architecture Invariants](../architecture/invariants.md) — All invariants govern these definitions
- [Glossary](../glossary.md) — Canonical term definitions
- [Kernel Boundary](./kernel-boundary.md) — What is Kernel vs. Plugin
- [Execution Model](./execution-model.md) — How these entities execute
- [Task Graph](./task-graph.md) — Task state machine and DAG details
- [Capability Registry](./capability-registry.md) — Capability lifecycle details
- [Scheduler](./scheduler.md) — Provider selection details
- [Execution Engine](./execution-engine.md) — Dispatch and lifecycle details
- [Event Bus](./event-bus.md) — Event system details
- [Memory Architecture](./memory-architecture.md) — Memory layers and providers
- [Plugin Architecture](./plugin-architecture.md) — Plugin system details
- [Runtime API](./runtime-api.md) — Runtime API contract
- [Protocol Layer](./protocol-layer.md) — Protocol adapter details
