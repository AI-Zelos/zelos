# 09 — Policy and Governance

## Two Layers of Policy

Policy operates at two levels in Zelos:

**Execution Time (before dispatch):**
- Cost limits per task/goal
- Rate limits per minute
- Allowlists for capabilities

**Decision Time (after execution):**
- Auto-approve high-confidence, low-risk changes
- Auto-reject very low-confidence changes
- Escalate medium-confidence or high-risk to human review

## Policy Gate v2 (Decision Time)

```
Execution Report generated
    ↓
Policy Gate evaluates:
    risk_level == "critical"?      → require_human
    evidence has failures?          → require_human
    confidence >= 0.95, risk=low?   → auto_approve
    confidence < 0.40?              → auto_reject
    default                         → require_human
    ↓
Gate Decision (auto_approve / auto_reject / require_human)
```

## Governance Principles

1. **Policy is declarative** — no code in policy rules
2. **Policy runs after evidence** — decisions are evidence-driven
3. **Policy decisions are events** — immutable, auditable, replayable
4. **Default to human** — when in doubt, escalate. Safety over speed.

## The Governance Loop

```
Define Intent
    → Execute
    → Verify
    → Collect Evidence
    → Score Confidence
    → Apply Policy
    → Auto-approve / Reject / Escalate
    → Record Decision (immutable event)
```

Every decision is traceable. Every approval has evidence. Every rejection has a reason.

## Next
[10 — From Code Review to Change Review](10-from-code-review-to-change-review.md)
