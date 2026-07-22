# Plugin Architecture

> Complete plugin system: discovery, loading, versioning, isolation, dependencies, lifecycle, failure handling, upgrade, compatibility.

---

## Document Status

| Status  | Author                     | Date       |
|---------|----------------------------|------------|
| Revised | Zelos Architecture Team  | 2026-07-19 |

---

## 1. Overview

Everything above the Kernel is a Plugin. The Plugin system is the extensibility mechanism of Zelos. [Invariant 10](../architecture/invariants.md#invariant-10-kernel-is-plugin-oriented).

### 1.1 Plugin Types

| Plugin Type | Kernel Interface | Role |
|-------------|-----------------|------|
| **Planner** | `plan(goal) → ExecutionPlan` | Goal → Task decomposition |
| **Verifier** | `verify(artifact, criteria) → Verdict` | Artifact quality gate |
| **Policy** | `evaluate(event, context) → Decision` | Allow / Reject / Delay / Retry |
| **Scoring Strategy** | `score(task, candidates) → [ScoredCandidate]` | Custom Agent ranking for scheduling |
| **Memory Provider** | `store() / retrieve() / search() / update()` | Context storage at all layers |
| **Storage Backend** | `append() / read() / snapshot()` | Event and state persistence |
| **Protocol Adapter** | `translate(external) → Runtime API` | External protocol translation |

Agents are also plugins, but they connect asynchronously rather than being loaded at startup.

---

## 2. Plugin Lifecycle

### 2.1 State Machine

```
                  ┌──────────┐
                  │ UNLOADED │
                  └────┬─────┘
                       │ load()
                  ┌────▼─────┐
                  │  LOADED  │
                  └────┬─────┘
                       │ configure()
                  ┌────▼─────┐
                  │CONFIGURED│
                  └────┬─────┘
                       │ initialize()
                  ┌────▼─────┐
             ┌────┤INITIALIZED├────┐
             │    └──────────┘    │
             │ start()       failure
             │                    │
        ┌────▼─────┐        ┌────▼─────┐
        │ STARTING │        │  ERROR   │
        └────┬─────┘        └────┬─────┘
             │              restart()
        ┌────▼─────┐             │
        │ RUNNING  │←────────────┘
        └────┬─────┘
             │
        ┌────┼────────┐
        │    │        │
    error  pause()  stop()
        │    │        │
   ┌────▼──┐ ┌──▼───┐ ┌──▼──────┐
   │ ERROR │ │PAUSED│ │STOPPING │
   └───┬───┘ └──┬───┘ └──┬──────┘
       │        │        │
  restart   resume()     │
       │    │            │
       └────┼────────────┘
            │
       ┌────▼─────┐
       │ STOPPED  │
       └────┬─────┘
            │ unload()
       ┌────▼─────┐
       │ UNLOADED │
       └──────────┘
```

### 2.2 Lifecycle Hooks

| Phase | Hook | Description |
|-------|------|-------------|
| Load | `load()` | Load plugin code/process into memory |
| Configure | `configure(config)` | Apply validated configuration |
| Initialize | `initialize()` | Allocate resources, open connections |
| Start | `start()` | Begin accepting work |
| Health Check | `health()` | Return health status |
| Pause | `pause()` | Temporarily suspend work |
| Resume | `resume()` | Resume after pause |
| Stop | `stop()` | Graceful shutdown |
| Unload | `unload()` | Release resources, remove from memory |

---

## 3. Plugin Discovery

### 3.1 Discovery Sources

| Source | Description | Phase |
|--------|-------------|-------|
| **Configuration file** | `zelos.yaml` lists plugins with entrypoints | Phase 1 |
| **Filesystem scan** | Scan `plugins/` directory for plugin manifests | Phase 2 |
| **Container registry** | Pull plugin containers from registry | Phase 3 |
| **Marketplace** | Discover and install from Zelos marketplace | Ecosystem |

### 3.2 Configuration File Format (zelos.yaml)

The `zelos.yaml` file is the single source of configuration for the Zelos Runtime in Phase 1. It defines runtime settings, plugin declarations, and per-plugin configuration.

#### 3.2.1 File Location

Zelos searches for `zelos.yaml` in this order (first found wins):
1. `./zelos.yaml` (current working directory)
2. `$ZELOS_HOME/zelos.yaml` (environment variable)
3. `~/.zelos/zelos.yaml` (user config directory)

#### 3.2.2 Complete Example

```yaml
# zelos.yaml — Zelos Runtime Configuration (Phase 1)

# ============================================================
# Runtime Settings
# ============================================================
runtime:
  # Unique identifier for this Runtime instance
  instance_id: "zelos-prod-01"

  # API server binding (for HTTP adapter)
  api:
    host: "0.0.0.0"
    port: 9876

  # Authentication (Phase 1: API keys)
  auth:
    method: "api_key"            # Phase 1 only
    keys:
      - key: "zk-admin-xxxx"
        role: "admin"
      - key: "zk-agent-xxxx"
        role: "agent"
      - key: "zk-client-xxxx"
        role: "client"

  # Concurrency limits
  limits:
    max_goals: 100               # Maximum concurrent Goals
    max_tasks_per_goal: 50       # Default per-Goal concurrency
    global_max_tasks: 500        # Global in-flight Task cap

  # Logging
  logging:
    level: "info"                # debug | info | warn | error
    format: "json"               # json | text

# ============================================================
# Plugin Declarations
# ============================================================
plugins:
  # --- Storage Backend (loaded first) ---
  - id: "in-memory-storage"
    type: "storage"
    version: "0.1.0"
    display_name: "In-Memory Storage Backend"
    description: "Phase 1 in-memory event store and state backend"
    entrypoint: "zelos.storage.in_memory.InMemoryStorageBackend"
    config:
      max_events: 100000         # Ring buffer capacity
      snapshot_interval: 10000   # Events between snapshots

  # --- Memory Provider ---
  - id: "in-memory-provider"
    type: "memory"
    version: "0.1.0"
    display_name: "In-Memory Memory Provider"
    description: "Phase 1 in-memory context store"
    entrypoint: "zelos.memory.in_memory.InMemoryProvider"
    config:
      max_entries_per_layer: 5000
      ttl_seconds: 3600

  # --- Policy Engine ---
  - id: "default-policy"
    type: "policy"
    version: "0.1.0"
    display_name: "Default Policy Engine"
    description: "Basic cost and rate limiting policies"
    entrypoint: "zelos.policy.default.DefaultPolicy"
    config:
      max_cost_per_goal: 100.0
      max_tasks_per_minute: 60
      allowlist_agents: []       # Empty = all agents allowed

  # --- Scoring Strategy ---
  - id: "default-scoring"
    type: "scoring_strategy"
    version: "0.1.0"
    display_name: "Default Scoring Strategy"
    description: "Weighted multi-factor agent ranking"
    entrypoint: "zelos.scoring.default.DefaultScoringStrategy"
    config:
      weights:                   # Customize the built-in formula
        success_rate: 0.30
        cost_efficiency: 0.20
        load_distribution: 0.15
        latency: 0.15
        availability: 0.10
        affinity: 0.05
        recency: 0.05

  # --- Verifier ---
  - id: "schema-verifier"
    type: "verifier"
    version: "0.1.0"
    display_name: "Schema Verifier"
    description: "Validates Artifact content against expected output schema"
    entrypoint: "zelos.verifier.schema.SchemaVerifier"
    config:
      strict_mode: true
      max_artifact_size_bytes: 10485760  # 10 MB

  # --- Planner ---
  - id: "llm-planner"
    type: "planner"
    version: "0.1.0"
    display_name: "LLM-Based Planner"
    description: "Decomposes Goals into Task DAGs using an LLM"
    entrypoint: "zelos.planner.llm.LLMPlanner"
    config:
      model_endpoint: "https://api.anthropic.com/v1/messages"
      model: "claude-opus-4-8"
      max_tokens_per_plan: 16000
      # The Planner itself may be an Agent using a model —
      # this is Planner-internal config, invisible to the Runtime.

  # --- Protocol Adapter ---
  - id: "http-adapter"
    type: "adapter"
    version: "0.1.0"
    display_name: "HTTP Protocol Adapter"
    description: "REST/JSON adapter for the Runtime API"
    entrypoint: "zelos.adapter.http.HTTPAdapter"
    # The HTTP adapter reads host/port/auth from runtime.api config above.
    config: {}
```

#### 3.2.3 Field Reference

**Runtime Settings (`runtime`):**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `instance_id` | String | Yes | — | Unique Runtime instance identifier |
| `api.host` | String | Yes | `"0.0.0.0"` | API bind address |
| `api.port` | Int | Yes | `9876` | API bind port |
| `auth.method` | String | No | `"api_key"` | Authentication method (Phase 1: `api_key` only) |
| `auth.keys` | Array | No | `[]` | API keys with roles (`admin`, `agent`, `client`) |
| `limits.max_goals` | Int | Yes | `100` | Max concurrent Goals |
| `limits.max_tasks_per_goal` | Int | No | `50` | Default Task concurrency per Goal |
| `limits.global_max_tasks` | Int | Yes | `500` | Global in-flight Task cap |
| `logging.level` | String | No | `"info"` | Log level |
| `logging.format` | String | No | `"json"` | Log format (`json` or `text`) |

**Plugin Declaration (`plugins[]`):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | String | Yes | Unique plugin identifier |
| `type` | String | Yes | `storage` / `memory` / `policy` / `scoring_strategy` / `verifier` / `planner` / `adapter` |
| `version` | String | Yes | Semantic version of the plugin |
| `display_name` | String | No | Human-readable name |
| `description` | String | No | Short description of the plugin |
| `entrypoint` | String | Yes | Python import path (Phase 1: in-process loading). Must be importable via standard Python import. |
| `config` | Object | No | Plugin-specific configuration, validated against the plugin's `config_schema` at load time |
| `restart_policy` | String | No | `"always"` / `"never"` / `"on_crash"`. Default: `"always"` |
| `max_restarts` | Int | No | Max restart attempts before plugin stays in ERROR. Default: `5` |

#### 3.2.4 Load Order Enforcement

The Plugin Lifecycle Manager enforces the load order from Section 4.1 regardless of declaration order in `zelos.yaml`. Plugins are topologically sorted by type:
```
storage → memory → policy → scoring_strategy → verifier → planner → adapter
```
Within the same type, order in `zelos.yaml` is preserved.

Plugins of the same type may declare `dependencies` on each other (by `id`), which adds topological constraints within the type group.

#### 3.2.5 Plugin Discovery Flow

```
1. Read zelos.yaml
2. Parse into RuntimeConfig + [PluginDeclaration]
3. Build dependency graph
4. Topological sort (circular deps → reject at startup)
5. For each plugin in load order:
   a. load(manifest)
   b. configure(plugin, config)
   c. initialize(plugin)
   d. start(plugin)
   e. If any step fails → follow restart_policy
6. All plugins RUNNING → Runtime enters RUNNING
```


### 3.2 Plugin Manifest

```
PluginManifest {
    plugin_id: String            // Unique identifier
    plugin_type: PluginType      // planner | verifier | policy | scoring_strategy | memory | storage | adapter
    version: String              // Semantic version
    display_name: String         // Human-readable
    description: String
    entrypoint: String           // Path, URL, or container image
    dependencies: [String]       // Plugin IDs this plugin depends on
    runtime_api_version: String  // Minimum Runtime API version
    config_schema: JSON Schema   // Expected configuration schema
    capabilities: [String]       // For agents: declared capabilities
}
```

---

## 4. Plugin Loading

### 4.1 Load Order

Plugins are loaded in topological order based on declared dependencies:

```
1. Storage Backends       (must exist before state)
2. Memory Providers       (must exist before context)
3. Policies               (must exist before scheduling)
4. Scoring Strategies     (must exist before scheduling)
5. Verifiers              (may be needed before task completion)
6. Planner                (needed for Goal processing)
7. Protocol Adapters      (needed for external access)
```

### 4.2 Dependency Resolution

```
plugin A depends on [B, C]
plugin B depends on [D]
plugin C depends on []
plugin D depends on []

Load order: D → B → C → A
```

Circular dependencies are rejected at load time.

---

## 5. Plugin Versioning and Compatibility

### 5.1 Version Compatibility

| Field | Rule |
|-------|------|
| `runtime_api_version` | Plugin declares minimum Runtime API version. Runtime rejects if too old. |
| `plugin.version` | Plugin's own version. Used for upgrade decisions. |

### 5.2 Compatibility Matrix

| Runtime API Version | Plugin Built For | Compatible? |
|--------------------|------------------|-------------|
| 1.0.0 | 1.0.0 | Yes |
| 1.1.0 | 1.0.0 | Yes (backward compatible) |
| 1.0.0 | 1.1.0 | No (plugin requires newer API) |
| 2.0.0 | 1.x.x | No (major version break) |

---

## 6. Plugin Isolation

### 6.1 Isolation Levels

| Level | Description | Failure Blast Radius | Phase |
|-------|-------------|---------------------|-------|
| **In-Process** | Plugin runs in same process | Plugin panic may crash Runtime | Phase 1 |
| **Sub-Process** | Plugin runs as child process | Process crash isolated | Phase 2 |
| **Container** | Plugin in separate container | Fully isolated | Phase 3 |
| **Remote** | Plugin on separate host | Network-isolated | Phase 3 |

### 6.2 Isolation Trade-offs

| Level | Latency | Complexity | Safety |
|-------|---------|-----------|--------|
| In-Process | Lowest | Lowest | Lowest |
| Sub-Process | Low | Medium | Medium |
| Container | Medium | High | High |
| Remote | Highest | Highest | Highest |

---

## 7. Plugin Failure Handling

### 7.1 Failure Detection

| Method | Description |
|--------|-------------|
| Health check | Periodic `health()` call, configurable interval |
| Error response | Plugin returns error from API call |
| Crash | Process exit (sub-process/container modes) |

### 7.2 Restart Policy

```
restart_policy:
  never:      Plugin stays in ERROR, operator intervenes
  always:     Plugin restarted immediately
  on_crash:   Plugin restarted only if crashed (not if health check fails)
```

### 7.3 Backoff on Restart

```
restart 1: immediate
restart 2: 1s delay
restart 3: 2s delay
restart 4: 4s delay
...
restart N: min(2^(N-2) * 1000ms, max_backoff_ms)
```

Max restarts configurable. After max: Plugin stays in ERROR.

---

## 8. Plugin Upgrade

### 8.1 Hot Reload (Future — Phase 3)

```
1. New plugin version deployed
2. PLM starts new instance alongside old
3. New instance reaches RUNNING
4. Traffic gradually shifts (canary): 10% → 50% → 100%
5. Old instance drains in-flight work
6. Old instance stops and unloads
```

### 8.2 Rolling Upgrade (for Agents)

Agents are upgraded independently:
1. New Agent version registers with same capabilities
2. Old Agent announces deprecation
3. Scheduler gradually shifts traffic to new Agent
4. Old Agent shuts down when all in-flight tasks complete

---

## 9. Plugin API (Internal)

```
PluginLifecycleManager {
    // Discovery
    discover_from_config(config: Config) → [PluginManifest]
    
    // Lifecycle
    load(manifest: PluginManifest) → Plugin
    configure(plugin: Plugin, config: Config) → void
    initialize(plugin: Plugin) → void
    start(plugin: Plugin) → void
    
    // Monitoring
    health_check(plugin: Plugin) → HealthStatus
    restart(plugin: Plugin) → void
    
    // Shutdown
    stop(plugin: Plugin) → void
    unload(plugin: Plugin) → void
    
    // Query
    get_plugin(plugin_id: String) → Plugin?
    list_plugins(filter?: Filter) → [Plugin]
    get_status(plugin_id: String) → PluginStatus
}
```

---

## 10. Observability

| Metric | Description |
|--------|-------------|
| `plugin.state` | Current state (gauge) |
| `plugin.uptime_seconds` | Time in RUNNING |
| `plugin.health_checks_total` | Health checks performed |
| `plugin.health_failures_total` | Failed health checks |
| `plugin.restarts_total` | Restart count |
| `plugin.errors_total` | Errors during operation |

---

## 11. References

- [Architecture Invariants](../architecture/invariants.md) — Invariants 10, 12
- [Kernel Boundary](./kernel-boundary.md) — Plugin vs Kernel boundary
- [Runtime Lifecycle](./runtime-lifecycle.md) — Plugin loading during startup
- [Protocol Layer](./protocol-layer.md) — Protocol adapters are plugins
- [Memory Architecture](./memory-architecture.md) — Memory providers are plugins
