# ZEIP-0006: Policy

| Field | Value |
|-------|-------|
| **ZEIP** | 0006 |
| **Title** | Policy |
| **Status** | Draft |
| **Version** | 1.0 |
| **Created** | 2026-07-28 |
| **Author** | Zelos Core Team |

## Abstract

Policy defines the rules that govern Agent behavior. It operates at two levels: **execution-time** (before dispatch: cost limits, rate limits, allowlists) and **decision-time** (after execution: auto-approve, auto-reject, human escalation based on Evidence and Confidence).

## Motivation

Without Policy, every Agent decision is either manual (human bottleneck) or ungoverned (risk). Policy provides the middle ground: **define rules once, let the Runtime enforce them automatically.**

## Specification

### Execution-Time Policy (v0.8.x)

| Policy | What it does |
|--------|-------------|
| CostLimitPolicy | Reject Tasks exceeding per-call or per-goal budget |
| RateLimitPolicy | Limit Tasks per minute |
| AllowlistPolicy | Only allow specific Capabilities or Agents |

### Decision-Time Policy (v0.9.x: Policy Gate v2)

| Rule | Condition | Action |
|------|-----------|--------|
| Critical risk | `risk_level == "critical"` | `require_human` |
| Evidence failure | `evidence_bag.all_pass == False` | `require_human` |
| High confidence + low risk | `confidence >= 0.95 AND risk == "low"` | `auto_approve` |
| High confidence + medium risk | `confidence >= 0.90 AND risk in ("low","medium")` | `auto_approve` |
| Very low confidence | `confidence < 0.40` | `auto_reject` |
| Default | none of the above | `require_human` |

### GateDecision Fields

| Field | Type | Description |
|-------|------|-------------|
| `action` | string | `auto_approve` / `auto_reject` / `require_human` |
| `reason` | string | Why this decision was made |
| `required_approvers` | list[string] | Who must approve (when `require_human`) |

### Rules

1. **Policy MUST be declarative** — no code in policy rules.
2. **Policy runs AFTER Evidence collection** — decisions are evidence-driven.
3. **Policy decisions are Events** — immutable, replayable, auditable.

## Related
- ZEIP-0001: Intent
- ZEIP-0003: Evidence
- ZEIP-0007: Change Proposal
