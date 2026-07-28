# ZEIP-0001: Intent Specification

| Field | Value |
|-------|-------|
| **ZEIP** | 0001 |
| **Title** | Intent Specification |
| **Status** | Draft |
| **Version** | 1.0 |
| **Created** | 2026-07-28 |
| **Author** | Zelos Core Team |

## Abstract

Intent is the structured representation of a user's Goal. It is the entry point to the Zelos runtime — before any Agent runs, Intent defines **what success looks like, what constraints apply, and what is explicitly out of scope.**

## Motivation

`submit_goal("Implement login")` is insufficient. The Planner may misunderstand scope. The Agent may produce a correct implementation of the wrong thing. IntentSpec prevents this by requiring the user to articulate:
- What business problem this solves
- What success looks like (verifiable criteria)
- What constraints must not be violated
- What is explicitly NOT included (scope boundary)

## Specification

### IntentSpec Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `description` | string | Yes | Natural language description of the goal |
| `success_criteria` | list[string] | No | Verifiable success conditions |
| `constraints` | list[string] | No | Hard constraints that must not be violated |
| `scope` | string | No | `single_module` / `multi_module` / `system_wide` / `auto` |
| `rollback_on_failure` | boolean | No | Whether to auto-rollback on failure (default: true) |

### Example

```json
{
  "description": "Implement OAuth2 login with Google and GitHub",
  "success_criteria": [
    "Users can sign in with Google OAuth",
    "Users can sign in with GitHub OAuth",
    "Auth tokens expire after 24 hours",
    "Existing password login still works"
  ],
  "constraints": [
    "Do not modify password hashing logic",
    "Use standard OAuth2.0 libraries",
    "No client_secret in frontend code"
  ],
  "scope": "single_module",
  "rollback_on_failure": true
}
```

### Backward Compatibility

`IntentSpec` is optional. If not provided, the Runtime falls back to the legacy `description`-only mode. This ensures v0.8.x code continues to work unchanged.

## Implementation Notes

- `IntentSpec` is a Python dataclass in `zelos/execution_report.py`
- Exposed via `runtime.submit_goal(description, intent=IntentSpec(...))`
- Stored in the Goal dict as `goal["intent"]`
- Included in `ExecutionReport` via `report.intent`

## Related

- ZEIP-0003: Evidence
- ZEIP-0006: Policy
- ZEIP-0007: Change Proposal
