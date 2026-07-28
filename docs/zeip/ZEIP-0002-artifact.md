# ZEIP-0002: Artifact

| Field | Value |
|-------|-------|
| **ZEIP** | 0002 |
| **Title** | Artifact |
| **Status** | Draft |
| **Version** | 1.0 |
| **Created** | 2026-07-28 |
| **Author** | Zelos Core Team |

## Abstract

An Artifact is the structured output of a Task execution. Every Agent execution produces exactly one Artifact. The Artifact is immutable — created once, never modified.

## Motivation

Without a standard Artifact format, every Agent returns different shapes of output. Downstream Tasks, Verifiers, and Evidence collectors cannot reliably consume Agent output.

## Specification

### Artifact Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `artifact_id` | string | Yes | Unique artifact identifier |
| `task_id` | string | Yes | The Task that produced this artifact |
| `agent_id` | string | Yes | The Agent that executed the Task |
| `content_type` | string | Yes | MIME type of the content (default: `application/json`) |
| `content` | any | Yes | The actual output data |
| `content_ref` | string | No | Storage reference for large content |
| `size_bytes` | int | No | Size of the content in bytes |
| `verification_status` | string | No | `pending` / `verified` / `rejected` |
| `execution_metadata` | dict | No | Arbitrary metadata about the execution |

### Rules

1. **Immutability**: Once created, an Artifact MUST NOT be modified.
2. **Content reference**: If `size_bytes > 100KB`, content SHOULD be stored in StorageBackend and referenced via `content_ref` to avoid bloating event payloads.
3. **Verification**: Every Artifact SHOULD be verified by at least one Verifier before downstream Tasks consume it.
4. **Traceability**: `artifact_id`, `task_id`, and `agent_id` together provide full traceability from output back to the execution context.

## Related
- ZEIP-0003: Evidence
- ZEIP-0004: Verification
