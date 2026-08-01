# Zelos 与主流 Agent 框架及 Harness 的对比分析报告

> 编写日期：2026-07-31
>
> 目的：系统分析 Zelos 与 LangGraph、CrewAI、AutoGen/Microsoft Agent Framework、OpenAI Agents SDK 等主流 Agent 框架的架构差异，以及 Harness 概念与 Zelos 的关系与区别，明确 Zelos 的独特定位。

---

## 目录

1. [AI 工程化演进的三个阶段](#1-ai-工程化演进的三个阶段)
2. [Zelos 架构全景](#2-zelos-架构全景)
3. [主流 Agent 框架深度分析](#3-主流-agent-框架深度分析)
   - [3.1 LangGraph](#31-langgraph)
   - [3.2 CrewAI](#32-crewai)
   - [3.3 AutoGen / Microsoft Agent Framework](#33-autogen--microsoft-agent-framework)
   - [3.4 OpenAI Agents SDK](#34-openai-agents-sdk)
4. [Harness 深度分析](#4-harness-深度分析)
   - [4.1 Harness Inc 平台](#41-harness-inc-平台)
   - [4.2 Harness Engineering（行业范式）](#42-harness-engineering行业范式)
   - [4.3 Harness 与 Zelos 的关系与区别](#43-harness-与-zelos-的关系与区别) ⭐️ 投资人必读
     - [4.3.1 一句话结论](#431-一句话结论)
     - [4.3.2 建筑 vs 城市：核心类比](#432-用类比来理解建筑-vs-城市)
     - [4.3.3 Harness 能做什么、不能做什么](#433-harness-能做什么不能做什么)
     - [4.3.4 为什么不能"在 Harness 上面做升级"](#434-为什么不能在-harness-上面做完善和升级)
     - [4.3.5 "Agent City"的定位](#435-agent-city概念的定位)
     - [4.3.6 互补关系架构图](#436-互补关系harness-是-zelos-中每个-agent-的内部实现)
     - [4.3.7 回应投资人的三个核心问题](#437-总结回应投资人的三个核心问题)
5. [全维度对比矩阵](#5-全维度对比矩阵)
6. [Zelos 的独特差异化](#6-zelos-的独特差异化)
7. [竞争定位与生态关系](#7-竞争定位与生态关系)
8. [结论](#8-结论)

---

## 1. AI 工程化演进的三个阶段

回顾 2023–2026 年的 AI 工程化历史，可以清晰地看到三个阶段的演进：

```
Phase 1: 单体 Agent (2023)
  单个 LLM + 工具调用
  LangChain, OpenAI Function Calling

Phase 2: Agent 框架 (2024–2025)
  多 Agent 协作 + 流程编排
  LangGraph, CrewAI, AutoGen

Phase 3: Agent Runtime (2025–2026)
  治理 + 调度 + 可观测 + 不可变审计
  Zelos, Harness Engineering, Murmur
```

**关键判断**：2026 年，行业正从 Phase 2 向 Phase 3 过渡。框架已经解决了"如何构建 Agent"的问题，但"如何可靠地编排数百个独立 Agent"的问题尚未被解决。



Zelos 的目标不是成为又一个框架，而是成为 Phase 3 的 Runtime 标准。

---

## 2. Zelos 架构全景

### 2.1 定位

Zelos 是一个**开放的、LLM 无关的、以目标为中心的多 Agent 编排 Runtime**。它的核心隐喻是：

```
Linux 管理进程
Kubernetes 管理容器
Temporal 管理工作流执行
Zelos 管理多 Agent 的目标执行
```

### 2.2 核心理念：三权分立

Zelos 在架构层面施行**宪法性权力分割**：

| 权力 | 持有者 | 职责 |
|------|--------|------|
| **规划权** | Planner (Plugin) | 将 Goal 分解为 Execution Plan |
| **调度权** | Scheduler (Kernel) | 匹配 Capability → Agent，决定调度策略 |
| **验证权** | Verifier (Plugin) | 验证 Artifact 质量 |
| **执行权** | Agent (外部进程) | 接收 Task，执行，返回 Artifact |

三权永远不能集中在同一个组件中。Agent **只有执行权**——它不规划、不调度、不验证、不与其他 Agent 通信。

### 2.3 架构分层

```
┌─────────────────────────────────────┐
│           Protocol Layer            │  ← HTTP / gRPC / MCP / A2A Adapters
├─────────────────────────────────────┤
│             Plugin Layer            │  ← Planner / Verifier / Policy / Memory / Storage
├─────────────────────────────────────┤
│          Kernel (Sealed)            │  ← EventBus / CapabilityRegistry / Scheduler
│                                     │     TaskGraphEngine / ExecutionEngine
├─────────────────────────────────────┤
│         Infrastructure Layer        │  ← Process / Container / Network
└─────────────────────────────────────┘
```

### 2.4 15 条 Architecture Invariants（宪法级约束）

Zelos 定义了 15 条不可违反的架构约束，是项目的最高法则：

1. **Runtime 拥有编排权** — Agent 只是执行插件
2. **Goal 是第一公民抽象** — 不是 Workflow，不是 DAG，不是 Prompt Chain
3. **Execution Plan 是唯一事实来源**
4. **Task 是原子单位** — 一个 Task = 一个 Agent 调用
5. **Capability 先于 Agent** — 按能力调度，不按名称调度
6. **Agent 无状态** — 所有状态归 Runtime
7. **Event 不可变** — 追加写入，不可修改或删除
8. **Artifact 不可变** — 创建后不可修改，任何变换产生新 Artifact
9. **契约高于实现** — 组件间只能通过 Schema/API/Event 通信
10. **Kernel 密封、Plugin 可替换**
11. **Schema 是版本化契约**
12. **一切都有生命周期**
13. **Runtime 永远不依赖 LLM** — Runtime 不知道 Claude/GPT/Gemini 的存在
14. **Capability 描述意图，不描述实现**
15. **Policy 只能 Allow/Reject/Delay/Retry**，不能修改 Plan 或 Task

### 2.5 Agent 模型

Agent 在 Zelos 中是**外部进程**，只需实现 5 个 API：

```
register()   — 注册 Agent 及其 Capability
heartbeat()  — 心跳存活信号
execute()    — 接收 Task，执行，返回 Artifact
cancel()     — 取消正在执行的 Task
shutdown()   — 优雅关闭
```

Agent 可以是**任意语言、任意框架、任意实现**。Runtime 不知道 Agent 内部是否使用了 LLM。

### 2.6 事件驱动架构

所有组件间通信通过不可变的 Event Bus：

```
GoalSubmitted → ExecutionPlanCreated → TaskReady → TaskAssigned
→ TaskStarted → TaskCompleted → ArtifactCreated
→ VerificationCompleted → GoalCompleted
```

每个 Event 携带 `correlation_id` 和 `causation_id`，形成完整的因果审计链。

---

## 3. 主流 Agent 框架深度分析

### 3.1 LangGraph

**基本信息**

| 维度 | 详情 |
|------|------|
| 开发者 | LangChain Inc. |
| 开源协议 | MIT |
| GitHub Stars | ~32,000+ |
| 语言 | Python + TypeScript |
| 当前版本 | 1.x (2025.10 GA) |
| 月下载量 | 65M+ |

**架构核心：有状态的图状态机**

LangGraph 将 Agent 工作流建模为**有向图**（支持循环），核心抽象：

```
State (TypedDict / Pydantic) → Nodes (Python 函数) → Edges (路由规则)
                                                         ↓
                                                  Checkpointer (持久化层)
```

**关键能力：**
- **状态共享**：所有 Node 共享一个 State 对象，通过 Reduce 函数合并更新
- **持久化**：Checkpointer 在每个 Node 转换后持久化状态，支持暂停/恢复
- **Human-in-the-Loop**：`interrupt()` 原语可在图中任意节点暂停等待人工审批
- **Send API**：动态并行 fan-out（Map-Reduce 模式）
- **Subgraph**：整个 Agent 团队可封装为可复用的子图

**多 Agent 模式：**

| 模式 | 描述 |
|------|------|
| Supervisor | 一个中心 Node 路由给专业 Worker Node，收集结果后决定下一步 |
| Orchestrator-Worker | 动态规划子任务 + Send API 并行分发 + 聚合结果 |
| Hierarchical | Subgraph 封装子 Agent 团队，嵌套复用 |

**核心优势：**
- 任意复杂的状态机，支持循环和条件分支
- 强大的持久化和 Time-Travel 调试
- 庞大的 LangChain 生态系统
- 已在 Klarna、Uber、LinkedIn 等企业级生产环境验证

**核心局限性：**
- **图必须静态定义**，无法在运行时动态构建
- 共享状态在复杂场景下容易膨胀，Token 消耗大
- Agent 间通信只能通过 State 对象，不能直接通信
- 深度绑定 Python/TypeScript 生态
- 不解决模型无关性——图结构和 Node 实现隐式依赖特定 LLM
- 编排逻辑和业务逻辑混在 Node 中，缺乏治理层分离

---

### 3.2 CrewAI

**基本信息**

| 维度 | 详情 |
|------|------|
| 开发者 | CrewAI Inc. |
| 开源协议 | MIT |
| GitHub Stars | ~51,000+ |
| 语言 | Python |
| 当前版本 | 1.14–1.15 |

**架构核心：角色 + 任务 + 团队**

CrewAI 采用**双层架构**：

```
Flows (确定性骨架)            Crews (自主智能)
  @start / @listen / @router    角色扮演 Agent 团队
  事件驱动 + 状态管理            自主协作 + 创意探索
  确定性条件逻辑 + 循环          用于研究、头脑风暴、初稿
```

**四大核心原语：**

| 原语 | 职责 |
|------|------|
| Agent | `role` + `goal` + `backstory` + `tools` + `llm` |
| Task | `description` + `expected_output` + `agent` + `context` |
| Crew | 容器：Agent 列表 + Task 列表 + `process` 策略 |
| Process | 执行策略：Sequential / Hierarchical / Consensus (预留) |

**执行策略：**
- **Sequential**：按声明顺序执行，上一 Task 输出 → 下一 Task 上下文
- **Hierarchical**：Manager Agent (LLM) 动态路由给 Specialist，增加 Token 开销
- **Consensus**：未来投票机制（未实现）

**核心优势：**
- 角色/目标/背景故事的声明式 API 门槛极低
- 丰富的内置 Tool 生态（搜索、文件、代码执行、RAG）
- 四层 Memory 系统（短期/长期/实体/上下文）
- CrewAI AMP 企业平台提供 A2A 协议支持
- NVIDIA NemoClaw 集成提供安全沙箱

**核心局限性：**
- **Agent 直接指定**：`task.agent = researcher_agent`，没有 Capability 调度层
- **角色耦合**：Agent 的 `role` 和 `backstory` 就是调度键，无法动态替换
- **Agent 间可以委托**（delegation），破坏了执行隔离
- LLM 深度依赖：Manager Agent 本身就是 LLM 调用
- Hierarchical 模式 Token 消耗是指数级的
- **Python only**，Agent 必须是 Python 内部对象

---

### 3.3 AutoGen / Microsoft Agent Framework

**基本信息**

| 维度 | 详情 |
|------|------|
| 开发者 | Microsoft Research → Microsoft |
| 开源协议 | MIT |
| GitHub Stars | ~50,000–55,000 |
| 语言 | Python (主) + .NET |
| 当前状态 | AutoGen v0.7.5 维护模式；MAF 公开预览 |

**AutoGen 三层架构（v0.4+）：**

```
autogen-agentchat (高级 API)    ← AssistantAgent / GroupChat / SelectorGroupChat
autogen-core (Runtime 层)       ← 事件驱动 Actor 模型 / 消息传递
autogen-ext (扩展层)            ← 模型客户端 / 代码执行器 / MCP / 工具
```

**关键模式：**
- **GroupChat**：多个 Agent 在同一会话中轮流发言，`GroupChatManager` 管理发言权
- **SelectorGroupChat**：LLM 驱动的动态发言者选择
- **MagenticOneGroupChat**：基于 Magentic-One 研究系统的规划-委派-重规划模式

**演进：AutoGen → Microsoft Agent Framework (MAF)**

2025 年 10 月，Microsoft 将 AutoGen 与 Semantic Kernel 合并为 **MAF**：

| AutoGen 贡献 | Semantic Kernel 贡献 |
|-------------|---------------------|
| 多 Agent 对话式编排 | 企业级类型安全、中间件、DI |
| 涌现式团队行为 | OpenTelemetry 可观测性 |
| 研究级灵活性 | Plugin/Connector 生态 |
| GroupChat 模式 | 生产稳定性 |

**MAF 新增原语：**
- `ChatAgent`：每个 Agent 的原子原语，含线程状态和工具
- `Workflow`：基于图/DAG 的显式编排，确定性边界和条件
- 原生 MCP 客户端/服务端支持

**核心优势：**
- 对话式 Agent 协作的先驱模式
- 一流的代码执行沙箱（Docker/Jupyter）
- 分布式 Runtime 支持
- GAIA 和 SWE-bench 基准测试表现强劲

**核心局限性：**
- **框架 API 频繁 Breaking Change**（v0.2 → v0.4 两次重写，18 个月）
- GroupChat Token 成本高（8 Agent GPT-4o 对话可达 $5–$30/任务）
- 非确定性使测试和复现困难
- 目前处于维护模式，新功能投入 MAF
- MAF 的 `Workflow` 图编排能力本质上是 LangGraph 的竞争者
- **本质仍是框架，不是 Runtime**——Agent 的构造和编排都在同一层

---

### 3.4 OpenAI Agents SDK

**基本信息**

| 维度 | 详情 |
|------|------|
| 开发者 | OpenAI |
| 开源协议 | MIT |
| 语言 | Python + TypeScript |
| 核心代码量 | ~800 行 Python |

**架构核心：极简四原语**

| 原语 | 角色 |
|------|------|
| Agent | 不可变配置（name, instructions, tools, handoffs, model, output_type） |
| Runner | 无状态执行引擎，运行 Agent Loop |
| Handoff | 委派原语——切换 Agent 建模为特殊工具调用 |
| Guardrail | 安全防护（Input / Output / Tool 三级） |

**关键设计决策：**

```
Runner.run(agent, input)   ← 不是 agent.run(input)
```

- **Agent 是数据，Runner 是执行**——同一个 Agent 实例可跨并发请求安全复用
- **Handoff 复用 Function Calling 通道**——模型不需要知道"Agent 切换"概念
- **三层 Guardrail**——Input (并行) → Tool (包装) → Output (顺序)

**核心优势：**
- 极简设计——核心 Loop < 800 行
- Agent 作为工具 vs Handoff 两种委派模式清晰分离
- 内置 OpenTelemetry Tracing
- 100+ 模型支持（通过 Chat Completions API）

**核心局限性：**
- **模型决定路由**——Handoff 由 LLM 判断，不可显式控制
- 无持久化/Checkpoint 机制
- 无显式状态机控制
- **主要面向 OpenAI 生态**（尽管支持 LiteLLM）
- 没有 Memory 系统
- 无限 handoff 循环风险

---

## 4. Harness 深度分析

### 4.1 Harness Inc 平台

Harness Inc. 是一个 **DevOps/CI/CD 软件交付平台**，2025–2026 年在平台内构建了 AI Agent 编排能力。

**核心公式：Agent = Model + Harness**

**三层 MCP 架构：**

```
Layer 1: MCP Tool Surface (Syscall Table)
  10–11 个通用动词 (harness_list, harness_get, harness_create...)
  → 调度到 30+ 工具集，覆盖 140+ 资源类型

Layer 2: Registry (Kernel / vtable)
  Map<resource_type, ResourceDefinition>
  → 统一执行管线：路径构建 → 作用域注入 → 认证 → 分页 → 响应提取

Layer 3: HarnessClient (Block Device Driver)
  原始 HTTP Client + 认证 + 重试/退避 + 限流
```

**关键设计：**
- **可组合性优于增殖**：少量动词 + 大量名词 + 统一接口
- **按需加载领域知识**：`harness_describe()` 按需加载 Schema（~500–3000 tokens），不预先加载
- **运行时自描述**：Agent 在运行时通过内省发现能力
- **声明式优于命令式**：资源定义为数据结构（`EndpointSpec`），非处理函数

**自治 Worker Agent：**
- 容器化沙箱执行（非 root，只读文件系统）
- 临时凭证（Agent 权限 ∩ 用户 RBAC）
- OPA 策略框架（与部署相同的策略门）
- 完整审计链

**统一 Agent vs 多 Agent：**
从 20+ 子 Agent 合并为 1 个统一 Agent，Token 消耗降低 ~90%，响应时间 40s → 20s。

### 4.2 Harness Engineering（行业范式）

2026 年 2 月，Mitchell Hashimoto (HashiCorp) 正式将 "Harness Engineering" 命名为一门新的工程学科。

**六个架构层 + 两个横切能力：**

| 层 | 角色 |
|----|------|
| L1: Access & Interface | 系统边界、协议转换、认证入口 |
| L2: Execution & Orchestration | 任务分解、流程调度、状态机 |
| L3: Memory & State | 知识存储、上下文管理、状态持久化 |
| L4: Tool Integration | 标准化能力接口 |
| L5: Evaluation & Observability | 正确性验证、质量评估、全链路追踪 |
| L6: Constraint, Validation & Recovery | 最后防线——错误拦截、护栏、自愈 |

**四大架构模式：**

| 模式 | 描述 | 适用场景 |
|------|------|----------|
| Loop-Based | 单 Agent `while` 循环，无持久化 | 短原型 (<10 步) |
| Graph/Stateful (DAG) | Node + Edge + State + Checkpoint | 中等复杂度，HITL |
| Microkernel | 控制面 + 执行 Worker 分离 | 企业集群，高并发 (1000+) |
| Multi-Agent | Planner → Worker 并行 + 上下文隔离 | 复杂多模块工程 |

**生产推荐：** Microkernel 基座 + Graph 单任务流 + Multi-Agent 并行子任务 = 分层混合

**Harness 填补的三个核心 Gap：**

| Gap | 机制 |
|-----|------|
| 反应性（LLM 不会自己醒来） | 事件接入 → 统一调度队列 |
| 持久性（LLM 跨会话遗忘） | 记忆去重 + 本地状态文件 + git 同步工作区 |
| 质量（LLM 从弱证据写自信结论） | 结构化输出契约 + 质量门（假设锁定/经验锚/对抗审查/置信度机械天花板） |

**自我进化闭环** 是 Harness Engineering 的差异化模式：闭合案例反馈到 Harness 本身——差距分析 → 对 Harness 源码提 PR → 人类合并 → 下一个案例在更好的 Harness 上运行。

### 4.3 Harness 与 Zelos 的关系与区别

> **本节核心目的：回答投资人最关心的问题——"Harness 已经能做任务分解、执行和验证了，为什么你们还要自己造，而不是在 Harness 上面做完善和升级？"**

---

#### 4.3.1 一句话结论

**Harness 和 Zelos 是两个不同抽象层级的系统。Harness 解决"一个 Agent 如何可靠运行"，Zelos 解决"成百上千个 Agent 如何协同完成一个复杂目标"。这两个问题的规模和性质完全不同——正如管理一座建筑的水电和管理一座城市的电网，不是同一个工程问题。**

---

#### 4.3.2 用类比来理解：建筑 vs 城市

这是理解 Zelos 与 Harness 关系最重要的框架：

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   Harness Engineering          │        Zelos               │
│   ─────────────────            │        ─────               │
│                                                             │
│   一座建筑的                   │        一座城市的            │
│   配电 / 供水 / 消防            │        电网 / 水网 / 交通调度 │
│                                                             │
│   管理对象：1 栋楼              │        管理对象：1000 栋楼    │
│   管理粒度：房间级              │        管理粒度：城区级       │
│   核心能力：供电稳定             │        核心能力：负载均衡     │
│            供水充足                      错峰调度             │
│            火灾报警                      跨区调配             │
│                                          故障隔离             │
│                                                             │
│   "让一个 Agent 可靠地运行"     │       "让数百个 Agent         │
│                                 │        可靠地协同"          │
│                                                             │
│   管理的问题规模：O(1)           │       管理的问题规模：O(n²)   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**为什么不能"基于 Harness 做升级"？**

因为管理一座建筑和管理一座城市，需要的是**完全不同性质的系统**：

| 一座建筑需要 | 一座城市需要 |
|-------------|-------------|
| 配电箱 | 变电站 + 电网调度中心 |
| 供水管道 | 水厂 + 加压站 + 管网调度 |
| 消防喷淋 | 消防局 + 119 指挥中心 |
| 监控摄像头 | 城市大脑 + 跨区域协查 |
| 物业经理 | 市政府 + 各职能部门 |

**你不能通过"给 1000 栋建筑各装一套配电箱，然后把它们连起来"来建造城市电网。城市电网需要的是一个中枢调度系统——变电站、高压输电线、负载均衡、错峰调度。这和单栋建筑的配电是完全不同性质的工程。**

**同理，你不能通过"给 100 个 Agent 各套一个 Harness，然后把它们拼起来"来构建 Agent City。这需要的是 Zelos 这样的中枢调度系统。**

---

#### 4.3.3 Harness 能做什么、不能做什么

投资人说"Harness 也能做任务分解、执行、检查"，这没错。但关键是看**在什么规模上**做：

**Harness 能做的（单 Agent 范畴）：**

| 能力 | Harness 如何做 | 适用规模 |
|------|---------------|---------|
| 任务分解 | Agent 内部 `observe → reason → plan → act` Loop | 1 个 Agent 自己规划自己的子步骤 |
| 任务执行 | Agent Loop 串行执行工具调用 | 同一上下文内，工具级并行 |
| 质量检查 | Guardrails / Quality Gates | 单 Agent 输出的结果级校验 |
| 记忆管理 | 会话记忆 + 向量检索 | 单 Agent 自己的历史上下文 |
| 工具调用 | MCP Tool 注册 | 单 Agent 可用的工具集 |

**Zelos 做的（多 Agent 编排范畴，Harness 做不到）：**

| 能力 | Zelos 如何做 | 为什么 Harness 做不了 |
|------|-------------|----------------------|
| **跨 Agent 任务分发** | Goal → Planner 分解 → Execution Plan → Scheduler 按 Capability 分发 | Harness 的"任务分解"是单 Agent 内部的子步骤规划。它无法拆解一个复杂 Goal 为 50 个并行 Task，然后分发给 50 个不同能力的 Agent |
| **多 Agent 并发调度** | Task DAG → 依赖解析 → Scheduler 5 阶段 7 因子评分 → 并行调度 | Harness 没有 Agent Pool 概念。它管理的是 1 个 Agent 的工具调用队列，不是 N 个异构 Agent 的调度池 |
| **跨 Agent 依赖编排** | Task Graph Engine：DAG 拓扑排序 + 依赖状态机 | Harness 没有跨 Agent 的 DAG 概念。Agent A 的输出需要作为 Agent B 的输入？这超出了 Harness 的范畴 |
| **Capability 招标分发** | Capability Registry → "需要 coding" → 自动匹配 [Claude Code, Codex, Local Agent] → 调度最优 | Harness 直接指定工具名称，没有"按能力招标、多供应商竞争"的概念 |
| **Agent 热替换与容错** | Agent A 挂了 → Scheduler 自动将 Task 重新分配给同 Capability 的 Agent B | Harness 的 Agent 是单体，挂了就是挂了 |
| **跨 Agent 审计链** | Event Bus：`correlation_id` + `causation_id` 完整因果链 | Harness 的审计是单 Agent 视角。一个 Task 被哪个 Agent 执行、哪个 Event 触发了它、它的输出流向了哪里——跨 Agent 因果链在 Harness 中不存在 |
| **三权分立治理** | Planner ≠ Scheduler ≠ Verifier，Agent 只有执行权，永远不能调度其他 Agent | Harness 的 Guardrail 是安全防护，不是权力制衡。Agent 可以自己决定下一步，甚至可以调用其他 Agent（Handoff） |
| **LLM 无关 Runtime** | Runtime 不知道 Agent 内部是否使用 LLM | Harness 深度绑定 LLM——Agent Loop 就是围绕 LLM 的 observe→reason→act 循环 |
| **语言无关 Agent** | Agent 是外部进程，5 个 API，任意语言 | Harness 的 Agent 定义和工具注册都在 Python/TS 代码内部 |
| **Policy Gate** | 全局策略引擎：Allow/Reject/Delay/Retry，作用于所有 Task | Harness 的 Guardrail 是 Agent 级的安全校验，不是跨 Agent 的策略门 |

---

#### 4.3.4 为什么不能"在 Harness 上面做完善和升级"？

这是投资人最直接的问题。答案有四个层面：

**第一，基因层面：Harness 是"Agent 内部 Runtime"，Zelos 是"Agent 间 Runtime"。**

Harness 的架构基因是：
```
Model → Agent Loop → Tool1 → Tool2 → Tool3 → Output
         ↑_____↓
        (同一上下文)
```

Zelos 的架构基因是：
```
Goal → Planner → [Task1, Task2, ..., Task50]
                    ↓
              Scheduler 按 Capability 分发
                    ↓
           Agent A    Agent B    Agent C
           (Harness)  (Harness)  (Harness)
                    ↓
              Event Bus 聚合
                    ↓
              Verifier 验证
```

在 Harness 的基础上"往上加"多 Agent 调度层，就像在单机操作系统的进程管理器上直接加分布式调度——你可以做，但那是**硬塞进一个不是为它设计的架构里**。正确的做法是：进程管理器继续管好进程，之上另建一层 Kubernetes 来管容器。

**第二，假设冲突：Harness 假设 LLM 是核心，Zelos 假设 Agent 是核心。**

Harness 的整个架构围绕着 LLM 设计——Agent Loop 就是一个 LLM 驱动的 while 循环，Memory 面向 LLM 上下文窗口，Guardrails 面向 LLM 输出校验。

Zelos 的 Invariant 13 明确规定：**Runtime 不知道 LLM 的存在**。

这意味着 Zelos 可以编排任何类型的 Agent：LLM Agent、规则引擎 Agent、人类审批 Agent、传统脚本 Agent。这是一个**根本性架构假设的不同**——你不能在一个"以 LLM 为心脏"的架构上，改出一个"LLM 透明"的系统。

**第三，权力模型的冲突：Harness 赋予 Agent 自主权，Zelos 剥夺 Agent 自主权。**

Harness 的 Agent 可以自己规划、自己选择工具、自己决定下一步、甚至 Handoff 给其他 Agent——这是 Harness Engineering 的设计意图。

Zelos 的 Agent **永远不能**：规划、调度、调用其他 Agent、修改 Execution Plan、拥有状态。Agent 只有执行权。

这两个权力模型是**根本对立**的。你不能在一个赋予 Agent 充分自主权的框架上，"限制"出一个剥夺 Agent 自主权的 Runtime。

**第四，单 Agent 优化 vs 全局优化。**

Harness 优化的是**单个 Agent 的任务完成质量**：更好的 Memory、更准的 Guardrail、更低的 Token 消耗。

Zelos 优化的是**整个 Agent 集群的全局目标达成**：最优的任务-Agent 匹配、最小的全局完成时间、最合理的资源分配、最完整的审计追踪。

这两类优化目标有时是**矛盾的**。单个 Agent 的"局部最优"（比如不停重试直到满意）可能导致全局最差（占用资源，阻塞下游）。Zelos 的 Scheduler 需要的是全局视角——哪些该重试、哪些该降级、哪些该换供应商——这个视角只有在 Runtime 层才有。

---

#### 4.3.5 "Agent City"概念的定位

投资人觉得"太大，感觉我们要把整个生态都做了"——这个直觉需要被精确地回应：

**Zelos 做的不是"整个生态"，而是生态中没有人做的那一层。**

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│  应用层         │  开发者构建自己的业务应用               │
│  (Zelos 不做)    │  "帮我做一个自动化的客服系统"            │
│                 │  "帮我做一个自动化的代码审查系统"         │
│                                                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Agent 构建层   │  LangGraph / CrewAI / AutoGen          │
│  (Zelos 不做)    │  这些框架已经做得很好了                  │
│                 │  "如何构建一个能写代码的 Agent"          │
│                                                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Agent 内部层   │  Harness Engineering                  │
│  (Zelos 不做)    │  Agent Loop + MCP + Memory + Guard    │
│                 │  "如何让一个 Agent 可靠地运行"           │
│                                                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ★ 多 Agent 编排层 ★                                    │
│  (Zelos 做的)    │  Planner → Scheduler → Verifier       │
│                 │  Capability Registry → Event Bus       │
│                 │  "如何让 100 个 Agent 协同完成 Goal"     │
│                 │  👆 这是目前市场上空白的层               │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Zelos 做的事情就是"Agent City"的市政基础设施——不是盖楼（Harness 做），也不是造家具（框架做），而是铺设城市级的电网、水网、交通调度系统。**

这部分现在没有任何人在做。LangGraph/CrewAI/AutoGen 是在帮开发商盖楼，Harness 是帮每栋楼装智能家居系统。但没有人做"市政厅"。

"Agent City"听起来大，因为它是**基础设施层**——基础设施层天然就是大的，就像没有人说 Kubernetes 太大了。大的不是"我们要做所有事情"，大的是"我们要解决分布式多 Agent 系统的基础性问题"。

---

#### 4.3.6 互补关系：Harness 是 Zelos 中每个 Agent 的内部实现

两者不是竞争关系，而是**互补的层级关系**：

```
┌──────────────────────────────────────────────────────────────┐
│                    Zelos Runtime                             │
│                    (Agent City 市政府)                        │
│                                                              │
│  Goal → Planner → ExecutionPlan → TaskGraph                  │
│                                  ↓                           │
│                    Scheduler 按 Capability 分发               │
│                        ↓         ↓         ↓                │
│              ┌─────────┐  ┌─────────┐  ┌─────────┐          │
│              │ Agent A │  │ Agent B │  │ Agent C │  ...     │
│              │         │  │         │  │         │          │
│              │ ┌─────┐ │  │ ┌─────┐ │  │ ┌─────┐ │          │
│              │ │Harness│ │  │ │Harness│ │  │ │Harness│ │          │
│              │ │Engine│ │  │ │Engine│ │  │ │Engine│ │          │
│              │ │ering │ │  │ │ering │ │  │ │ering │ │          │
│              │ └─────┘ │  │ └─────┘ │  │ └─────┘ │          │
│              │ LLM+Tool│  │ LLM+Tool│  │ LLM+Tool│          │
│              └─────────┘  └─────────┘  └─────────┘          │
│                        ↓         ↓         ↓                │
│              Event Bus ← Artifact ← Verifier ← Policy       │
│                        ↓                                    │
│                    Goal Completed                            │
└──────────────────────────────────────────────────────────────┘
```

**每一个被 Zelos 调度的 Agent，内部完全可以、也应该使用 Harness Engineering 来构建。**

这不是二选一，这是分工：

- **Harness** 负责"Agent 内部的质量"（工具调用可靠、记忆准确、输出合规）
- **Zelos** 负责"Agent 之间的质量"（任务分对了吗、执行顺序对吗、失败了谁接管、谁验证结果）

一个 Zelos Agent 对外只暴露 5 个 API（`register / heartbeat / execute / cancel / shutdown`），内部用什么 Harness 模式（Loop / Graph / Microkernel）完全自由。Zelos Runtime 不关心也无需关心。

这就是 Zelos Invariant 13 的精髓：**Runtime never depends on LLM**。Runtime 只知道 Agent 是一个接收 Task、返回 Artifact 的外部进程。Agent 内部是一个 Harness Loop 还是一个传统程序——对 Runtime 来说都是一样的。

---

#### 4.3.7 总结：回应投资人的三个核心问题

| 投资人的问题 | Zelos 的答案 |
|-------------|-------------|
| **"Harness 已经能做任务拆解、执行、验证了"** | Harness 做的是 **1 个 Agent 内部的**拆解/执行/验证。Zelos 做的是 **100 个 Agent 协同的**拆解/调度/验证。前者是"一个人怎么规划自己的一天"，后者是"一个公司怎么协调 100 个人完成一个项目"。**
| **"为什么不在 Harness 上面做升级？** | 因为这两种系统的**架构基因、核心假设和权力模型是根本对立的**。Harness 假设 LLM 是心脏、Agent 拥有自主决策权、单 Agent 的局部最优。Zelos 假设 Agent 是执行单元、Runtime 拥有所有编排权、全局最优。在 Harness 上"加"多 Agent 调度，就像在单机 OS 上"加"分布式编排——可以做，但那是把错误的抽象硬塞进不属于它的架构。正确的做法是在 Harness 之上建一层新的抽象，就像 Kubernetes 之于 Linux 进程。 |
| **"Agent City 是不是太大了？** | Agent City 大，不是因为它要做所有事情，而是因为**基础设施层天然就是大的**。Zelos 不做 Agent 构建（框架的事），不做 Agent 内部运行（Harness 的事），不做上层应用（开发者的事）。Zelos 只做一件事——**多 Agent 的编排治理**。这件事目前没有任何人在做，而这个空白恰恰是多 Agent 系统从 PoC 走向生产的关键瓶颈。 |

---

## 5. 全维度对比矩阵

### 5.1 架构哲学

| 维度 | Zelos | LangGraph | CrewAI | AutoGen/MAF | OpenAI Agents SDK |
|------|-------|-----------|--------|-------------|-------------------|
| **定位** | 多 Agent 编排 Runtime | Agent 图状态机框架 | 角色扮演 Agent 框架 | 对话式多 Agent 框架 | Agent 循环 SDK |
| **核心隐喻** | Kubernetes for Agents | Stateful Graph | Role + Task + Crew | GroupChat | Agent Loop + Handoff |
| **编排主体** | Runtime 拥有全部编排权 | 开发者定义图结构 | 开发者定义角色和流程 | GroupChatManager 管理 | Runner 运行 Agent Loop |
| **权力模型** | **三权分立**（Plan/Schedule/Verify） | 无显式分离 | Agent 可委托和调用其他 Agent | Agent 自由对话 | Model 决定路由 |
| **是否 LLM 无关** | ✅ **完全无关** (Invariant 13) | ❌ Node 通常含 LLM 调用 | ❌ Agent.llm 是核心属性 | ❌ GroupChat 依赖 LLM | ❌ 深度依赖 OpenAI |

### 5.2 Agent 模型

| 维度 | Zelos | LangGraph | CrewAI | AutoGen/MAF | OpenAI Agents SDK |
|------|-------|-----------|--------|-------------|-------------------|
| **Agent 定义** | 外部进程，5 个 API | Python 函数/Subgraph | Python 对象 (role/goal/backstory) | Python 对象 (AssistantAgent) | 不可变配置对象 |
| **Agent 语言** | **任意语言** | Python/TypeScript | Python | Python/.NET | Python/TypeScript |
| **Agent 状态** | **完全无状态** | 共享 State | Agent 可有 Memory | 对话历史 | 无状态配置 |
| **Agent 通信** | Event Bus (不可变) | 共享 State 对象 | 直接委托 + 上下文传递 | GroupChat 消息 | Handoff (模型切换) |
| **Agent 调度** | **Capability-based** | 图边静态路由 | Task.agent 直接指定 | 发言者选择函数 | Model 判断 Handoff |
| **Agent 发现** | Capability Registry | 无（静态图定义） | 无（代码中创建） | Agent 列表 | Handoffs 列表 |

### 5.3 执行模型

| 维度 | Zelos | LangGraph | CrewAI | AutoGen/MAF | OpenAI Agents SDK |
|------|-------|-----------|--------|-------------|-------------------|
| **任务单位** | Task (原子) | Node (函数调用) | Task (含 Agent 分配) | Message (一轮发言) | Agent Run |
| **执行分解** | Goal → Plan → Task Graph (DAG) | StateGraph 定义 | Crew 内 Task 序列 | GroupChat 轮次 | Agent Loop |
| **并行支持** | ✅ DAG 自动识别 | ✅ Send API fan-out | ❌ 顺序/层级 | ✅ GroupChat 并行 | ❌ 单 Agent Loop |
| **持久化** | Event Store (不可变) | Checkpointer | 可选 Memory | Agent State | Session |
| **暂停/恢复** | ✅ Event Sourcing Replay | ✅ Checkpoint 恢复 | ✅ Flow @persist() | ❌ 有限 | ❌ |
| **人工介入** | Policy Gate + Verifier Gate | `interrupt()` 原语 | Human-in-the-loop | UserProxyAgent | ❌ |

### 5.4 治理与可观测

| 维度 | Zelos | LangGraph | CrewAI | AutoGen/MAF | OpenAI Agents SDK |
|------|-------|-----------|--------|-------------|-------------------|
| **Policy 引擎** | ✅ Policy Plugin | ❌ | ❌ (Rules 有限) | ❌ | Guardrails |
| **审计链** | ✅ causation_id 完整因果链 | LangSmith (外部) | ❌ | OpenTelemetry | Tracing |
| **不可变事件** | ✅ Event Bus 追加写入 | ❌ State 可变 | ❌ | ❌ | ❌ |
| **Verification** | ✅ Verifier Plugin (可替换) | ❌ 需手动实现 | ❌ | ❌ | Guardrails |
| **Capability Registry** | ✅ 核心组件 | ❌ | ❌ | ❌ | ❌ |
| **重试策略** | ✅ Scheduler 多策略重试 | ❌ 手动实现 | ✅ max_retry_limit | ❌ | ❌ |

### 5.5 生态与成熟度

| 维度 | Zelos | LangGraph | CrewAI | AutoGen/MAF | OpenAI Agents SDK |
|------|-------|-----------|--------|-------------|-------------------|
| **开发状态** | 架构阶段 | **生产就绪 (1.0)** | **生产就绪 (1.x)** | 维护+迁移中 | **生产就绪** |
| **企业采用** | 无 | Klarna/Uber/LinkedIn/Elastic | 多个企业案例 | 研究/原型为主 | OpenAI 生态 |
| **社区规模** | 新项目 | 65M+ 月下载 | 51K+ Stars | 50K+ Stars | OpenAI 官方 |
| **MCP 支持** | ✅ Adapter Plugin | ✅ | ✅ | ✅ MAF 原生 | ✅ |
| **A2A 支持** | ✅ Adapter Plugin | 社区 | ✅ AMP 企业版 | ✅ MAF | ❌ |
| **多语言 SDK** | 规划中 (Python/Go/Java/Rust) | Python + TS | Python | Python + .NET | Python + TS |

---

## 6. Zelos 的独特差异化

基于以上全面对比，Zelos 在以下维度拥有**任何其他项目都不具备的独特差异化**：

### 差异化 1：LLM 零依赖（Invariant 13）

**所有竞品都深度绑定 LLM**。LangGraph 的 Node 通常是 LLM 调用，CrewAI 的 Agent.llm 是核心属性，AutoGen 的 GroupChat 依赖 LLM 发言者选择，OpenAI Agents SDK 深度依赖 OpenAI。

Zelos 的 Runtime 不知道 Claude/GPT/Gemini 的存在。Agent 可能内部使用 LLM，但 Runtime 完全不关心。

**这意味着**：
- Zelos 可以编排任何类型的 Agent——LLM Agent、规则引擎 Agent、人类 Agent
- Zelos 不受任何模型厂商的战略变化影响
- Zelos 可以在模型不可用的环境中运行（如内网/合规环境的部分工作流）

### 差异化 2：宪法性三权分立

**没有任何竞品在架构层面做 Planner ≠ Scheduler ≠ Verifier 的权力分割**。

所有竞品都将规划、调度、执行的权力混在一起：
- LangGraph：图定义就是规划 = 执行
- CrewAI：Manager Agent 同时规划 + 调度 + 执行
- AutoGen：GroupChat Manager 同时选择发言者（调度）+ 评估终止（验证）

Zelos 的分离意味着：
- 更换 Planner 不影响 Scheduler 行为
- Verifier 可以独立于执行链升级
- 任何单一组件故障不会导致全局治理失效

### 差异化 3：Capability 分发（非名称分发）

**只有 Zelos 和 meta-agent 采用纯 Capability 分发**。

```
# 其他框架
Task → "send this to claude-code"        # 名称耦合

# Zelos
Task → requires: "code-generation.python"  # 能力描述
        → Capability Registry: [Claude Code, Codex, Local Agent]
        → Scheduler: 选择最佳 Provider
```

这意味着：
- Agent 可以热替换（同一个 Capability 多个 Provider）
- 支持 A/B 测试和灰度（Scheduler 动态调整权重）
- Agent 市场成为可能（任何实现 Capability 的 Agent 都可以接入）

### 差异化 4：语言无关的 Agent 模型

Zelos 的 Agent 是**外部进程**，只需实现 5 个 API。所有竞品都需要 Agent 使用特定语言：
- LangGraph / CrewAI / AutoGen / OpenAI Agents SDK → Python
- LangGraph → Python + TypeScript
- MAF → Python + .NET

Zelos 的 Agent 可以用 Rust、Go、Java、Zig、Bash 或任何语言编写——只要能通过 Runtime API 通信。

### 差异化 5：不可变事件审计链

Zelos 的 Event Bus 是**追加写入、不可变、带 causal chain**（`correlation_id` + `causation_id`）。

这意味着：
- 完整的审计追踪：任何状态都可以回溯到触发它的 Event
- 确定性回放：重放 Event Store 可以重建任何时刻的状态
- 合规保证：企业审计需求天然满足

### 差异化 6：15 条 Architecture Invariants

没有任何竞品有同等级别的架构约束力。Zelos 的 Invariants 是**宪法级设计约束**——任何实现冲突以 Invariant 为准。

这保证了：
- 项目规模的扩大不会导致架构退化
- 新贡献者可以在清晰的约束下工作
- 不会出现"框架腐化"（框架随功能增长而丧失核心哲学）

### 差异化 7：纯 Runtime 定位

Zelos **不构建 Agent**，只**运行 Agent**。

这与所有其他项目形成根本区别：
- LangGraph/CrewAI/AutoGen：提供 Agent 的**构建工具**
- Zelos：提供 Agent 的**运行环境**

这个区别就像"给我造房子的工具"（框架）vs "给你一套城市基础设施"（Runtime）。

---

## 7. 竞争定位与生态关系

### 7.1 Zelos 不是任何框架的替代品

Zelos 和 LangGraph/CrewAI/AutoGen 不在同一个赛道：

```
┌─────────────────────────────────────────────────┐
│              应用层 (Application)                │
├─────────────────────────────────────────────────┤
│            Agent 构建框架 (Build-time)            │
│  LangGraph  /  CrewAI  /  AutoGen  /  OA SDK    │
│  "构建一个 Agent 需要什么？"                      │
├─────────────────────────────────────────────────┤
│          Agent Runtime (Run-time)               │
│                   Zelos                          │
│  "100 个 Agent 如何协同完成一个 Goal？"            │
├─────────────────────────────────────────────────┤
│          Agent Harness (Agent-internal)          │
│       Harness Engineering / Agent Loop           │
│  "一个 Agent 内部如何可靠运行？"                   │
└─────────────────────────────────────────────────┘
```

### 7.2 潜在生态关系

**Zelos + LangGraph**：
- LangGraph Agent 作为一个 Zelos Agent 注册，内部使用 StateGraph 完成复杂推理，对外只暴露 5 个 API

**Zelos + CrewAI**：
- CrewAI Team 作为一个 Zelos Agent 注册，内部使用 Role-based 协作，对外呈现为一个 Capability

**Zelos + OpenAI Agents SDK**：
- OpenAI Agent 注册到 Zelos Capability Registry，Zelos Scheduler 决定何时调用

**Zelos + Harness Engineering**：
- Agent 开发者使用 Harness 工程模式构建 Agent（Loop/Memory/Guardrails）
- 然后将 Agent 注册到 Zelos Runtime
- Zelos 负责多个这样的 Agent 的协调和治理

### 7.3 竞争风险（更新）

| 风险 | 等级 | 说明 |
|------|------|------|
| **LangGraph 增加调度层** | 🟡 中 | 如果 LangGraph 在 StateGraph 之上增加 Agent Pool + Capability Dispatch，可能部分覆盖 Zelos 的定位 |
| **CrewAI 增加能力注册** | 🟢 低 | CrewAI 的角色模型与 Capability 模型有根本性冲突 |
| **MAF Workflow 扩展** | 🟡 中 | Microsoft Agent Framework 的 Workflow 原语可能向编排方向演进 |
| **Harness Engineering 向上扩展** | 🟡 中 | 如果 Harness 的多 Agent 模式从 Agent 内部实现提升为独立调度层 |
| **新 Runtime 项目入场** | 🟡 中 | "Agent Runtime"概念持续升温，预计 2026 H2–2027 H1 会有新进入者 |

---

## 8. 结论

1. **Zelos 的定位在市场上没有完全对标者**：LLM 无关 + 三权分立 + Capability 分发 + 不可变审计 + 纯 Runtime = 空白赛道

2. **Zelos 与现有框架不构成直接竞争**：LangGraph/CrewAI/AutoGen 是 Agent 构建层的工具，Zelos 是 Agent 运行层的 Runtime。它们是上下游关系，不是替代关系。

3. **Harness 是 Zelos 的互补概念，不是竞品**：Harness Engineering 解决"单个 Agent 如何可靠运行"，Zelos 解决"多个 Agent 如何协同完成 Goal"。一个 Zelos Agent 内部完全可以使用 Harness Engineering 模式。

4. **窗口期有限**：2026 H2–2027 H1 是最佳切入窗口。行业正在从"Agent 框架"向"Agent Runtime"过渡，但尚未有成熟的生产级 Runtime 出现。

5. **Zelos 的最大挑战不是技术，而是认知**：开发者已经习惯了"框架"思维（给我工具让我构建），需要教育市场接受"Runtime"思维（给你运行环境，你只需注册 Agent）。

---

> 📄 **此文档位置：** `docs/zelos-vs-frameworks-analysis.md`
>
> 参考：
> - [Zelos 竞争格局分析](./competitive-analysis.md)
> - [Architecture Invariants](./architecture/invariants.md)
> - [ADR-0000: Why Zelos Exists](./adr/ADR-0000-why-zelos-exists.md)
> - [Domain Model](./blueprint/domain-model.md)
