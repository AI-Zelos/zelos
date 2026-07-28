# 04 — Verification and Evidence

## The Core Problem

AI's biggest challenge is not generation — it's verification. An agent can produce 10,000 lines of code in seconds. How do you know it's correct?

The answer: **you don't trust the agent. You trust the evidence.**

## Verification Chain

Every Artifact passes through a chain of Verifiers:

```
Agent Output (Artifact)
    → SchemaVerifier     (does it match the expected JSON Schema?)
    → CodeReviewer       (any anti-patterns or complexity issues?)
    → SecurityScanner    (any vulnerability patterns?)
    → Final Verdict      (PASS / FAIL / WARN)
```

If any Verifier returns FAIL, the chain stops. The Task is marked as verification-failed.

## Evidence

Evidence is **typed, quantified, verifiable proof**. It's the currency of trust in Zelos.

An agent should never return just `{"status": "completed"}`. It should return:

```python
evidence=[
    Evidence(type="test_result", tool="pytest", result="PASS",
             data={"passed": 47, "failed": 0, "coverage_pct": 89}),
    Evidence(type="security_scan", tool="bandit", result="PASS",
             data={"issues": 0}),
    Evidence(type="benchmark", tool="wrk", result="PASS",
             data={"tps": 1120, "baseline_tps": 850}),
]
```

## Verification Escalation

Low confidence triggers **more verification**:

```
Initial Verifiers → Confidence 0.60 (below threshold)
    → Deploy additional Verifiers
    → Confidence 0.85 (still below)
    → Deploy more Verifiers
    → Confidence 0.94 → Above threshold → Proceed
```

## The Rule

> **Agent will get cheaper. Verification never will. That's where the value is.**

## Next
[05 — Confidence and Decision](05-confidence-and-decision.md)
