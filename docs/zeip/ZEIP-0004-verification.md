# ZEIP-0004: Verification

| Field | Value |
|-------|-------|
| **ZEIP** | 0004 |
| **Status** | Draft |
| **Version** | 1.0 |

## Abstract

Verification is the process of checking that an Agent's output meets its expected contract. Verification is the **core value proposition** of the Zelos Runtime — Agent execution gets cheaper over time, but verification never does.

## Motivation

AI's biggest problem is not "can it write code?" — it is **"how do we know the code is correct?"** Zelos answers this by making Verification a first-class Runtime concern, not an afterthought.

## Specification

### Verifier Interface

```python
class Verifier(ABC):
    def verify(self, artifact: Artifact, expected_schema: dict) -> Verdict:
        """Verify an artifact against its expected schema."""
```

### Verdict

| Field | Type | Description |
|-------|------|-------------|
| `verdict` | string | `PASS` / `FAIL` / `WARN` |
| `reason` | string | Human-readable explanation |
| `details` | dict | Detailed findings |

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
