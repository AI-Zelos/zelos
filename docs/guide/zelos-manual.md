# Zelos User Manual v0.3.0

> **Open Multi-Agent Orchestration Runtime** — The Runtime that executes, coordinates, and governs intelligent agents.

---

## Table of Contents

| Section | Module | Description |
|---------|--------|-------------|
| [1. Quick Start](#1-quick-start) | — | 5-minute setup, first goal, Dashboard |
| [1a. Dashboard](#1a-dashboard) | — | Built-in Web UI at GET / |
| [2. Core Concepts](#2-core-concepts) | — | Architecture & design philosophy |
| [3. Runtime](#3-runtime) | `zelos.runtime` | Central entry point |
| [4. Event Bus](#4-event-bus) | `zelos.event_bus` | Pub/sub communication backbone |
| [5. Capability Registry](#5-capability-registry) | `zelos.capability_registry` | Agent capability management |
| [6. Task Graph](#6-task-graph) | `zelos.task_graph` | DAG execution engine |
| [7. Scheduler](#7-scheduler) | `zelos.scheduler` | 5-phase scheduling pipeline |
| [8. Execution Engine](#8-execution-engine) | `zelos.execution_engine` | Task dispatch & lifecycle |
| [9. Planner](#9-planner) | `zelos.planner` | LLM-based goal decomposition |
| [10. Verifier](#10-verifier) | `zelos.verifier` | Artifact validation gate |
| [11. Policy](#11-policy) | `zelos.policy` | Cost/rate/allowlist enforcement |
| [12. Memory](#12-memory) | `zelos.memory` | 6-layer context management |
| [13. Observability](#13-observability) | `zelos.observability` | Logs, metrics, tracing |
| [14. Protocol Adapters](#14-protocol-adapters) | `zelos.protocol_adapters` | gRPC, WebSocket, MCP, A2A |
| [15. Plugin Isolation](#15-plugin-isolation) | `zelos.plugin_isolation` | Sub-process plugins |
| [16. Storage](#16-storage) | `zelos.storage` | Persistent backends |
| [17. Security](#17-security) | `zelos.security` | RBAC, Audit, API Keys, mTLS |
| [18. Multi-tenancy](#18-multi-tenancy) | `zelos.multi_tenancy` | Namespace isolation & quotas |
| [19. Advanced Execution](#19-advanced-execution) | `zelos.advanced_execution` | Dynamic plans, sub-goals, HITL |
| [20. Container Isolation](#20-container-isolation) | `zelos.container_isolation` | Docker/Podman/Remote plugins |
| [21. Hot Reload](#21-hot-reload) | `zelos.hot_reload` | Zero-downtime upgrades |
| [22. Distributed Runtime](#22-distributed-runtime) | `zelos.distributed` | Leader election & work stealing |
| [23. CLI Tool](#23-cli-tool) | `zelos.cli` | Command-line interface |
| [24. Configuration](#24-configuration) | `zelos.yaml` | Full config reference |
| [25. API Reference](#25-api-reference) | — | Complete method reference |
| [26. Deployment Guide](#26-deployment-guide) | — | Production deployment |
| [27. Troubleshooting](#27-troubleshooting) | — | Common issues & solutions |

---

## 1. Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/zelos/runtime.git
cd runtime/

# No pip install needed — pure Python stdlib
# Verify:
python3 -c "from zelos.runtime import ZelosRuntime; print('OK')"
```

### Your First Goal

```python
from zelos.runtime import ZelosRuntime

# ── 1. Create Runtime ──
rt = ZelosRuntime({"plugins": []})
rt.start()

# ── 2. Register an Agent ──
rt.add_agent(
    name="CodeAgent",
    entrypoint="my_agents.coder:CodingAgent",
    capabilities=[
        {"name": "code-generation.python", "version": "1.0.0"}
    ],
)

# ── 3. Submit a Goal ──
goal = rt.submit_goal(
    description="Write a function that checks if a string is a palindrome",
    priority="high",
)
print(f"Goal: {goal['goal_id']} → {goal['status']}")

# ── 4. Wait for completion ──
result = rt.wait_for_goal(goal["goal_id"], timeout_seconds=30)
print(f"Result: {result['status']} — {result['progress']['percent_complete']:.0f}%")

# ── 5. Shutdown ──
rt.shutdown()
```

### With zelos.yaml

```yaml
# zelos.yaml
runtime:
  api:
    host: "127.0.0.1"
    port: 9876

plugins:
  - id: "llm-planner"
    type: "planner"
    entrypoint: "zelos.planner.LLMPlanner"
    config:
      provider: "openai"
      model: "gpt-4o"
      api_key: "${OPENAI_API_KEY}"
```

```python
rt = ZelosRuntime.from_yaml("zelos.yaml")
# Everything loaded from config — Planner, Verifier, Policy, Memory
rt.start()
```

---

## 1a. Dashboard

Zelos 内置一个 Web Dashboard，通过 HTTP Adapter 自动提供服务。**无需安装任何额外依赖**。

### 启动 Runtime + Dashboard

```bash
# 方式 1：一行命令启动（推荐）
python3 -c "
from zelos.runtime import ZelosRuntime
from zelos.http_adapter import HTTPAdapter

rt = ZelosRuntime({'plugins': []})
rt.start()

adapter = HTTPAdapter(rt, host='127.0.0.1', port=9876)
adapter.start()
print(f'✅ Dashboard: {adapter.url}')
# 保持运行，Ctrl+C 停止
import time
try:
    while True: time.sleep(1)
except KeyboardInterrupt:
    adapter.stop(); rt.shutdown()
"
```

```bash
# 方式 2：使用启动脚本
python3 start.py
```

### 访问 Dashboard

启动后在浏览器打开 **http://127.0.0.1:9876/**，即可看到：

- **Dashboard** — Runtime 状态、活跃 Goals、活跃 Agents、事件数、租户数
- **Goals** — 所有 Goal 的状态和进度条
- **Agents** — 所有 Agent 的连接状态
- **Audit Log** — 审计事件（时间、操作者、操作、资源、结果）
- **Tenants** — 租户列表和配额使用情况
- **Cluster** — 集群节点状态和领导者信息
- **Health & Metrics** — 原始 JSON 数据
- **API Reference** — 完整 REST API 文档

页面每 5 秒自动刷新，无需手动操作。

### REST API 端点

Dashboard 调用的所有 API 也可直接用 curl 访问：

```bash
curl http://127.0.0.1:9876/api/v1/health
curl http://127.0.0.1:9876/api/v1/metrics
curl http://127.0.0.1:9876/api/v1/goals
curl http://127.0.0.1:9876/api/v1/agents
curl http://127.0.0.1:9876/api/v1/audit
curl http://127.0.0.1:9876/api/v1/tenants
curl http://127.0.0.1:9876/api/v1/cluster
curl http://127.0.0.1:9876/api/v1/approvals/pending
```

### HTTPS / mTLS

```python
from zelos.security import TLSConfig

tls = TLSConfig(
    cert_file="/etc/zelos/certs/server.crt",
    key_file="/etc/zelos/certs/server.key",
    ca_file="/etc/zelos/certs/ca.crt",
    require_client_cert=True,
)

adapter = HTTPAdapter(rt, host='0.0.0.0', port=8443, tls_config=tls)
adapter.start()
# Dashboard: https://your-host:8443/
```

---

## 2. Core Concepts

### Architecture

```
Goal → Planner → ExecutionPlan → TaskGraph → Scheduler → ExecutionEngine → Agent
  │                                                                              │
  └────────────────────────── Event Bus (everything) ────────────────────────────┘
                                   │
                    Memory / Policy / Verifier / Observability
```

### Design Principles

| Principle | Meaning |
|-----------|---------|
| **Runtime First** | Runtime owns scheduling, memory, lifecycle. Agents are plugins. |
| **Capability First** | Dispatch by WHAT, never by WHO. `"code-generation.python"` not `"Claude"`. |
| **Execution Plan First** | Plan exists before any agent is invoked. |
| **Event Driven** | Every state change is an immutable event. No direct calls between components. |
| **Plugin Architecture** | Everything above the Kernel is replaceable. |
| **Stateless Agents** | Agents: Receive Task → Execute → Return Artifact → Exit. Nothing more. |

### Agent Lifecycle

```
Register → Connect → Heartbeat → Dispatch → Execute → Return → Repeat
   │                                              │
   └────────────── Hot-Join / Hot-Leave ──────────┘
```

---

## 3. Runtime

**Module**: `zelos.runtime` | **Class**: `ZelosRuntime`

The central entry point. Owns the complete lifecycle of the Kernel and all Agents.

### Basic Usage

```python
from zelos.runtime import ZelosRuntime

# From dict config
rt = ZelosRuntime({"plugins": [...]})

# From YAML file
rt = ZelosRuntime.from_yaml("zelos.yaml")

# Lifecycle
rt.start()       # Initialize all components + start agents
# ... use the runtime ...
rt.shutdown()    # Graceful shutdown
```

### Agent Management

```python
# Register (hot-join if Runtime is running)
agent_id = rt.add_agent(
    name="ClaudeCode-v2",
    entrypoint="my_agents.coder:CodingAgent",
    capabilities=[
        {"name": "code-generation.python", "version": "1.0.0"},
        {"name": "code-generation.typescript", "version": "1.0.0"},
    ],
    max_concurrent_tasks=5,
    auth_context={"role": "admin", "tenant_id": "eng"},
)

# List agents (tenant-filtered)
agents = rt.list_agents(auth_context={"role": "operator", "tenant_id": "eng"})

# Get agent details
agent = rt.get_agent("ClaudeCode-v2")

# Remove (hot-leave)
rt.remove_agent("ClaudeCode-v2", auth_context={"role": "admin"})
```

### Goal Lifecycle

```python
# Submit — Planner decomposes into Task DAG
goal = rt.submit_goal(
    description="Build a REST API for user management",
    budget=50.0,
    priority="high",
    auth_context={"role": "admin", "tenant_id": "eng"},
    require_approval=True,          # Phase 3: HITL gate
    approvers=["alice", "bob"],     # Phase 3: multi-approver
)

# Check progress
status = rt.get_goal_status(goal["goal_id"])

# Block until done
result = rt.wait_for_goal(goal["goal_id"], timeout_seconds=600)

# Cancel
rt.cancel_goal(goal["goal_id"], auth_context={"role": "admin"})
```

### Phase 3: Advanced APIs

```python
# ── Security ──
key = rt.generate_api_key("agent", "CI pipeline", ttl_seconds=86400,
                          auth_context={"role": "admin"})
audit = rt.get_audit_log(actor="alice", action="goal.submit")

# ── Dynamic Plan Modification ──
rt.modify_plan(plan_id, "add_task",
               task_id="extra-1", description="Additional validation",
               required_capability="code-review.security")

# ── Sub-Goal Spawning ──
sub = rt.spawn_sub_goal("task-123", "Investigate alternatives",
                        budget=25.0, num_tasks=3)

# ── HITL Approval ──
rt.approve_task("approval-abc123", "alice", "LGTM, ship it")
rt.reject_task("approval-abc123", "bob", "Needs more tests")

# ── Hot Reload ──
rt.reload_plugin("verifier", "zelos.verifier_v3:FullVerifier", "3.0.0")
rt.rollback_plugin("verifier", "2.0.0")
rt.set_upgrade_strategy("canary")

# ── Multi-tenancy ──
rt.register_tenant("fintech", "Fintech Division",
                   quotas={"max_goals": 100, "budget_per_goal": 5000})
usage = rt.get_tenant_usage()

# ── Distributed ──
is_leader = rt.is_leader()
cluster = rt.get_cluster_status()
```

### API Reference

| Method | Parameters | Returns | Auth Required |
|--------|-----------|---------|---------------|
| `submit_goal(description, ...)` | `budget, priority, tenant_id, auth_context, require_approval, approvers` | `{goal_id, status, plan_id, task_count}` | `goal.submit` |
| `get_goal_status(goal_id)` | `auth_context` | `{status, progress, ...}` | `goal.read` |
| `cancel_goal(goal_id)` | `auth_context` | `{goal_id, status}` | `goal.cancel` |
| `wait_for_goal(goal_id, timeout)` | `timeout_seconds, poll_interval` | `{status, progress, ...}` | — |
| `add_agent(name, entrypoint, caps)` | `max_concurrent_tasks, auth_context` | `agent_id` | `agent.register` |
| `remove_agent(name_or_id)` | `auth_context` | `None` or error dict | `agent.remove` |
| `list_agents()` | `auth_context` | `[{agent_id, name, status, ...}]` | `agent.read` |
| `get_agent(name_or_id)` | `auth_context` | `{agent_id, capabilities, ...}` | `agent.read` |
| `modify_plan(plan_id, op, **kw)` | `operation: add_task\|remove_task\|modify_task\|add_dependency\|remove_dependency` | `{status, operation}` | — |
| `spawn_sub_goal(parent_id, desc)` | `budget, required_capability, num_tasks` | `{sub_goal_id, task_ids, ...}` | — |
| `approve_task(task_id, approver)` | `comment` | `{status}` | — |
| `reject_task(task_id, approver)` | `reason` | `{status}` | — |
| `reload_plugin(plugin_id, entry, ver)` | — | `{status, plugin_id, version}` | — |
| `rollback_plugin(plugin_id, version)` | — | `{status}` | — |
| `set_upgrade_strategy(name)` | `"rolling"\|"blue_green"\|"canary"\|"instant"` | `{status, strategy}` | — |
| `generate_api_key(role, desc, ttl)` | `auth_context` | `key_string` | `admin.api_key.generate` |
| `revoke_api_key(key)` | `auth_context` | `bool` | `admin.api_key.revoke` |
| `validate_api_key(key)` | — | `{role, ...}` or `None` | — |
| `get_audit_log(**filters)` | `actor, action, resource, start_time, end_time` | `[{event_id, actor, ...}]` | `admin.audit.read` |
| `register_tenant(id, name, quotas)` | `auth_context` | `{status, tenant_id}` | `admin.tenant.manage` |
| `list_tenants()` | — | `[{tenant_id, namespace, ...}]` | — |
| `get_health()` | — | `{status, uptime, components, ...}` | `metrics.read` |
| `get_metrics()` | — | `{goals, tasks, agents, events, ...}` | `metrics.read` |
| `is_leader()` | — | `bool` | — |
| `get_cluster_status()` | — | `{total_nodes, is_leader, ...}` | — |

---

## 4. Event Bus

**Module**: `zelos.event_bus` | **Classes**: `EventBus`, `Event`, `InMemoryEventStore`

The central communication backbone. Every state change in Zelos is an Event. Components never call each other directly.

### Key Concepts

```python
from zelos.event_bus import EventBus, Event, HandlerResult

bus = EventBus(max_events=10000)

# ── Immutable Events ──
event = Event(
    event_id="evt-001",
    event_type="task.completed",
    source="execution-engine",
    timestamp=time.time(),
    correlation_id="goal-g-001",
    payload={"task_id": "t-1", "agent_id": "agent-1", "duration_ms": 1234},
)
bus.publish(event)

# ── Subscribe by exact type ──
def on_task_completed(event: Event):
    print(f"Task done: {event.payload['task_id']}")
    return HandlerResult.ACK

bus.subscribe("task.completed", on_task_completed)

# ── Subscribe by pattern ──
bus.subscribe_pattern("task.*", lambda e: print(f"Task event: {e.event_type}"))

# ── Subscribe by correlation ──
bus.subscribe_correlation("goal-g-001", lambda e: print(f"Goal event: {e}"))
# All events with correlation_id="goal-g-001" are delivered here

# ── Replay ──
count = bus.replay_from(0, lambda e: print(e.event_type))
# count: number of events replayed
```

### Event Schema

| Field | Type | Description |
|-------|------|-------------|
| `event_id` | `str` | UUID v4 — globally unique |
| `event_type` | `str` | Dot-separated: `task.completed`, `goal.submitted` |
| `source` | `str` | Component that emitted the event |
| `timestamp` | `float` | Unix timestamp (seconds) |
| `correlation_id` | `str` | Links events to a Goal or Task |
| `payload` | `dict` | Event-specific data |
| `causation_id` | `str?` | ID of the event that caused this one |
| `data_version` | `str` | Schema version (semver) |
| `metadata` | `dict` | Extra annotations |

### Handler Results

| Result | Behavior |
|--------|----------|
| `HandlerResult.ACK` | Event processed, stop retries |
| `HandlerResult.RETRY` | Retry delivery (max 3 times) |
| `HandlerResult.SKIP` | Skip this event |
| Any other | Treated as ACK |

### Event Taxonomy

```
goal.submitted  goal.planned  goal.started  goal.completed  goal.failed  goal.cancelled
task.created  task.ready  task.assigned  task.started  task.completed  task.failed  task.timed_out
agent.registered  agent.connected  agent.heartbeating  agent.disconnected  agent.removed
artifact.created  artifact.verified
verification.passed  verification.failed
plugin.loaded  plugin.started  plugin.stopped  plugin.error
```

---

## 5. Capability Registry

**Module**: `zelos.capability_registry` | **Classes**: `CapabilityRegistry`, `CapabilityEntry`

The WHAT registry. Agents register their capabilities. The Runtime discovers providers automatically. Never dispatch by agent name.

### Usage

```python
from zelos.capability_registry import CapabilityRegistry

reg = CapabilityRegistry()

# ── Register capabilities ──
reg.register(
    agent_id="agent-1",
    agent_name="CodeAgent",
    capabilities=[
        {
            "name": "code-generation.python",
            "version": "1.0.0",
            "description": "Generate Python code from specifications",
            "input_schema": {"type": "object", "properties": {"spec": {"type": "string"}}},
            "output_schema": {"type": "object", "properties": {"code": {"type": "string"}}},
            "tags": ["production", "python", "soc2-compliant"],
        }
    ]
)

reg.mark_available("agent-1")

# ── Query by capability ──
providers = reg.find_providers_for("code-generation.python")
# → ["agent-1"]

# ── Query by name pattern ──
providers = reg.find_by_name_pattern("code-generation.*")
# → ["agent-1"]

# ── Query by tags (AND logic) ──
providers = reg.find_by_tags(["production", "python"])
# → ["agent-1"]

# ── Query by version constraint ──
providers = reg.find_by_version("code-generation.python", ">=1.0,<2.0")
# → providers with matching version

# ── Lifecycle ──
reg.mark_deprecated("agent-1")  # Stop routing new tasks
reg.mark_unavailable("agent-1") # Agent is down
```

---

## 6. Task Graph

**Module**: `zelos.task_graph` | **Classes**: `TaskGraphEngine`, `Task`, `TaskStatus`

Manages the Task state machine and DAG dependency resolution. Every Goal becomes a Plan, every Plan is a DAG of Tasks.

### Task State Machine

```
CREATED → READY → ASSIGNED → STARTED → COMPLETED  (terminal)
  ↓        ↓         ↓           ↓
  ↓        ↓         ↓           ├── FAILED → READY (retry)
  ↓        ↓         ↓           └── TIMED_OUT → READY (retry)
  ↓        ↓         └── READY (reject)
  ↓        └── FAILED (escalation tier 3)
  └── CANCELLED (terminal)
```

### Usage

```python
from zelos.task_graph import Task, TaskStatus, TaskGraphEngine

tg = TaskGraphEngine()

# ── Create tasks ──
t1 = Task(task_id="t1", plan_id="plan-1",
          description="Design the architecture",
          required_capability="design.architecture",
          priority="high", timeout_ms=60000)
t2 = Task(task_id="t2", plan_id="plan-1",
          description="Code the implementation",
          required_capability="code-generation.python",
          dependencies=["t1"])  # t2 depends on t1 completing
t3 = Task(task_id="t3", plan_id="plan-1",
          description="Review the code",
          required_capability="code-review.security",
          dependencies=["t2"])

tg.add_task(t1)
tg.add_task(t2)
tg.add_task(t3)

# ── Evaluate dependencies ──
ready = tg.evaluate_all()
# t1 has no deps → READY immediately
# t2 waits for t1
# t3 waits for t2

# ── State transitions ──
tg.transition("t1", TaskStatus.ASSIGNED, agent_id="agent-1")
tg.transition("t1", TaskStatus.STARTED)
tg.transition("t1", TaskStatus.COMPLETED)
# Now t2 becomes READY automatically

ready = tg.evaluate_all()  # → ["t2"]

# ── DAG validation ──
tg.add_dependency("t3", "t1")  # ⚠️ Would create cycle t1→t2→t3→t1
# → ValueError: Adding edge t3→t1 would create a cycle

# ── Dynamic modification (Phase 3) ──
tg.add_task_dynamic(Task(task_id="t4", plan_id="plan-1",
                         description="Extra step",
                         required_capability="testing.e2e",
                         dependencies=["t3"]))
tg.remove_task("t4")  # Only unstarted tasks
```

### Task Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task_id` | `str` | required | Unique task identifier |
| `plan_id` | `str` | required | Parent plan ID |
| `description` | `str` | required | What this task does |
| `required_capability` | `str` | required | Capability name to dispatch to |
| `status` | `TaskStatus` | `CREATED` | Current state |
| `dependencies` | `List[str]` | `[]` | Task IDs that must complete first |
| `priority` | `str` | `"medium"` | `low` / `medium` / `high` / `critical` |
| `max_retries` | `int` | `3` | Maximum retry attempts |
| `timeout_ms` | `int` | `30000` | Execution timeout |
| `fallback_capability` | `str?` | `None` | Alternative capability if primary unavailable |
| `preferred_agent_id` | `str?` | `None` | Affinity hint for scheduler |
| `excluded_agent_ids` | `List[str]` | `[]` | Agents to never dispatch to |
| `required_tags` | `List[str]` | `[]` | Required agent tags |
| `min_success_rate` | `float` | `0.0` | Minimum agent historical success |
| `max_cost_per_call` | `float?` | `None` | Cost ceiling |

---

## 7. Scheduler

**Module**: `zelos.scheduler` | **Classes**: `Scheduler`, `ScoringStrategy`, `DefaultScoringStrategy`

The 5-phase scheduling pipeline that matches READY tasks to available Agents.

### The Pipeline

```
Phase 1: ORDER   → Sort READY tasks by priority > fan-out > age
Phase 2: FILTER  → Find agents matching capability + tags + constraints
Phase 3: SCORE   → Rank agents (delegated to ScoringStrategy plugin)
Phase 4: POLICY  → Apply policy decisions (Allow/Reject/Delay/Retry)
Phase 5: SELECT  → Pick the best agent and mark task ASSIGNED
```

### Custom Scoring Strategy

```python
from zelos.scheduler import ScoringStrategy, AgentCandidate, ScoredCandidate

class CostFirstScoring(ScoringStrategy):
    """Prioritize cheapest agents. Fail-safe with success_rate floor."""

    def score(self, task, candidates):
        results = []
        for c in candidates:
            # Quality floor
            if c.success_rate < 0.80:
                results.append(ScoredCandidate(c, score=0,
                    reason=f"Success rate {c.success_rate:.0%} below 80% threshold"))
                continue

            # Cost-first formula
            score = (
                (1.0 / (c.cost_per_call + 0.01)) * 0.6 +  # Cheaper = better
                c.success_rate * 0.3 +                      # Some quality
                (1.0 - c.current_load) * 0.1                # Less loaded = better
            )
            results.append(ScoredCandidate(c, score=score,
                reason=f"Cost=${c.cost_per_call:.3f} Success={c.success_rate:.0%}"))
        return sorted(results, key=lambda r: r.score, reverse=True)
```

### Default Scoring Weights

```python
DefaultScoringStrategy(weights={
    "success_rate": 0.30,       # Proven reliability
    "cost_efficiency": 0.20,    # Lower cost preferred
    "load_distribution": 0.15,  # Prefer less busy agents
    "latency": 0.15,            # Faster is better
    "availability": 0.10,       # Higher uptime
    "affinity": 0.05,           # Same agent for related tasks
    "recency": 0.05,            # Recently used (context warmth)
})
```

### Retry Logic

```
Task FAILED or TIMED_OUT
  → attempt += 1
  → if attempt <= max_retries:
      backoff = base * 2^(attempt-1) + random(0, 500) ms
      → READY again
  → else:
      → FAILED (terminal)
```

---

## 8. Execution Engine

**Module**: `zelos.execution_engine` | **Classes**: `ExecutionEngine`, `AgentState`

Dispatches tasks to agents, monitors their lifecycle, enforces timeouts, and tracks heartbeats.

### Agent State Machine

```
registered → connected → heartbeating → disconnected → shutdown
                │                                      │
                └── (after heartbeat recovers) ────────┘
```

### Dispatch Flow

```python
# ── Agent Side ──
engine.register_agent(agent_id="agent-1", agent_name="CodeAgent",
                      max_concurrent_tasks=5)

# Heartbeat every 30s
engine.heartbeat("agent-1")  # → "heartbeating"

# ── Runtime Side ──
engine.dispatch("t1", "agent-1")
# → Task status: ASSIGNED → STARTED
# → Agent.current_tasks: ["t1"]
# → InFlight: {task_id, agent_id, started_at, timeout_at}

# ── Agent returns result ──
engine.submit_result("t1", "agent-1", {
    "status": "completed",
    "artifact": {"content_type": "application/json", "content": {...}}
})
# → Task status: COMPLETED
# → Agent.current_tasks: [] → "idle"

# ── Error handling ──
engine.submit_result("t2", "agent-1", {
    "status": "failed",
    "error": {"code": "internal_error", "message": "Out of memory"}
})
# → Task status: FAILED → Scheduler retries if attempts remain

# ── Cancellation ──
engine.cancel_task("t3")
# → Task status: CANCELLED
```

### Timeout Monitor

Background thread checks every second:
- Tasks exceeding `timeout_at` → `TIMED_OUT`
- Agents without heartbeat for 3× heartbeat_interval → `disconnected`

---

## 9. Planner

**Module**: `zelos.planner` | **Class**: `LLMPlanner`

Decomposes natural-language Goals into structured Execution Plans (Task DAGs) using an LLM.

### Supported Providers

```python
from zelos.planner import LLMPlanner

# OpenAI / DeepSeek / Ollama / vLLM
planner = LLMPlanner({
    "provider": "openai",
    "model": "deepseek-v4-flash",
    "api_key": "sk-...",
    "base_url": "https://api.deepseek.com/v1",
    "temperature": 0.3,
    "max_tokens": 4000,
})

# Anthropic
planner = LLMPlanner({
    "provider": "anthropic",
    "model": "claude-sonnet-5",
    "api_key": "sk-ant-...",
})

# Google Gemini
planner = LLMPlanner({
    "provider": "google",
    "model": "gemini-2.0-flash",
    "api_key": "...",
})

# Mock (for testing)
planner = LLMPlanner({"provider": "mock"})
```

### Plan → Replan

```python
# Initial plan
plan = planner.plan("Build a user authentication system")
# → ExecutionPlan with Task DAG:
#   t1: Design auth architecture [design.architecture]
#   t2: Implement backend [code-generation.python] ← depends on t1
#   t3: Implement frontend [code-generation.typescript] ← depends on t1
#   t4: Security review [code-review.security] ← depends on t2,t3
#   t5: Integration tests [testing.e2e] ← depends on t4

# Replan on failure
new_plan = planner.replan(
    goal_description="Build a user authentication system",
    current_plan=plan,
    failed_tasks=[
        {"task_id": "t2", "reason": "no agent provides capability: code-generation.python"}
    ]
)
# → New alternative tasks to replace failed ones
```

---

## 17. Security (Phase 3)

**Module**: `zelos.security` | **Classes**: `AccessControl`, `AuditLogger`, `APIKeyManager`, `TLSConfig`

Production-grade security infrastructure. Integrated into `ZelosRuntime` — all API methods enforce RBAC and log audit events.

### Role-Based Access Control

```python
from zelos.security import AccessControl

ac = AccessControl()

# ── Default Roles ──
# admin:    * (wildcard — everything)
# operator: goal.*, task.*, agent.read, plugin.*
# agent:    task.execute, agent.heartbeat, artifact.create
# viewer:   goal.read, task.read, agent.read, metrics.read

# ── Permission checks ──
ac.check("admin", "goal.submit")     # → True (wildcard)
ac.check("operator", "task.create")  # → True (task.* pattern)
ac.check("agent", "goal.submit")     # → False (no permission)
ac.check("viewer", "agent.delete")   # → False

# ── Custom roles ──
ac.add_role("sre", [
    "goal.read", "metrics.read", "agent.read",
    "plugin.configure", "audit.read",
])
ac.update_role("sre", add_permissions=["goal.cancel"])
ac.remove_role("sre")
```

### Audit Logging

```python
from zelos.security import AuditLogger

al = AuditLogger(max_events=100000)

# Every operation logs automatically through ZelosRuntime
# Manual logging:
al.log("admin", "goal.submit", "g-001",
       detail="Deploy v2.0 to production", result="success")

# ── Multi-field query ──
events = al.query(
    actor="admin",           # Who did it
    action="goal.submit",    # What they did
    resource="g-001",        # On what
    result="success",        # Outcome
    start_time=last_hour,    # When
    limit=100,
)

# ── Export ──
json_str = al.export_json()
```

### API Key Management

```python
from zelos.security import APIKeyManager

akm = APIKeyManager()

# Generate (plaintext shown once — hash stored)
key = akm.generate_key("agent", "CI/CD pipeline", ttl_seconds=86400)
# → "zelos_a1b2c3d4e5f6..."

# Validate → returns role info or None
info = akm.validate(key)
# → {"role": "agent", "description": "CI/CD pipeline", "expires_at": ...}

# Revoke
akm.revoke(key)
akm.validate(key)  # → None

# List (hashes only, never plaintext)
keys = akm.list_keys()
```

### mTLS Configuration

```python
from zelos.security import TLSConfig

tls = TLSConfig(
    cert_file="/etc/zelos/certs/server.crt",
    key_file="/etc/zelos/certs/server.key",
    ca_file="/etc/zelos/certs/ca.crt",
    require_client_cert=True,
    min_tls_version="TLSv1.3",
)

if tls.is_configured():
    # Apply to HTTP adapter / gRPC server
    pass
```

### Integration with Runtime

```python
rt = ZelosRuntime(...)
rt.start()

# All API calls enforce RBAC:
rt.submit_goal("...", auth_context={"role": "agent"})
# → {"status": "rejected", "reason": "Permission denied: role 'agent' cannot 'goal.submit'"}

# All state changes auto-logged:
audit = rt.get_audit_log(actor="alice")
# → [{event_id, timestamp, actor, action, resource, detail, result}, ...]

# API key auth:
key = rt.generate_api_key("admin", "my key", auth_context={"role": "admin"})
rt.submit_goal("...", auth_context={"api_key": key})
```

---

## 18. Multi-tenancy (Phase 3)

**Module**: `zelos.multi_tenancy` | **Classes**: `Namespace`, `ResourceQuota`, `TenantManager`

Hard isolation between tenants sharing a single Runtime. Integrated into `ZelosRuntime`.

### Namespace & Quotas

```python
from zelos.multi_tenancy import Namespace, ResourceQuota

# ── Quota configuration ──
quotas = ResourceQuota(
    max_goals=100,              # Active goals
    max_tasks=500,              # Active tasks
    max_agents=20,              # Registered agents
    budget_per_goal=5000.0,     # Max cost per goal
    max_concurrent_tasks=50,    # Parallel execution limit
    max_storage_mb=2048,        # Storage allocation
)

# ── Namespace isolation ──
ns = Namespace("fintech", "Fintech Division", quotas=quotas)

ns.add_goal("g-1")
ns.add_agent("agent-1")
ns.add_task("t-1")

ns.check_quota("goals")      # → True (1/100)
ns.check_quota("agents")     # → True (1/20)
ns.quotas.check_budget(3000) # → True (within $5000 limit)
```

### Tenant Management

```python
from zelos.multi_tenancy import TenantManager

tm = TenantManager()

# ── Register tenants ──
tm.register_tenant("acme-corp", "ACME Corporation",
    quotas=ResourceQuota(max_goals=500, budget_per_goal=10000),
    metadata={"org": "Engineering", "tier": "enterprise"})

tm.register_tenant("dev-team", "Development Team",
    quotas=ResourceQuota(max_goals=20, budget_per_goal=200),
    metadata={"org": "R&D", "tier": "standard"})

# ── Lifecycle ──
tm.deactivate_tenant("dev-team")
tm.is_active("dev-team")    # → False
tm.activate_tenant("dev-team")

# ── Cross-tenant isolation ──
ns_a = tm.get_namespace("acme-corp")
ns_b = tm.get_namespace("dev-team")
ns_a.add_goal("g-1")
# g-1 is invisible to dev-team namespace

# ── Usage report ──
report = tm.get_usage_report()
# → {"total_tenants": 2, "active_tenants": 2,
#    "tenants": {"acme-corp": {"goals": 1, ...}, ...}}
```

### Runtime Integration

```python
rt = ZelosRuntime({
    "multi_tenancy": {
        "enabled": True,
        "tenants": [
            {"id": "eng", "name": "Engineering",
             "quotas": {"max_goals": 100, "budget_per_goal": 5000}},
            {"id": "research", "name": "Research Lab",
             "quotas": {"max_goals": 10, "budget_per_goal": 2000}},
        ]
    }
})

# Tenant-scoped operations
rt.submit_goal("...", auth_context={"role": "admin", "tenant_id": "eng"})
rt.add_agent("...", capabilities=[...],
             auth_context={"role": "admin", "tenant_id": "eng"})

# Cross-tenant isolation enforced automatically
rt.get_goal_status("g-from-eng", auth_context={"tenant_id": "research"})
# → None (not in research tenant)
```

---

## 19. Advanced Execution (Phase 3)

**Module**: `zelos.advanced_execution` | **Classes**: `DynamicPlanModifier`, `SubGoalManager`, `HumanInTheLoop`

Production execution features beyond basic task dispatch.

### Dynamic Plan Modification

```python
rt.modify_plan(plan_id, "add_task",
               task_id="hotfix-1",
               description="Emergency security patch",
               required_capability="code-generation.python",
               priority="critical",
               dependencies=["existing-task-3"])

rt.modify_plan(plan_id, "remove_task", task_id="obsolete-task")
rt.modify_plan(plan_id, "modify_task", task_id="t-2",
               priority="critical", timeout_ms=120000)
rt.modify_plan(plan_id, "add_dependency",
               from_task_id="t-1", to_task_id="t-4")
rt.modify_plan(plan_id, "remove_dependency",
               from_task_id="t-1", to_task_id="t-4")
```

### Sub-Goal Spawning

```python
# A task discovers it needs additional work:
sub = rt.spawn_sub_goal(
    parent_task_id="task-123",
    description="Research competitor pricing strategy",
    budget=25.0,
    required_capability="research.analysis",
    num_tasks=3,  # Create 3 sequential sub-tasks
)
# → {sub_goal_id: "sub-a1b2c3d4", parent_task_id: "task-123",
#    plan_id: "sub-plan-sub-a1b2c3d4", task_ids: ["sub-...-t1", "sub-...-t2", "sub-...-t3"],
#    budget: 25.0, status: "running"}

# Check sub-goal status
status = rt.get_sub_goal_status(sub["sub_goal_id"])

# All sub-goals for a parent auto-propagate:
# - All sub-goals completed → parent can complete
# - Any sub-goal failed → parent fails
```

### Human-in-the-Loop Approval

```python
# ── Require approval before goal executes ──
goal = rt.submit_goal(
    "Deploy v3.0 to production",
    require_approval=True,
    approvers=["alice", "bob"],  # Both must approve
    auth_context={"role": "admin"},
)
# → Goal is "planned" but tasks won't dispatch until approved

# ── Check pending approvals ──
pending = rt.list_pending_approvals()
# → [{request_id, task_id, description, approvers, require_all, status}, ...]

# ── First approver ──
rt.approve_task(pending[0]["task_id"], "alice", "Code review passed ✅")
# → Still pending — needs bob too

# ── Second approver ──
rt.approve_task(pending[0]["task_id"], "bob", "Monitoring dashboards clean ✅")
# → Approved! Tasks start dispatching

# ── Alternatively: Reject ──
rt.reject_task(task_id, "alice", "Security scan found 3 critical issues")
# → Goal marked "failed"

# ── Request changes ──
rt._hitl.request_changes(request_id, "bob", "Please add integration tests")
# → Status: "changes_requested" — developer sees feedback
```

---

## 21. Hot Reload (Phase 3)

**Module**: `zelos.hot_reload` | **Classes**: `HotReloadManager`, `FileWatcher`, `UpgradeStrategy`

Zero-downtime plugin upgrades. Supports 4 strategies with distinct behaviors.

### Upgrade Strategies

| Strategy | Behavior | Use Case |
|----------|----------|----------|
| `ROLLING` | One instance at a time | Default safe upgrade |
| `BLUE_GREEN` | Spin up new, keep old, then cut over | Major version bumps |
| `CANARY` | Route X% traffic to new | Test new version on subset |
| `INSTANT` | Immediate cut-over | Hotfixes, config changes |

### Usage

```python
from zelos.hot_reload import HotReloadManager, UpgradeStrategy

hrm = HotReloadManager(upgrade_strategy=UpgradeStrategy.ROLLING)

# ── Version lifecycle ──
hrm.register_version("my-plugin", "1.0.0", "plugins:v1", checksum="sha256:abc")
hrm.register_version("my-plugin", "1.1.0", "plugins:v2", checksum="sha256:def")
hrm.register_version("my-plugin", "2.0.0", "plugins:v3", checksum="sha256:ghi")

active = hrm.get_active_version("my-plugin")
# → PluginVersion(version="2.0.0", status="active")

# ── Drain old ──
hrm.drain_version("my-plugin", "1.0.0")
# → status: "drained" — no new tasks routed here

# ── Rollback ──
hrm.rollback("my-plugin", "1.1.0")
# → Version 1.1.0 active again

# ── Canary deployment ──
hrm.set_upgrade_strategy(UpgradeStrategy.CANARY)
hrm.register_version("api-gateway", "3.0.0", "gateway:v3",
                     canary_percent=5)
# → 5% traffic → v3.0.0, 95% → v2.x

# ── Version history ──
history = hrm.get_version_history("my-plugin")
# → [v1.0.0 (drained), v1.1.0 (active), v2.0.0 (rolled_back)]

# ── File watcher ──
fw = FileWatcher("/etc/zelos/plugins", patterns=["*.py"])
fw.on_change(lambda event: print(f"Plugin changed: {event['filename']}"))
fw.start()
```

### Runtime Integration

```python
# In zelos.yaml:
# hot_reload:
#   plugin_dir: "/etc/zelos/plugins"
#   upgrade_strategy: "rolling"

rt.reload_plugin("verifier", "zelos.verifier_v3:FullVerifier", "3.0.0")
rt.rollback_plugin("verifier", "2.0.0")
rt.set_upgrade_strategy("canary")
rt.get_plugin_versions("verifier")
```

---

## 22. Distributed Runtime (Phase 3)

**Module**: `zelos.distributed` | **Classes**: `LeaderElection`, `WorkStealing`, `NodeRegistry`

Multi-node cluster coordination. Reference implementation using in-memory coordination (production: etcd/Raft).

### Leader Election

```python
from zelos.distributed import LeaderElection

le = LeaderElection(node_id="zelos-01", heartbeat_interval_ms=500)
le.register_peer("zelos-02")
le.register_peer("zelos-03")
le.on_leader_change(lambda new_leader: print(f"New leader: {new_leader}"))
le.start()

le.is_leader()       # → True/False
le.get_leader_id()   # → "zelos-01" or None
le.resign()          # Voluntary step-down
le.stop()
```

### Work Stealing

```python
from zelos.distributed import WorkStealing

ws = WorkStealing(node_id="worker-1", max_concurrent_tasks=10)

ws.enqueue_task("t-1", "code-generation.python", priority="high")
ws.enqueue_task("t-2", "code-review.security", priority="medium")

ws.queue_size()       # → 2
ws.get_load_percent() # → 20.0%

# Steal from overloaded peer
overloaded = WorkStealing("worker-2", max_concurrent_tasks=5)
for i in range(8):
    overloaded.enqueue_task(f"heavy-{i}", "code-generation.python")

stolen = ws.steal_from(overloaded, max_count=3)
# → [{task_id, capability, priority, stolen_from, stolen_at}, ...]
```

### Node Registry

```python
from zelos.distributed import NodeRegistry, ClusterNode

nr = NodeRegistry(heartbeat_timeout_seconds=30.0)

nr.register(ClusterNode(
    node_id="zelos-primary", host="10.0.1.10", port=9876,
    capabilities=["code-generation.python", "code-review.security"],
    capacity=20,
))

nr.heartbeat("zelos-primary")
nr.find_by_capability("code-generation.python")  # → [ClusterNode, ...]
nr.detect_dead_nodes()                            # → ["zelos-worker-2"]
nr.cluster_status()
# → {total_nodes: 4, healthy_nodes: 3, dead_nodes: 1, cluster_capabilities: [...]}
```

### Runtime Integration

```yaml
# zelos.yaml
distributed:
  enabled: true
  node_id: "zelos-master-1"
  host: "10.0.1.10"
  port: 9876
  capacity: 20
  peers:
    - node_id: "zelos-worker-1"
      host: "10.0.1.11"
      capabilities: ["automation.browser"]
    - node_id: "zelos-worker-2"
      host: "10.0.1.12"
      capabilities: ["code-review.security"]
```

```python
rt.is_leader()            # → True/False
rt.get_cluster_status()   # → {total_nodes, healthy_nodes, is_leader, ...}
rt.get_work_queue_depth() # → current task queue depth
```

---

## 23. CLI Tool (Phase 3)

**Module**: `zelos.cli` | **Class**: `ZelosCLI`

Complete command-line interface.

### Available Commands

```bash
zelos --version                              # 0.3.0
zelos --help

# Runtime
zelos start --config zelos.yaml --port 9876
zelos stop

# Goals
zelos goal submit --description "Build a landing page" --priority high --budget 100
zelos goal status --goal-id g-abc123
zelos goal list
zelos goal cancel --goal-id g-abc123

# Agents
zelos agent list
zelos agent info --agent-id agent-codex-1

# Admin
zelos health
zelos metrics
zelos plugin list
zelos namespace list
zelos config show
zelos config validate
```

### Programmatic Usage

```python
from zelos.cli import ZelosCLI

cli = ZelosCLI(runtime=my_runtime)  # Connect to real runtime
# OR
cli = ZelosCLI()                     # Simulation mode

output = cli.run(["goal", "submit", "--description", "Test"])
print(output)
```

---

## 24. Configuration

Complete `zelos.yaml` reference:

```yaml
runtime:
  instance_id: "zelos-prod-01"
  api:
    host: "0.0.0.0"
    port: 9876
    auth:
      enabled: true
      keys:
        - key: "zelos_admin_***"
          role: admin
  limits:
    max_goals: 1000
    max_tasks_per_goal: 100

plugins:
  - id: "llm-planner"
    type: "planner"
    entrypoint: "zelos.planner.LLMPlanner"
    config:
      provider: "openai"
      model: "gpt-4o"
      api_key: "${OPENAI_API_KEY}"
      temperature: 0.3

  - id: "schema-verifier"
    type: "verifier"
    entrypoint: "zelos.verifier.SchemaVerifier"

  - id: "default-policy"
    type: "policy"
    entrypoint: "zelos.policy.CompositePolicy"
    config:
      max_cost_per_goal: 100.0
      max_tasks_per_minute: 60

  - id: "default-scoring"
    type: "scoring_strategy"
    entrypoint: "zelos.scheduler.DefaultScoringStrategy"
    config:
      weights:
        success_rate: 0.30
        cost_efficiency: 0.20

  - id: "inmemory-storage"
    type: "storage"
    entrypoint: "zelos.storage.InMemoryStorageBackend"

storage:
  type: "postgresql"
  url: "postgresql://user:pass@host:5432/zelos"

security:                     # Phase 3
  cert_file: "/etc/zelos/certs/server.crt"
  key_file: "/etc/zelos/certs/server.key"
  ca_file: "/etc/zelos/certs/ca.crt"
  require_client_cert: true
  audit_max_events: 100000

multi_tenancy:                # Phase 3
  enabled: true
  tenants:
    - id: "eng"
      name: "Engineering"
      quotas:
        max_goals: 100
        max_agents: 20
        budget_per_goal: 5000

hot_reload:                   # Phase 3
  plugin_dir: "/etc/zelos/plugins"
  upgrade_strategy: "rolling"
  watch_patterns: ["*.py", "*.yaml"]

distributed:                  # Phase 3
  enabled: true
  node_id: "zelos-01"
  host: "10.0.1.10"
  port: 9876
  capacity: 20
  peers:
    - node_id: "zelos-02"
      host: "10.0.1.11"
```

---

## 25. API Reference

### Auth Context

Every API method accepts an optional `auth_context` dict:

```python
# Full auth
{"role": "admin", "tenant_id": "eng", "actor": "alice@corp.com"}

# API key auth
{"api_key": "zelos_a1b2c3..."}

# No auth → defaults to admin (backward compatible)
None
```

### Return Value Patterns

**Success**:
```python
{"goal_id": "g-...", "status": "planned", "plan_id": "...", "task_count": 4}
{"status": "ok", "operation": "add_task"}
{"status": "approved"}
```

**Rejection**:
```python
{"goal_id": "...", "status": "rejected", "reason": "Permission denied: role 'agent' cannot 'goal.submit'"}
{"status": "rejected", "reason": "Goal quota exceeded for tenant 'eng'"}
{"goal_id": "...", "status": "rejected", "reason": "Invalid or expired API key"}
```

**Error**:
```python
{"status": "failed", "reason": "Task 'x' not found"}
{"status": "not_found"}
None
```

### Role Permission Matrix

| Action | admin | operator | agent | viewer |
|--------|-------|----------|-------|--------|
| `goal.submit` | ✅ | ✅ | ❌ | ❌ |
| `goal.cancel` | ✅ | ✅ | ❌ | ❌ |
| `goal.read` | ✅ | ✅ | ❌ | ✅ |
| `task.execute` | ✅ | ✅ | ✅ | ❌ |
| `task.create` | ✅ | ✅ | ❌ | ❌ |
| `task.read` | ✅ | ✅ | ❌ | ✅ |
| `agent.register` | ✅ | ✅ | ❌ | ❌ |
| `agent.heartbeat` | ✅ | ❌ | ✅ | ❌ |
| `agent.read` | ✅ | ✅ | ❌ | ✅ |
| `metrics.read` | ✅ | ✅ | ❌ | ✅ |
| `plugin.configure` | ✅ | ✅ | ❌ | ❌ |
| `admin.api_key.*` | ✅ | ❌ | ❌ | ❌ |
| `admin.audit.*` | ✅ | ❌ | ❌ | ❌ |
| `admin.tenant.*` | ✅ | ❌ | ❌ | ❌ |

---

## 26. Deployment Guide

### Development (Single Node)

```bash
python3 -c "
from zelos.runtime import ZelosRuntime
rt = ZelosRuntime.from_yaml('zelos.yaml')
rt.start()
# ... ctrl-c to stop
"
```

### Production (Multi-node)

```yaml
# Node 1 (leader candidate)
distributed:
  enabled: true
  node_id: "zelos-primary"
  host: "10.0.1.10"
  peers:
    - {node_id: "zelos-worker-1", host: "10.0.1.11"}
    - {node_id: "zelos-worker-2", host: "10.0.1.12"}

security:
  cert_file: "/etc/zelos/certs/server.crt"
  key_file: "/etc/zelos/certs/server.key"
  ca_file: "/etc/zelos/certs/ca.crt"
  require_client_cert: true

storage:
  type: "postgresql"
  url: "postgresql://zelos:${DB_PASS}@pg-cluster:5432/zelos"
```

### Container Deployment

```dockerfile
FROM python:3.12-slim
COPY zelos/ /app/zelos/
COPY zelos.yaml /app/
CMD ["python3", "-c", "from zelos.runtime import ZelosRuntime; \
     rt = ZelosRuntime.from_yaml('zelos.yaml'); rt.start()"]
```

---

## 27. Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| `Permission denied` | Wrong role | Check `auth_context["role"]` or API key role |
| `Goal quota exceeded` | Tenant at limit | Increase `quotas.max_goals` or complete old goals |
| `no agent provides capability: X` | No agent registered for X | Add agent with that capability, or use `fallback_capability` |
| `Invalid transition: X → Y` | Task in wrong state | Check `task.status` before calling `transition()` |
| `Adding edge X→Y would create cycle` | Circular dependency | Re-design DAG to be acyclic |
| `Hot reload not detecting changes` | FileWatcher not started | Check `hot_reload.plugin_dir` in config |
| `Multiple leaders detected` | No peer registration | Register all peers with `register_peer()` |
| `Expired API key` | TTL too short | Generate key with longer `ttl_seconds` |
