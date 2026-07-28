# ZEIP-0005: Capability

| Field | Value |
|-------|-------|
| **ZEIP** | 0005 |
| **Status** | Draft |
| **Version** | 1.0 |

## Abstract

A Capability describes **what** an Agent can do — never **who** the Agent is. Dispatch is by Capability name, never by Agent identity. This is one of Zelos's 15 Architecture Invariants.

## Specification

### Capability Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Namespaced name: `domain.subdomain` |
| `version` | string | Yes | Semantic version |
| `description` | string | No | Human-readable description |
| `input_schema` | dict | No | JSON Schema for input |
| `output_schema` | dict | No | JSON Schema for expected output |
| `qos` | dict | No | Quality-of-service metadata |
| `tags` | list[string] | No | Discovery tags |
| `cost_per_call` | float | No | Estimated cost |

### Naming Convention

```
{domain}.{subdomain}
```

Examples: `code-generation.python`, `code-review.security`, `automation.browser`, `data-query.sql`

### Rules

1. **Dispatch by name, never by agent ID.** The Scheduler matches Tasks to Agents via Capability.
2. **Versioning is required.** Schema changes require version bumps.
3. **Multiple Agents can register the same Capability.** The Scheduler picks the best one.

## Related
- ZEIP-0001: Intent
- ZEIP-0006: Policy
