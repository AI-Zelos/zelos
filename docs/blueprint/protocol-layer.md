# Protocol Layer

> External protocol translation into the Runtime API. HTTP, gRPC, MCP, A2A adapters — their roles, boundaries, and relationships.

---

## Document Status

| Status  | Author                     | Date       |
|---------|----------------------------|------------|
| Revised | Zelos Architecture Team  | 2026-07-19 |

---

## 1. Overview

The Protocol Layer is the outermost layer. It translates external wire protocols into the Runtime API. It contains no business logic, no state, no decisions. [Invariant 9](../architecture/invariants.md#invariant-9-contracts-over-implementation).

### 1.1 Position

```
External Systems
      │
      ▼
┌─────────────────────────────┐
│      PROTOCOL LAYER (L5)     │
│                              │
│  HTTP    gRPC    MCP    A2A  │  ← Adapters (Plugins)
│  Adapter Adapter Adapter Adapter
│                              │
│  Protocol → Runtime API      │
└────────────┬─────────────────┘
             │
             ▼
┌─────────────────────────────┐
│      RUNTIME API (L4)        │
│  (stable, transport-agnostic)│
└─────────────────────────────┘
```

### 1.2 Adapter Rule

Every adapter:
- Translates one external protocol → Runtime API
- Contains no business logic
- Contains no persistent state
- Is stateless and horizontally scalable
- Is replaceable without Kernel changes

---

## 2. HTTP Adapter

### 2.1 Purpose

Primary external interface. Used by web clients, SDKs, and curl-based tooling.

### 2.2 Endpoint Mapping

| Runtime API | HTTP Method | Path |
|------------|-------------|------|
| SubmitGoal | POST | `/api/v1/goals` |
| GetGoalStatus | GET | `/api/v1/goals/{goal_id}` |
| ListGoals | GET | `/api/v1/goals` |
| CancelGoal | DELETE | `/api/v1/goals/{goal_id}` |
| WatchGoal | GET (Upgrade to WS) | `/api/v1/goals/{goal_id}/events` |
| GetPlan | GET | `/api/v1/goals/{goal_id}/plan` |
| Register | POST | `/api/v1/agents` |
| Heartbeat | POST | `/api/v1/agents/{agent_id}/heartbeat` |
| SubmitResult | POST | `/api/v1/agents/{agent_id}/tasks/{task_id}/result` |
| ListAgents | GET | `/api/v1/agents` |
| GetAgent | GET | `/api/v1/agents/{agent_id}` |
| ListCapabilities | GET | `/api/v1/capabilities` |
| GetHealth | GET | `/api/v1/health` |
| GetMetrics | GET | `/api/v1/admin/metrics` |

### 2.3 Error Mapping

| Runtime Error | HTTP Status |
|--------------|-------------|
| invalid_input | 400 Bad Request |
| unauthorized | 401 Unauthorized |
| forbidden | 403 Forbidden |
| not_found | 404 Not Found |
| conflict | 409 Conflict |
| timeout | 408 Request Timeout |
| rate_limited | 429 Too Many Requests |
| internal_error | 500 Internal Server Error |
| service_unavailable | 503 Service Unavailable |

### 2.4 Authentication

| Method | Description | Phase |
|--------|-------------|-------|
| API Key (Bearer) | `Authorization: Bearer <key>` | Phase 1 |
| mTLS | Mutual TLS | Phase 2 |
| OAuth 2.0 | Token-based delegation | Phase 2 |

---

## 3. gRPC Adapter

### 3.1 Purpose

High-performance, strongly-typed service-to-service communication. Used by SDKs and internal services.

### 3.2 Service Definition

```protobuf
service Zelos {
    rpc SubmitGoal(SubmitGoalRequest) returns (Goal);
    rpc GetGoalStatus(GetGoalStatusRequest) returns (Goal);
    rpc CancelGoal(CancelGoalRequest) returns (Goal);
    rpc WatchGoal(WatchGoalRequest) returns (stream Event);
    
    rpc RegisterAgent(RegisterAgentRequest) returns (Agent);
    rpc AgentHeartbeat(HeartbeatRequest) returns (HeartbeatResponse);
}
```

### 3.3 Advantages over HTTP

- Protocol Buffers (binary, typed, smaller payloads)
- Bidirectional streaming (for event watching and progress)
- Built-in deadline propagation
- Service reflection for client generation

### 3.4 Phase

Phase 2 (HTTP adapter is Phase 1 priority).

---

## 4. MCP Adapter

### 4.1 What MCP Is

MCP (Model Context Protocol) is a protocol for AI models to access tools and resources.

### 4.2 Role in Zelos

MCP is NOT how Agents communicate with the Runtime.

MCP is how Agents access **tools** during Task execution.

```
Agent executing a task:
  │
  ├─→ Runtime API: "Task received, executing..."
  │
  ├─→ MCP: Access GitHub tool (read repository)
  ├─→ MCP: Access Database tool (query schema)
  ├─→ MCP: Access Browser tool (take screenshot)
  │
  └─→ Runtime API: "Here is the Artifact"
```

The Runtime is unaware of MCP. The Agent manages its own MCP connections.

### 4.3 MCP Adapter Role (Future)

When the Runtime needs to manage MCP for Agents:
- MCP Server lifecycle management
- Tool registry (which tools are available to which Agents)
- Tool invocation auditing

### 4.4 Phase

Phase 2 (Agent-managed MCP is Phase 1).

---

## 5. A2A Adapter

### 5.1 What A2A Is

A2A (Agent-to-Agent Protocol) is a protocol for interoperable agent communication across systems.

### 5.2 Role in Zelos

A2A is NOT the internal Zelos communication protocol.

A2A is an **external interoperability adapter** for:

1. **Runtime ↔ Runtime**: Two Zelos instances coordinating across organizations
2. **External Agent Integration**: Non-Zelos agents participating in Zelos Goals
3. **Third-Party Agent Services**: Delegating work to external agent services

### 5.3 Translation

| A2A Concept | Zelos Mapping |
|------------|----------------|
| Agent Card | Capability declaration |
| Task | Task (dispatched to external agent) |
| Message | Event (published on Event Bus) |
| Artifact | Artifact |

### 5.4 Key Difference

A2A assumes direct agent-to-agent communication. Zelos prohibits this. The A2A Adapter routes all A2A messages through the Runtime:

```
A2A message: Agent A → Agent B
A2A Adapter translates to: Agent A → Runtime → Agent B
```

This ensures governance, observability, and policy enforcement.

### 5.5 Phase

Phase 2.

---

## 6. Adapter Comparison

| Adapter | Protocol | Transport | Primary Use Case | Phase |
|---------|----------|-----------|-----------------|-------|
| HTTP | REST/JSON | HTTP/1.1, HTTP/2 | Web clients, SDKs, curl | Phase 1 |
| gRPC | Protobuf | HTTP/2 | Service-to-service, SDKs | Phase 2 |
| MCP | JSON-RPC | stdio, HTTP | Agent tool access | Phase 2 |
| A2A | A2A spec | HTTP | External agent integration | Phase 2 |
| WebSocket | JSON frames | WebSocket | Real-time event streaming | Phase 2 |

---

## 7. Protocol Layer Invariants

1. Adapters contain zero business logic
2. Adapters contain zero persistent state
3. Adding a new protocol does not require Kernel changes
4. Removing an adapter does not affect other adapters or the Kernel
5. All adapters translate to the same Runtime API — the Runtime sees no difference

---

## 8. References

- [Architecture Invariants](../architecture/invariants.md) — Invariants 9, 13
- [ADR-0005](../adr/ADR-0005-protocol-adapter-architecture.md) — Protocol adapter architecture decision
- [Runtime API](./runtime-api.md) — The API that adapters translate to
- [Plugin Architecture](./plugin-architecture.md) — Adapters are plugins
- [Kernel Boundary](./kernel-boundary.md) — Adapters are outside Kernel
