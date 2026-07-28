# Papers Executive Summary — For Leadership Review

> Two foundational papers defining AI-Native Software Engineering. One provides the formal theory. The other provides the practical engineering workflow.

---

## Paper 1: Beyond Code — A Formal Theory of Software Engineering in AI-Native Paradigm

**One sentence**: AI doesn't just change how we write code — it changes what "software engineering" means, at a formal, mathematical level.

### What it argues

Traditional software engineering was designed for a world where humans write code and humans review code. That world is ending. When AI produces 35,000+ lines per hour and humans read at ~200 lines per hour, **the bottleneck has moved**. It's no longer code production. It's trust.

The paper formalizes this shift mathematically:

- **11 theorems** proving that traditional code-review-centric processes **cannot scale** to AI-driven development speeds
- A formal theory showing that the fundamental unit of software engineering is shifting from "code" to "change" — and the job of the runtime is to **prove trustworthiness**, not execute instructions
- The "Subject-Decoupled Credibility Law": verification and execution must be separated for trust to scale

### Why a boss should care

Every engineering leader is asking: "AI is writing more code. How do we govern it?" This paper provides the **theoretical foundation** for the answer. It's not an opinion piece — it builds a formal mathematical argument that this shift is inevitable and provides the vocabulary (Intent, Evidence, Confidence, Verdict) to talk about it.

**Publication target**: ICSE/FSE (SEIP track), ASE. This paper has the "Editor's Pick" quality — it challenges a 50-year-old paradigm with formal rigor.

---

## Paper 2: From PR to CP — A Novel Software Change Governance Workflow for Large-Scale AI Development

**One sentence**: GitHub PRs were designed for humans writing 200-line changes. For AI writing 20,000-line changes, we need something fundamentally different. Here it is.

### What it proposes

**CP (Change Proposal)** — a replacement for the Pull Request, designed from scratch for the AI era.

| Traditional PR | Change Proposal (CP) |
|---------------|---------------------|
| Code is the primary artifact | Change intent + evidence is primary |
| Review happens AFTER code is written | Constraints are locked BEFORE code generation |
| Human must read every line | Human sees a confidence score + evidence summary |
| "It looks right" | "Confidence is 97%. Evidence: 47/47 tests passed. Security: PASS. Benchmark: +31.8% TPS." |
| No rollback plan required | Rollback plan is mandatory |

### The experiment results (20 tasks, single-variable controlled)

| Metric | Traditional PR | CP (This Paper) | AI-Assisted PR |
|--------|---------------|-----------------|----------------|
| Rework rate | 35% | **5%** | 20% |
| Constraint violations | 30% | **0%** | 15% |
| Human dependency | 100% | **0%** | 100% |
| Human time per task | 11.7 min | **3.2 min** (73% less) | ~10 min |

The critical finding: **AI-Assisted PR** (AI pre-reviews code, human does final approval) still has 100% human dependency. The bottleneck is topological — PR's "generate → review → merge" chain puts human review on the critical path regardless of tooling. CP fixes the topology, not just the tooling.

### Why a boss should care

This directly addresses the question every CTO asks: "If AI writes the code, who reviews it?" The answer: **no one reads every line. The runtime verifies the change and presents the evidence.** The 73% time compression is real data, not an estimate.

The paper also includes **formal proofs** (3 theorems) showing that PR cannot evolve into CP through incremental improvements — they are structurally different paradigms. This isn't an enhancement to PR. It's a replacement.

**Publication target**: ICSE 2027 / FSE 2027 (SEIP track). Strong industrial relevance + rigorous formal backing.

---

## How These Papers Connect

**Paper 1** (Beyond Code) builds the **theoretical foundation**: why the old paradigm breaks down, what the new one must look like.

**Paper 2** (From PR to CP) builds the **engineering implementation**: a concrete, measured, working replacement for the 50-year-old Pull Request model.

Together, they form a complete argument:

```
Theory (Paper 1): Code review is mathematically unscalable in AI era
    ↓
Engineering (Paper 2): Here's what replaces it — and it works (73% time reduction)
    ↓
Platform (Zelos): Here's the open-source runtime that implements it
```

---

## Quick Read Path for a Busy Executive

1. **Start with Paper 2** (15 min) — the CP paper has the most immediate business impact. Read the abstract, the experiment results table, and Section 7 (Discussion).
2. **Then Paper 1** (20 min) — for the deeper "why this matters" argument. Read the Introduction, the First-Order Invariant, and the Core Theorem System sections.
3. **Then the Zelos README** (5 min) — to see the open-source platform that implements both.

---

## Publication Status & Plan

| Paper | Status | Target Venue | Confidence |
|-------|--------|-------------|-----------|
| Beyond Code | Manuscript ready | ICSE/FSE SEIP 2027 | High |
| From PR to CP | Manuscript ready, revised per reviewer feedback | ICSE/FSE SEIP 2027, ASE 2027 | High |
| Zelos Platform | Open-source, v0.9.1 on PyPI | Companion artifact for both papers | — |

Both papers have undergone rigorous internal review and revision. Reviewer feedback on the CP paper was incorporated (terminology refinements, AI-Assisted PR baseline addition, cognitive overhead quantification, honest 0% caveat declaration).
