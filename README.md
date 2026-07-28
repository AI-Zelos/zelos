# Zelos

> The missing operating system for the multi-agent era.

**Status:** Phase 9 Complete · **Version:** 0.9.1 · **139 Tests** · **33 Modules** · **3 SDKs** · **Apache 2.0**

<p align="center">
  <b>Linux manages Processes. Kubernetes manages Containers. Temporal manages Workflows.</b><br>
  <b>Zelos manages <em>Goals</em> — and now, <em>verifies</em> them.</b>
</p>

<p align="center">
  <i>"The ultimate purpose of AI-Native Software Engineering is not to assist humans in writing code, but to replace 'code review' with the formal verification of software changes."</i><br>
  — <a href="https://ai-zelos.github.io/zelos/beyond-code-formal-theory-ai-se.pdf"><b>Beyond Code: A Formal Theory of Software Engineering in AI-Native Paradigm</b></a>
</p>

---

## Why Zelos Exists

**Two hard problems define the agent era:**

1. **Running hundreds of agents — safely.** A single request triggers planning, coding, browser automation, SQL, verification, and approval. Each step is a different agent. Who orchestrates them? Who verifies their output? Who keeps the audit trail?

2. **Reviewing AI-generated changes — at scale.** When agents produce 35,000 lines of code per hour, humans cannot read every line. The old model — "write code → code review → merge" — is broken. The new model is: **review the evidence, not the code.**

Nobody planned for this. We got:
- **LangGraph / CrewAI / AutoGen** — agent construction kits. They help you _build_ agents, but they don't _run_ or _verify_ them.
- **Temporal / Airflow** — workflow engines for deterministic code. Autonomous agents are anything but deterministic.
- **MCP / A2A** — communication protocols. They let agents talk, but don't govern what they do.
- **GitHub PRs** — designed for humans writing hundreds of lines. Collapse under AI writing thousands.

All four miss the same thing: **there is no platform that orchestrates agents, collects evidence, scores confidence, and lets humans approve changes instead of reading code.**

**Zelos is that platform.** It started as a runtime. Now it's a governance platform — the missing layer between "agents did something" and "we're confident this change should ship."

---

## What Zelos Is

Zelos is a **governance platform for multi-agent execution**, not a framework. It sits beneath your agents — the same way an OS sits beneath your processes.

**Two layers, one platform:**

| Layer | What it does |
|-------|-------------|
| **Runtime** (v0.1–v0.8) | Goal → Plan → Task DAG → Schedule → Execute → Retry → Verify → Audit |
| **Governance** (v0.9+) | Execution Trace → Evidence Collection → Confidence Scoring → Policy Gate → Change Approval Request |

| If you're building... | You need... | Zelos provides... |
|----------------------|-------------|-------------------|
| 5 agents in a script | A `for` loop | Overkill — don't use Zelos |
| 20 agents across 3 teams | A scheduler | Goal → Plan → Task DAG → auto-dispatch |
| 100 agents in production | A runtime | Distributed coordination, failover, retry, audit |
| 500+ agents as a service | A governance platform | CAR, evidence scoring, auto-approve/reject, compliance |

**Zelos does not build agents. Zelos orchestrates them, verifies their output, scores their quality, and lets you approve changes — not read code.**

---

## v0.9.0: The Governance Layer

v0.9.0 answers the question: **"The agents did something. Should we ship it?"**

### One API call. Complete confidence.

```python
report = runtime.get_execution_report(goal_id)

# What was the intent?
print(report.intent.description)
# → "Implement OAuth2 login with Google/GitHub"

# What changed?
print(report.architecture_delta.risk_level, report.architecture_delta.modified_modules)
# → "medium", ["auth-service", "user-model"]

# What happened, step by step?
for task in report.trace.tasks:
    print(f"{task.task_id}: {task.description} → {task.status} ({task.agent_name})")
# → "t1: Design OAuth flow → completed (ClaudeCode)"
# → "t2: Implement auth endpoints → completed (ClaudeCode)"
# → "t3: Security review → completed (SecurityBot)"

# What's the evidence?
print(report.evidence_bag.all_pass, report.confidence.score)
# → True, 0.97

# What should we do?
print(report.confidence.recommendation)
# → "approve"

# How do we roll back if needed?
print(report.rollback_plan.strategy, report.rollback_plan.estimated_downtime_s)
# → "event_sourcing_replay", 5.0
```

**No code review required. The evidence speaks for itself.**

### The CAR (Change Approval Request) Paradigm

```
Traditional PR:
  Code Diff (primary) + Description (afterthought)
  → "Review this code"

CAR (Zelos v0.9.0):
  Intent → Architecture Delta → Impact Analysis → Evidence → Risk → Rollback → Code (collapsed)
  → "Approve this change"
```

See: [`docs/blueprint/CAR-Change-Approval-Request.md`](docs/blueprint/CAR-Change-Approval-Request.md)

---

## When to Use Zelos

| Scenario | Why Zelos |
|----------|-----------|
| 🤖 **AI-powered SaaS platform** — your product uses 10+ specialized agents behind a single API | You need a scheduler that picks the right agent, retries on failure, and tracks cost per request. You don't want every agent directly calling every other agent. |
| 🏢 **Enterprise AI transformation** — multiple departments deploy agents that need to collaborate cross-team | You need namespace isolation (Finance can't touch Engineering's agents), RBAC, and an audit trail that your compliance team can actually read. |
| 🔒 **Regulated industry** (finance, healthcare, legal) — AI agents handling sensitive workflows | You need every agent action to be immutable and replayable. EU AI Act / SOC2 auditors don't accept "trust me bro." Zelos gives you a cryptographic audit chain. |
| 🧪 **AI research lab** — evaluating governance vs. ungoverned multi-agent systems | You need a test harness that can run the same workload with and without governance, then compare failure rates, cost, and Byzantine resilience. |
| 🏗️ **Agent infrastructure provider** — building a platform where third-party agents can register and get discovered | You already have the kernel of an Agent Marketplace. Capability Registry = agent search. ScoringStrategy = ranking. EventBus = billing audit. |
| ⚡ **High-reliability automation** — CI/CD, incident response, data pipelines with AI steps | You need retry logic, timeouts, dead-letter queues, and the ability to hot-join agents without restarting the pipeline. |

---

## What Zelos Is NOT

Zelos explicitly rejects these categories — and that's its strength:

| NOT | Why that matters |
|-----|-----------------|
| Agent Framework | We don't tell you how to build agents. Bring any agent — Python, Go, TypeScript, curl. |
| Workflow Engine | We don't force static DAGs. Plans are goal-derived, dynamic, and replan on failure. |
| Prompt Framework | We don't touch your prompts. Your agent owns its LLM interaction end-to-end. |
| LLM Wrapper | The Runtime knows nothing about GPT, Claude, or Gemini. LLM-agnostic by design. |
| LangGraph / CrewAI Alternative | Those are agent _construction_ toolkits. Zelos is agent _infrastructure_. Complementary. |
| SaaS / Marketplace | Those are future ecosystem projects on top of Zelos. The Runtime comes first.

---

## Architecture

### The Core Idea

```
Developer builds an Agent.
Developer describes its Capabilities.
Developer registers it with Zelos.

Everything else — planning, scheduling, coordination, retry,
verification, memory, lifecycle, observability — is handled by the Runtime.
```

### Runtime Architecture

```
                          ┌────────────────────────────┐
                          │          CLIENT             │
                          │  SDK / CLI / REST / gRPC    │
                          └─────────────┬──────────────┘
                                        │
                                        ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                             ZELOS RUNTIME                              │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                         API LAYER                                   │  │
│  │        Goal API  │  Agent API  │  Admin API  │  SDK Bindings       │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                    │                                     │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                        RUNTIME KERNEL                              │  │
│  │                                                                    │  │
│  │  Goal → Planner → ExecutionPlan → TaskGraph → Scheduler            │  │
│  │                                    │                               │  │
│  │                                    ▼                               │  │
│  │                        Capability Registry                         │  │
│  │                                    │                               │  │
│  │                                    ▼                               │  │
│  │                          Execution Engine                           │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                    │                                     │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                     RUNTIME INFRASTRUCTURE                          │  │
│  │ EventBus │ Memory │ Policy │ Verifier │ Context │ EventSourcing │ Observability    │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                    │                                     │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                       PLUGIN INTERFACES                             │  │
│  │ Planner │ Verifier │ Memory │ Policy │ Storage │ Protocol Adapter   │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
                 │
                 ▼
      HTTP / gRPC / MCP / A2A / stdio
                 │
                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                               AGENTS                                     │
│ Claude │ Gemini │ Codex │ Browser │ SQL │ Search │ Custom ...           │
└──────────────────────────────────────────────────────────────────────────┘
```

### Separation of Concerns

**Runtime owns:** Goal decomposition, Execution Plan, Task Graph, Scheduling, Retry, Verification, Memory, Context, Event Bus, Policy, Observability, Lifecycle.

**Agent owns:** Receive Task → Execute → Return Artifact → Exit. Nothing more.

### Dispatch: Capability, Never Name

```
Task requires: "code-generation.python"
       ↓
Capability Registry finds providers
       ↓
Scheduler selects best (cost, latency, success rate, policy)
       ↓
Agent receives Task — never knows it was "chosen," only that it was dispatched
```

### Custom Scoring: You Own the "Who Gets the Task"

The Scoring Strategy plugin lets you replace the entire Agent ranking logic.
The default is a weighted formula — but you can make it **cost-first**,
**compliance-first**, or any logic you need.

```python
# zelos.yaml — default weighted scoring
plugins:
  - id: "default-scoring"
    type: "scoring_strategy"
    entrypoint: "zelos.scoring.default.DefaultScoringStrategy"
    config:
      weights:
        success_rate: 0.30       # Proven reliability
        cost_efficiency: 0.20    # Lower cost preferred
        load_distribution: 0.15  # Prefer less busy agents
        latency: 0.15            # Faster is better
        availability: 0.10       # Higher uptime
        affinity: 0.05           # Same agent for related tasks
        recency: 0.05            # Recently used (context warmth)
```

```python
# Custom strategy example: Fintech — compliance first
from zelos.scoring import ScoringStrategy, AgentCandidate, ScoredCandidate

class FintechScoring(ScoringStrategy):
    def score(self, task, candidates):
        results = []
        for c in candidates:
            # SOC2 compliance is non-negotiable
            if "soc2-compliant" not in c.tags:
                results.append(ScoredCandidate(c, score=0,
                    reason="Not SOC2 compliant"))
                continue
            # Security-first formula
            score = (
                c.success_rate      * 0.40 +
                self._compliance(c) * 0.25 +
                self._cost(c)       * 0.15 +
                c.availability      * 0.10 +
                self._latency(c)    * 0.10
            )
            results.append(ScoredCandidate(c, score=score,
                reason=f"Compliant, success={c.success_rate:.0%}"))
        return sorted(results, key=lambda r: r.score, reverse=True)
```

```yaml
# zelos.yaml — use the custom strategy
plugins:
  - id: "fintech-scoring"
    type: "scoring_strategy"
    entrypoint: "my_org.scoring.FintechScoring"
```

---



---

## Install

[![PyPI version](https://img.shields.io/pypi/v/zelos-runtime)](https://pypi.org/project/zelos-runtime/)
[![Python versions](https://img.shields.io/pypi/pyversions/zelos-runtime)](https://pypi.org/project/zelos-runtime/)

```bash
pip install zelos-runtime
```

Zelos core has **zero external dependencies** — pure Python stdlib. That's engineering philosophy.

```bash
pip install "zelos-runtime[dev]"    # adds pytest + ruff
```

→ [zelos-runtime on PyPI](https://pypi.org/project/zelos-runtime/)

---

## Development

```bash
# Clone the repo
git clone https://github.com/AI-Zelos/zelos.git && cd zelos
pip install -e ".[dev]"

# Quick reference
make dev        # Start Runtime in hot-reload mode
make test       # Run all 139 tests
make lint       # Ruff code quality check (zero errors)
make format     # Auto-format all code
make check      # Full CI pipeline (lint + test)
make build      # Build Docker image
make run        # Start via Docker Compose
make clean      # Remove build artifacts
```

---

## Quick Start: One Command

```bash
# Start Runtime + Dashboard
python3 start.py

# Open http://127.0.0.1:9876/ in your browser
# Custom port: python3 start.py --port 8080
# With config: python3 start.py --config zelos.yaml
# CLI only:    python3 start.py --no-dashboard
```

---

## Quick Start: Multiple Agents, One Goal

This is what using Zelos looks like end-to-end. Three agents, one Goal, zero coordination code.

### Step 1：Configure zelos.yaml

All settings in one file. Planner (LLM), Verifier, Policy, Memory — everything declared here.

```yaml
# zelos.yaml
runtime:
  api:
    host: "127.0.0.1"
    port: 9876
  limits:
    max_goals: 100
    max_tasks_per_goal: 50

plugins:
  # ── LLM Planner — decomposes Goals into Tasks ──
  - id: "llm-planner"
    type: "planner"
    entrypoint: "zelos.planner.LLMPlanner"
    config:
      provider: "openai"                # openai / anthropic / google
      model: "deepseek-v4-flash"
      api_key: "${OPENAI_API_KEY}"
      base_url: "https://api.deepseek.com/v1"
      temperature: 0.3
      max_tokens: 4000

  # ── Schema Verifier — validates every Agent output ──
  - id: "schema-verifier"
    type: "verifier"
    entrypoint: "zelos.verifier.SchemaVerifier"

  # ── Policy Engine — cost limits + rate limits ──
  - id: "default-policy"
    type: "policy"
    entrypoint: "zelos.policy.CompositePolicy"
    config:
      max_cost_per_goal: 100.0
      max_tasks_per_minute: 60

  # ── Scoring Strategy — how Scheduler ranks Agents ──
  - id: "default-scoring"
    type: "scoring_strategy"
    entrypoint: "zelos.scheduler.DefaultScoringStrategy"
    config:
      weights:
        success_rate: 0.30
        latency: 0.15
        cost_efficiency: 0.20
```

### Step 2：Start the Runtime and Register Agents

One line to load config + a few `add_agent()` calls. That's it.

```python
from zelos.runtime import ZelosRuntime
from zelos_sdk.schema import CapabilityDeclaration

# ── Load from zelos.yaml ──
runtime = ZelosRuntime.from_yaml("zelos.yaml")

# Register agents. Runtime manages their lifecycles.
runtime.add_agent(
    name="ClaudeCode-v2",
    entrypoint="my_agents.coder:CodingAgent",
    capabilities=[
        CapabilityDeclaration(name="code-generation.python", version="1.0.0", ...),
        CapabilityDeclaration(name="code-generation.typescript", version="1.0.0", ...),
    ],
)
runtime.add_agent("SecurityReviewer", "my_agents.reviewer:ReviewAgent", [
    CapabilityDeclaration(name="code-review.security", version="1.0.0", ...),
])
runtime.add_agent("PlaywrightBot", "my_agents.browser:BrowserAgent", [
    CapabilityDeclaration(name="automation.browser", version="1.0.0", ...),
])

# ── ONE call starts everything — Kernel, Plugins, Memory, Verifier, Agents ──
runtime.start()
```

### Step 3：Hot-Join and Hot-Leave (Anytime)

```python
# Agent joins mid-run → instantly dispatchable
runtime.add_agent("DataAnalyst", "my_agents.analyst:SQLAgent", [...])

# Agent leaves → in-flight tasks rescheduled
runtime.remove_agent("SecurityReviewer")
```

### Step 4：Submit a Goal — Fully Automatic, Tiered Escalation

One sentence → `wait_for_goal()`. Everything in between is automatic.

```python
goal = runtime.submit_goal(
    description="Build a landing page. Design it. Code it. Review it. Screenshot it.",
    budget=50.0, priority="high",
)
# → goal_id: "g-001", status: "planned", task_count: 6

result = runtime.wait_for_goal(goal["goal_id"], timeout_seconds=60)
# → status: "completed", 6/6 tasks done
```

What happened automatically behind the scenes:

| Layer | What Runs | When |
|-------|-----------|------|
| **Orchestrator Loop** | evaluate deps → schedule → dispatch → collect → verify → unblock | Every 500ms |
| **Three-Tier Escalation** | READY Task with no Agent: Tier 1 (<60s) wait → Tier 2 (>60s) FAIL → Tier 3 Planner.replan() | On stuck tasks |
| **Verifier Gate** | SchemaVerifier validates every Artifact against its expected schema | After each Task |
| **Policy Engine** | CostLimit + RateLimit enforced | On every dispatch |
| **6-Layer Memory** | Context auto-assembled from session/project/user/knowledge/execution/skill | Before each Task |
| **Event Bus** | Every state change = immutable, replayable audit record | Continuously |

### Step 4：Zelos Takes Over

```
User: "Build a landing page..."

  │  Runtime receives Goal
  ▼
┌─────────────────────────────────────────────────────────────┐
│  PLANNER (Plugin)                                           │
│  Goal → ExecutionPlan: 6 Tasks in a DAG                     │
│                                                             │
│  Task 1: design-landing-page    [design.architecture]       │
│  Task 2: code-react-frontend    [code-generation.typescript]│
│  Task 3: review-security        [code-review.security]      │
│  Task 4: fix-issues             [code-generation.typescript]│
│  Task 5: screenshot-result      [automation.browser]        │
│  Task 6: generate-report        [code-generation.python]    │
│                                                             │
│  Dependencies: 1→2→3→4→5→6                                   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  SCHEDULER + EXECUTION ENGINE                               │
│                                                             │
│  Task 2 "code React frontend" → Ready                       │
│    Capability: code-generation.typescript                   │
│    Providers: [ClaudeCode-v2]                               │
│    → Dispatched to ClaudeCode-v2                            │
│                                                             │
│  Task 3 "review security" → Ready (after Task 2 completes) │
│    Capability: code-review.security                        │
│    Providers: [SecurityReviewer]                            │
│    → Dispatched to SecurityReviewer                         │
│                                                             │
│  Task 5 "screenshot" → Ready (after Task 4 completes)      │
│    Capability: automation.browser                          │
│    Providers: [PlaywrightBot]                              │
│    → Dispatched to PlaywrightBot                            │
│                                                             │
│  Every Task: dispatched, monitored, verified, logged.       │
│  Every failure: retried or re-planned automatically.        │
└─────────────────────────────────────────────────────────────┘
```

### Step 5：Get the Result and Shut Down

```python
result = runtime.wait_for_goal("g-001", timeout_seconds=600)
print(f"Goal: {result.status}")          # → "completed"
print(f"Tasks: {result.progress.completed_tasks}/6")
# Download artifacts: React code, security report, screenshot, final report

# ── One call shuts down everything ──
runtime.shutdown()
# Stops all agents, flushes state, shuts down Kernel.
```

**The agents never spoke to each other. They never knew the Goal. They just received Tasks, executed, returned Artifacts, and exited. The Runtime coordinated everything.**

### What This Example Demonstrates

| Principle | How It Shows |
|-----------|-------------|
| **Zelos.yaml First** | One config file: Planner, Verifier, Policy, Scoring, Memory — all declared, loaded with `from_yaml()`. |
| **Runtime First** | `ZelosRuntime` is the only entry point. `runtime.start()` launches everything. |
| **LLM Planner** | One sentence → N Tasks in a DAG. Backed by OpenAI / Anthropic / Google / DeepSeek. |
| **Capability First** | Tasks dispatched by capability name, never by agent name. |
| **Verifier Gate** | Every Agent output validated against its expected schema before downstream Tasks consume it. |
| **Policy Engine** | Cost limits + rate limits + allowlists enforced automatically. |
| **6-Layer Memory** | session / project / user / knowledge / execution / skill — with TTL, LRU, and Context Assembly. |
| **Hot-Join / Hot-Leave** | `add_agent()` mid-run → instantly dispatchable. `remove_agent()` → tasks reassigned. |
| **Separation of Powers** | Planner plans. Agent executes. Verifier verifies. Policy constrains. No single agent holds all powers. |
| **Pluggable Storage** | InMemory / Redis / PostgreSQL / MySQL — one line in zelos.yaml to switch. Events + State persisted across restarts. |
| **Event Sourcing** | Every Goal state reconstructable from its immutable event history. `EventSourcingEngine.apply_event()` is a pure function — given the same events, you always get the same state. |
| **Goal Persistence** | All active Goals auto-persisted to `StorageBackend`. Runtime restart → all incomplete Goals automatically recovered with full task state. |
| **Heartbeat Timeout** | Agent stops heartbeating → Task auto-FAILED → Scheduler retries. `submit_heartbeat()` API keeps long-running tasks alive. |
| **NonRetryableError** | `ValidationError` / `AuthError` → `FATAL_FAILED` (terminal). No retry, no replan. The right failure for the right error. |

---

## Architecture Invariants

Every design decision and implementation must conform to these 15 non-negotiable principles. [Full document →](docs/architecture/invariants.md)

1. **Runtime Owns Orchestration** — Agents are execution plugins only
2. **Goal is First-Class** — The Runtime accepts Goals, not workflows
3. **Execution Plan is Single Source of Truth** — No component bypasses the Plan
4. **Task is Atomic** — One Task = one Agent invocation
5. **Capability Before Agent** — Dispatch by what, not who
6. **Agent is Stateless** — All state owned by Runtime
7. **Events are Immutable** — Append only, never modify
8. **Artifacts are Immutable** — Created once, never changed
9. **Contracts Over Implementation** — Components communicate only through schemas, APIs, events
10. **Kernel is Plugin-Oriented** — Kernel sealed; all behavior in replaceable plugins
11. **Schemas are Contracts** — Schema changes require version bumps
12. **Everything Has a Lifecycle** — Every concept has defined states and transitions
13. **Runtime Never Depends on LLM** — Claude, GPT, Gemini are Agent internals
14. **Capability Describes Intent** — What, not who or how
15. **Policies Never Change Business Logic** — Policies only Allow, Reject, Delay, Retry

---

## Project Structure

```
zelos/
├── README.md
├── ROADMAP.md
├── docs/
│   ├── glossary.md                     ← Canonical definitions
│   ├── architecture/
│   │   └── invariants.md               ← 15 non-negotiable principles
│   ├── adr/                            ← Architecture Decision Records
│   │   ├── ADR-0000-why-zelos-exists.md
│   │   ├── ADR-0001-runtime-first.md
│   │   ├── ADR-0002-capability-first.md
│   │   ├── ADR-0003-execution-plan-first.md
│   │   ├── ADR-0004-plugin-architecture.md
│   │   └── ADR-0005-protocol-adapter-architecture.md
│   ├── blueprint/                      ← Architecture Blueprints
│   │   ├── domain-model.md             ← All entities, lifecycles, relationships
│   │   ├── kernel-boundary.md          ← Kernel vs. Plugin vs. SDK boundary
│   │   ├── runtime-lifecycle.md        ← Startup → Execute → Shutdown → Recovery
│   │   ├── execution-model.md          ← Goal → Plan → Schedule → Execute → Verify
│   │   ├── task-graph.md               ← Task state machine and DAG
│   │   ├── capability-registry.md      ← Namespace, versioning, matching, QoS
│   │   ├── scheduler.md                ← Filter → Score → Policy → Select
│   │   ├── execution-engine.md         ← Dispatch, heartbeat, timeout, retry
│   │   ├── event-bus.md                ← Taxonomy, ordering, delivery, replay
│   │   ├── memory-architecture.md      ← 6 layers, providers, context assembly
│   │   ├── verifier.md                 ← Verification gate, verdict model, types
│   │   ├── plugin-architecture.md      ← Discovery, lifecycle, isolation, upgrade
│   │   ├── runtime-api.md              ← Stable API: Goal, Agent, Admin, Plugin
│   │   ├── change-evidence-package.md   ← v0.9.0 vision: Evidence-based governance
│   │   ├── protocol-layer.md           ← HTTP, gRPC, MCP, A2A adapters
│   │   ├── python-sdk.md               ← Agent base class, ZelosClient, testing
│   │   └── agent-registration-guide.md  ← How any Agent registers on Zelos
│   ├── rfc/                            ← Request for Comments
│   │   ├── rfc-0001-goal-execution-lifecycle.md
│   │   ├── rfc-0002-agent-registration-protocol.md
│   │   ├── rfc-0003-event-bus-specification.md
│   │   ├── rfc-0004-capability-semantics.md
│   │   └── rfc-0005-pluggable-scheduler-strategy.md
│   └── schema/                         ← JSON Schemas (versioned contracts)
│       ├── goal.json
│       ├── execution-plan.json
│       ├── task.json
│       ├── capability.json
│       ├── agent.json
│       ├── agent-registration.json
│       ├── artifact.json
│       └── event.json
```

---

## Reading Order

For a new engineer joining the project:

1. **This README** — understand what Zelos is and why it exists
2. **[Architecture Invariants](docs/architecture/invariants.md)** — internalize the 15 principles
3. **[Glossary](docs/glossary.md)** — learn the canonical terminology
4. **[Domain Model](docs/blueprint/domain-model.md)** — understand every entity, its lifecycle, and relationships
5. **[Kernel Boundary](docs/blueprint/kernel-boundary.md)** — learn what is Kernel vs. Plugin
6. **[Execution Model](docs/blueprint/execution-model.md)** — trace a Goal from submission to completion
7. **[Runtime Lifecycle](docs/blueprint/runtime-lifecycle.md)** — understand startup, operation, shutdown
8. **Remaining Blueprints** — dive into specific components as needed
9. **ADRs** — understand why key architectural decisions were made
10. **RFCs** — explore open design questions and proposals

After reading these, you should understand the entire Runtime architecture without reading any code.

---

## Development Phases

| Phase | Focus | Status |
|-------|-------|--------|
| **Phase 0** | Architecture Specification | ✅ Complete |
| **Phase 1** | Runtime Kernel (single-node) | ✅ Complete |
| **Phase 2** | Developer Platform (plugins, SDKs) | ✅ Complete |
| **Phase 3** | Runtime Ecosystem (distributed) | ✅ Complete |
| **Phase 4** | Engineering Completeness (CI/CD, Docker, TS SDK, mTLS) | ✅ Complete |
| **Phase 5** | Production Hardening (Anomaly Detection, K8s Probes, Operations) | ✅ Complete |
| **Phase 6** | Demo Enrichment & Documentation (HITL, Multi-tenancy, Docs) | ✅ Complete |
| **Phase 7** | Advanced Production (etcd, NATS, Go SDK, Perf, OTel) | ✅ Complete |
| **Phase 8** | Event Sourcing & Reliability (Goal persistence, heartbeat, NonRetryableError) | ✅ Complete |
| **Phase 9** | Change Evidence Package (Execution trace, evidence, confidence, policy gate) | ✅ Complete |

### Phase 7 Deliverables

| Module | Components |
|--------|-----------|
| **Coordination** | etcd + InMemory backends, leader election, watch, heartbeat, factory |
| **Messaging** | NATS + InMemory message bus, pub/sub, pattern match, request-reply |
| **Go SDK** | `zelos-go/` — schema types, Agent interface, ZelosClient, DemoAgent |
| **Performance** | TaskGraph O(1) evaluate_all |
| **OpenTelemetry** | Jaeger OTLP export, span verification |

### Phase 8 Deliverables

| Module | Components |
|--------|-----------|
| **Event Sourcing** | `EventSourcingEngine` — pure-function `apply_event`, full rebuild from events, snapshot + incremental replay |
| **Goal State** | `GoalState` dataclass — `to_dict()`/`from_dict()`, auto-persisted on every state change, startup recovery |
| **Event Sequence** | `Event.sequence_id` — monotonic auto-assign, `replay_from()`, backward compatible |
| **Heartbeat Timeout** | `InFlightTask.heartbeat_at`, monitor loop detection, `submit_heartbeat()` API, auto-retry on timeout |
| **NonRetryableError** | `Task.non_retryable_errors`, `TaskStatus.FATAL_FAILED` (terminal), no retry on matched errors |
| **Retry History** | `task.retry_scheduled` event with full context, per-task retry timeline in `get_goal_status()` |
| **Query Isolation** | Confirmed `get_goal_status()`, `list_agents()`, `get_health()` produce zero events |

### Phase 9 Deliverables

| Module | Components |
|--------|-----------|
| **Lifecycle Events** | Full Task lifecycle events with input/output context, large payload content_ref |
| **Execution Trace** | `get_goal_trace()` — complete Task timeline, pagination, lazy-load artifacts |
| **Intent Spec** | Structured intent capture with success criteria, constraints, backward compat |
| **Evidence Collection** | `Evidence` dataclass, `EvidenceBag` auto-aggregation, per-type summaries |
| **Confidence Scoring** | `WeightedConfidenceScorer` — 6-factor weighted, configurable, recommendation output |
| **Execution Report** | `get_execution_report()` — unified Change Evidence Package with trace+evidence+confidence |
| **Policy Gate v2** | `EvidenceBasedPolicyGate` — auto-approve/reject/require_human based on evidence |

### Phase 6 Deliverables

| Module | Components |
|--------|-----------|
| **HITL Demos** | Single/multi approver, rejection, change request, timeout, audit trail (6 scenarios) |
| **Multi-tenancy Demos** | Registration, quotas, isolation, lifecycle, usage report (5 scenarios) |
| **Documentation** | CHANGELOG v0.1.0–v0.8.0, ROADMAP all phases, Operations manual, API docs |

### Phase 5 Deliverables

| Module | Components | Tests |
|--------|-----------|-------|
| **Security Hardening** | API Key anomaly detection (brute-force tracking, sliding window, auto-revoke), audit log file export | 4 |
| **K8s Probes** | `/live` liveness + `/ready` readiness endpoints (no auth) | 3 |
| **Operations** | Grafana dashboard JSON template, Operations manual (deploy guide, troubleshooting, backup/recovery) | — |

### Phase 4 Deliverables

| Module | Components | Tests |
|--------|-----------|-------|
| **CI/CD & DevOps** | GitHub Actions (Python matrix + lint), Docker multi-stage, Docker Compose, Makefile, Pre-commit hooks | — |
| **Storage Verification** | Integration tests against real Redis + PostgreSQL (connect, CRUD, snapshots, stream isolation) | 30 |
| **Event Persistence** | PersistentEventStore (WAL), crash recovery, state persistence (Goal/Agent save + restore) | 9 |
| **Distributed Testing** | Multi-node cluster tests (leader election, work stealing, node registry, dead node detection) | 9 |
| **TypeScript SDK** | `zelos-ts/` — schema types, BaseAgent, ZelosClient, DemoAgent | — |
| **Security Verification** | mTLS integration tests (self-signed CA, mutual TLS handshake, client rejection) | 3 |
| **Observability** | Prometheus /metrics HTTP endpoint (text exposition format) | — |
| **Performance** | Benchmark suite (EventBus 1.4M/s, TaskGraph 2.5M/s, Capability matching, Scheduler scoring) | 5 |
| **Documentation** | CHANGELOG.md, pdoc API docs, ROADMAP Phase 4/5/6 | — |

### Phase 2 Deliverables

| Module | Components | Tests |
|--------|-----------|-------|
| **Verifier Framework** | SchemaVerifier, CodeReviewer, SecurityScanner, FactChecker, VerificationGate | 28 |
| **Policy Engine** | CostLimitPolicy, RateLimitPolicy, AllowlistPolicy, CompositePolicy | 8 |
| **Observability** | StructuredLogger, MetricsCollector (Counter/Gauge/Histogram), Tracer, Prometheus export | 10 |
| **Plugin Isolation** | SubProcessPlugin, JSON-line stdin/stdout protocol | 5 |
| **Protocol Adapters** | gRPC, WebSocket (event streaming), MCP (tool registry), A2A (agent card) | 13 |
| **LLM Planner** | OpenAI, Anthropic, Google, Mock providers; replan; three-tier escalation | 32 |

### Phase 3 Deliverables

| Module | Components | Tests |
|--------|-----------|-------|
| **Security** | AccessControl (RBAC + wildcards), AuditLogger (immutable, multi-field query), APIKeyManager (SHA-256 hashed), TLSConfig (mTLS) | 24 |
| **Multi-tenancy** | Namespace (quota-enforced isolation), ResourceQuota, TenantManager (activate/deactivate/cross-tenant) | 14 |
| **Advanced Execution** | DynamicPlanModifier (add/remove/modify tasks in running DAG), SubGoalManager (spawn + failure propagation), HumanInTheLoop (multi-step approval, audit trail) | 20 |
| **Container Isolation** | ContainerPluginConfig (Docker/Podman cmd generation), RemotePlugin (HTTP retry/timeout), IsolationFactory | 12 |
| **Hot Reload** | FileWatcher (poll + debounce), HotReloadManager (version history, drain, rollback, rolling/blue-green/canary strategies) | 12 |
| **Distributed Runtime** | LeaderElection (bully algorithm + heartbeat), WorkStealing (capacity-aware, priority-ordered), NodeRegistry (health monitoring, capability lookup) | 14 |
| **CLI Tool** | ZelosCLI (argparse, goal/agent/health/metrics/plugin/namespace/config subcommands) | 10 |
| **Total Phase 3** | | **106** |

See [ROADMAP.md](ROADMAP.md) for detailed milestones.

---

## Design Philosophy

> Zelos is built on 15 non-negotiable Architecture Invariants. Every line of code must conform.

- **Runtime First** — The Runtime owns everything; agents are execution plugins only
- **Capability First** — Dispatch by _what_ (capability name), never by _who_ (agent name)
- **Execution Plan First** — A Plan exists before any agent is invoked; no agent can bypass it
- **Event Driven** — Every state change is an immutable event; no component communicates directly
- **Plugin Architecture** — The Kernel is sealed. Planner, Verifier, Policy, Memory, Storage — all replaceable
- **Specification First** — Code follows specification. Schema changes require version bumps
- **Cloud Native** — Designed for distributed, multi-node operation from Phase 1

[Full Architecture Invariants →](docs/architecture/invariants.md)

---

## Documentation

### Online (GitHub Pages)

Full documentation site auto-deployed on every push to `main` — includes **User Manual**, **Operations Guide**, and **API Reference** for all 33 modules.

Visit: **https://AI-Zelos.github.io/zelos**

### Local

```bash
make docs    # generates to public/
open public/index.html
```

To regenerate after code changes:
```bash
make docs
git add public/ && git commit -m "docs: regenerate API docs"
git push
```

### Local

```bash
make docs
open public/index.html
```

---

## License

Apache 2.0
