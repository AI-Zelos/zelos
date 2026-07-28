# Zelos

> **Zelos orchestrates trustworthy software changes produced by AI.**
>
> It is the runtime between AI-generated code and production systems — the layer that collects evidence, scores confidence, and lets humans approve changes instead of reading code.

---

## What is Zelos?

Zelos is the infrastructure layer for AI-native software engineering. When an AI agent modifies 40,000 lines of code, Zelos does not write the code. Zelos proves it is trustworthy.

```
Developer submits Intent
        ↓
Zelos plans the change, analyzes impact
        ↓
Agents execute tasks, each returning Evidence
        ↓
Verifiers check every output against its expected contract
        ↓
Evidence is collected, scored, and presented as a Confidence number
        ↓
Policy Gate decides: auto-approve, auto-reject, or need human
        ↓
Human sees a Change Evidence Package — not a code diff
        ↓
Approve, with a Rollback Plan on standby
```

Zelos is **not** the agent. Zelos is the system that governs the agent.

---

## Why does Zelos exist?

**Because AI can write code faster than humans can verify it.**

The old model is broken:

```
Human → Write Code → Code Review → Merge
```

When agents produce 35,000+ lines per hour, no human can read every line. The bottleneck is no longer code generation — it is **trust**.

Zelos replaces "review the code" with "review the evidence."

---

## Why now?

Three forces are converging:

1. **Agents are producing code at industrial scale.** Manual review is mathematically impossible.
2. **Enterprises are adopting AI coding tools.** They need governance, not just generation.
3. **No one has defined what AI-native software engineering looks like.** The protocols, the evidence standards, the approval workflows — the entire layer between "agent did something" and "this change can ship" is missing.

Zelos is that layer.

---

## What is NOT Zelos?

- **Not an Agent Framework.** We don't build agents. We govern them.
- **Not a Workflow Engine.** We don't force static DAGs. Plans are goal-derived and dynamic.
- **Not a Prompt IDE.** The Runtime knows nothing about GPT, Claude, or Gemini.
- **Not a SaaS.** Zelos is open-source infrastructure. The cloud can come later.
- **Not a Marketplace.** We don't sell or rank agents. We verify their output.

**Zelos does one thing: it makes AI-produced software changes trustworthy.**

---

## The Core Loop

The Zelos loop is not "Agent → Done." It is:

```
Intent → Plan → Execute → Verify → Evidence → Confidence → Decide
```

Every stage is owned by the Runtime. Agents are execution plugins. Verifiers check their work. Evidence is the currency. Confidence is the score. Decision is the output.

---

## The Vocabulary

Zelos defines its own language. Like Kubernetes defined Pod and Deployment, Zelos defines:

| Term | Definition |
|------|-----------|
| **Goal** | A desired outcome, expressed as structured Intent |
| **Execution Plan** | A DAG of Tasks derived from the Goal |
| **Task** | A single unit of work, dispatched by Capability |
| **Capability** | What an Agent can do — never who the Agent is |
| **Artifact** | The output of a Task execution |
| **Evidence** | Typed, verifiable proof that a Task was done correctly |
| **Confidence** | A 0.0–1.0 score computed from all Evidence |
| **Policy Gate** | Rules that decide: approve, reject, or escalate to human |
| **Execution Report** | The unified Change Evidence Package — one document, all proof |
| **CAR** | Change Approval Request — the next-generation PR |

---

## The Promise

If you build agents, Zelos gives you:

- **Orchestration** — Goal → Plan → Task DAG, auto-scheduled
- **Verification** — Every agent output checked against its contract
- **Evidence** — Typed, collected, summarized proof of correctness
- **Confidence** — A single number you can trust
- **Governance** — Policy-driven auto-approve, auto-reject, or human escalation
- **Audit** — Immutable, replayable event chain for every decision

If you run a team, Zelos gives you:

- **CAR instead of PR** — Approve changes, not code
- **One report, all evidence** — No more hunting through CI logs
- **Rollback built in** — Every change has a revert plan
- **Accountability** — Every approval decision is recorded and replayable

---

> **Zelos does not write code. Zelos makes code trustworthy.**
>
> That is the mission.
