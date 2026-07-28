# 01 — What is Agent Engineering?

## Software Engineering Before Agents

For 50 years, software engineering followed the same fundamental loop:

```
Human understands requirements
    → Human writes code
    → Human reviews code
    → Machine compiles and runs
```

The bottleneck was always **code production**. Humans are slow at writing code. Tooling evolved around this constraint: IDEs for speed, linters for consistency, code review for quality, CI/CD for safety.

## The Shift

In 2025–2026, AI crossed a threshold. It can now produce working code faster than any human. A single Claude Code session can output 5,000–35,000 lines per hour — across dozens of files, with tests, documentation, and configuration.

The bottleneck inverted. **Code production is no longer the constraint. Trust is.**

The new loop looks like this:

```
Human defines Intent
    → AI produces implementation
    → Multiple Verifiers check the output
    → Evidence is collected and scored
    → Human approves the change (not the code)
    → System deploys with rollback on standby
```

## What Agent Engineering Is

Agent Engineering is the discipline of **managing software changes produced by AI agents at industrial scale**. It encompasses:

1. **Intent Specification** — defining what success looks like before any code is written
2. **Execution Planning** — decomposing goals into verifiable, capability-matched tasks
3. **Verification Architecture** — designing chains of checks that prove correctness
4. **Evidence Collection** — requiring agents to produce typed, quantified proof
5. **Confidence Scoring** — computing a single trust score from multiple evidence sources
6. **Policy Governance** — defining rules for auto-approval, escalation, and rejection
7. **Change Approval** — reviewing evidence packages, not code diffs

## How It Differs from Traditional SE

| Traditional SE | Agent Engineering |
|---------------|-------------------|
| Code is the primary artifact | Change proposal is the primary artifact |
| Human writes, human reviews | AI writes, Verifiers check, human approves |
| Quality = code review | Quality = evidence score |
| Merge = done | Merge = approved change with rollback plan |
| Audit = git log | Audit = immutable event chain |

## The Role of a Runtime

Agent Engineering requires a Runtime that:

- **Orchestrates** the Intent → Plan → Execute → Verify → Decide loop
- **Collects** Evidence from every agent execution
- **Scores** Confidence from all available evidence
- **Enforces** Policy at both execution time and decision time
- **Records** every decision as an immutable, replayable event

This is what Zelos provides.

## Next
[02 — Intent Specification](02-intent-specification.md)
