# Architecture Invariants

> The constitution of Zelos. Every document, decision, and implementation must conform to these invariants. They are non-negotiable.

---

## Purpose

This document defines the **Architecture Invariants** of Zelos — principles that can never be violated by any design decision, implementation choice, or future evolution of the project.

An Invariant is not a guideline. It is not a best practice. It is not a preference.

An Invariant is a **binding constraint** on the architecture.

All other documents — ADRs, Blueprints, RFCs, Schemas — derive their authority from this document and must cite the relevant invariants they satisfy.

---

## Invariant 1: Runtime Owns Orchestration

**Statement:**

The Runtime is the sole owner of all orchestration responsibilities. Agents are execution plugins only.

**Runtime owns:**

| Responsibility | Description |
|---------------|-------------|
| Scheduling | Deciding which task runs when, on which agent |
| Retry | Deciding whether, when, and how to retry a failed task |
| Verification | Deciding which verifiers to invoke and how to act on results |
| Memory | Storing, retrieving, and managing all context |
| Policy | Enforcing rules and constraints on execution |
| Execution Lifecycle | Managing task state transitions from creation to completion |
| Context Assembly | Gathering and providing relevant context to agents |
| Plan Management | Creating, validating, and modifying execution plans |

**Agent owns:**

| Responsibility | Description |
|---------------|-------------|
| Task Reception | Accepting a fully-formed task from the Runtime |
| Execution | Performing the work described by the task |
| Artifact Production | Returning a structured artifact as the result |

**An Agent must never:**

- Schedule a task
- Invoke another agent
- Manage memory
- Retry a failed task
- Modify the execution plan
- Know about the workflow topology
- Discover or select other agents

**Violation example:**

An Agent that, upon encountering an error, decides to retry with a different approach and dispatches a sub-task to another agent. This is forbidden.

**Correct behavior:**

The Agent reports failure. The Runtime evaluates the retry policy. The Runtime may re-dispatch the task to a different agent.

---

## Invariant 2: Goal is the First-Class Abstraction

**Statement:**

The Runtime accepts a **Goal** as its primary unit of work. Not a workflow. Not a DAG. Not a prompt chain.

**Definition:**

A Goal is a declaration of a desired outcome. It is the highest-level unit of work in Zelos.

**The Execution Plan is derived, not submitted:**

The Runtime (via a Planner plugin) derives an Execution Plan from the Goal. The client does not submit an Execution Plan directly — though they may provide constraints and preferences.

**Why:**

Goals express intent. Plans express method. The Runtime must own the method to guarantee correct execution. If the client submits a plan, the Runtime becomes a mere executor — not an orchestrator.

**Exception (acknowledged):**

In Phase 1, a client MAY submit a manually-defined Execution Plan to bootstrap the system before a Planner plugin is available. This is a development convenience, not an architectural pattern.

---

## Invariant 3: Execution Plan is the Single Source of Truth

**Statement:**

During the execution of a Goal, the Execution Plan is the single source of truth for what work must be performed, in what order, and by what capabilities.

**Every component must reference the Plan:**

- The Scheduler reads Ready tasks from the Plan
- The Task Graph Engine enforces Plan dependencies
- The Verifier validates artifacts against Plan expectations
- Observability reports progress against the Plan

**No component may bypass the Plan:**

- The Scheduler cannot create tasks
- The Execution Engine cannot modify dependencies
- Agents cannot add tasks to the Plan

**Plan modification is governed:**

The Plan may be modified during execution, but only through a defined modification protocol: Planner proposes → Runtime validates → Plan updated → `ExecutionPlanModified` event published. No ad-hoc modification.

---

## Invariant 4: Task is Atomic

**Statement:**

A Task is the smallest unit of dispatch in Zelos. One Task = one Agent invocation.

**Within a single Task:**

- Exactly one Agent is invoked
- The Agent receives one input and produces one output (Artifact)
- The Agent cannot spawn sub-tasks
- The Agent cannot call other agents
- The Agent cannot modify the Task Graph

**Why:**

Atomicity is required for scheduling, retry, verification, and observability. If a Task can spawn arbitrary sub-work, the Runtime loses control over execution. The Task Graph becomes incomplete, the Scheduler cannot optimize globally, and retry semantics become undefined.

**If an Agent discovers it needs additional work:**

The Agent reports this in its Artifact. The Verifier or a policy may trigger plan modification. The Planner adds new Tasks. Normal scheduling proceeds.

---

## Invariant 5: Capability Before Agent

**Statement:**

Dispatch is always by Capability, never by Agent identity.

**The dispatch chain:**

```
Task (requires Capability)
  → Capability Registry (finds Providers)
    → Scheduler (selects best Provider)
      → Agent (receives Task)
```

**The forbidden dispatch chain:**

```
Task
  → Agent Name ("send this to Claude")
```

**Why:**

Capability-based dispatch enables provider independence, multi-vendor support, fallback, optimization, and ecosystem growth. Name-based dispatch creates tight coupling and eliminates all of these properties.

**The Scheduler may consider Agent identity as a scoring factor (affinity, history), but never as a dispatch requirement.**

---

## Invariant 6: Agent is Stateless

**Statement:**

An Agent owns no persistent state. All state is owned by the Runtime.

**An Agent does not own:**

| State | Owner |
|-------|-------|
| Workflow / Plan | Runtime |
| Memory / Context | Runtime (Memory Providers) |
| Task Graph | Runtime (Task Graph Engine) |
| Scheduling decisions | Runtime (Scheduler) |
| Retry state | Runtime (Execution Engine) |
| Verification state | Runtime (Verifiers) |
| Other agents' state | Not applicable |

**An Agent receives everything it needs in the Task:**

- Task description (what to do)
- Input artifact (data to work with)
- Context (relevant memory, assembled by Runtime)
- Timeout and constraints

**After execution, the Agent retains nothing from the Task. The Runtime persists the Artifact.**

---

## Invariant 7: Events are Immutable

**Statement:**

Once published, an Event can never be modified. The Event Store is append-only.

**Operations permitted on Events:**

| Operation | Permitted? |
|-----------|-----------|
| Append (publish) | Yes |
| Read (subscribe, replay) | Yes |
| Modify | **No** |
| Delete | **No** |

**Why:**

Events are the audit trail. If events can be modified, the single source of truth is compromised. Crash recovery, debugging, and compliance all depend on immutable event history.

**Correction pattern:**

If incorrect state was recorded, publish a **corrective event** — do not modify the original. Example: a `TaskCompleted` event was published in error. Publish a `TaskCompletionRevoked` event, then a new `TaskCompleted` when the task actually completes.

---

## Invariant 8: Artifacts are Immutable

**Statement:**

Once created, an Artifact can never be modified. Any transformation produces a new Artifact.

**Operations permitted on Artifacts:**

| Operation | Permitted? |
|-----------|-----------|
| Create (Agent produces) | Yes |
| Read (Verifier inspects, dependents consume) | Yes |
| Modify | **No** |
| Delete | **No** |

**Why:**

Artifacts are the products of agent work. Dependent tasks consume artifacts. If an artifact could be modified after creation, the dependencies become non-deterministic. Verification results become invalid.

**Correction pattern:**

If an Artifact is incorrect, the Task that produced it must be retried (producing a new Artifact) or a new correction Task must be added to the Plan.

---

## Invariant 9: Contracts Over Implementation

**Statement:**

Components communicate only through defined contracts: Schemas, APIs, Protocols, and Events. Never through direct invocation of internal methods.

**Allowed communication channels between components:**

| Channel | Description |
|---------|-------------|
| Schema | Data structure definition (JSON Schema) |
| API | Synchronous request/response contract |
| Protocol | Wire-level communication format |
| Event | Asynchronous state change notification |

**Forbidden communication patterns:**

- Direct method calls across component boundaries
- Shared mutable state between components
- Import of another component's internal module
- Assumptions about another component's implementation

---

## Invariant 10: Kernel is Plugin-Oriented

**Statement:**

The Kernel is a sealed, minimal core. All extensible behavior is in Plugins.

**Kernel components (in Kernel, not replaceable):**

- Event Bus
- Capability Registry
- Task Graph Engine
- Scheduler
- Execution Engine
- Plugin Lifecycle Manager

**Plugin components (replaceable, outside Kernel):**

- Planner
- Verifier
- Policy Engine
- Memory Provider
- Storage Backend
- Protocol Adapter
- Agent

**The Kernel never knows about specific Plugin implementations.** It only knows Plugin interfaces.

---

## Invariant 11: Schemas are Contracts

**Statement:**

Every Schema is a versioned contract. Schema changes require version bumps following Semantic Versioning.

**Version rules:**

| Change Type | Version Bump |
|-------------|-------------|
| Add optional field | MINOR |
| Add required field | MAJOR |
| Remove field | MAJOR |
| Change field type | MAJOR |
| Rename field | MAJOR |
| Change validation constraint | MAJOR (if restricting) |
| Fix description / metadata | PATCH |

**All schemas must declare:**
- `$schema` (JSON Schema version)
- `$id` (canonical URI)
- Version in the `$id` or a top-level `version` field

---

## Invariant 12: Everything Has a Lifecycle

**Statement:**

Every concept in Zelos has a defined lifecycle with explicit states, transitions, and owners.

**Concepts with defined lifecycles:**

| Concept | Lifecycle States |
|---------|-----------------|
| Goal | Submitted → Accepted → Planned → Executing → Completed / Failed / Cancelled |
| Execution Plan | Created → Validated → Executing → Modified → Completed / Abandoned |
| Task | Created → Ready → Assigned → Started → Completed / Failed / Cancelled / TimedOut |
| Artifact | Created → Validated (optional) → Accepted / Rejected |
| Agent | Registered → Connected → Heartbeating → Disconnected / Shutdown |
| Capability | Registered → Available → Unavailable / Deprecated → Removed |
| Plugin | Unloaded → Loaded → Configured → Initialized → Running → Stopped |
| Runtime | Stopped → Starting → Running → Degraded → Stopping → Stopped |

**No concept may exist without a defined lifecycle.**

---

## Invariant 13: Runtime Never Depends on LLM

**Statement:**

The Runtime has no knowledge of any specific AI model, model provider, or model API.

**The Runtime does not know about:**
- Claude
- GPT
- Gemini
- Open-source models
- Model endpoints
- Token limits
- Prompt formats
- Model capabilities or limitations

**The Runtime knows only about Agents.**

An Agent may use an LLM internally. The Runtime is unaware of this. From the Runtime's perspective, an Agent is an opaque execution provider that receives a Task and returns an Artifact.

---

## Invariant 14: Capability Describes Intent, Not Implementation

**Statement:**

A Capability describes **what** work can be done, never **who** does it or **how**.

**Correct capability names:**

```
code-generation.python
code-review.security
research.web-search
automation.browser
design.architecture
```

**Incorrect capability names (implementation-specific):**

```
claude-code        ← names a specific agent
gpt4-generation    ← names a specific model
gemini-research    ← names a specific model provider
my-custom-script   ← names a specific implementation
```

**Why:**

If a capability names an implementation, it cannot be provided by multiple agents. This defeats capability-based dispatch and locks the system to specific providers.

---

## Invariant 15: Policies Never Change Business Logic

**Statement:**

Policies can only Allow, Reject, Delay, or Retry. They can never modify the Plan, modify a Task, or change the business logic of execution.

**Policies may:**

| Action | Description |
|--------|-------------|
| Allow | Permit an operation to proceed |
| Reject | Block an operation |
| Delay | Defer an operation |
| Retry | Request retry of a failed operation |

**Policies may not:**

| Action | Description |
|--------|-------------|
| Modify Plan | Add, remove, or change tasks |
| Modify Task | Change task description, input, or constraints |
| Modify Artifact | Change artifact content or metadata |
| Change capability requirements | Alter what capability a task needs |
| Override Scheduler selection | Force a specific agent (except as an explicit task constraint, set at plan time) |

**Why:**

Policies are governance, not execution logic. If a policy can modify the plan, the distinction between Planner and Policy collapses. The Planner owns "what to do." Policy owns "whether and when to do it."

---

## Authority

This document is the highest authority in the Zelos specification.

- When an ADR conflicts with an Invariant, the Invariant wins.
- When an implementation detail conflicts with an Invariant, the implementation is wrong.
- When a future proposal conflicts with an Invariant, the Invariant must be explicitly amended first.

Amending an Invariant requires an ADR that:
1. Explains why the Invariant must change
2. Describes the new Invariant
3. Analyzes the impact on all existing documents and implementations
4. Is approved by the Architecture Team

---

## References

This document is referenced by all other Zelos documents. Key references:

- [Glossary](../glossary.md) — Unified definitions of all terms
- [Domain Model](../blueprint/domain-model.md) — Entity definitions governed by these invariants
- [Kernel Boundary](../blueprint/kernel-boundary.md) — What is in Kernel vs. Plugin (Invariants 1, 6, 10)
- [Execution Model](../blueprint/execution-model.md) — How Goals flow through the system (Invariants 1-5)
- [Capability Registry](../blueprint/capability-registry.md) — Capability-based dispatch (Invariants 5, 14)
- [Scheduler](../blueprint/scheduler.md) — Provider selection (Invariants 5, 7, 15)
