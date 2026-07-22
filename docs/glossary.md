# Glossary

> The canonical definitions for all Zelos concepts. If a term appears in any Zelos document, it must match the definition here. No document may introduce alternative definitions.

---

## Core Concepts

### Goal

The highest-level unit of work submitted to the Runtime. A declaration of a desired outcome — not a specification of how to achieve it.

- **Owner**: Client (submits), Runtime (manages lifecycle)
- **Lifecycle**: Submitted → Accepted / Rejected → Planned → Executing → Completed / Failed / Cancelled
- **Related**: ExecutionPlan, Task, Artifact

### Execution Plan

A structured decomposition of a Goal into Tasks with dependencies, capability requirements, and constraints. Produced by a Planner plugin. The single source of truth for what work must be performed during Goal execution.

- **Owner**: Runtime (lifecycle), Planner (production)
- **Lifecycle**: Created → Validated / Invalid → Executing → Modified → Completed / Abandoned
- **Related**: Goal, Task, TaskGraph, Planner
- **Invariant**: [Invariant 3](architecture/invariants.md#invariant-3-execution-plan-is-the-single-source-of-truth)

### Task

The atomic unit of dispatch. One Task = one Agent invocation. Defined within an Execution Plan, requires a Capability, produces an Artifact.

- **Owner**: Runtime (lifecycle), Agent (execution)
- **Lifecycle**: Created → Ready → Assigned → Started → Completed / Failed / Cancelled / TimedOut
- **Related**: ExecutionPlan, Capability, Artifact, Agent
- **Invariant**: [Invariant 4](architecture/invariants.md#invariant-4-task-is-atomic)

### Task Graph

A directed acyclic graph (DAG) where nodes are Tasks and edges are Dependencies. The internal representation of execution order managed by the Task Graph Engine.

- **Owner**: Task Graph Engine (Kernel)
- **Related**: Task, ExecutionPlan, Scheduler

### Capability

A named, versioned, schema-described unit of work that an Agent can perform. Describes **what** can be done, not **who** does it.

- **Owner**: Agent (declares), Capability Registry (indexes), Runtime (matches)
- **Lifecycle**: Registered → Available → Unavailable / Deprecated → Removed
- **Related**: Agent, Task, CapabilityRegistry, Scheduler
- **Invariant**: [Invariant 5](architecture/invariants.md#invariant-5-capability-before-agent), [Invariant 14](architecture/invariants.md#invariant-14-capability-describes-intent-not-implementation)

### Agent

An external process — a worker. Registers Capabilities with the Runtime, receives Tasks, executes them, and returns Artifacts. Has no persistent state. Does not communicate with other agents.

- **Owner**: Agent developer (builds), Runtime (manages lifecycle connection)
- **Lifecycle**: Registered → Connected → Heartbeating → Disconnected / Shutdown
- **Responsibilities**: register(), heartbeat(), execute(), cancel(), shutdown()
- **Related**: Capability, Task, Artifact, ExecutionEngine
- **Invariant**: [Invariant 1](architecture/invariants.md#invariant-1-runtime-owns-orchestration), [Invariant 6](architecture/invariants.md#invariant-6-agent-is-stateless)

### Artifact

The structured output produced by an Agent executing a Task. Immutable once created. Passed as input to dependent tasks and to verifiers.

- **Owner**: Agent (produces), Runtime (manages lifecycle)
- **Lifecycle**: Created → Validating → Validated / Rejected → Accepted (or Created → Accepted if no verifier)
- **Related**: Task, Agent, Verifier
- **Invariant**: [Invariant 8](architecture/invariants.md#invariant-8-artifacts-are-immutable)

---

## Runtime Components

### Runtime

The entire Zelos system — the entity that accepts Goals, executes Plans, schedules Tasks, and coordinates Agents.

- **Layers**: Infrastructure → Kernel → Plugin → API → Protocol
- **Lifecycle**: Stopped → Starting → Running → Degraded → Stopping → Stopped
- **Invariant**: [Invariant 1](architecture/invariants.md#invariant-1-runtime-owns-orchestration)

### Kernel

The sealed, minimal, stable core of the Runtime. Contains only components that are irreducibly necessary for orchestration. Does not contain any replaceable business logic.

- **Components**: EventBus, CapabilityRegistry, TaskGraphEngine, Scheduler, ExecutionEngine, PluginLifecycleManager
- **Invariant**: [Invariant 10](architecture/invariants.md#invariant-10-kernel-is-plugin-oriented)

### Plugin Lifecycle Manager

The Kernel component responsible for discovering, loading, configuring, starting, health-checking, restarting, and stopping all Plugins. Enforces load order (storage → memory → policy → verifier → planner → adapter) and manages plugin lifecycle state transitions.

- **Owner**: Kernel
- **Related**: Plugin, Plugin Manifest, zelos.yaml

### Event Bus

The central communication backbone. All inter-component communication flows through events. No component calls another directly.

- **Owner**: Kernel
- **Related**: Event, EventStore
- **Invariant**: [Invariant 7](architecture/invariants.md#invariant-7-events-are-immutable), [Invariant 9](architecture/invariants.md#invariant-9-contracts-over-implementation)

### Event Store

The append-only persistence layer for Events. Supports append, read (by position or timestamp), and replay (full stream, by correlation ID, or by timestamp range). In Phase 1, implemented as an in-memory ring buffer via the Storage Backend plugin.

- **Owner**: Storage Backend (Plugin), Event Bus (consumer)
- **Related**: Event, Event Bus, Replay, Storage Backend

### Event

An immutable record of a state transition. The sole communication mechanism between components.

- **Owner**: Event Bus (manages delivery)
- **Properties**: Immutable, append-only, typed, timestamped, correlated
- **Invariant**: [Invariant 7](architecture/invariants.md#invariant-7-events-are-immutable)

### Correlation ID

A UUID that links all Events related to the same logical entity (e.g., all events for Goal G1 share the same `correlation_id`). Enables event filtering and replay scoped to a single entity.

- **Owner**: Runtime (assigns at entity creation)
- **Related**: Event, Causation ID

### Causation ID

A UUID reference to the Event that directly caused this Event (`causation_id` = the `event_id` of the preceding Event in the causal chain). Enables causal tracing: "what happened and why?"

- **Owner**: Runtime (assigns at event publication)
- **Related**: Event, Correlation ID

### Idempotency

The property that processing the same Event multiple times produces the same result as processing it once. Event handlers must be idempotent because the Event Bus delivers at-least-once. The `event_id` serves as the idempotency key.

- **Related**: Event, Event Bus, Delivery Semantics

### Subscription

A registered interest in a specific Event type, pattern, or correlation. The Event Bus delivers matching Events to the subscriber's handler. Three types: exact type (`task.completed`), pattern prefix (`task.*`), and correlation (`correlation_id = X`).

- **Owner**: Event Bus
- **Related**: Event, Event Bus

### Replay

The ability to re-process Events from the Event Store to reconstruct state, debug execution, or catch up new subscribers. Supports replay from position, timestamp, or correlation ID scope.

- **Owner**: Event Bus + Storage Backend
- **Related**: Event Store, Event Bus

### Delivery Semantics

The guarantee under which Events are delivered to subscribers. Phase 1: at-least-once (Events may be redelivered; subscribers must be idempotent). Future phases may add at-most-once and exactly-once.

- **Related**: Event Bus, Idempotency

### Heartbeat

A periodic liveness signal sent by an Agent to the Runtime. Default interval: 30 seconds. If three consecutive heartbeat intervals pass without a signal, the Agent is marked `disconnected` and its in-flight Tasks are reassessed.

- **Owner**: Agent (sends), Execution Engine (monitors)
- **Related**: Agent, Execution Engine

### Capability Registry

The Kernel component that maintains the index of all registered Capabilities and their Agent providers.

- **Owner**: Kernel
- **Responsibilities**: Registration, indexing, query, lifecycle tracking
- **Related**: Capability, Agent, Scheduler

### Task Graph Engine

The Kernel component that manages the Task state machine, dependency resolution, and graph evaluation.

- **Owner**: Kernel
- **Responsibilities**: State transitions, dependency satisfaction, graph validation, progress tracking

### Scheduler

The Kernel component that matches Ready tasks to available Agents based on Capability, cost, latency, QoS, policy, and historical performance.

- **Owner**: Kernel
- **Responsibilities**: Provider selection, scoring, constraint enforcement, retry evaluation
- **Invariant**: [Invariant 5](architecture/invariants.md#invariant-5-capability-before-agent)

### Execution Engine

The Kernel component that dispatches Tasks to Agents, monitors execution lifecycle, and enforces timeouts and heartbeats.

- **Owner**: Kernel
- **Responsibilities**: Dispatch, lifecycle monitoring, heartbeat tracking, cancellation

---

## Plugin Concepts

### Plugin

Any replaceable component that extends the Runtime's behavior. All business logic lives in plugins.

- **Owner**: Plugin developer (builds), Plugin Lifecycle Manager (manages)
- **Lifecycle**: Unloaded → Loaded → Configured → Initialized → STARTING → RUNNING / ERROR / PAUSED → STOPPING → Stopped → Unloaded
- **Invariant**: [Invariant 10](architecture/invariants.md#invariant-10-kernel-is-plugin-oriented)

### Planner

A Plugin that decomposes a Goal into an Execution Plan. Different planners exist for different goal types and strategies.

- **Type**: Plugin
- **Responsibilities**: plan(goal) → ExecutionPlan, replan(goal, current, events) → ExecutionPlan
- **Related**: Goal, ExecutionPlan

### Verifier

A Plugin that validates an Artifact against criteria. Acts as a quality gate before dependent tasks proceed.

- **Type**: Plugin
- **Responsibilities**: verify(artifact, criteria) → Verdict
- **Related**: Artifact, Task

### Policy

A Plugin that evaluates whether an operation is permitted, and may Allow, Reject, Delay, or Retry. Cannot modify Plans or Tasks.

- **Type**: Plugin
- **Responsibilities**: evaluate(event, context) → PolicyDecision
- **Invariant**: [Invariant 15](architecture/invariants.md#invariant-15-policies-never-change-business-logic)

### Scoring Strategy

A Plugin that ranks Agent candidates for Task dispatch in Phase 3 of the Scheduler pipeline. Receives all candidates that passed Filter (Phase 2) and returns a scored, sorted list. The default strategy uses a weighted multi-factor formula with configurable weights. Custom strategies can implement any ranking logic — cost-first, compliance-first, round-robin, or ML-based.

- **Type**: Plugin
- **Responsibilities**: score(task, candidates) → [ScoredCandidate]
- **Related**: Scheduler, Agent, Task

### Memory Provider

A Plugin that stores and retrieves context across different memory layers and time horizons.

- **Type**: Plugin
- **Related**: Memory Layer (Session, Project, User, Knowledge, Execution, Skill)

### Protocol Adapter

A Plugin that translates between an external protocol and the internal Runtime API. Contains no business logic.

- **Type**: Plugin
- **Related**: Runtime API, Protocol Layer

### Storage Backend

A Plugin that provides persistent storage for Events and Runtime state. Implements `append(stream, events)`, `read(stream, from, count)`, and `snapshot(stream, state)`. In Phase 1, implemented as an in-memory ring buffer.

- **Type**: Plugin
- **Related**: Event Store, Event Bus

---

## Execution Concepts

### DAG (Directed Acyclic Graph)

The data structure underlying the Task Graph. Vertices (V) are Tasks; edges (E) are Dependencies. The DAG invariant (no cycles) is enforced at plan creation and every subsequent modification.

- **Related**: Task Graph, Task, Dependency, Execution Plan

### Dependency

A directed edge in the Task Graph from a prerequisite Task to a dependent Task. Types: `hard` (blocks dependent until completed), `soft` (preference, Phase 2), `conditional` (runtime-evaluated, Phase 2). Phase 1 supports hard dependencies only.

- **Owner**: Task Graph Engine
- **Related**: Task, Task Graph, DAG

### Scheduling

The process of matching Ready tasks to available Agents. Performed by the Scheduler.

- **Phases**: Ordering → Filtering → Scoring → Policy Evaluation → Selection

### Retry

The process of re-executing a failed Task. Policy-driven, managed by the Runtime. The Agent does not decide to retry.

- **Strategy**: Exponential backoff with jitter: `base_ms * 2^attempt + random_jitter`
- **Owner**: Runtime (Scheduler)

### Verification

The process of validating an Artifact against defined criteria. Performed by a Verifier plugin. Acts as a gate in the execution process.

### Timeout

A deadline for Task completion. Enforced by the Execution Engine. If exceeded, the Task transitions to TimedOut.

---

## Memory Concepts

### Memory Layer

A logical partition of memory with a specific scope and lifetime.

| Layer | Scope | Lifetime |
|-------|-------|----------|
| Session | Single Goal execution | Goal lifespan |
| Project | All Goals in a project | Project lifespan |
| User | All Goals for a user | User lifespan |
| Knowledge | Cross-user reference knowledge | Persistent |
| Execution | Task-level operational context | Task lifespan |
| Skill | Reusable patterns and procedures | Persistent |

### Context

The set of Memory entries relevant to a specific Task, assembled by the Runtime before Task dispatch.

---

## Protocol Concepts

### Runtime API

The stable, versioned, internal contract between the Runtime Kernel and all Plugins. Transport-agnostic. Comprises five API groups: Goal API, Agent API, Admin API, Plugin API, and Plan API.

### Goal API

The Client → Runtime API for submitting and managing Goals. Operations: `SubmitGoal`, `GetGoalStatus`, `ListGoals`, `CancelGoal`, `WatchGoal`.

- **Owner**: Runtime (provides), Client / SDK (consumes)
- **Related**: Goal, Runtime API

### Agent API

The Runtime ↔ Agent protocol for Agent lifecycle and Task execution. Operations: `Register`, `Heartbeat`, `Execute` (Runtime → Agent), `SubmitResult` (Agent → Runtime), `Cancel`, `Shutdown`.

- **Owner**: Runtime (provides), Agent (implements)
- **Related**: Agent, Task, Artifact, Runtime API

### Admin API

The Operator → Runtime API for monitoring and management. Operations: `ListAgents`, `GetAgent`, `ListCapabilities`, `GetCapability`, `ListActiveGoals`, `GetMetrics`, `GetHealth`, `ListPlugins`, `ConfigurePlugin`.

- **Owner**: Runtime (provides), Operator / Dashboard (consumes)
- **Related**: Runtime API

### Plugin API

The Runtime ↔ Plugin interface. Defines type-specific contracts: `plan()` / `replan()` for Planners, `verify()` for Verifiers, `evaluate()` for Policies, `store()` / `retrieve()` / `search()` for Memory Providers, `append()` / `read()` / `snapshot()` for Storage Backends.

- **Owner**: Runtime (defines interface), Plugin (implements)
- **Related**: Plugin, Runtime API

### API Versioning

The strategy for evolving the Runtime API without breaking existing clients. Follows `v{MAJOR}.{MINOR}`: MAJOR for breaking changes (old versions deprecated but supported for N releases), MINOR for additive backward-compatible changes. Agents declare `protocol_version` at registration; the Runtime validates compatibility.

- **Related**: Runtime API, Schema Version

### Schema Version

A semantic version string embedded in every JSON Schema document and data instance (`schema_version: "1.0.0"`). Governs the structure of serialized data. Schema changes require version bumps per Invariant 11.

- **Related**: Runtime API, API Versioning

### Protocol Adapter

Translates between an external wire protocol (HTTP, gRPC, MCP, A2A) and the Runtime API.

### SDK

A language-specific library that encapsulates the Runtime API for developer convenience. Not part of the Runtime.

---

## Constraint Concepts

### Constraint

A condition that limits execution. Can be applied to Goals, Plans, or Tasks.

| Constraint Type | Example |
|----------------|---------|
| Budget | Maximum cost for execution |
| Deadline | Latest acceptable completion time |
| Priority | Relative importance (low, medium, high, critical) |
| Concurrency | Maximum simultaneous tasks |
| Resource | Memory, CPU, GPU limits |

### Budget

A Goal- or Plan-level constraint specifying the maximum cost allowed for execution. Defined as a currency + max_amount. Enforced by the Scheduler (cumulative Task cost tracking). When exceeded, the Goal transitions to `failed`.

- **Type**: Constraint
- **Related**: Goal, Execution Plan, Scheduler

### Deadline

A Goal- or Plan-level constraint specifying the latest acceptable completion timestamp. Enforced by the Scheduler on each scheduling round. When exceeded, the Goal transitions to `failed`.

- **Type**: Constraint
- **Related**: Goal, Execution Plan, Scheduler, Timeout

### QoS

Quality of Service — declared performance characteristics of a Capability. Includes latency, cost, availability, and accuracy.

---

## Document Cross-Reference

| Term | Blueprint | ADR | RFC | Schema |
|------|-----------|-----|-----|--------|
| Goal | [Domain Model](blueprint/domain-model.md), [Execution Model](blueprint/execution-model.md) | [ADR-0001](adr/ADR-0001-runtime-first.md) | [RFC-0001](rfc/rfc-0001-goal-execution-lifecycle.md) | [goal.json](schema/goal.json) |
| Execution Plan | [Domain Model](blueprint/domain-model.md), [Execution Model](blueprint/execution-model.md) | [ADR-0003](adr/ADR-0003-execution-plan-first.md) | [RFC-0001](rfc/rfc-0001-goal-execution-lifecycle.md) | [execution-plan.json](schema/execution-plan.json) |
| Task | [Domain Model](blueprint/domain-model.md), [Task Graph](blueprint/task-graph.md) | [ADR-0003](adr/ADR-0003-execution-plan-first.md) | [RFC-0001](rfc/rfc-0001-goal-execution-lifecycle.md) | [task.json](schema/task.json) |
| Capability | [Domain Model](blueprint/domain-model.md), [Capability Registry](blueprint/capability-registry.md) | [ADR-0002](adr/ADR-0002-capability-first.md) | [RFC-0004](rfc/rfc-0004-capability-semantics.md) | [capability.json](schema/capability.json) |
| Agent | [Domain Model](blueprint/domain-model.md) | [ADR-0001](adr/ADR-0001-runtime-first.md) | [RFC-0002](rfc/rfc-0002-agent-registration-protocol.md) | [agent.json](schema/agent.json), [agent-registration.json](schema/agent-registration.json) |
| Artifact | [Domain Model](blueprint/domain-model.md) | — | — | [artifact.json](schema/artifact.json) |
| Event | [Domain Model](blueprint/domain-model.md), [Event Bus](blueprint/event-bus.md) | — | [RFC-0003](rfc/rfc-0003-event-bus-specification.md) | [event.json](schema/event.json) |
| Python SDK | [Python SDK](blueprint/python-sdk.md) | — | [RFC-0002](rfc/rfc-0002-agent-registration-protocol.md) | — |

---

## Forbidden Terminology

The following terms must NOT appear in any Zelos document. They are either legacy terms from other frameworks or imprecise alternatives to canonical Zelos terminology.

| Forbidden Term | Use Instead | Reason |
|---------------|-------------|--------|
| Workflow | Execution Plan | Workflow implies static DAG; Plan is dynamic |
| Job | Task | Job is too generic |
| Skill | Capability | Skill implies learning; Capability is declared |
| Chain | Execution Plan (sequential tasks) | Chain implies LLM prompt chain |
| Pipeline | Task Graph (DAG) | Pipeline implies linear stages |
| Step | Task | Step is informal |
| Orchestrator | Runtime | The Runtime is the orchestrator, not a component |
| Worker | Agent | Worker is too generic |
| Tool | Capability (if describing agent ability) or MCP Tool (if specifically MCP) | Tool is ambiguous |
| Model | Agent (if describing an LLM) | The Runtime doesn't know about models |
| Prompt | Task description | Prompts are agent internals |
