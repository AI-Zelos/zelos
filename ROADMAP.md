# ROADMAP

> Zelos Development Roadmap

---

## Phase 0: Architecture (Current)

**Status:** Complete
**Timeline:** July 2026

### Goal

Establish the complete architecture specification as the single source of truth. No code is written.

### Deliverables

- [x] Architecture Invariants (15 principles)
- [x] Glossary (canonical terminology)
- [x] Domain Model (all entities, lifecycles, relationships)
- [x] Kernel Boundary (Kernel vs. Plugin vs. SDK)
- [x] 6 Architecture Decision Records
- [x] 12 Architecture Blueprints
- [x] 4 RFC Skeletons
- [x] 6 Versioned JSON Schemas
- [x] README (project entry point)
- [x] ROADMAP (this document)

### Success Criteria

A new engineer can understand the entire Runtime architecture without reading any code.

---

## Phase 1: Runtime Kernel

**Status:** Not Started
**Timeline:** TBD

### Goal

Implement the minimal viable Runtime Kernel — single-node, in-process.

### Scope

- Event Bus (in-process, pub/sub, event persistence)
- Capability Registry (registration, indexing, query)
- Task Graph Engine (state machine, dependency resolution)
- Scheduler (capability matching, basic scoring, FIFO dispatch)
- Execution Engine (dispatch, heartbeat, timeout, retry)
- Plugin Lifecycle Manager (load, configure, start, health check)
- Runtime API (Goal API, Agent API, Admin API)
- HTTP Protocol Adapter
- Python SDK (Agent base class, Goal submission)

### Out of Scope

- Distributed deployment
- Persistent storage (in-memory only)
- Advanced scheduling (cost, latency optimization)
- Plugin isolation (in-process only)
- MCP / A2A adapters
- Verifier framework (manual verification only)
- Policy engine

---

## Phase 2: Developer Platform

**Status:** Not Started
**Timeline:** TBD

### Goal

Complete development platform. Enable production use cases.

### Scope

- Pluggable Planner (LLM-based default, custom planner support)
- Verifier framework (schema, code review, security verifiers)
- Policy engine (cost limits, rate limits, allowlists)
- Memory architecture (all 6 layers, pluggable backends)
- Advanced Scheduler (cost-aware, latency-aware, affinity)
- Protocol Adapters (gRPC, MCP, A2A, WebSocket)
- Observability (OpenTelemetry, Prometheus, structured logging)
- SDKs (Python production, TypeScript, Go)
- Plugin isolation (sub-process mode)

---

## Phase 3: Runtime Ecosystem

**Status:** Complete
**Timeline:** July 2026

### Goal

Production-grade distributed infrastructure.

### Scope

- [x] Distributed Runtime (multi-node, work stealing, leader election)
- [x] Persistent Storage (Kafka/NATS, PostgreSQL, etcd) — Phase 2 completed
- [x] Security (mTLS, capability-scoped access control, audit logging)
- [x] Multi-tenancy (namespace isolation, resource quotas)
- [x] Advanced Execution (dynamic plan modification, sub-goal spawning, human-in-the-loop)
- [x] Plugin isolation (container and remote modes)
- [x] Hot reload (plugin upgrade without Runtime restart)
- [x] CLI tool, Dashboard, Documentation site

---

## Beyond: Ecosystem Projects

Explicitly NOT part of Zelos core. Future ecosystem:

- Agent Marketplace
- Cloud Zelos (managed SaaS)
- Enterprise Portal
- Agent IDE
- Benchmark Suite

---

## Versioning

Semantic Versioning. Current target: **v0.1.0** after Phase 1.
