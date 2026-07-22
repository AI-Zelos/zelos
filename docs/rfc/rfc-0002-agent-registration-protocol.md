# RFC-0002: Agent Registration Protocol

| Status      | Draft |
|-------------|-------|
| **Date**    | 2026-07-19 |
| **Authors** | Zelos Architecture Team |

---

## Problem

Agents are the execution providers in Zelos. For the Runtime to dispatch work, it must know an Agent exists, what Capabilities it provides, that it's alive, and have a reliable channel for task dispatch and artifact return.

Without a standardized, minimal, stable Agent protocol, the ecosystem cannot grow. Every Agent developer must implement this protocol — it must be as simple and stable as possible.

---

## Proposal

Define a 5-method Agent protocol:

```
register(capabilities)  → RegistrationResponse
heartbeat()             → HeartbeatResponse
execute(task)           → Artifact
cancel(task_id)         → CancelResponse
shutdown()              → void
```

### Registration

Agent declares identity, Capabilities (name, version, schemas, QoS), endpoint, protocol support, and capacity. Runtime validates, assigns agent_id, indexes capabilities. Agent begins heartbeat loop.

### Heartbeat

Agent sends heartbeat at configured interval (default: 30s). Runtime acknowledges. If `3 * interval` passes without heartbeat → Agent disconnected, capabilities unavailable, in-flight tasks reassessed.

### Task Execution

Runtime dispatches fully-assembled Task (description, input artifact, context, constraints, timeout). Agent executes and returns Artifact. Runtime handles timeout enforcement.

### Cancellation

Runtime sends cancel signal for a specific task. Agent acknowledges and stops work. Partial results discarded.

### Shutdown

Agent notifies Runtime before disconnecting. In-flight tasks: wait or cancel per policy.

---

## Compatibility

**Backward compatible**: This establishes v1.0 of the Agent protocol. Future versions must maintain backward compatibility or require explicit version negotiation at registration.

**Version negotiation**: Agent declares `protocol_version` at registration. Runtime checks compatibility. If incompatible, registration rejected with reason.

---

## Migration

Not applicable — establishes the initial protocol. Future protocol versions will require:
1. Agent declares new protocol version at registration
2. Runtime supports multiple versions simultaneously during migration period
3. Old version deprecated with notice period

---

## Open Questions

1. **Streaming progress**: Should Agents report incremental progress during execution? Current: No. Full artifact only in Phase 1.

2. **Task rejection**: Can an Agent reject a task after assignment? **Yes.** Agents may reject tasks after assignment. Rejection triggers immediate re-scheduling (Task returns to `ready` state, Scheduler picks the next best candidate). Rejections count against the Agent's historical success rate, which carries 30% weight in Scheduler scoring — this creates a natural economic disincentive against malicious rejection without requiring hard prohibition. Resolved: 2026-07-19.

3. **Partial results on cancel**: Should cancelled tasks return partial work? Current: Discarded. Useful for long-running research tasks.

4. **Agent authentication**: API keys (Phase 1), mTLS (Phase 2), signed capability claims (Phase 3)? **Resolved (2026-07-19): Phase 1 uses API Key Bearer tokens only.** `Authorization: Bearer <key>` header. Keys are configured in `zelos.yaml` under `runtime.auth.keys` with roles: `admin`, `agent`, `client`. mTLS deferred to Phase 2.

5. **Bidirectional streaming**: For long-running tasks, should protocol support streaming output? Current: Request/response only in Phase 1.

---

## Alternatives Considered

### A1: REST-only Protocol

Define Agent protocol as pure HTTP REST endpoints.

**Rejected**: Too limiting. gRPC streaming is valuable for long-running tasks and progress reporting. The protocol should be transport-agnostic.

### A2: Agent Push Model

Agents pull tasks from a queue rather than Runtime pushing tasks.

**Rejected**: Runtime loses control over scheduling. Cannot optimize globally if agents self-select tasks.

### A3: Rich Agent SDK Required

Require Agents to use a heavyweight SDK that handles registration, heartbeat, retry internally.

**Rejected**: SDKs are optional conveniences. The protocol must be implementable with raw HTTP — SDKs wrap the protocol, not define it.

---

## References

- [Architecture Invariants](../architecture/invariants.md) — Invariants 1, 5, 6
- [ADR-0002: Capability First](../adr/ADR-0002-capability-first.md)
- [ADR-0005: Protocol Adapter Architecture](../adr/ADR-0005-protocol-adapter-architecture.md)
- [Blueprint: Runtime API](../blueprint/runtime-api.md)
- [Blueprint: Execution Engine](../blueprint/execution-engine.md)
- [Blueprint: Capability Registry](../blueprint/capability-registry.md)
