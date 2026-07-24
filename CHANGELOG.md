# Changelog

All notable changes to Zelos will be documented in this file.

---

## [0.8.0] — 2026-07-24

### Added — Event Sourcing + Reliability
- **Event Sourcing Engine** (`zelos/event_sourcing.py`) — pure-function state reducer, full replay, snapshot + incremental recovery
- **Goal State persistence** (`zelos/goal_state.py`) — `GoalState` dataclass with `to_dict()`/`from_dict()`, auto-persisted on state change
- **Goal Recovery on startup** — Runtime automatically restores all incomplete goals from `StorageBackend`
- **Monotonic event `sequence_id`** — auto-assigned in `InMemoryEventStore`, `replay_from(seq_id)` API
- **Heartbeat Timeout detection** — `InFlightTask.heartbeat_at` + `heartbeat_timeout_ms`, monitor auto-detects missed heartbeats
- **`submit_heartbeat(task_id)` API** — Agent heartbeat to prevent task timeout
- **NonRetryableError support** — `Task.non_retryable_errors` field + `TaskStatus.FATAL_FAILED` terminal state
- **Retry history tracking** — `task.retry_scheduled` event with `task_id`/`attempt`/`backoff_ms`/`previous_error` payload
- **Retry history in `get_goal_status()`** — exposes per-task retry timeline
- Task serialization: `Task.to_dict()` / `Task.from_dict()` round-trip

### Changed
- Version bumped: 0.7.0 → 0.8.0
- `TaskStatus` enum: added `FATAL_FAILED` (terminal, no retry)
- `Event` dataclass: added `sequence_id: int = -1`
- `InFlightTask` dataclass: added `heartbeat_at` + `heartbeat_timeout_ms`
- `Scheduler`: publishes `task.retry_scheduled` events, skips `FATAL_FAILED` tasks
- `ExecutionEngine`: heartbeat timeout detection in monitor loop, `submit_heartbeat()` method
- `ZelosRuntime`: storage backend integration, goal recovery on startup, `submit_heartbeat()` API
- Test count: 28 new v0.8.0 tests (REQ-01 through REQ-07)

### Reference
- Requirements: `docs/v0.8.0-requirements.md`
- Analysis: `docs/temporal-reliability-analysis.md`

---

## [0.7.0] — 2026-07-23

### Added — Advanced Production
- etcd coordination backend (`zelos/coordination.py`) — pluggable InMemory + etcd, leader election, watch, heartbeat
- NATS messaging integration (`zelos/messaging_nats.py`) — pluggable InMemory + NATS, pub/sub, pattern match, request-reply
- Go SDK (`zelos-go/`) — schema types, Agent interface, ZelosClient, DemoAgent
- TaskGraph O(1) evaluate_all via `_created_task_ids` set optimization
- **Published to PyPI**: `pip install zelos-runtime` — zero external deps

### Changed
- Version bumped: 0.6.0 → 0.7.0
- Test count: 68 → 78 (71 passed, 7 skipped)
- ROADMAP: Phase 7 marked Complete

---

## [0.6.0] — 2026-07-22

### Added — Demo Enrichment, OTel, TS SDK Verification
- HITL approval workflow demo (6 scenarios)
- Multi-tenant isolation demo (5 scenarios)
- OpenTelemetry → Jaeger integration (OTLP export, Jaeger API verification)
- TypeScript SDK: `tsc` compilation verified
- GitHub Pages docs deployment workflow

### Changed
- Version bumped: 0.5.0 → 0.6.0
- Test count: 66 → 68

---

## [0.5.0] — 2026-07-22

### Added — Production Hardening
- API Key anomaly detection: brute-force tracking, sliding window, auto-revoke
- K8s readiness/liveness probes: `/live`, `/ready` HTTP endpoints
- Audit log file export: `export_json_file()` method
- Grafana dashboard JSON template (`deploy/grafana/zelos-dashboard.json`)
- Operations manual (`docs/guide/operations.md`)
- Phase 5 acceptance tests (7 tests)

### Changed
- Version bumped: 0.4.0 → 0.5.0
- Test count: 62 → 66

---

## [0.4.0] — 2026-07-22

### Added — Engineering Completeness
- CI/CD: GitHub Actions (Python matrix + lint), Docker, Docker Compose, Makefile, Pre-commit
- Storage verification: Redis/PostgreSQL integration tests (30 cases)
- Event persistence: PersistentEventStore, state persistence, crash recovery
- Distributed cluster tests: leader election, work stealing, node registry
- TypeScript SDK: `zelos-ts/` (schema, BaseAgent, ZelosClient, DemoAgent)
- mTLS verification tests
- Prometheus `/metrics` HTTP endpoint
- Benchmark suite (EventBus 1.4M/s, TaskGraph 2.5M/s)
- API docs (pdoc), CHANGELOG.md

### Changed
- Version bumped: 0.3.0 → 0.4.0
- Test count: 47 → 62

---

## [0.3.0] — 2026-07-21

### Added — Runtime Ecosystem
- Security module: RBAC + AuditLogger + APIKeyManager + TLSConfig
- Multi-tenancy: Namespace + ResourceQuota + TenantManager
- Advanced Execution: DynamicPlanModifier + SubGoalManager + HumanInTheLoop
- Container Isolation: Docker/Podman + Remote + Factory (5 modes)
- Hot Reload: FileWatcher + 4 upgrade strategies (rolling/blue-green/canary/instant)
- Distributed Runtime: LeaderElection (Bully) + WorkStealing + NodeRegistry
- CLI Tool: ZelosCLI with 11 subcommands
- 110 acceptance tests, 7 new demos

---

## [0.2.0] — 2026-07-21

### Added — Developer Platform
- Verifier v2: CodeReviewer + SecurityScanner + FactChecker
- Observability: StructuredLogger + MetricsCollector + Tracer + Prometheus export
- Protocol Adapters: gRPC + WebSocket + MCP + A2A
- Plugin Isolation: SubProcessPlugin (JSON-line stdin/stdout protocol)
- Pluggable Storage: InMemory / Redis / PostgreSQL / MySQL backends
- Messaging infrastructure
- 223 total tests

---

## [0.1.0] — 2026-07-20

### Added — Runtime Kernel
- Event Bus: pub/sub, pattern matching, correlation, replay, ring buffer
- Capability Registry: registration, versioning, tag query, prefix matching
- Task Graph: DAG state machine, cycle detection, dynamic modification
- Scheduler: 5-phase pipeline (sort → filter → score → policy → select)
- Execution Engine: dispatch, heartbeat, timeout, retry, cancel
- Plugin Lifecycle Manager: load order, dependency resolution, health check
- Runtime API: Goal/Agent/Admin APIs
- HTTP Protocol Adapter: 15 REST endpoints
- LLM Planner: OpenAI / Anthropic / Google / Mock providers
- Memory Architecture: 6-layer with TTL, LRU, Context Assembly
- Policy Engine: CostLimit / RateLimit / Allowlist / Composite
- 105 acceptance tests
