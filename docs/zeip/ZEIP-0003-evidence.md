# ZEIP-0003: Evidence

| Field | Value |
|-------|-------|
| **ZEIP** | 0003 |
| **Title** | Evidence |
| **Status** | Draft |
| **Version** | 1.0 |
| **Created** | 2026-07-28 |
| **Author** | Zelos Core Team |

## Abstract

Evidence is typed, verifiable proof that a Task was executed correctly. Evidence is the **currency of trust** in Zelos — it is what turns "the agent says it worked" into "we can prove it worked."

## Motivation

An Agent returning `{"status": "completed"}` tells you nothing about quality. Evidence requires the Agent to produce specific, typed, verifiable proof: test results, benchmark data, security scan output, API diffs.

## Specification

### Evidence Types

| Type | Tool Examples | Required Data |
|------|---------------|---------------|
| `test_result` | pytest, jest, go-test | `passed`, `failed`, `coverage_pct` |
| `benchmark` | wrk, k6, locust | `metric`, `baseline`, `actual` |
| `security_scan` | bandit, trivy, snyk | `issues`, `severity_high` |
| `api_diff` | openapi-diff | `breaking_changes`, `new_endpoints` |
| `canary` | custom | `duration_s`, `error_rate` |
| `code_review` | sonarqube, codeql | `issues`, `severity` |
| `custom` | any | any |

### Evidence Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | One of the types above |
| `tool` | string | Yes | Tool that produced the evidence |
| `result` | string | Yes | `PASS` / `FAIL` / `WARN` / `SKIP` |
| `data` | dict | Yes | Quantified, structured data |
| `summary` | string | No | Human-readable one-line summary |
| `timestamp` | float | No | Collection timestamp |

### Rules

1. **Every completed Task SHOULD produce at least one Evidence item.**
2. **Evidence.result = FAIL → EvidenceBag.all_pass = False → Policy Gate must be consulted.**
3. **Evidence data MUST be quantified. "Tests passed" is insufficient — must state "47 passed, 0 failed."**

## Related
- ZEIP-0001: Intent
- ZEIP-0004: Verification
- ZEIP-0006: Policy
