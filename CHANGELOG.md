# Changelog

All notable changes to Zelos will be documented in this file.

---

## [0.6.0] — 2026-07-22

### Added — Demo Enrichment, OTel, TS SDK Verification
- HITL approval workflow demo (6 scenarios: single/multi approver, reject, changes, timeout, audit)
- Multi-tenant isolation demo (5 scenarios: registration, quotas, isolation, lifecycle, usage report)
- OpenTelemetry → Jaeger integration (OTLP export, span verification, Jaeger UI query)
- TypeScript SDK: `tsc` compilation verified, `.d.ts` + `.js` output generated
- GitHub Pages docs deployment workflow (`.github/workflows/docs.yml`)
- Demo README updated with Phase 5/6 demos + supplementary notes

### Changed
- Version bumped: 0.5.0 → 0.6.0
- Test count: 66 → 68 (63 passed, 5 skipped)
- ROADMAP: Phase 6 Complete, OTel moved from Phase 7 to done

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
