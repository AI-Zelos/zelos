# Zelos 全面技术手册

> **Open Multi-Agent Orchestration Runtime**
> 一个完整的、生产就绪的多 Agent 编排运行时。不是框架，是基础设施。

---

## 目录

1. [项目简介](#1-项目简介)
2. [为什么存在](#2-为什么存在)
3. [什么时候使用](#3-什么时候使用)
4. [核心概念](#4-核心概念)
5. [快速上手](#5-快速上手)
6. [Runtime Kernel（内核）](#6-runtime-kernel)
7. [Plugin 生态系统](#7-plugin-生态系统)
8. [分布式与生产部署](#8-分布式与生产部署)
9. [安全与合规](#9-安全与合规)
10. [多租户](#10-多租户)
11. [可观测性](#11-可观测性)
12. [SDK 参考](#12-sdk-参考)
13. [API 参考](#13-api-参考)
14. [部署指南](#14-部署指南)
15. [常见问题](#15-常见问题)

---

## 1. 项目简介

### Zelos 是什么

**Zelos 是面向多 Agent 协同的编排运行时。** 它接受一个自然语言描述的 Goal（目标），自动将其分解为可执行的 Task DAG，按能力匹配合适的 Agent，调度执行，验证结果，并记录完整的不可变审计链。

```
用户: "帮我做一个电商网站的 Landing Page"

Zelos Runtime:
  ├── Planner    → 分解为 6 个 Task（设计 → 编码 → 审查 → 修复 → 截图 → 报告）
  ├── Scheduler  → 每个 Task 按 Capability 匹配最佳 Agent
  ├── ExecEngine → 派发 Task，监控心跳，超时重试
  ├── Verifier   → 验证每个 Agent 的输出是否符合预期 Schema
  ├── Policy     → 控制预算、频率、权限
  └── EventBus   → 全程不可变审计记录
```

### 类比

| 系统 | 管理单元 | 做什么 |
|------|:--:|------|
| Linux | Process | CPU、内存、IO 调度 |
| Kubernetes | Container | 扩缩容、网络、服务发现 |
| Temporal | Workflow | 确定性工作流执行、重试、状态 |
| **Zelos** | **Goal** | **多 Agent 规划、调度、验证、审计** |

### 核心数据

| 指标 | 数值 |
|------|------|
| 版本 | v0.7.0 |
| Phases | 0–7 全部完成 |
| 源码模块 | 28 个 |
| 自动化测试 | 78 个（71 passed） |
| Demo | 21 个 |
| SDK | Python / TypeScript / Go |
| 外部依赖 | **零**（核心纯 Python stdlib） |

---

## 2. 为什么存在

### 问题：多 Agent 系统的编排危机

2026 年的 AI 应用不再是单模型系统。一个用户请求可能需要：

```
规划 ──→ 研究 ──→ 编码 ──→ 浏览器自动化 ──→ 数据库查询 ──→ 验证 ──→ 人工审批
  ↑                        ↑                          ↑                ↑
  Planner              CodeAgent                   SQLAgent        HumanReviewer
```

每个环节由**不同团队、不同技术栈、不同框架**构建的 Agent 完成。问题来了：

1. **谁负责调度？** Agent A 不知道 Agent B 的存在，也不知道 B 什么时候完成
2. **谁负责重试？** Agent 执行失败了，应该换一个 Agent 还是重新规划？
3. **谁负责验证？** Agent C 的输出可能是错的，谁来检查？
4. **谁负责审计？** 如果出错了，怎么追溯是哪个 Agent 的哪个决策导致的？
5. **谁负责治理？** 预算超了谁踩刹车？频率超了谁限流？

### 现有方案为什么不够

| 方案 | 解决了什么 | 没解决什么 |
|------|-----------|-----------|
| **LangGraph / CrewAI** | Agent 构建 | 不负责调度、不负责审计、不负责治理 |
| **Temporal / Airflow** | 确定性工作流 | Agent 的行为是非确定性的——不适合工作流引擎 |
| **MCP / A2A** | Agent 通信协议 | 通信 ≠ 治理。没有规划、验证、审计 |

### Zelos 的答案

> 把"Agent 编排"从应用层问题变成基础设施层问题。

开发者不需要在自己的应用代码里管理 Agent 之间的依赖、重试、超时、验证。他们只需要：
1. 构建 Agent
2. 声明 Capability（能力）
3. 注册到 Zelos

剩下的一切——规划、调度、执行、重试、验证、审计——由 Runtime 处理。

---

## 3. 什么时候使用

### ✅ 适合使用 Zelos 的场景

| 场景 | 为什么 |
|------|--------|
| **AI SaaS 平台** — 产品背后有 10+ 个专用 Agent | 需要调度器选最佳 Agent、失败自动重试、追踪每次调用的成本 |
| **企业 AI 转型** — 多部门 Agent 需要跨团队协作 | Namespace 隔离、RBAC 权限、审计链满足合规要求 |
| **强合规行业**（金融/医疗/法律） | 不可变审计链 = 每一笔 Agent 决策都可追溯、可重放 |
| **Agent 基础设施商** — 构建第三方 Agent 注册和发现平台 | Capability Registry 天然就是 Agent 搜索引擎 |
| **AI 研究** — 评估治理 vs 无治理的多 Agent 系统 | 同一套 Benchmark 跑两遍，对比失败率和成本 |
| **高可靠性自动化** — CI/CD、事件响应、数据管道 | 重试、超时、热加入、零停机升级 |

### ❌ 不适合的场景

| 场景 | 为什么 |
|------|--------|
| 3-5 个 Agent 的简单脚本 | 一个 for 循环就够了，Zelos 是重型武器 |
| 确定性工作流（纯代码、无 AI） | 用 Temporal 更合适 |
| 只想做 Prompt 管理 | 用 LangChain 更轻量 |
| 单模型 API 调用 | 你不需要编排 Runtime |

---

## 4. 核心概念

### 4.1 Goal（目标）

用户提交的自然语言任务描述。例如："帮我写一个 Python Web 项目，包含登录和注册功能"。

```python
goal = rt.submit_goal(
    description="写一个 Python Web 项目，包含登录和注册功能",
    priority="high",
    budget=50.0,         # 最多花多少钱
    deadline_ms=600000,  # 10 分钟超时
)
```

Goal 生命周期：
```
submitted → accepted → planned → executing → completed / failed / cancelled
```

### 4.2 Execution Plan（执行计划）

Planner 将 Goal 分解为 Task DAG。Plan 是动态的——Task 失败后可以 re-plan。

```
Plan: "Build Web Project"
  ├── Task 1: Design database schema   [design.db-schema]
  ├── Task 2: Implement auth module    [code-generation.python]  ← depends on T1
  ├── Task 3: Write unit tests         [verification.unit-test]  ← depends on T2
  └── Task 4: Deploy to staging        [automation.cli]          ← depends on T3
```

### 4.3 Task（任务）

Plan 中的最小执行单元。一个 Task = 一次 Agent 调用。

```python
Task(
    task_id="task-auth",
    description="Implement user authentication",
    required_capability="code-generation.python",  # 按能力分发，不按 Agent 名称
    dependencies=["task-db-schema"],                # DAG 依赖
    constraints=TaskConstraints(
        max_retries=2,
        timeout_ms=300000,
        min_success_rate=0.85,
    ),
)
```

Task 状态机：
```
CREATED → READY → ASSIGNED → STARTED → COMPLETED
                    ↓                     ↓
                  (rejected)            FAILED → (retry) → READY
                                       CANCELLED
                                       TIMED_OUT
```

### 4.4 Capability（能力）

Agent 声明自己能做什么。Zelos 按能力分发，从不按 Agent 名称：

```python
CapabilityDeclaration(
    name="code-generation.python",      # 唯一能力标识（点分隔命名空间）
    version="1.0.0",                    # 语义化版本
    description="生成 Python 代码",
    qos={
        "max_latency_ms": 5000,
        "max_cost_per_call": 0.05,      # 每次调用成本
        "availability": 0.995,
    },
    tags=["python", "web", "enterprise"],
    capacity=10,                        # 最大并发数
)
```

### 4.5 Agent

Agent 是一个外部执行插件。它只知道：接收 Task → 执行 → 返回 Artifact → 退出。

Agent 不调度、不调用其他 Agent、不管内存、不知道工作流拓扑。

### 4.6 Artifact（产物）

Agent 执行 Task 后返回的结果。Artifact 是不可变的——创建后永不修改。如果 Agent 需要修正，会产生新的 Artifact。

### 4.7 Event（事件）

一切状态变化都表示为 Event。Event 是不可变的、仅追加的。所有 Event 通过 `correlation_id` 关联到同一个 Goal，通过 `causation_id` 形成因果链。

---

## 5. 快速上手

### 安装

```bash
pip install zelos-runtime
```

核心零外部依赖，纯 Python stdlib。这是设计哲学——Runtime 不应该绑死任何特定生态。

### 5 分钟跑起来

```python
from zelos.runtime import ZelosRuntime

# 1. 创建并启动 Runtime
rt = ZelosRuntime()
rt.start()

# 2. 注册一个 Agent
rt.add_agent(
    name="我的 Python 程序员",
    entrypoint="my_agent:CodeAgent",
    capabilities=[{"name": "code-generation.python", "version": "1.0.0"}],
)

# 3. 提交一个 Goal
goal = rt.submit_goal("写一个字符串反转函数")
print(f"Goal: {goal['goal_id'][:8]}... → {goal['status']}")

# 4. 查看状态
status = rt.get_goal_status(goal["goal_id"])
health = rt.get_health()
print(f"Runtime: {health['status']} v{health['version']}")

rt.shutdown()
```

### 用 zelos.yaml 配置

```yaml
# zelos.yaml
runtime:
  api:
    host: "0.0.0.0"
    port: 9876

plugins:
  - id: "llm-planner"
    type: "planner"
    entrypoint: "zelos.planner.LLMPlanner"
    config:
      provider: "openai"
      model: "deepseek-v4-flash"
      api_key: "${OPENAI_API_KEY}"
      base_url: "https://api.deepseek.com/v1"

  - id: "schema-verifier"
    type: "verifier"
    entrypoint: "zelos.verifier.SchemaVerifier"

  - id: "default-scoring"
    type: "scoring_strategy"
    entrypoint: "zelos.scheduler.DefaultScoringStrategy"
```

```python
rt = ZelosRuntime.from_yaml("zelos.yaml")
rt.start()
```

### 启动 Dashboard

```bash
python3 start.py
# 浏览器打开 http://127.0.0.1:9876
```

内建 Web UI，无需外部文件，实时展示 Goals、Agents、Tasks、Audit Log。

---

## 6. Runtime Kernel

Kernel 是 Zelos 的最小不可变核心。6 个组件，缺一不可——如果移除了它，多 Agent 编排就不再是 Zelos。

### 6.1 EventBus（事件总线）

进程内的发布/订阅系统。**所有组件通过它通信——永远不直接调用。**

```python
from zelos.event_bus import EventBus, Event

bus = EventBus(max_events=10000)

# 精确订阅
bus.subscribe("task.completed", lambda e: print(f"Task done: {e.payload}"))

# 模式匹配订阅
bus.subscribe_pattern("task.*", lambda e: print(f"Any task event: {e.event_type}"))

# 按 Goal 订阅
bus.subscribe_correlation("goal-g1", lambda e: process(e))

# 发布
bus.publish(Event(
    event_id="evt-001", event_type="task.completed",
    source="execution-engine", timestamp=time.time(),
    correlation_id="goal-g1", causation_id="evt-000",
    payload={"task_id": "task-1", "artifact_id": "art-1"},
))

# 重放
bus.replay_from(position=0, handler=process_function)
bus.replay_correlation("goal-g1", handler=process_function)
```

特性：
- 不可变事件（发布后不可修改）
- 幂等（相同 event_id 重复发布静默忽略）
- 环形缓冲区（max_events 限制内存）
- 1 MB 单事件上限
- Replay（按位置或 correlation_id）
- 持久化支持（PersistentEventStore + 任意 StorageBackend）

### 6.2 CapabilityRegistry（能力注册表）

Agent 的"搜索引擎"。按名称、标签、前缀、版本约束查询。

```python
from zelos.capability_registry import CapabilityRegistry

reg = CapabilityRegistry()
reg.register("agent-1", "CodeAgent", [
    {"name": "code-generation.python", "version": "1.0.0", "tags": ["python", "web"]},
    {"name": "code-review", "version": "1.0.0", "tags": ["security"]},
])

reg.find_by_name("code-generation.python")           # 精确名称
reg.find_by_prefix("code-generation")                 # 前缀匹配
reg.find_by_tag(["python", "web"])                    # 标签 AND
reg.find_providers_for("code-generation.python")      # 可用 Agent 列表
reg.find_by_name("code-generation.python", ">=1.0,<2.0")  # 版本约束

reg.mark_available("agent-1")     # 标记可用
reg.mark_unavailable("agent-1")   # 标记不可用（不会被调度）
reg.deprecate("agent-1", ...)     # 标记废弃（降低调度优先级）
```

### 6.3 TaskGraph（任务图引擎）

管理 Task 的 DAG 依赖关系和状态转换。

```python
from zelos.task_graph import TaskGraphEngine, Task, TaskStatus

tg = TaskGraphEngine()

t1 = Task(task_id="t1", plan_id="plan-1", description="设计 DB Schema",
          required_capability="design.db-schema")
t2 = Task(task_id="t2", plan_id="plan-1", description="实现 Auth 模块",
          required_capability="code-generation.python", dependencies=["t1"])

tg.add_task(t1)
tg.add_task(t2)

tg.transition("t1", TaskStatus.READY)
tg.transition("t1", TaskStatus.ASSIGNED)
tg.transition("t1", TaskStatus.STARTED)
tg.transition("t1", TaskStatus.COMPLETED)

# t1 完成 → t2 自动变为 READY
ready = tg.on_task_completed("t1")
print(ready)  # → ["t2"]

# 循环检测
tg.add_dependency("t2", "t1")  # → ValueError: cycle detected

# 动态修改
tg.add_task_dynamic(t3)        # 运行中插入新 Task
```

### 6.4 Scheduler（调度器）

5 阶段流水线：Sort → Filter → Score → Policy → Select

```python
from zelos.scheduler import Scheduler, DefaultScoringStrategy

sched = Scheduler(task_graph, capability_registry, scoring_strategy=DefaultScoringStrategy())

# 阶段 1: Sort — 按优先级排序
# 阶段 2: Filter — 11 个硬约束（能力匹配、版本兼容、Agent 存活、容量、预算、截止日期、标签、排除列表等）
candidates = sched._phase2_filter(task)  # 筛选可用 Agent
# 阶段 3: Score — 7 因子加权评分（可替换为自定义策略）
# 阶段 4: Policy — Allow / Reject / Delay / Retry
# 阶段 5: Select — 选择最高分 Agent
result = sched._schedule_one(task)
```

**自定义评分策略（竞价排名示例）：**

```python
class MarketplaceScoring(ScoringStrategy):
    def score(self, task, candidates):
        for c in candidates:
            quality = c.success_rate * 0.7
            price = 1.0 - min(c.cost_per_call / 0.50, 1.0)
            bid = min(c.metadata.get("bid", 0.0) / 0.10, 1.0)
            c.score = quality * 0.5 + price * 0.3 + bid * 0.2
        return sorted(candidates, key=lambda c: c.score, reverse=True)
```

### 6.5 ExecutionEngine（执行引擎）

Task 派发、心跳监控、超时控制。

```python
from zelos.execution_engine import ExecutionEngine

ee = ExecutionEngine(task_graph, event_bus)
ee.register_agent("agent-1", "CodeAgent", max_concurrent_tasks=5, heartbeat_interval_ms=30000)

ee.dispatch("task-1", "agent-1")           # 派发 Task
ee.heartbeat("agent-1")                    # Agent 心跳
ee.submit_result("task-1", "agent-1", {    # Agent 提交结果
    "status": "completed",
    "artifact": {"content_type": "application/json", "content": {...}},
})
ee.cancel_task("task-1")                   # 取消 Task
ee.start_monitor()                         # 启动超时/心跳监控线程
```

Agent 状态机：
```
registered → heartbeating → disconnected（心跳超时）
```

### 6.6 PluginLifecycleManager（插件生命周期管理器）

管理插件的加载顺序、依赖解析、健康检查、重启。

```python
from zelos.plugin_manager import PluginLifecycleManager

plm = PluginLifecycleManager()
manifests = plm.discover_from_config(plugin_configs)
instances = plm.load_all(manifests)  # 按拓扑序加载

plm.health_check("schema-verifier")  # 健康检查
plm.restart_plugin("llm-planner")    # 重启
plm.stop_plugin("llm-planner")       # 优雅停止
```

加载顺序（强制执行）：
```
storage → memory → policy → scoring_strategy → verifier → planner → adapter
```

---

## 7. Plugin 生态系统

### 7.1 Planner（规划器）

将自然语言 Goal 分解为 Task DAG。支持多种 LLM Provider。

```python
from zelos.planner import LLMPlanner, create_provider

# OpenAI
provider = create_provider({"provider": "openai", "model": "gpt-4o", "api_key": "sk-..."})

# Anthropic Claude
provider = create_provider({"provider": "anthropic", "model": "claude-opus-4-8", "api_key": "sk-ant-..."})

# Google Gemini
provider = create_provider({"provider": "google", "model": "gemini-2.5-pro", "api_key": "..."})

# DeepSeek（OpenAI 兼容）
provider = create_provider({"provider": "openai", "model": "deepseek-v4-flash",
                             "api_key": "sk-...", "base_url": "https://api.deepseek.com/v1"})

# Mock（测试用，返回固定 JSON）
provider = create_provider({"provider": "mock"})

planner = LLMPlanner({"provider": "mock"})
plan = planner.plan("Write a hello world function", goal_id="g1")
# 自动校验：DAG 无环、依赖引用有效、每个 Task 有 capability

# Replan — 某个 Task 失败后重新规划
new_plan = planner.replan(original_plan=plan, failed_task_id="task-3")
```

### 7.2 Verifier（验证器）

Agent 的每个 Artifact 必须通过验证关卡才能流向下游。

```python
from zelos.verifier import SchemaVerifier, VerificationGate, VerificationCriteria
from zelos.verifier_v2 import CodeReviewer, SecurityScanner

# Schema 验证
schema_v = SchemaVerifier()
result = schema_v.verify(
    {"name": "hello", "version": 1},
    VerificationCriteria(expected_output_schema={"type": "object", "required": ["name"]}),
)
print(result.verdict)  # → "passed"

# 代码审查
cr = CodeReviewer()
result = cr.verify("eval(user_input)", VerificationCriteria(options={"language": "python"}))
# → "failed" — 检测到 eval() 使用

# 安全扫描（SQL 注入、XSS、命令注入、不安全的反序列化、硬编码密钥）
ss = SecurityScanner()
result = ss.verify('"SELECT * FROM users WHERE id=" + user_id', VerificationCriteria())
# → "failed" — SQL 注入

# 四级验证链
gate = VerificationGate()
gate.add_verifier(SchemaVerifier())
gate.add_verifier(CodeReviewer())
gate.add_verifier(SecurityScanner())
gate.add_verifier(FactChecker())
result = gate.verify(artifact, criteria)
# 全部通过 → accepted。任意一个失败 → 短路拒绝。
```

### 7.3 Policy（策略引擎）

策略只做 Allow / Reject / Delay / Retry——从不改变业务逻辑。

```python
from zelos.policy import CostLimitPolicy, AllowlistPolicy, CompositePolicy

cost = CostLimitPolicy({"max_cost_per_goal": 100})
cost.evaluate({"goal_id": "g1", "task_cost": 50})  # → "allow"

allow = AllowlistPolicy({"allowlist_agents": ["agent-coder"]})
allow.evaluate({"agent_id": "unknown-agent"})  # → "reject"

combo = CompositePolicy({"policies": [cost, allow]})
# 顺序执行，首次 reject 即短路
```

### 7.4 Memory（记忆架构）

6 层隔离的记忆系统。**Memory 属于 Runtime，不属于 Agent。**

```python
from zelos.memory import InMemoryMemoryProvider

mem = InMemoryMemoryProvider(max_entries_per_layer=5000, ttl_seconds=3600)

# 6 层记忆，独立生命周期
mem.store("session", "goal-1", {"goal": "...", "deadline": "2026-08-01"})      # Goal 生命周期
mem.store("project", "coding-style", {"language": "python"})                     # 持久
mem.store("user", "preferences", {"model": "claude"})                            # 持久
mem.store("knowledge", "api-docs", {"endpoint": "/api/v1"})                      # 持久，跨用户
mem.store("execution", "task-1-cache", {"intermediate": "data"})                 # Task 生命周期
mem.store("skill", "code-review-template", {"checklist": [...]})                 # 持久，可复用

# Context Assembly — Task 派发前自动组装上下文
from zelos.memory import ContextAssembler
ctx = ContextAssembler(mem).assemble(task_id="task-1", goal_id="goal-1")
# → 聚合 session/project/user/knowledge/execution/skill 层的相关条目
```

### 7.5 Storage（存储后端）

一行配置切换存储后端，代码无需改动。

```python
from zelos.storage import create_storage_backend

backend = create_storage_backend({"type": "postgresql", "url": "postgresql://..."})
backend.connect()
backend.append("task-events", [{"event_id": "e1"}])
events = backend.read("task-events", 0, 100)
backend.set_state("goal-g1", {"status": "executing"})
backend.create_snapshot("goal-g1", events_position=5, state={...})
```

支持的后端：`memory` / `redis` / `postgresql` / `mysql`

---

## 8. 分布式与生产部署

### 8.1 分布式 Runtime

```python
from zelos.distributed import LeaderElection, WorkStealing, NodeRegistry, ClusterNode

# Leader 选举（Bully 算法——最小 node_id 当选）
le = LeaderElection(node_id="node-alpha")
le.register_peer("node-bravo")
le.start()
print(le.get_leader_id())  # → "node-alpha"

# 工作窃取（忙节点的 READY 任务被空闲节点窃走）
ws_a = WorkStealing(node_id="node-a")
ws_b = WorkStealing(node_id="node-b")
ws_a.enqueue_task("t1", capability="code")
stolen = ws_b.steal_from(ws_a, max_count=3)  # → 窃走 t1

# 节点注册中心（健康监控 + 能力查询）
reg = NodeRegistry()
reg.register(ClusterNode(node_id="n1", host="10.0.0.1", port=9001, capabilities=["code"]))
reg.find_by_capability("code")  # → [n1]
reg.detect_dead_nodes(timeout_seconds=60)  # → 心跳过期的节点列表
```

### 8.2 多节点集群部署

```yaml
# zelos-node-1.yaml
distributed:
  enabled: true
  node_id: "node-1"
  peers: ["10.0.0.1:9877", "10.0.0.2:9877", "10.0.0.3:9877"]

coordination:
  type: etcd
  endpoints: "10.0.0.1:2379"

messaging:
  type: nats
  servers: ["nats://10.0.0.1:4222"]
```

```bash
python3 start.py --config zelos-node-1.yaml &
python3 start.py --config zelos-node-2.yaml &
python3 start.py --config zelos-node-3.yaml &

curl http://10.0.0.1:9876/api/v1/cluster
# → {"is_leader": true, "peers": ["node-1","node-2","node-3"], "healthy": 3}
```

### 8.3 容器部署

```bash
make build        # 构建 Docker 镜像（80 MB）
make run          # Docker Compose 一键启动
make run-storage  # 附带 Redis
```

### 8.4 热重载

零停机升级插件。支持 4 种策略：

| 策略 | 行为 | 适用场景 |
|------|------|---------|
| ROLLING | 逐个替换实例 | 默认安全升级 |
| BLUE_GREEN | 先启新版，保留旧版，再切流量 | 大版本升级 |
| CANARY | X% 流量到新版 | 灰度验证 |
| INSTANT | 立即切换 | 热修复 |

---

## 9. 安全与合规

### 9.1 RBAC 权限控制

```python
from zelos.security import AccessControl

ac = AccessControl()
# 4 个内置角色：
#   admin:    * （全部操作）
#   operator: goal.*, task.*, agent.read, plugin.*
#   agent:    task.execute, agent.heartbeat, artifact.create
#   viewer:   goal.read, task.read, agent.read, metrics.read

ac.check("agent", "task.execute")   # → True
ac.check("agent", "goal.submit")    # → False
ac.check("admin", "anything")       # → True（wildcard）
ac.check("operator", "task.create") # → True（task.* prefix match）
```

### 9.2 审计日志

```python
from zelos.security import AuditLogger

logger = AuditLogger(max_events=100000)
logger.log("admin", "goal.submit", "goal-g1", result="allow", detail="Submitted by user")
logger.log("agent-1", "task.execute", "task-t1", result="allow", detail="Executed in 340ms")

# 多字段查询
events = logger.query(actor="agent-1", action="task.execute")
events = logger.query(resource="goal-g1", time_start=1721654400, time_end=1721655000)

# 导出
count = logger.export_json_file("/var/log/zelos/audit.json")
```

### 9.3 API Key 管理 + 异常检测

```python
from zelos.security import APIKeyManager

mgr = APIKeyManager(max_failures=10, failure_window_seconds=60, auto_revoke=True)
key = mgr.generate_key("admin", "production-key")  # → "zelos_<128 hex>"
mgr.validate(key)    # → {"role": "admin", ...}
mgr.revoke(key)      # → True

# 暴力破解防护：10 次失败 → 60 秒内 → 自动吊销
fail_count = mgr.get_failure_count(key)
```

### 9.4 mTLS

```python
from zelos.security import TLSConfig

tls = TLSConfig(
    cert_file="/etc/zelos/server.pem",
    key_file="/etc/zelos/server.key",
    ca_file="/etc/zelos/ca.pem",
    require_client_cert=True,
)

adapter = HTTPAdapter(rt, host="0.0.0.0", port=8443, tls_config=tls)
adapter.start()
# 现在只接受持有有效客户端证书的连接
```

---

## 10. 多租户

```python
from zelos.multi_tenancy import TenantManager, ResourceQuota

tm = TenantManager()
tm.register_tenant("tenant-finance", "Finance Dept", quotas=ResourceQuota(
    max_goals=50, max_tasks=200, max_agents=10, budget_per_goal=100
))
tm.register_tenant("tenant-eng", "Engineering", quotas=ResourceQuota(
    max_goals=200, max_tasks=1000, max_agents=50
))

# 租户隔离：Finance 看不到 Engineering 的 Goals/Agents
ns_fin = tm.get_namespace("tenant-finance")
ns_fin.add_goal("goal-1")
ns_fin.add_goal("goal-2")
# 超出配额自动拒绝

# 启停控制
tm.deactivate_tenant("tenant-finance")   # 暂停所有操作
tm.activate_tenant("tenant-finance")     # 恢复
```

---

## 11. 可观测性

### 11.1 Prometheus Metrics

```bash
curl http://localhost:9876/metrics
```

```
# HELP zelos_goals_active Number of active goals
# TYPE zelos_goals_active gauge
zelos_goals_active 3

# HELP zelos_tasks_completed_total Total completed tasks
# TYPE zelos_tasks_completed_total counter
zelos_tasks_completed_total 1042

# HELP zelos_agents_connected Connected agents
# TYPE zelos_agents_connected gauge
zelos_agents_connected 12
```

### 11.2 OpenTelemetry / Jaeger

```python
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

exporter = OTLPSpanExporter(endpoint="http://localhost:4318/v1/traces")
# 创建 Span → 导出到 Jaeger → http://localhost:16686 可视化
```

### 11.3 Grafana Dashboard

`deploy/grafana/zelos-dashboard.json` — 导入即可。

### 11.4 K8s 探针

```
GET /live   → {"status": "alive"}     # 存活探针
GET /ready  → {"status": "ready"}     # 就绪探针
```

---

## 12. SDK 参考

### 12.1 Python SDK (`zelos_sdk`)

```python
from zelos_sdk import BaseAgent, CapabilityDeclaration, ZelosClient, Task

class MyAgent(BaseAgent):
    def declare_capabilities(self):
        return [CapabilityDeclaration(name="code-generation.python", version="1.0.0")]

    def execute(self, task: Task):
        return {"status": "completed", "artifact": {"content_type": "text/plain", "content": "result"}}

# 远程客户端
client = ZelosClient("http://localhost:9876", "zk-client-dev")
client.submit_goal("Build something")
client.health()
```

### 12.2 TypeScript SDK (`@zelos/sdk`)

```typescript
import { ZelosClient, BaseAgent } from "@zelos/sdk";

const client = new ZelosClient("http://localhost:9876", "zk-client-dev");
await client.health();

class MyAgent extends BaseAgent {
  declareCapabilities() { return [{ name: "code-generation.python", version: "1.0.0" }]; }
  async execute(task) { return { status: "completed", artifact: { contentType: "text/plain", content: "done" } }; }
}
```

### 12.3 Go SDK (`zelos-go`)

```go
import "github.com/AI-Zelos/zelos-go/client"

c := client.New("http://localhost:9876", "zk-client-dev")
health, _ := c.Health()
goal, _ := c.SubmitGoal("Build a landing page", "high")
```

---

## 13. API 参考

所有 API 返回 JSON，通过 `Authorization: Bearer <key>` 认证。

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/goals` | 提交 Goal |
| GET | `/api/v1/goals` | 列出所有 Goal |
| GET | `/api/v1/goals/{id}` | 获取 Goal 状态 |
| DELETE | `/api/v1/goals/{id}` | 取消 Goal |
| POST | `/api/v1/agents` | 注册 Agent |
| GET | `/api/v1/agents` | 列出 Agent |
| GET | `/api/v1/agents/{id}` | 获取 Agent 详情 |
| POST | `/api/v1/agents/{id}/heartbeat` | Agent 心跳 |
| POST | `/api/v1/agents/{id}/tasks/{tid}/result` | 提交 Task 结果 |
| GET | `/api/v1/health` | Runtime 健康检查 |
| GET | `/api/v1/metrics` | Runtime 指标 |
| GET | `/api/v1/audit` | 审计日志 |
| GET | `/api/v1/tenants` | 租户列表 |
| GET | `/api/v1/cluster` | 集群状态 |
| GET | `/api/v1/approvals/pending` | 待审批项 |
| GET | `/live` | K8s 存活探针 |
| GET | `/ready` | K8s 就绪探针 |
| GET | `/metrics` | Prometheus 指标 |

---

## 14. 部署指南

### 开发环境

```bash
pip install zelos-runtime
python3 start.py
```

### 生产环境（单节点）

```bash
pip install zelos-runtime[dev]
# 配置 zelos.yaml → python3 start.py --config zelos.yaml
```

### 生产环境（Docker）

```bash
docker build -t zelos:0.7.0 .
docker compose up -d
```

### 生产环境（Kubernetes）

```yaml
# deploy/k8s/deployment.yaml
livenessProbe:
  httpGet: { path: /live, port: 9876 }
readinessProbe:
  httpGet: { path: /ready, port: 9876 }
```

### 生产环境（多节点集群）

见 [8.2 多节点集群部署](#82-多节点集群部署)

---

## 15. 常见问题

### Q: Zelos 和 LangGraph 有什么区别？

LangGraph 是 Agent 构建工具包——帮你定义 Agent 内部的图结构。Zelos 是 Agent 编排 Runtime——帮你管理多个独立 Agent 之间的调度、验证、审计。两者是互补的：你可以用 LangGraph 构建 Agent，用 Zelos 编排这些 Agent。

### Q: Zelos 和 Temporal 有什么区别？

Temporal 管理确定性工作流（纯代码，可回放）。Zelos 管理非确定性 Agent（LLM 调用、浏览器自动化——天然不确定）。Temporal 要求工作流代码是确定性的，Zelos 明确接受 Agent 的不确定性，通过三权分立（Planner ≠ Scheduler ≠ Verifier）来治理。

### Q: Zelos 依赖哪些外部服务？

**核心 Runtime 零依赖。** 生产部署推荐：
- PostgreSQL / Redis（事件持久化）
- etcd（多节点领导者选举）
- NATS（跨节点消息传递）
- Jaeger（分布式追踪）

全部可选——单节点开发模式不需要任何外部服务。

### Q: Agent 必须用 Python 写吗？

不。Agent 是外部进程，任何语言都可以。只要通过 HTTP API 注册、心跳、执行、提交结果即可。Python/TypeScript/Go SDK 只是提供了便利的封装。

### Q: 能支持多少个 Agent？

在单节点上测试过 500 个 Agent 同时注册，Capability 查询 < 1ms。多节点通过 etcd + NATS 横向扩展。

### Q: 怎么保证 Agent 不互相调用？

**架构层面保证。** Agent 只知道 Runtime，不知道其他 Agent 的存在。它收到的 Task 不包含任何其他 Agent 的信息。Agent 无法直接与其他 Agent 通信——所有通信必须通过 EventBus。

### Q: Planner 一定要用 LLM 吗？

不。Planner 是一个可替换的插件。你可以实现一个基于模板的 Planner，或者基于规则引擎的 Planner。LLMPlanner 只是默认实现。

---

> 📄 [English User Manual →](zelos-manual.html) | [API Reference →](zelos.html) | [GitHub →](https://github.com/AI-Zelos/zelos)
