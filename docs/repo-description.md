# Zelos

> **Open Multi-Agent Orchestration Runtime.**
>
> Linux manages Processes. Kubernetes manages Containers. Temporal manages Workflows.
> **Zelos manages Goals — executed across dozens of autonomous Agents.**

---

Zelos is **NOT** another Agent framework. It does not build agents.

Zelos is the **Runtime** that plans, schedules, coordinates, verifies, retries, and audits the execution of Goals across hundreds of heterogeneous, independently-built Agents — each of which may use any language, any model, and any implementation.

---

## The Problem

Modern AI applications are no longer single-model systems. A single request demands planning, research, coding, browser automation, database queries, verification, and human approval — each delivered by a different Agent.

The problem is no longer *how to build an Agent.*

The problem is **how to reliably orchestrate hundreds of independent, heterogeneous Agents to achieve a Goal — with governance, accountability, and a complete audit trail.**

No existing system solves this.
- **Agent Frameworks** (LangGraph, CrewAI) couple agent construction with orchestration.
- **Workflow Engines** (Temporal, Airflow) are built for deterministic code, not autonomous agents.
- **Communication Protocols** (MCP, A2A) provide pipes, not governance.

Zelos exists to be the missing layer.

---

## What Zelos Is

Zelos accepts a **Goal** — a declaration of desired outcome — and owns every stage of its execution:

```
Goal → Plan → Task Graph → Capability Matching → Scheduling → Execution → Verification → Artifact → Completion
```

**Every stage is recorded as an immutable event, forming a complete Logic Pedigree — auditable from the first intent to the final output.**

---

## Architecture Invariants

Zelos is designed around 15 non-negotiable constitutional principles:

| Invariant | Principle |
|-----------|-----------|
| **Runtime Owns Orchestration** | Agents are execution plugins only. They never schedule, never invoke each other, never self-retry. |
| **Capability Before Agent** | Dispatch is always by *what* can be done, never by *who*. Scheduler selects by success rate, cost, latency — not by name. |
| **Agent is Stateless** | All state, memory, context, and lifecycle owned by the Runtime. Agent receives Task → executes → returns Artifact → exits. |
| **Events are Immutable** | Append-only Event Bus. Every state transition is a typed, timestamped, causally-linked event. Never modified. Never deleted. |
| **Artifacts are Immutable** | Agent outputs are created once, never changed. Corrections produce new Artifacts. |
| **Kernel is Sealed, Plugins are Replaceable** | 6 Kernel components. 6 Plugin types. Constitution stays, institutions can change. |
| **Runtime Never Depends on LLM** | Claude, GPT, Gemini are Agent internals. The Runtime has no knowledge of any model, provider, or prompt. |

[→ Full Architecture Invariants](docs/architecture/invariants.md)

---

## Architecture

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
│  │                     RUNTIME KERNEL (Sealed)                        │  │
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
│  │  EventBus │ Memory │ Policy │ Verifier │ Context │ Observability    │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                    │                                     │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                     PLUGIN INTERFACES (Replaceable)                  │  │
│  │  Planner │ Verifier │ Memory Provider │ Policy │ Storage │ Adapter   │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
                 │
                 ▼
      HTTP / gRPC / MCP / A2A / stdio
                 │
                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                               AGENTS                                     │
│  Claude │ Gemini │ Codex │ Browser │ SQL │ Search │ Human Review │ ...  │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## The Agent Contract — Just 5 Methods

An Agent in Zelos is an external process. It implements exactly 5 API methods:

```python
register()    # Declare capabilities — "I can do code-generation.python"
heartbeat()   # Prove liveness
execute()     # Receive Task, perform work, return Artifact
cancel()      # Handle cancellation
shutdown()    # Graceful disconnect
```

That's it. The Agent never schedules tasks. Never invokes other agents. Never manages memory. Never self-retries. Never modifies the execution plan.

The Runtime handles **everything else.**

---

## Separation of Powers — Architecturally Enforced

Zelos implements a constitutional separation of authority at the architecture level:

| Branch | Component | Responsibility |
|--------|-----------|---------------|
| **Legislation** | Planner (Plugin) | Decomposes Goal into ExecutionPlan. Defines *what* must be done. |
| **Execution** | Scheduler + Execution Engine (Kernel) | Matches Tasks to Agents by capability, cost, and reputation. Dispatches and monitors. |
| **Adjudication** | Verifier + Policy (Plugins) | Validates Artifacts against contracts. Allows, rejects, or delays execution. |

**No single Agent simultaneously writes the rules, executes against them, and judges the outcome.**

This is not a policy layer bolted on after the fact. It is the constitutional geometry of the system.

---

## Developer Experience — 3 Steps

**Step 1 — Build an Agent:**

```python
from zelos_sdk.agent import Agent
from zelos_sdk.schema import Task, Artifact, CapabilityDeclaration

class MyCodingAgent(Agent):
    def declare_capabilities(self):
        return [CapabilityDeclaration(
            name="code-generation", version="1.0.0",
            description="Generates Python code",
            input_schema={...}, output_schema={...}
        )]

    def execute(self, task: Task) -> Artifact:
        code = self._call_my_llm(task.input.content["spec"])
        return Artifact(content_type="application/json", content={"code": code})
```

**Step 2 — Register with the Runtime:**

```python
agent = MyCodingAgent(name="ClaudeCode", runtime_url="http://localhost:9876")
agent.run()  # Auto-register, heartbeat, wait for Tasks
```

**Step 3 — Submit a Goal:**

```python
from zelos_sdk.client import ZelosClient

client = ZelosClient(runtime_url="http://localhost:9876")
goal = client.submit_goal(
    description="Build an e-commerce website with React + FastAPI",
    budget=100.0, priority="high"
)
result = client.wait_for_goal(goal.goal_id)
```

---

## Why Zelos

| | Zelos |
|---|---|
| 🔓 **Vendor-Neutral** | Capability dispatch, not name dispatch. Agents in any language, any model. |
| 🏛️ **Governance by Architecture** | Separation of planning, execution, and verification — not bolt-on policy. |
| 📡 **Immutable Audit Trail** | Every state transition is a typed, append-only event with causal tracing. |
| 🧩 **Composable** | Agents from any source co-execute within the same Goal. |
| 🔄 **Resilient Execution** | Built-in retry, exponential backoff, Smart Retry, Fallback, dynamic re-planning. |
| 🌐 **Protocol-Agnostic** | HTTP, gRPC, MCP, A2A — protocol adapters isolate the Runtime from the wire. |
| 📐 **Specification First** | 15 Invariants, 6 ADRs, 12 Blueprints, 4 RFCs, 6 versioned JSON Schemas. |
| 🚀 **Plugin Architecture** | Kernel is sealed. Planner, Verifier, Policy, Memory, Storage are all replaceable. |

---

## Project Status

| Phase | Focus | Status |
|-------|-------|--------|
| **Phase 0** | Architecture Specification | ✅ Complete |
| **Phase 1** | Runtime Kernel (single-node) | ⬜ In Development |
| **Phase 2** | Developer Platform (plugins, SDKs) | ⬜ Planned |
| **Phase 3** | Runtime Ecosystem (distributed) | ⬜ Planned |

---

## License

Apache 2.0 — Infrastructure should not be proprietary.

---

> *"When everyone is racing to build better Agents, Zelos builds the Runtime that makes them governable at scale."*
