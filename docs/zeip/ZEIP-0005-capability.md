# ZEIP-0005: Capability

| Field | Value |
|-------|-------|
| **ZEIP** | 0005 |
| **Title** | Capability |
| **Status** | Draft |
| **Version** | 1.0 |
| **Created** | 2026-07-28 |
| **Author** | Zelos Core Team |

## Abstract

A Capability describes **what** an Agent can do — never **who** the Agent is. Dispatch is by Capability name, never by Agent identity. This is one of Zelos's 15 Architecture Invariants.

## Specification

### CapabilityEntry Fields

The canonical capability entry in the Capability Registry:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Namespaced name: `domain.subdomain` |
| `version` | string | Yes | Semantic version (e.g., `1.0.0`) |
| `description` | string | No | Human-readable description |
| `input_schema` | dict | No | JSON Schema for expected Task input |
| `output_schema` | dict | No | JSON Schema for expected Task output |
| `tags` | list[string] | No | Discovery and filtering tags |
| `agent_id` | string | (auto) | Agent that registered this capability |
| `agent_name` | string | (auto) | Human-readable agent name |

Note: `agent_id` and `agent_name` are set automatically by the Capability Registry at registration time, not provided by the user.

### Naming Convention

```
{domain}.{subdomain}
```

Examples: `code-generation.python`, `code-review.security`, `automation.browser`, `data-query.sql`

### Rules

1. **Dispatch by name, never by agent ID.** The Scheduler matches Tasks to Agents via Capability name, not agent identity.
2. **Versioning is required.** Schema changes require version bumps. The Registry supports version-range queries.
3. **Multiple Agents can register the same Capability.** The Scheduler selects the best provider at dispatch time based on scoring strategy.
4. **Capabilities are immutable once registered.** To change a capability, register a new version.

## Related
- ZEIP-0001: Intent
- ZEIP-0006: Policy
