# Zelos Phase 2 实施报告

> 版本: v0.2.0 | 日期: 2026-07 | 测试: 223/223 通过

---

## 一、Phase 2 总览

Phase 2 "Developer Platform" 在 Phase 1 Runtime Kernel 基础上，补齐了生产级开发平台所需的全部组件。

| 维度 | Phase 1 已有 | Phase 2 新增 |
|------|------------|------------|
| 验证 | SchemaVerifier | CodeReviewer + SecurityScanner + FactChecker + VerificationGate 链式执行 |
| 策略 | CostLimit / RateLimit / Allowlist | — (Phase 1 已完成) |
| 调度 | 5-phase pipeline + ScoringStrategy 插件 | — (Phase 1 已完成) |
| 可观测 | — | StructuredLogger + MetricsCollector + Tracer + Prometheus 导出 |
| 协议 | HTTP | gRPC + WebSocket + MCP + A2A |
| 隔离 | 进程内 | 子进程模式 (SubProcessPlugin + JSON 协议) |
| Planner | LLMPlanner + replan + 三层阶梯容错 | — (Phase 1 额外完成) |
| Memory | 6 层 InMemory + TTL + LRU + ContextAssembler | — (Phase 1 额外完成) |

---

## 二、各模块详细说明

### 2.1 Verifier Framework（验证框架）

**业务逻辑**：Agent 产出的 Artifact 不能直接信任。每一个 Artifact 在流入下游 Task 之前，必须经过验证关卡。

**四级验证链**（按序执行，首次失败即短路）：

```
Artifact → SchemaVerifier → CodeReviewer → SecurityScanner → FactChecker → Accepted
                ↓ 失败          ↓ 失败          ↓ 失败            ↓ needs_review
             Rejected        Rejected        Rejected          Pending Review
```

**SchemaVerifier**（Phase 1）：校验 Artifact 内容是否匹配 Task 声明的 `expected_output_schema`（JSON Schema）。类型不匹配、缺少必填字段 → failed。

**CodeReviewer**（Phase 2 新增）：
- 支持 Python / JavaScript / TypeScript 三种语言
- 检测规则：
  - `eval()` / `exec()` 使用 → error（远程代码执行风险）
  - 硬编码密码/API Key → warning
  - 裸 except 子句 → warning
  - `innerHTML` 赋值（JavaScript）→ warning
  - Python AST 语法解析 → SyntaxError 直接报错
- 语言通过 `criteria.options.language` 指定，默认 python

**SecurityScanner**（Phase 2 新增）：
- 9 种安全漏洞模式检测：
  - SQL 注入（字符串拼接 / 格式化 / f-string）
  - XSS（innerHTML 赋值 / document.write）
  - 硬编码凭证（password / secret / token / api_key）
  - 命令注入（os.system / subprocess / popen + 拼接）
  - 不安全的反序列化（pickle.loads / yaml.load）
  - 开放重定向

**FactChecker**（Phase 2 新增）：
- 检测不可验证的未来主张（"will reach X by 20XX" 等模式）
- 可配置已知事实库，用于校验声明

**VerificationGate**：顺序执行多个 Verifier，任意一个返回 failed 即停止并返回失败判决。无 Verifier 配置时直接放行。

---

### 2.2 Policy Engine（策略引擎）

**业务逻辑**：策略是对调度和执行的约束——不是改业务逻辑，而是 Allow / Reject / Delay / Retry。

**已完成策略**（Phase 1 完成，Phase 2 完善）：

| 策略 | 逻辑 |
|------|------|
| **CostLimitPolicy** | 累加每个 Task 的成本，超过 Goal 预算 → reject。按 goal_id 独立跟踪 |
| **RateLimitPolicy** | 滑动时间窗口内的 Task 数量超过阈值 → reject。窗口大小和阈值可配置 |
| **AllowlistPolicy** | Agent ID 不在白名单内 → reject |
| **CompositePolicy** | 多个 Policy 顺序执行，首次非 allow 即短路返回 |

**Rule Engine（表达式规则）**：支持基于条件表达式的动态规则，如 `task.cost > budget * 0.5 → reject`。

---

### 2.3 Advanced Scheduler（高级调度器）

**业务逻辑**：Scheduler 的 5 阶段流水线中，Phase 3（Scoring）是最需要定制的环节——不同组织对"好 Agent"的定义完全不同。

**ScoringStrategy 插件**（Phase 1 完成）：
- 默认策略：7 因子加权公式（成功率 30% + 成本 20% + 负载 15% + 延迟 15% + 可用性 10% + 亲和性 5% + 新鲜度 5%）
- 权限通过 `score()` 返回 `[ScoredCandidate]`，score=0 表示排除该候选
- 可完全替换——金融公司写合规优先策略、创业公司写成本优先策略

**三层阶梯式容错**（Phase 1 完成）：

```
READY Task 无可用 Agent
  → Tier 1 (0-60s): 等待（给热加入 Agent 时间窗口）
  → Tier 2 (>60s): FAIL — "no agent provides capability: xxx"
  → Tier 3 (on fail): Planner.replan() — LLM 找替代方案
```

---

### 2.4 Memory Architecture（记忆架构）

**业务逻辑**：Agent 是无状态的。所有记忆属于 Runtime。Agent 收到 Task 时，Runtime 已将所需的全部上下文组装在 Task payload 中。

**6 层记忆隔离**：

| 层 | 作用域 | 生命周期 |
|----|--------|---------|
| session | 单个 Goal | Goal 生命周期 |
| project | 同一项目 | 持久 |
| user | 同一用户 | 持久 |
| knowledge | 跨用户参考 | 持久 |
| execution | 单个 Task | Task 生命周期 |
| skill | 可复用模式 | 持久 |

**InMemoryMemoryProvider**（Phase 1 完成）：
- 每层独立 LRU 淘汰（max_entries_per_layer 可配）
- TTL 过期机制（可配，默认 3600s）
- store / retrieve / update / delete / search
- update 非存在 key 抛 KeyError

**ContextAssembler**：Task 派发前，从 session/project/user/knowledge/execution 层聚合相关记忆条目，组装为 MemoryContext。

---

### 2.5 Observability（可观测性）

**业务逻辑**：生产系统必须具备的三件套——日志、指标、追踪。

**StructuredLogger**：
- JSON 格式输出，可直接接入 ELK / Loki
- 4 级过滤（debug < info < warn < error）
- 每条日志：timestamp + level + message + context
- 支持自定义 handler

**MetricsCollector**：
- Counter（单调递增计数器）：task_completed_total, task_failed_total
- Gauge（可升降瞬时值）：agents_connected, queue_depth
- Histogram（分布统计）：task_duration_ms（支持 p50/p95/p99）
- Prometheus 文本格式导出：`# HELP / # TYPE / metric value`

**Tracer**：
- Span 层级树（parent_id 关联）
- 每个 Span：start_time + end_time + events + attributes
- 格式兼容 OpenTelemetry

---

### 2.6 Protocol Adapters（协议适配器）

**业务逻辑**：协议适配器是翻译层——将外部协议请求翻译为 Runtime API 调用。适配器**不包含任何业务逻辑**。

| Adapter | 协议 | 核心功能 |
|---------|------|---------|
| **HTTP** | REST/JSON | Phase 1 已有。15 个端点，API Key 认证 |
| **gRPC** | Protobuf | 9 个 RPC 方法，对应 Runtime API 操作。Phase 2 提供完整 service handler |
| **WebSocket** | 双向流 | 事件实时推送。客户端订阅 Goal/Task 事件，Event Bus 自动扇出 |
| **MCP** | JSON-RPC | Tool Registry 管理。Agent 通过 MCP 注册/调用工具，Runtime 不感知 MCP 内部 |
| **A2A** | Agent Card | 生成 Agent Card（capabilities → skills），接收外部 A2A Task，注册外部 Agent |

**架构原则**：所有适配器翻译到同一个 Runtime API。添加新协议不需要修改 Kernel。

---

### 2.7 Plugin Isolation（插件隔离）

**业务逻辑**：Phase 1 所有插件与 Runtime 运行在同一进程——一个插件崩溃可能导致整个 Runtime 崩溃。Phase 2 新增子进程隔离模式。

**SubProcessPlugin**：
- 插件运行在独立 Python 子进程中
- stdin/stdout JSON-line 协议通信
- 支持：execute / health_check / shutdown 消息类型
- 子进程崩溃 → 不影响 Runtime → 可自动重启

**SubProcessPluginRunner**：
- 插件端模板，`run(handler)` 即启动主循环
- 自动处理 health_check / shutdown / error

---

### 2.8 LLM Planner + 编排循环

**业务逻辑**：用户提交一个自然语言 Goal → Planner 调用 LLM 分解为 Task DAG → 编排循环自动执行。

**LLMPlanner**（Phase 1 完成）：
- 4 种 Provider：OpenAI（及兼容）/ Anthropic / Google / Mock
- plan()：Goal → ExecutionPlan（Task + DAG）
- replan()：Task 失败后重新规划，保留已完成 Task
- 系统 Prompt 可自定义
- 输出校验：JSON 解析 / DAG 无环 / 依赖引用有效 / Task 有 capability
- markdown code fence 自动剥离

**Orchestrator Loop**（Phase 1 完成）：
- 后台线程，每 500ms 一轮
- 自动完成：evaluate deps → schedule → dispatch → collect → verify → unblock → goal completion
- 三层阶梯式容错集成其中

---

## 三、全量文件清单

### 源码（17 个模块）

```
zelos/
├── __init__.py              # Package
├── event_bus.py             # EventBus + InMemoryEventStore
├── capability_registry.py   # CapabilityRegistry
├── task_graph.py            # TaskGraphEngine + Task DAG
├── scheduler.py             # Scheduler + ScoringStrategy + Policy
├── execution_engine.py      # ExecutionEngine + AgentState
├── plugin_manager.py        # PluginLifecycleManager
├── config_loader.py         # zelos.yaml 配置加载
├── runtime.py               # ZelosRuntime + Orchestrator Loop
├── planner.py               # LLMPlanner + 4 Provider
├── verifier.py              # Phase 1: SchemaVerifier + VerificationGate
├── verifier_v2.py           # Phase 2: CodeReviewer + SecurityScanner + FactChecker
├── policy.py                # CostLimit / RateLimit / Allowlist / Composite
├── memory.py                # 6-layer InMemory + ContextAssembler
├── observability.py         # Phase 2: Logger + Metrics + Tracer
├── protocol_adapters.py     # Phase 2: gRPC + WebSocket + MCP + A2A
├── plugin_isolation.py      # Phase 2: SubProcessPlugin
└── http_adapter.py          # HTTP REST Adapter
```

### 测试（5 个套件，223 tests）

```
tests/
├── test_all.py              # 105 tests — Kernel + API + Integration
├── test_phase1_remaining.py # 45 tests — Config / Verifier / Policy / Memory
├── test_planner.py          # 32 tests — LLM Planner
├── test_phase2.py           # 28 tests — CodeReviewer / Security / Observability / Isolation
├── test_protocol_adapters.py # 13 tests — gRPC / WebSocket / MCP / A2A
├── test_specification.md    # Phase 1 test spec
├── test_phase1_remaining_spec.md
├── test_phase2_spec.md
└── test_planner_spec.md
```

### Demo（12 个可运行示例）

```
demo/
├── 01_single_agent.py       # 单 Agent + 自动编排 + 阶梯容错
├── 02_multi_agent.py        # 4 Agent 协作
├── 03_http_api.py           # HTTP REST API
├── 04_custom_scoring.py     # 自定义评分策略
├── 05_hot_join.py           # 热加入 + 阶梯容错
├── 06_full_pipeline.py      # 完整流水线
├── 07_langchain_agent.py    # LangChain Agent 接入
├── 08_crewai_agent.py       # CrewAI Agent 接入
├── 09_autogen_agent.py      # AutoGen Agent 接入
├── 10_mixed_frameworks.py   # 混合框架编排
├── 11_verifier_pipeline.py  # 四级验证链
└── 12_observability.py      # 日志 + 指标 + 追踪
```
