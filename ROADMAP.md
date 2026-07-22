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

**Status:** Complete
**Timeline:** July 2026

### Goal

Implement the minimal viable Runtime Kernel — single-node, in-process.

### Scope

- [x] Event Bus (in-process, pub/sub, event persistence)
- [x] Capability Registry (registration, indexing, query)
- [x] Task Graph Engine (state machine, dependency resolution)
- [x] Scheduler (capability matching, basic scoring, FIFO dispatch)
- [x] Execution Engine (dispatch, heartbeat, timeout, retry)
- [x] Plugin Lifecycle Manager (load, configure, start, health check)
- [x] Runtime API (Goal API, Agent API, Admin API)
- [x] HTTP Protocol Adapter
- [x] Python SDK (Agent base class, Goal submission)
- [x] Config Loader (zelos.yaml support)
- [x] LLM Planner (OpenAI / Anthropic / Google / Mock providers)
- [x] Memory Architecture (6-layer, in-memory provider)
- [x] Policy Engine (cost limits, rate limits, allowlists)

---

## Phase 2: Developer Platform

**Status:** Complete
**Timeline:** July 2026

### Goal

Complete development platform. Enable production use cases.

### Scope

- [x] Pluggable Planner (LLM-based default, custom planner support)
- [x] Verifier framework (schema, code review, security verifiers)
- [x] Policy engine (cost limits, rate limits, allowlists)
- [x] Memory architecture (all 6 layers, pluggable backends)
- [x] Advanced Scheduler (ScoringStrategy plugin, tiered escalation)
- [x] Protocol Adapters (gRPC, WebSocket, MCP, A2A)
- [x] Observability (structured logging, Prometheus metrics, tracing)
- [x] SDK expansion (schema module, BaseAgent, ZelosClient)
- [x] Plugin isolation (sub-process mode)
- [x] Pluggable Storage (InMemory, Redis, PostgreSQL, MySQL backends)

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

Semantic Versioning. Current version: **v0.3.0** (Phase 3 Complete).
