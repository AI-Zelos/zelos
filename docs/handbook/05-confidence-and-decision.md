# 05 — Confidence and Decision

## From Evidence to a Single Number

After all agents execute and all evidence is collected, one question remains:

> **Should we ship this change?**

Confidence answers this with a single number: 0.0 (no trust) to 1.0 (complete trust).

## How Confidence is Computed

```
Evidence Bag
    ├── test_result: 3 PASS, 0 FAIL  → test_pass score = 1.0
    ├── security_scan: 1 PASS        → security score = 1.0
    ├── benchmark: 1 PASS            → benchmark score = 1.0
    └── api_diff: 0 items           → no contribution

Weighted sum, normalized by active evidence types:
    test_pass:  1.0 × 0.30 = 0.30
    security:   1.0 × 0.20 = 0.20
    benchmark:  1.0 × 0.15 = 0.15
    active_weight = 0.65
    Confidence = 0.65 / 0.65 = 1.0
```

## Recommendation

| Confidence | Risk | Recommendation |
|-----------|------|---------------|
| ≥ 0.95 | low | **approve** — auto-ship |
| ≥ 0.90 | low–medium | **approve** — auto-ship |
| 0.70–0.94 | medium+ | **need_human** — escalate |
| < 0.40 | any | **reject** — auto-reject |
| < 0.70 | any | **need_human** — escalate |

## The Core Insight

The human's job is no longer to read code. It's to look at a Confidence score, review the evidence breakdown, and decide: **approve or reject**. The Runtime does the rest.

## Next
[06 — Architecture Delta](06-architecture-delta.md)
