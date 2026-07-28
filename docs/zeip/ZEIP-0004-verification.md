# ZEIP-0004: Verification

| Field | Value |
|-------|-------|
| **ZEIP** | 0004 |
| **Title** | Verification |
| **Status** | Draft |
| **Version** | 1.0 |
| **Created** | 2026-07-28 |
| **Author** | Zelos Core Team |

## Abstract

Verification is the process of checking that an Agent's output meets its expected contract. Verification is the **core value proposition** of the Zelos Runtime — Agent execution gets cheaper over time, but verification never does.

## Motivation

AI's biggest problem is not "can it write code?" — it is **"how do we know the code is correct?"** Zelos answers this by making Verification a first-class Runtime concern, not an afterthought.

## Specification

### Verifier Interface

```python
class Verifier(ABC):
    def verify(self, artifact_content: Any, criteria: VerificationCriteria) -> Verdict:
        """Verify artifact content against verification criteria."""
```

### VerificationCriteria

| Field | Type | Description |
|-------|------|-------------|
| `expected_schema` | dict | JSON Schema the artifact must conform to |
| `constraints` | list[str] | Additional constraints to check |
| `severity` | string | `error` / `warning` — failures at `error` level block the chain |

### Verdict Fields

| Field | Type | Description |
|-------|------|-------------|
| `verdict` | string | `PASS` / `FAIL` / `WARN` |
| `reason` | string | Human-readable explanation |
| `details` | dict | Detailed findings |
| `confidence` | float | Per-verifier confidence (0.0-1.0) |

### Verifier Chain

A Task MAY have multiple Verifiers. They execute in sequence:

```
Artifact → Verifier₁ → Verifier₂ → Verifier₃ → Final Verdict
```

If any Verifier returns `FAIL`, the chain stops and the Task is marked as verification-failed.

### Built-in Verifiers

| Verifier | Checks |
|----------|--------|
| SchemaVerifier | JSON Schema conformance |
| CodeReviewer | Anti-patterns, complexity |
| SecurityScanner | Vulnerability patterns |
| FactChecker | Claim vs. evidence consistency |

### Rules

1. **Every Artifact MUST pass at least one Verifier before being consumed by downstream Tasks.**
2. **Confidence < threshold SHOULD trigger additional Verifiers** (verification escalation).
3. **Verification results are Evidence** (see ZEIP-0003).

## Related
- ZEIP-0002: Artifact
- ZEIP-0003: Evidence
- ZEIP-0005: Capability
