# Changelog

All notable changes to Zelos will be documented in this file.

---

## [0.4.0] — 2026-07-22

### Added — Engineering Completeness

#### CI/CD & DevOps
- GitHub Actions CI: Python 3.10/3.11/3.12 matrix test + Ruff lint
- Docker multi-stage build (base ~80MB, dev with test tools)
- Docker Compose (Runtime + optional Redis)
- Makefile: dev/test/lint/format/check/build/run/clean
- Pre-commit hooks: Ruff format + lint

#### Storage & Persistence
- Storage backend integration tests (InMemory/Redis/PostgreSQL, 30 test cases)
- `PersistentEventStore` for durable event storage with crash recovery
- State persistence: Goal/Agent save + restore after restart

#### Distributed Runtime
- Multi-node cluster tests: leader election, work stealing, node registry
- Dead node detection verification

#### TypeScript SDK (`zelos-ts/`)
- Schema types: `CapabilityDeclaration`, `Task`, `Artifact`, `MemoryContext`
- `BaseAgent` abstract class with `declareCapabilities()` + `execute()`
- `ZelosClient` HTTP client for remote Runtime access
- `DemoAgent` reference implementation

#### Security
- mTLS verification tests: self-signed CA, mutual TLS handshake, client rejection

#### Observability
- Prometheus `/metrics` HTTP endpoint (text exposition format)
- Metrics: `zelos_goals_active`, `zelos_tasks_completed_total`, `zelos_agents_connected`, etc.

#### Performance
- Benchmark suite: EventBus 1.4M events/s, TaskGraph 2.5M ops/s

#### Documentation
- API docs auto-generated via pdoc (`docs/api/`)
- CHANGELOG.md (this file)
- ROADMAP updated with Phase 4/5/6

### Changed
- Version bumped: 0.3.0 → 0.4.0
- Ruff formatted all 63 source files
- Lint: zero errors across entire codebase
- Test count: 47 → 62 (59 passed, 4 integration-skipped)

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
