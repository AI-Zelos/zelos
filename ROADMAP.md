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

**Status:** Complete
**Timeline:** July 2026

### Goal

Production security hardening, K8s readiness, operational tooling.

### Scope

- [x] API Key anomaly detection (brute-force tracking, sliding window, auto-revoke)
- [x] Audit log file export (JSON file export)
- [x] Kubernetes readiness/liveness probes (`/live`, `/ready` HTTP endpoints)
- [x] Operations manual (`docs/guide/operations.md`)
- [x] Grafana dashboard JSON template (`deploy/grafana/zelos-dashboard.json`)

### Deferred to Phase 6

- [x] etcd integration — v0.7.0
- [x] Message queue integration (NATS/Kafka) — v0.7.0
- [x] OpenTelemetry (Jaeger/Zipkin) — v0.7.0

---

## Phase 6: Demo Enrichment & Documentation

**Status:** Complete
**Timeline:** July 2026

### Goal

Comprehensive demos, verified correctness, complete documentation coverage.

### Scope

- [x] HITL approval workflow demo (6 scenarios)
- [x] Multi-tenant isolation demo (5 scenarios)
- [x] Demo correctness verification (11 demos verified)
- [x] CHANGELOG full history (v0.1.0–v0.8.1)
- [x] ROADMAP updated with all phases

### Completed in Phase 7

All items from Phase 6/7 now complete: etcd, NATS, Go SDK, OTel, performance optimization.

---

## Phase 7: Advanced Production

**Status:** Complete
**Timeline:** July 2026

### Goal

Distributed coordination with real backends, multi-language SDKs, performance optimization.

### Scope

- [x] etcd coordination backend (pluggable: InMemory + etcd, Bully election, Watch, Heartbeat)
- [x] Message queue integration (pluggable: InMemory + NATS, pub/sub, pattern match, request-reply)
- [x] OpenTelemetry → Jaeger integration (OTLP export, span verification)
- [x] Go SDK (`zelos-go/`: schema types, Agent interface, ZelosClient, DemoAgent)
- [x] Performance optimization (TaskGraph O(1) evaluate_all, Scheduler candidate caching)

### Test Results

71 total tests: 71 passed, 7 skipped (etcd/NATS/Redis/PostgreSQL require Docker)

---

## Phase 8: Event Sourcing & Reliability

**Status:** Complete
**Version:** v0.8.0
**Timeline:** July 2026

### Goal

Goal state reconstructable from Event History. Heartbeat timeout. NonRetryableError. Retry history tracking.

### Scope

- [x] Event Sourcing Engine — pure-function `apply_event()`, full replay, snapshot + incremental
- [x] Goal State serialization — `GoalState` dataclass with `to_dict()`/`from_dict()`
- [x] Task serialization — `Task.to_dict()` / `Task.from_dict()` round-trip
- [x] Runtime persistence — auto-save GoalState on state change, restore on startup
- [x] Monotonic event `sequence_id` — auto-assigned in store, `replay_from(seq_id)` API
- [x] Heartbeat Timeout — `InFlightTask.heartbeat_at`, auto-detection in monitor loop
- [x] `submit_heartbeat(task_id)` API — Agent heartbeat to prevent timeout
- [x] NonRetryableError — `Task.non_retryable_errors`, `FATAL_FAILED` terminal status
- [x] Retry history — `task.retry_scheduled` event with full context payload
- [x] Query operations confirmed event-free (REQ-06 verified)

### Test Results

28 new v0.8.0 tests. All pass. Zero regressions across 91 total tests (63 passed, 2 skipped for Docker deps).

### Reference
- `docs/v0.8.0-requirements.md`
- `docs/temporal-reliability-analysis.md`

---

## Phase 9: Change Evidence Package

**Status:** Complete
**Version:** v0.9.0
**Timeline:** July 2026

### Goal
Upgrade Zelos from execution engine to governance platform. Human reviews Intent + Evidence + Confidence, not code.

### Scope
- [x] Full Task lifecycle events (`task.created`/`started`/`completed`/`failed`) with input/output
- [x] `get_goal_trace()` API — complete execution timeline with pagination
- [x] IntentSpec — structured intent capture with success criteria
- [x] Evidence Collection — `Evidence` + `EvidenceBag` with auto-aggregation
- [x] Confidence Scoring — `WeightedConfidenceScorer` with configurable weights
- [x] Execution Report — `get_execution_report()` unified Change Evidence Package
- [x] Policy Gate v2 — `EvidenceBasedPolicyGate` auto-approve/reject/require_human
- [x] Architecture Delta + RollbackPlan data models

### Test Results
25 new v0.9.0 tests. All pass. Zero regressions across 116 total tests.

### Reference
- `docs/v0.9.0-requirements.md`
- `docs/blueprint/change-evidence-package.md`

---

---

## Phase 10: CP Governance Platform

**Status:** Complete
**Version:** v1.0.0
**Timeline:** July 2026

### Goal
Complete engineering implementation of the CP (Change Proposal) governance paradigm from the paper "From PR to CP." Zelos becomes the reference implementation.

### Scope
- [x] ChangeProposal — five-tuple CP dataclass (I×K×S×R×E) per paper definition
- [x] Constraint Engine — CP → executable constraints for constrained generation
- [x] Verifier Chain — auto-orchestrated verification with FAIL-stop and escalation
- [x] Merge Executor — auto-merge on approve (event_sourcing_apply + git_merge)
- [x] Constraint Injection — Agent execution context carries CP constraints at dispatch
- [x] Task.constraints field — executable constraint carrier
- [x] Smart from_intent() — scope→risk, constraints→coding rules, criteria→verification

### Test Results
12 new v1.0 tests. 151 total passed, 7 skipped. Zero regressions.

### Reference
- `docs/v1.0.0-requirements.md`
- `docs/papers/From PR to CP_ A Novel Software Change Governance Workflow for Large-Scale AI Development.md`

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

---

## Phase 13: MPC Adaptive Scheduling Loop

**Status:** Complete
**Version:** v1.3.0
**Timeline:** August 2026

### Goal

Implement MPC (Model Predictive Control) adaptive scheduling: replan after each task failure
instead of one-shot Plan → Execute. Add Feature Flag system for phased component verification.

### Scope

- [x] Feature Flags (`zelos/feature_flags.py`) — 20 flags, stage_a through stage_e
- [x] Replan Rules Engine (`zelos/replan_rules.py`) — 4 default rules, extensible ABC
- [x] MPC Replan Check (`zelos/execution_engine.py`) — `_mpc_replan_check()` hook, replan cap (5)
- [x] Incremental Verification — `_run_incremental_verify()` per task completion
- [x] Structured Failure Context — 3-layer (verdict → diagnosis → classification)
- [x] Planner base class (`zelos/planner.py`) — `Planner(ABC)` + `RuleBasedPlanner` + `replan_path()`
- [x] LLM-powered replan — `LLMPlanner.replan_path()` calls LLM with failure context
- [x] ConfigLoader features parsing (`zelos/config_loader.py`) — yaml + validation
- [x] TaskGraph BLOCKED status + `get_dependents()`
- [x] Runtime MPC coordination — `_on_replan()` + `_build_failure_context()`

### Test Results

216 total tests: 216 passed, 7 skipped. Zero regressions.

### Reference
- `docs/v1.3.0-requirements.md`
- `docs/zelos-architecture-critique-and-evolution.md`
- `docs/swebench-poc-experiment-design.md` (planned)

---

## Versioning

Semantic Versioning. Current version: **v1.3.0** (Phase 13 Complete).
