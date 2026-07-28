# ZEIP-0002: Artifact

| Field | Value |
|-------|-------|
| **ZEIP** | 0002 |
| **Status** | Draft |
| **Version** | 1.0 |

## Abstract

An Artifact is the structured output of a Task execution. Every Agent execution produces exactly one Artifact. The Artifact is immutable — created once, never modified.

## Motivation

Without a standard Artifact format, every Agent returns different shapes of output. Downstream Tasks, Verifiers, and Evidence collectors cannot reliably consume Agent output.

## Specification

### Artifact Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `content_type` | string | Yes | MIME type of the content |
| `content` | any | Yes | The actual output data |
| `content_ref` | string | No | Storage reference for large content |
| `size_bytes` | int | No | Size of the content |
| `verification_status` | string | No | `pending` / `verified` / `rejected` |

### Rules

1. **Immutability**: Once created, an Artifact MUST NOT be modified.
2. **Content reference**: If `size_bytes > 100KB`, content SHOULD be stored in StorageBackend and referenced via `content_ref`.
3. **Verification**: Every Artifact SHOULD be verified by at least one Verifier before downstream consumption.

## Related
- ZEIP-0003: Evidence
- ZEIP-0004: Verification
