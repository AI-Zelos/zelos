# Zelos 全面技术手册

> **Open Multi-Agent Orchestration Runtime**
> 一个完整的、生产就绪的多 Agent 编排运行时。不是框架，是基础设施。

---

## 目录

1. [项目简介](#1)
2. [为什么存在](#2)
3. [什么时候使用](#3)
4. [核心概念](#4)
   - [4.1 Goal](#41-goal)
   - [4.2 Execution Plan](#42-execution-plan)
   - [4.3 Task](#43-task)
   - [4.4 Capability](#44-capability)
   - [4.5 Agent](#45-agent)
   - [4.6 Artifact](#46-artifact)
   - [4.7 Event](#47-event)
5. [快速上手](#5)
6. [Runtime Kernel（内核）](#6)
7. [Plugin 生态系统](#7)
8. [分布式与生产部署](#8)
9. [安全与合规](#9)
10. [多租户](#10)
11. [可观测性](#11)
12. [SDK 参考](#12)
13. [API 参考](#13)
14. [部署指南](#14)
15. [常见问题](#15)
16. [v0.9.0 新特性：Change Evidence Package](#16)
   - [16.1 Execution Trace](#161-execution-trace)
   - [16.2 Evidence Collection](#162-evidence-collection)
   - [16.3 Confidence Scoring](#163-confidence-scoring)
   - [16.4 Execution Report](#164-execution-report)
   - [16.5 Policy Gate v2](#165-policy-gate-v2)
   - [16.6 Intent Specification](#166-intent-specification)
   - [16.7 Architecture Delta](#167-architecture-delta)

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
| 版本 | v1.0.0 |
| Phases | 0–10 全部完成 |
| 源码模块 | 37 个 |
| 自动化测试 | 151 个（151 passed） |
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
docker build -t zelos:0.9.0 .
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

## 16. v0.9.0 新特性：Change Evidence Package

v0.9.0 将 Zelos 从**执行引擎**升级为**治理平台**。核心设计理念来自一个根本问题：

> **"Agent 时代，AI 生成的代码还应该让人来逐行审查吗？"**

答案是不应该。当 Agent 每小时可以产出数万行代码时，Code Review 已经超出了人的带宽极限。人应该审查的是三件事：

1. **Intent（意图）** — 这次变更到底要达成什么目标？
2. **Evidence（证据）** — 凭什么说目标达成了？（测试、Benchmark、安全扫描……）
3. **Confidence（置信度）** — 综合评估，这次变更值不值得被接受？

v0.9.0 的所有特性都围绕这个模型构建。

---

### 16.1 Execution Trace（执行链路追溯）

**背景：** v0.8.1 只能查询 Goal 的当前状态快照，无法回溯"每一步发生了什么、输入是什么、输出是什么"。v0.9.0 新增了完整的 Task 生命周期事件，并在 EventBus 中持久化。

#### API

```python
ExecutionTrace runtime.get_goal_trace(
    goal_id: str,
    include_artifacts: bool = False,   # 是否加载输入/输出
    limit: int = 50,                   # 分页大小
    offset: int = 0,                   # 分页偏移
) -> ExecutionTrace | None
```

#### 返回值：ExecutionTrace

| 字段 | 类型 | 说明 |
|------|------|------|
| `goal_id` | str | Goal ID |
| `goal_description` | str | Goal 描述 |
| `status` | str | 当前状态 |
| `total_duration_ms` | float | 总执行耗时（毫秒） |
| `tasks` | list[TaskTrace] | 每个 Task 的执行链路 |
| `total_tasks` | int | 总 Task 数（分页前） |

#### TaskTrace 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `task_id` | str | Task ID |
| `description` | str | Task 描述 |
| `required_capability` | str | 所需能力 |
| `agent_id` | str \| None | 分配的 Agent ID |
| `agent_name` | str \| None | Agent 名称 |
| `status` | str | 当前状态 |
| `attempt` | int | 第几次尝试 |
| `timeline` | list[TraceEvent] | 时间线事件列表 |
| `input_context` | dict \| None | 输入上下文（include_artifacts=True 时加载） |
| `output_artifact` | dict \| None | 输出产物（include_artifacts=True 时加载） |
| `error` | dict \| None | 错误信息（失败时） |

#### TraceEvent 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `event_type` | str | 事件类型：task.created / task.ready / task.assigned / task.started / task.completed / task.failed / task.retry_scheduled |
| `timestamp` | float | Unix 时间戳 |
| `payload` | dict | 事件负载 |

#### 使用示例

```python
# 基础查询
trace = runtime.get_goal_trace(goal_id)
print(f"Goal: {trace.goal_description}")
print(f"Status: {trace.status}, Duration: {trace.total_duration_ms:.0f}ms")
print(f"Tasks: {trace.total_tasks}")

for task in trace.tasks:
    print(f"\n📋 {task.task_id}: {task.description}")
    print(f"   Agent: {task.agent_name or 'unassigned'}")
    print(f"   Status: {task.status}, Attempt: {task.attempt}")
    for event in task.timeline:
        print(f"   ⏱ {event.event_type} @ {event.timestamp}")

# 包含输入/输出（大 payload 按需加载）
trace = runtime.get_goal_trace(goal_id, include_artifacts=True)
for task in trace.tasks:
    if task.input_context:
        print(f"Input: {task.input_context}")
    if task.output_artifact:
        print(f"Output: {task.output_artifact}")

# 分页查询（大数据量场景）
page1 = runtime.get_goal_trace(goal_id, limit=20, offset=0)
page2 = runtime.get_goal_trace(goal_id, limit=20, offset=20)
```

#### 大数据量设计

- `input_context` 和 `output_artifact` 默认不加载（`None`），传 `include_artifacts=True` 才加载
- 大 payload（>100KB）在事件中只存 `content_ref` 引用，不存内联数据
- 支持 `limit/offset` 分页，避免一次加载全部 Task
- 事件按 `correlation_id == plan_id` 过滤，一次 O(n) 遍历完成归并

---

### 16.2 Evidence Collection（证据收集）

**背景：** v0.8.1 的 Agent 只返回一个 Artifact（"做完了"），但没有人知道"做得好不好"。v0.9.0 引入了类型化的 Evidence 输出——Agent 必须附带证据，Runtime 负责收集和归并。

#### Evidence 数据结构

```python
@dataclass
class Evidence:
    type: str           # 证据类型：test_result | benchmark | security_scan | api_diff | canary | code_review | custom
    tool: str           # 产生证据的工具：pytest | wrk | bandit | openapi-diff | custom-tool
    result: str         # PASS | FAIL | WARN | SKIP
    data: dict          # 详细数据（passed/failed、TPS 数值、漏洞数等）
    summary: str        # 人类可读的一行摘要
    timestamp: float    # 收集时间戳
```

#### Evidence 类型约定

| type | 含义 | 推荐 tool | data 示例 |
|------|------|-----------|-----------|
| `test_result` | 测试结果 | pytest, jest, go-test | `{"passed": 47, "failed": 0, "coverage_pct": 89}` |
| `benchmark` | 性能基准 | wrk, k6, locust | `{"metric": "tps", "baseline": 850, "actual": 1120}` |
| `security_scan` | 安全扫描 | bandit, trivy, snyk | `{"issues": 0, "severity_high": 0}` |
| `api_diff` | API 变更 | openapi-diff | `{"breaking_changes": 0, "new_endpoints": 2}` |
| `canary` | 金丝雀发布 | custom | `{"duration_s": 300, "error_rate": 0.001}` |
| `code_review` | 代码审查 | sonarqube, codeql | `{"issues": 3, "severity": "minor"}` |
| `custom` | 自定义 | 任意 | 任意 |

#### EvidenceBag（证据袋）

Runtime 自动收集所有 Task 返回的 Evidence，归并成 EvidenceBag：

```python
@dataclass
class EvidenceBag:
    goal_id: str
    items: list[Evidence]                    # 所有证据项
    summary: dict[str, EvidenceSummary]      # 按类型汇总
    all_pass: bool                           # 是否全部 PASS
    failed_items: list[Evidence]             # 失败的证据项
```

#### EvidenceSummary 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | str | 证据类型 |
| `total` | int | 该类型总数 |
| `passed` | int | 通过数 |
| `failed` | int | 失败数 |
| `warned` | int | 警告数 |
| `skipped` | int | 跳过数 |

#### 使用示例

```python
from zelos.evidence import Evidence

# 方式一：Agent 通过 ExecutionResult 返回 Evidence
def execute(self, task):
    return ExecutionResult(
        status="completed",
        artifact=Artifact(content=result),
        evidence=[
            Evidence(type="test_result", tool="pytest", result="PASS",
                     data={"passed": 47, "failed": 0, "coverage_pct": 89},
                     summary="47/47 tests passed"),
            Evidence(type="security_scan", tool="bandit", result="PASS",
                     data={"issues": 0},
                     summary="No security issues found"),
        ],
    )

# 方式二：通过 Runtime API 手动添加 Evidence
from zelos.evidence import Evidence
runtime.add_evidence(goal_id, Evidence(
    type="benchmark", tool="wrk", result="PASS",
    data={"tps": 1120, "p99_ms": 45, "baseline_tps": 850},
    summary="TPS improved 31.8% (850→1120)"
))

# 查询归并结果
report = runtime.get_execution_report(goal_id)
bag = report.evidence_bag
print(f"All pass: {bag.all_pass}")          # True/False
print(f"Failed: {len(bag.failed_items)}")   # 失败数量
for ev_type, summary in bag.summary.items():
    print(f"  {ev_type}: {summary.passed}/{summary.total} passed")
```

#### EvidenceBag 特性

- **自动聚合**：相同 type 的 Evidence 自动汇总
- **增量添加**：`add_evidence()` 支持运行时动态追加，O(1) 更新汇总
- **批量优化**：100 条 Evidence 聚合在毫秒级完成
- **all_pass 判断**：任一 `result == "FAIL"` → False；空 EvidenceBag → True（无失败 = 通过）

---

### 16.3 Confidence Scoring（置信度评分）

**背景：** 即使所有 Task 都完成了，人也需要判断"这次变更质量怎么样？敢不敢上线？"ConfidenceScorer 基于 Evidence 给出 0.0-1.0 的客观评分。

#### 插件接口

```python
class ConfidenceScorer(ABC):
    def score(self, evidence: EvidenceBag, arch_delta: ArchDelta | None = None) -> ConfidenceResult:
        """计算置信度分数"""
```

#### WeightedConfidenceScorer（默认实现）

六因子加权评分引擎：

```python
scorer = WeightedConfidenceScorer(
    weights={
        "test_pass": 0.30,      # 测试通过率
        "benchmark": 0.15,      # 性能基准
        "security": 0.20,       # 安全扫描
        "api_compat": 0.10,     # API 兼容性
        "code_review": 0.10,    # 代码审查
        "canary": 0.15,         # 金丝雀发布
    },
    thresholds={
        "auto_approve": 0.95,   # >= 0.95 自动批准
        "require_human": 0.70,  # < 0.70 强制人审
        "auto_reject": 0.40,    # < 0.40 自动拒绝
    }
)
```

#### 评分逻辑

每个因子的分数 = 该类型中 `PASS` 的比例（0.0-1.0），乘以权重。然后按**实际收集到的证据类型**做归一化。

例如：只收集了 test_result（全 PASS）和 security_scan（全 PASS），没有 benchmark：
- test_pass: 1.0 × 0.30 = 0.30
- security: 1.0 × 0.20 = 0.20
- benchmark: 无数据，不计入
- active_weight = 0.30 + 0.20 = 0.50
- score = 0.50 / 0.50 = **1.0**

如果 security_scan 有一条 FAIL：
- test_pass: 1.0 × 0.30 = 0.30
- security: 0.0 × 0.20 = 0.00
- active_weight = 0.50
- score = 0.30 / 0.50 = **0.60**

#### Benchmark 特殊逻辑

Benchmark 类型会额外检查性能回归：如果 `actual < baseline × 0.9`（下降 >10%），即使 result="PASS" 也视为 0 分。

#### ConfidenceResult 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `score` | float | 0.0-1.0 置信度分数 |
| `breakdown` | dict | 各项得分明细 `{"test_pass": 0.30, "security": 0.20, ...}` |
| `recommendation` | str | "approve" / "reject" / "need_human" |
| `reasoning` | str | 人类可读的解释 |

#### 自定义评分器

```python
from zelos.confidence import ConfidenceScorer, ConfidenceResult

class MyScorer(ConfidenceScorer):
    def score(self, evidence, arch_delta=None):
        # 自定义评分逻辑
        all_pass = evidence.all_pass
        score = 0.8 if all_pass else 0.3
        return ConfidenceResult(
            score=score,
            recommendation="approve" if score > 0.7 else "need_human",
            reasoning="My custom logic"
        )

# 通过 zelos.yaml 配置
# plugins:
#   - id: "my-scorer"
#     type: "confidence_scorer"
#     entrypoint: "my_package.MyScorer"
```

---

### 16.4 Execution Report（变更证据包）

**背景：** v0.9.0 的核心交付物。REQ-01 到 REQ-08 的所有能力最终汇聚到 ExecutionReport 中——一份结构化报告，让人在不看代码的情况下做出批准/拒绝决策。

#### API

```python
ExecutionReport runtime.get_execution_report(goal_id: str) -> ExecutionReport | None
```

#### ExecutionReport 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `goal_id` | str | Goal ID |
| `status` | str | Goal 状态 |
| `intent` | IntentSpec \| None | 结构化意图 |
| `intent_confirmed` | bool | 意图是否已经人确认 |
| `architecture_delta` | ArchDelta \| None | 架构影响分析 |
| `trace` | ExecutionTrace | 完整执行链路 |
| `evidence_bag` | EvidenceBag | 证据袋 |
| `confidence` | ConfidenceResult | 置信度评分 |
| `risk_level` | str | 风险等级：low / medium / high / critical |
| `rollback_plan` | RollbackPlan \| None | 回滚方案 |
| `changed_files` | int | 变更文件数 |
| `total_duration_ms` | float | 总耗时 |

#### RollbackPlan 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `strategy` | str | 回滚策略：event_sourcing_replay / manual / none |
| `restore_to_event_position` | int \| None | 恢复到的事件位置 |
| `estimated_downtime_s` | float | 预计停机时间（秒） |
| `steps` | list[str] | 回滚步骤 |

#### 完整使用示例

```python
report = runtime.get_execution_report(goal_id)

# ── 顶层概览 ──
print(f"Goal: {report.goal_id}")
print(f"Status: {report.status}, Duration: {report.total_duration_ms:.0f}ms")
print(f"Risk: {report.risk_level}")
print(f"Changed Files: {report.changed_files}")

# ── Intent ──
if report.intent:
    print(f"\n📝 Intent: {report.intent.description}")
    print(f"   Success Criteria: {report.intent.success_criteria}")
    print(f"   Constraints: {report.intent.constraints}")

# ── Architecture Delta ──
if report.architecture_delta:
    ad = report.architecture_delta
    print(f"\n🏗️ Architecture Delta:")
    print(f"   Modified: {ad.modified_modules}")
    print(f"   New Deps: {ad.new_dependencies}")
    print(f"   API Changes: {len(ad.api_changes)}")
    for a in ad.api_changes:
        print(f"     {a.change_type} {a.endpoint} ({a.compatibility})")
    print(f"   Risk: {ad.risk_level}")
    print(f"   Why: {ad.explanation}")

# ── Evidence ──
bag = report.evidence_bag
print(f"\n📊 Evidence: all_pass={bag.all_pass}")
for ev_type, summary in bag.summary.items():
    print(f"   {ev_type}: {summary.passed}/{summary.total} ({summary.failed} failed)")

# ── Confidence ──
c = report.confidence
print(f"\n🎯 Confidence: {c.score:.0%}")
print(f"   Recommendation: {c.recommendation}")
print(f"   Breakdown: {c.breakdown}")

# ── Decision ──
if c.recommendation == "approve":
    print(f"\n✅ AUTO-APPROVED: {c.reasoning}")
elif c.recommendation == "reject":
    print(f"\n❌ AUTO-REJECTED: {c.reasoning}")
else:
    print(f"\n🤔 NEEDS HUMAN: {c.reasoning}")

# ── Rollback ──
if report.rollback_plan:
    rp = report.rollback_plan
    print(f"\n🔄 Rollback: {rp.strategy}")
    if rp.restore_to_event_position is not None:
        print(f"   Restore to event #{rp.restore_to_event_position}")
    print(f"   Downtime: ~{rp.estimated_downtime_s}s")
```

#### 序列化

```python
# JSON 序列化
import json
data = json.dumps(report.to_dict(), indent=2, default=str)

# 存储到文件或发送到外部系统
with open(f"report-{goal_id}.json", "w") as f:
    json.dump(report.to_dict(), f, indent=2, default=str)
```

---

### 16.5 Policy Gate v2（证据驱动自动决策）

**背景：** v0.8.1 的 Policy 只能做 CostLimit / RateLimit / Allowlist（执行前的过滤）。v0.9.0 的 Policy Gate v2 是基于**执行后的证据**做决策——要不要批准这次变更？

#### 插件接口

```python
class PolicyGate(ABC):
    def evaluate(self, report: ExecutionReport) -> GateDecision:
        """评估 ExecutionReport，输出决策"""
```

#### GateDecision 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `action` | str | auto_approve / auto_reject / require_human |
| `reason` | str | 决策理由 |
| `required_approvers` | list[str] | 需要审批的人（action=require_human 时） |

#### EvidenceBasedPolicyGate（默认实现）

按优先级依次评估 5 条规则，命中即返回：

| 优先级 | 条件 | 动作 |
|--------|------|------|
| 1 | risk_level == "critical" | require_human，approvers=["architect", "security-lead"] |
| 2 | evidence 有 FAIL | require_human，reason="Evidence has failures" |
| 3 | confidence >= 0.95 AND risk == "low" | auto_approve |
| 4 | confidence >= 0.90 AND risk in ("low", "medium") | auto_approve |
| 5 | confidence < 0.40 | auto_reject |
| default | 以上都不匹配 | require_human |

#### 执行流程

```
ExecutionReport 生成
    ↓
PolicyGate.evaluate(report)
    ↓
GateDecision
    ├── auto_approve → 自动通过
    ├── auto_reject  → 自动拒绝
    └── require_human → 创建 HITL 审批请求
```

#### 使用示例

```python
from zelos.policy_gate import EvidenceBasedPolicyGate

gate = EvidenceBasedPolicyGate()

# 手动评估
report = runtime.get_execution_report(goal_id)
decision = gate.evaluate(report)
print(f"Decision: {decision.action}")
print(f"Reason: {decision.reason}")
if decision.required_approvers:
    print(f"Approvers needed: {decision.required_approvers}")
```

---

### 16.6 Intent Specification（意图规格化）

**背景：** 当前 `submit_goal(description="实现登录")` 太自由，Agent 可能理解偏了。IntentSpec 在 Agent 动手之前，让人和 Agent 对"要做什么、成功标准是什么"达成共识。

#### IntentSpec 字段

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `description` | str | (必填) | 自然语言描述 |
| `success_criteria` | list[str] | [] | 可验证的成功标准 |
| `constraints` | list[str] | [] | 约束条件 |
| `scope` | str | "auto" | 影响范围：auto / single_module / multi_module / system_wide |
| `rollback_on_failure` | bool | True | 失败时是否自动回滚 |

#### 使用示例

```python
from zelos.execution_report import IntentSpec

# 带 Intent 的 Goal 提交
intent = IntentSpec(
    description="实现 OAuth2 第三方登录",
    success_criteria=[
        "用户可以使用 Google 账号登录",
        "用户可以使用 GitHub 账号登录",
        "Token 24 小时后自动过期",
        "刷新 Token 功能正常",
    ],
    constraints=[
        "不破坏现有的用户名/密码登录",
        "使用标准的 OAuth2.0 协议",
        "不在前端存储 client_secret",
        "新增依赖必须经过安全审查",
    ],
    scope="single_module",
    rollback_on_failure=True,
)

result = runtime.submit_goal(
    "OAuth2 login",     # 简短描述（向后兼容）
    intent=intent,      # 结构化意图（v0.9.0）
    priority="high",
    budget=50.0,
)

# 在 ExecutionReport 中查看
report = runtime.get_execution_report(result["goal_id"])
print(report.intent.description)
print(report.intent.success_criteria)
print(report.intent_confirmed)  # 是否被人确认
```

#### 向后兼容

`intent` 参数为可选——不传则保持旧行为，完全兼容 v0.8.x 代码：

```python
# 仍然可以这样用
runtime.submit_goal("简单任务")
```

---

### 16.7 Architecture Delta（架构影响分析）

**背景：** Planner 以前只输出 Task 列表，不输出"改了哪里"。v0.9.0 让 Planner 自动推断架构影响，人一眼就能看出变更范围。

#### ArchDelta 字段

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `modified_modules` | list[str] | [] | 修改的模块/服务名 |
| `new_dependencies` | list[str] | [] | 新增的依赖（含版本号） |
| `removed_dependencies` | list[str] | [] | 删除的依赖 |
| `api_changes` | list[APIChange] | [] | API 变更列表 |
| `data_model_changes` | list[str] | [] | 数据模型变更 |
| `risk_level` | str | "unknown" | 风险等级 |
| `explanation` | str | "" | 人类可读的解释 |

#### APIChange 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `endpoint` | str | API 端点（如 "POST /auth/oauth"） |
| `change_type` | str | new / modified / deprecated / removed |
| `compatibility` | str | additive / backward_compatible / breaking |

#### 工作方式

LLM Planner 在同一个 prompt 里输出 `architecture_delta` 字段。`_parse_response` 自动解析。如果 LLM 没输出这个字段（旧版 prompt 或不支持的模型），`ArchDelta.risk_level` 基于 confidence score 自动推断。

#### Planner prompt 中新增的 JSON schema：

```json
{
  "architecture_delta": {
    "modified_modules": ["auth-service"],
    "new_dependencies": ["oauthlib==3.2.0"],
    "removed_dependencies": [],
    "api_changes": [
      {"endpoint": "POST /auth/oauth", "change_type": "new", "compatibility": "additive"}
    ],
    "data_model_changes": ["users.add(oauth_provider)"],
    "risk_level": "medium",
    "explanation": "标准 OAuth2 增量，隔离在 auth 模块，不影响现有登录流程"
  }
}
```

#### 使用示例

```python
report = runtime.get_execution_report(goal_id)
ad = report.architecture_delta

if ad.risk_level == "critical":
    print("⚠️ 高风险变更，需要额外审批！")
elif ad.risk_level == "unknown":
    print("⚠️ 无法评估风险，建议人工审查")

print(f"影响模块: {ad.modified_modules}")
print(f"新增依赖: {ad.new_dependencies}")

for change in ad.api_changes:
    if change.compatibility == "breaking":
        print(f"❌ Breaking change: {change.endpoint}")
    elif change.change_type == "new":
        print(f"➕ New endpoint: {change.endpoint}")
```

---

## 17. v1.0.0 新特性：CP（Change Proposal）治理平台

v1.0.0 完整实现了论文"从 PR 到 CP"中定义的 CP 治理范式。Zelos 从此成为论文的完整参考实现。

### 17.1 ChangeProposal 五元模型

论文定义 CP = (I, K, S, R, E) 五元信息模型：

```python
from zelos.change_proposal import ChangeProposal

cp = ChangeProposal(
    goal_id="g-1",
    knowledge_constraints=KnowledgeConstraints(
        coding_standards=["pep8"],
        forbidden_patterns=["eval", "exec"],
    ),
    structural_constraints=StructuralConstraints(
        modified_modules=["auth"],
        protected_modules=["payment"],
    ),
    risk_spec=RiskSpec(risk_level="medium"),
    verification_criteria=VerificationCriteria(
        test_pass_rate=1.0, coverage_threshold_pct=80.0,
    ),
)
# 自动构建：submit_goal 时从 IntentSpec 自动推导 CP
```

### 17.2 约束引擎

将 CP 固化为可执行约束，注入 Agent 执行上下文：

```python
from zelos.constraint_engine import ConstraintEngine
engine = ConstraintEngine()
constraints = engine.apply(cp)
# → coding_rules, architecture_boundaries, risk_thresholds, verification_requirements
```

### 17.3 Verifier 链

基于 CP 的验证准则自动编排 Verifier，FAIL 停止 + 低置信度升级：

```python
from zelos.verifier_chain import VerifierChain
chain = VerifierChain()
result = chain.execute(artifact, cp.verification_criteria)
# 自动注册: SchemaVerifier + CodeReviewer + SecurityScanner
```

### 17.4 自动合并

Policy Gate 批准后自动执行合并：

```python
rt.auto_decide(goal_id)
# auto_approve → MergeExecutor 自动合并
# 策略: event_sourcing_apply / git_merge
```

---

### Q: Planner 一定要用 LLM 吗？

不。Planner 是一个可替换的插件。你可以实现一个基于模板的 Planner，或者基于规则引擎的 Planner。LLMPlanner 只是默认实现。

---

> 📄 [English User Manual →](zelos-manual.html) | [API Reference →](zelos.html) | [GitHub →](https://github.com/AI-Zelos/zelos)
