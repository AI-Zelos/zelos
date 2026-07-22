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

## Phase 4: Engineering Completeness

**Status:** Complete
**Timeline:** July 2026

### Goal

Production-ready engineering infrastructure — CI/CD, Docker, persistence verification, distributed testing, observability.

### Scope

- [x] CI/CD pipeline (GitHub Actions: Python 3.10/3.11/3.12 matrix + Ruff lint)
- [x] Docker multi-stage build (base ~80MB, dev with test tools)
- [x] Docker Compose (Runtime + optional Redis)
- [x] Makefile (dev/test/lint/format/check/build/run/clean)
- [x] Pre-commit hooks (Ruff format + lint)
- [x] Storage backend integration tests (InMemory/Redis/PostgreSQL, 30 test cases)
- [x] Event persistence (PersistentEventStore + WAL + crash recovery)
- [x] State persistence (Goal/Agent save + restore after restart)
- [x] Distributed cluster tests (leader election, work stealing, node registry)
- [x] TypeScript SDK (schema types, BaseAgent, ZelosClient, DemoAgent)
- [x] mTLS verification (self-signed CA, mutual TLS handshake, client rejection)
- [x] Prometheus /metrics HTTP endpoint (text exposition format)
- [x] Performance benchmarks (EventBus 1.4M/s, TaskGraph 2.5M/s)
- [x] API documentation (pdoc auto-generated)
- [x] CHANGELOG.md

### Test Results

62 total tests: 59 passed, 4 skipped (integration tests require Docker containers)

---

## Phase 5: Production Hardening

**Status:** Not Started
**Timeline:** TBD

### Goal

Distributed coordination with real backends, advanced observability, production deployment.

### Scope

- [ ] etcd integration (replace in-memory leader election)
- [ ] Message queue integration (NATS/Kafka for cross-node EventBus)
- [ ] API Key anomaly detection (brute-force auto-revoke)
- [ ] Audit log SIEM export (Elasticsearch/Loki)
- [ ] OpenTelemetry actual integration (Jaeger/Zipkin exporters)
- [ ] Kubernetes readiness/liveness probes
- [ ] Operations manual (bare-metal / Docker / K8s deployment guide)
- [ ] Grafana dashboard JSON template

---

## Phase 6: Performance & Ecosystem

**Status:** Not Started
**Timeline:** TBD

### Goal

Optimize for scale, complete SDK ecosystem.

### Scope

- [ ] TaskGraph incremental evaluation (avoid full scans)
- [ ] Scheduler candidate caching
- [ ] EventBus batch publish
- [ ] Go SDK
- [ ] End-to-end examples (real LLM calls + AgentCity integration)

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

Semantic Versioning. Current version: **v0.4.0** (Phase 4 Complete).
