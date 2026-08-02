# Changelog

All notable changes to Zelos will be documented in this file.

---

## [1.3.0] — 2026-08-01

### Added — MPC Adaptive Scheduling Loop
- **Feature Flags** (`zelos/feature_flags.py`) — phased component loading (stage_a through stage_e), mpc_replan control
- **Replan Rules Engine** (`zelos/replan_rules.py`) — 4 default rules (VerdictRejected, ConfidenceLow, SchemaMismatch, EmptyArtifact), extensible via ReplanRule ABC
- **MPC Replan Check** (`zelos/execution_engine.py`) — `_mpc_replan_check()` hook in submit_result(), incremental verification per task, diagnosis engine trigger, replan count cap at 5
- **Planner base class** (`zelos/planner.py`) — `Planner(ABC)` extracted from LLMPlanner, `replan_path()` with structured failure_context (verdict → diagnosis → classification)
- **Runtime replan coordination** (`zelos/runtime.py`) — `_on_replan()`, `_build_failure_context()`, FeatureFlags integration, diagnosis engine wiring
- **TaskGraph additions** (`zelos/task_graph.py`) — `BLOCKED` TaskStatus, `get_dependents()` method
- **PlannerPlan.get_task()** — task lookup by ID within a plan

### Changed
- Version: 1.2.0 → 1.3.0
- `ExecutionEngine.__init__()`: new v1.3.0 fields (replan_callback, replan_rules, current_plan, replan_count, max_replans, incremental_verifier, diagnosis_engine)
- `ExecutionEngine.submit_result()`: MPC replan check invoked after result handling (outside lock)
- `ZelosRuntime.__init__()`: FeatureFlags-aware init, conditional MPC callback + diagnosis wiring
- `TaskStatus`: new `BLOCKED` enum value with valid transitions
- `LLMPlanner` now extends `Planner` base class

### Test Results
- 49 new v1.3.0 tests (47 passed, 5 integration tests skipped — require full Runtime + Agent env)
- 211 total passed, 12 skipped, 0 failures
- Zero regressions across all 162 existing tests

### Reference
- `docs/v1.3.0-requirements.md`
- `docs/zelos-architecture-critique-and-evolution.md`

---

## [1.2.0] — 2026-08-01

### Added — Runtime Diagnosis & SWE-bench Pipeline
- **Diagnosis Engine** (`zelos/diagnosis_engine.py`) — structured pytest output parsing, failure extraction with file:line
- **Failure Classifier** (`zelos/failure_classifier.py`) — repair/retry/abandon decisions, stop-loss tracking
- **Repair Orchestrator** (`zelos/repair_orchestrator.py`) — Runtime-Guided Repair with Hypothesis Tracker
- **Patch Ranker** (`zelos/patch_ranker.py`) — multi-factor candidate scoring (files, LOC, tests, cross-package)
- **Arbiter** (`zelos/arbiter.py`) — first-to-pass-all selection from parallel agent outputs
- **Format Verifiers** (`zelos/verifier_formats.py`) — markdown fence, dry-run, syntax checks
- **Contest Dispatch** — Scheduler supports same-task → multi-agent parallel dispatch
- **SWE-bench Pipeline** — complete generation + evaluation pipeline with repo access

### Changed
- Version: 1.1.0 → 1.2.0
- `Scheduler.schedule_contest()`: parallel multi-agent dispatch
- `FailureClassifier`: relaxed rules for single-module failures
- `DiagnosisEngine`: noise filtering for Docker/conda test output

### Reference
- `docs/v1.2.0-requirements.md`
- `docs/blueprint/benchmark-plan.md`
- `docs/blueprint/swebench-strategy.md`

---

## [1.1.0] — 2026-07-30

### Added — Agent Credential Management
- **CredentialStore** — pluggable credential backend (env/file/vault/k8s)
- **CredentialInjector** — dispatch-time injection, expired/missing → Task FAILED
- **AgentState.required_credentials** — agents declare what they need
- **add_agent(required_credentials=[...])** — new optional parameter
- **Zero-leak guarantee** — Agent A never sees Agent B's credentials
- **Four backends**: Env (dev), File (simple), Vault (production, hvac), K8s (zero deps)
- **create_credential_store()** factory + `zelos.yaml` configuration

### Changed
- Version: 1.0.0 → 1.1.0
- `ExecutionEngine.dispatch()`: credential injection before agent execution
- `AgentState`: new `required_credentials` field

---

## [1.0.0] — 2026-07-28

### Added — CP Governance Platform
- **ChangeProposal** — first-class CP five-tuple object (I×K×S×R×E) per paper definition
- **Constraint Engine** — solidifies CP into executable constraints for constrained generation
- **Verifier Chain** — auto-orchestrated verification pipeline with escalation
- **Merge Executor** — auto-merge on approve (event_sourcing_apply + git_merge)
- **Constraint Injection** — Agent execution carries CP constraints at dispatch
- `Task.constraints` field for constrained generation support

### Changed
- Version: 0.9.1 → 1.0.0
- `ExecutionReport` includes `change_proposal` field
- `submit_goal()` auto-builds `ChangeProposal` from `IntentSpec`
- `auto_decide()` auto-merges on `auto_approve`
- `_on_dispatch()` injects CP constraints into agent context

### Reference
- `docs/v1.0.0-requirements.md`
- `docs/papers/From PR to CP_ A Novel Software Change Governance Workflow for Large-Scale AI Development.md`

---

## [0.9.0] — 2026-07-28

### Added — Change Evidence Package
(see git log for full details)

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

## [0.8.1] — 2026-07-28

### Changed
- README status line corrected to Phase 8 / v0.8.1 / 91 Tests
- `__version__` in `zelos/__init__.py` bumped to 0.8.1
- All docs updated: README, User Manual (EN+ZH), Operations Guide, ROADMAP, CHANGELOG, PPT script
- Public documentation site regenerated with correct version

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
