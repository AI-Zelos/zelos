# RFC-0003: Event Bus Specification

| Status      | Draft |
|-------------|-------|
| **Date**    | 2026-07-19 |
| **Authors** | Zelos Architecture Team |

---

## Problem

The Event Bus is the central nervous system of Zelos. Every component communicates through events — no component calls another directly. If the Event Bus fails, the Runtime fails.

Currently, event semantics are scattered across the domain model, execution model, and runtime lifecycle documents. We need a single authoritative specification covering: event schema, type taxonomy, ordering guarantees, delivery semantics, subscription model, persistence, and replay.

---

## Proposal

### Event Structure

```
Event {
    event_id: UUID              // Globally unique, idempotency key
    event_type: String          // domain.entity.action (e.g., "task.completed")
    source: String              // Publishing component
    timestamp: RFC3339          // Publication time
    correlation_id: UUID        // Groups related events (same Task/Goal)
    causation_id: UUID?         // Causal predecessor event
    data_version: String        // Payload schema version
    payload: Object             // Type-specific data
    metadata: { trace_id, span_id }
}
```

### Type Taxonomy

`{domain}.{entity}.{action}` — 9 domains, 50+ event types. Full catalog in [Event Bus Blueprint](../blueprint/event-bus.md).

### Ordering Guarantees

| Scope | Guarantee |
|-------|-----------|
| Per event type | Total order |
| Per correlation_id | Causal order |
| Per entity | Total order |
| Across types | No guarantee |

### Delivery: At-Least-Once (Phase 1)

Subscribers must be idempotent. `event_id` serves as idempotency key.

### Subscription

```
subscribe(event_type, handler) → Subscription
subscribe_pattern("task.*", handler) → Subscription
subscribe_correlation(correlation_id, handler) → Subscription
```

### Persistence

All events appended to Event Store (append-only log). Replay support for state reconstruction and crash recovery.

### Immutability

Events are immutable. Never modified. Never deleted. Corrections via corrective events.

---

## Compatibility

**Backward compatible**: Adding new event types is always safe. Adding required fields to event payloads requires a `data_version` bump (major).

**Subscriber compatibility**: Subscribers must handle unknown event types gracefully (no-op) and unknown payload fields (ignore).

---

## Migration

Not applicable — establishes the initial Event Bus specification. Future migration concerns (e.g., moving from in-memory to Kafka) are implementation details that do not affect the event schema or API.

---

## Open Questions

1. **Exactly-once delivery**: Is it needed, or is at-least-once with idempotent handlers sufficient?

2. **Event size limits**: Maximum event size? Large artifacts referenced by URI, not embedded. **Resolved (2026-07-19): Phase 1 limit is 1 MB per event.** Events exceeding 1 MB are rejected at publish time. Large Artifacts must use `content_ref` (URI reference) rather than inline `content`. This limit is enforced by the Event Bus, not the publisher.

3. **Dead letter queue**: Undeliverable events → dead letter queue for manual inspection?

4. **Event compaction**: For state-representing events, compaction (keep only latest per key)?

5. **Wildcard subscriptions**: Prefix matching (`task.*`) only, or full glob/regex? **Resolved (2026-07-19): Phase 1 supports prefix matching only.** The pattern `domain.*` matches all events under that domain (e.g., `task.*` matches `task.created`, `task.completed`, `task.failed`, etc.). Single-level wildcards (`task.*.result`) and full regex are deferred to Phase 2+.

---

## Alternatives Considered

### A1: Direct Component-to-Component Calls

Components call each other directly. No Event Bus.

**Rejected**: Tight coupling. Changing one component requires changing all callers. No audit trail. Violates Invariant 9.

### A2: Central Message Queue (Kafka-like) from Day 1

Use a full distributed message queue even in Phase 1.

**Rejected**: Over-engineering for Phase 1. In-process Event Bus with the same API allows seamless migration to distributed queue in Phase 3.

### A3: Webhook-based (HTTP Callbacks)

Components register HTTP callbacks. Events delivered as HTTP POST.

**Rejected**: Too much latency for internal Kernel communication. Appropriate for external notifications, not internal orchestration.

---

## References

- [Architecture Invariants](../architecture/invariants.md) — Invariants 7, 9
- [Blueprint: Event Bus](../blueprint/event-bus.md)
- [Blueprint: Domain Model](../blueprint/domain-model.md) — Event entity
- [Schema: Event](../schema/event.json)
