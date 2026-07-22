# ADR-0005: Protocol Adapter Architecture

| Status       | Decided |
|--------------|---------|
| **Date**     | 2026-07-19 |
| **Deciders** | Zelos Architecture Team |
| **Depends On** | [ADR-0001](./ADR-0001-runtime-first.md), [ADR-0004](./ADR-0004-plugin-architecture.md) |

---

## Context

Zelos defines its own Runtime API — the native protocol for Kernel-to-Plugin communication. But the world already has protocols: MCP (tool access), A2A (agent interoperability), HTTP/gRPC (universal network protocols). Zelos must interoperate without depending on any of them.

Protocol dependence is architectural coupling. If the Runtime depends on MCP, MCP's evolution constrains the Runtime. The same applies to any external protocol.

### Relevant Invariants

- [Invariant 9](../architecture/invariants.md#invariant-9-contracts-over-implementation)
- [Invariant 13](../architecture/invariants.md#invariant-13-runtime-never-depends-on-llm)

---

## Decision

Zelos implements external protocols as **Adapters** — plugins that translate between external protocols and the Runtime API. All protocols are treated identically. None is privileged.

**Adapter responsibilities**: Parse external message → Validate → Translate → Runtime API call → Format response → Return.

**Key principle**: Adapters contain zero business logic, zero state. They are stateless translation layers.

---

## Consequences

### Positive

- Protocol independence — Runtime evolves independently of protocol evolution
- Future-proof — new protocols added without Kernel changes
- Clean boundaries — each protocol's concerns isolated
- Ecosystem compatibility — integrates with MCP tools, A2A agents, HTTP/gRPC services

### Negative

- Translation overhead — external messages must be translated to Runtime API
- Semantic gaps — external protocols may have concepts that don't map cleanly
- Adapter maintenance — each adapter must track protocol evolution
- Latency — translation adds processing time

### Mitigations

- Adapters are thin translation layers
- Semantic gaps documented as "best effort mapping"
- Adapter versions pinned to protocol versions
- Hot-path optimization for translation

---

## Alternatives Considered

### A1: MCP as Native Protocol

Use MCP as Zelos's internal protocol.

**Rejected**: MCP is designed for tool access, not multi-agent orchestration. Lacks task graphs, scheduling, capability matching, execution plans.

### A2: A2A as Native Protocol

Use A2A as the internal protocol.

**Rejected**: A2A assumes direct agent-to-agent communication. Zelos explicitly prevents this. Using A2A internally encodes the wrong communication pattern.

### A3: Direct Multi-Protocol Support in Kernel

Kernel natively understands MCP, A2A, HTTP, gRPC.

**Rejected**: Couples Kernel to external protocol evolution. Kernel becomes a protocol multiplexer, not an orchestration runtime.

---

## Trade-offs

| Trade-off | Choice | Rationale |
|-----------|--------|-----------|
| Native protocol vs. Adapters | Adapters | Protocol independence > translation efficiency |
| Single protocol vs. Multi-protocol | Multi-protocol via adapters | Ecosystem compatibility requires supporting all major protocols |
| Adapter in Kernel vs. Plugin | Plugin | Adding a protocol should never require Kernel changes |

---

## References

- [Architecture Invariants](../architecture/invariants.md)
- [ADR-0001: Runtime First](./ADR-0001-runtime-first.md)
- [ADR-0004: Plugin Architecture](./ADR-0004-plugin-architecture.md)
- [Blueprint: Protocol Layer](../blueprint/protocol-layer.md)
- [Blueprint: Runtime API](../blueprint/runtime-api.md)
