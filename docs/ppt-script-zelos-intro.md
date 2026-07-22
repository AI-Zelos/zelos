# Zelos PPT 脚本

> PPT 脚本 — 用于制作 Zelos 介绍演示文稿的完整文案与视觉指引。
> 主线：Zelos 是什么、解决什么问题、怎么设计、架构、优势、怎么用、带来什么价值。
> 支线：Zelos 与 Agent City 概念的关联（NEF 白皮书）— 仅在相关处自然提及。
> 设计风格关键词：**科技感、极简、深色背景、霓虹蓝/紫色调、网格线条、代码美学**

---

## Slide 1 — 封面

**标题：** Zelos

**副标题：** Open Multi-Agent Orchestration Runtime

**标语：** 管理 Goals 的 Runtime，如同 Linux 管理进程，Kubernetes 管理容器。

**视觉建议：**
- 深空黑背景，中央一个发光的蓝色核心（代表 Runtime Kernel），周围环绕多个小型节点（代表 Agents），由细光线连接。
- 底部小字：`Phase 2 Complete · v0.2.0 · Apache 2.0`

**演讲者备注：**
大家好，今天我要介绍的是 Zelos——一个面向多智能体协同的开源编排运行时。它不是又一个 Agent 框架，而是重新思考了 AI 系统底层基础设施的产物：当你的系统里有几十上百个 Agent 需要协作时，谁来负责规划、调度、验证和审计？这就是 Zelos 要做的事。

---

## Slide 2 — 我们面临什么问题？

**标题：** 问题：多 Agent 协同的编排危机

**核心矛盾：**

```
一个用户请求，可能需要：

  规划 ──→ 研究 ──→ 编码 ──→ 浏览器自动化 ──→ 数据库查询 ──→ 验证 ──→ 人工审批

                    ↑  每个环节由不同的 Agent 提供  ↑
```

**现有方案的局限：**

| 方案 | 问题 |
|------|------|
| Agent 框架 (LangGraph, CrewAI) | 把 Agent 构建和编排耦合在一起，Agent 自己管自己 |
| 工作流引擎 (Temporal, Airflow) | 为确定性代码设计，不适合自主 Agent 的非确定性行为 |
| MCP / A2A 协议 | 解决了通信问题，但不解决谁来治理的问题 |
| 手动脚本 | 无法规模化，没有治理，没有可观测性 |

**结论框（高亮）：**

> 问题不再是"如何构建一个 Agent"
> 而是 **"如何可靠地编排成百上千个独立、异构的 Agent 来完成一个目标"**

**视觉建议：**
- 左侧：混乱的 Agent-to-Agent 网状直连（红色线条，代表反模式）
- 右侧：一个中央调度节点接管所有连接（蓝色，代表 Zelos 的解法）
- 底部：现有工具局限对比表

**演讲者备注：**
现代 AI 应用已经不再是调用一个模型那么简单。一个真实的业务需求从规划到执行到验证需要多个不同能力的 Agent 协同完成。现有方案要么把编排逻辑硬编码在 Agent 内部，要么根本不适合 Agent 的非确定性行为。MCP 和 A2A 协议让 Agent 之间可以通信，但通信不等于治理——就像一个城市有了高速公路，不代表有了交通法规。市场上缺失了一个关键的层级：Runtime 层。

---

## Slide 3 — Zelos 是什么？

**标题：** Zelos：多智能体编排的 Runtime

**核心定位：**

```
┌──────────────────────────────────────────────────────────────┐
│                                                               │
│     Linux     管理  Processes   →  CPU / Memory / I/O         │
│     Kubernetes 管理 Containers  →  调度 / 扩缩容 / 网络       │
│     Temporal  管理  Workflows  →  执行 / 重试 / 状态          │
│                                                               │
│     ★ Zelos   管理  Goals      →  规划 / 调度 / 协同 / 验证   │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

**一句话定义：**

> Zelos 不构建 Agent。Zelos **运行** Agent。

**三个关键词：**
- 🎯 **Goal 驱动** — 声明你要什么，Runtime 规划怎么做，Agent 只管执行
- ⚡ **Capability 分发** — 按"能做什么"匹配 Agent，不按名字指定
- 🔌 **Agent 即插件** — Agent 只负责执行 Task，规划/调度/验证/审计都由 Runtime 负责

**视觉建议：**
- 类比表格用深色卡片呈现，Zelos 那一行用霓虹蓝高亮
- 三个关键词用图标 + 简短文字横向排列

**演讲者备注：**
Zelos 的定位非常清晰——它和 Linux、Kubernetes、Temporal 是同一类基础设施软件。它们都管理某种"执行单元"的完整生命周期。Zelos 管理的执行单元就是 "Goal"——一个由多个 Agent 协同完成的目标。关键区别是：Builder 构建 Agent，Zelos 运行 Agent。Agent 只需要注册能力、接收 Task、执行、返回结果，其余一切由 Runtime 包办。

---

## Slide 4 — Zelos 不是什么（划清边界）

**标题：** 明确边界：Zelos 拒绝成为什么

| 不是 | 为什么 |
|------|--------|
| ❌ Agent Framework | 不规定如何构建 Agent |
| ❌ Workflow Engine | 不定义静态 DAG，执行计划是由 Goal 动态派生的 |
| ❌ Prompt Framework | 不管理 Prompt，Agent 自己掌握 |
| ❌ LLM Wrapper | 不封装模型 API，Runtime 不知道 LLM 的存在 |
| ❌ LangGraph / CrewAI 替代品 | 那些是 Agent 构建工具包，Zelos 是基础设施层 |
| ❌ Marketplace / SaaS | 这些是未来的生态项目 |

**核心信息框：**

> Zelos 只做一件事：**接受 Goal，规划执行，调度 Agent，验证结果，全程审计。**

**视觉建议：**
- 左侧"不是"列表用红色叉号，右侧解释用灰色文字
- 底部核心信息用大号霓虹蓝字体突出

**演讲者备注：**
在这里我想特别强调 Zelos 不是什么。市场上有很多优秀的 Agent 框架（LangGraph、CrewAI），它们解决的是"如何构建 Agent"的问题。Zelos 解决的是另一个层面的问题——当你有了一群 Agent 之后，如何让它们有序地协同工作，并且整个过程可治理、可审计。这种边界感是 Zelos 设计的基石。

---

## Slide 5 — 设计哲学

**标题：** 设计哲学：一切从 Runtime 出发

**六大设计原则：**

| 原则 | 含义 |
|------|------|
| 🔒 **Runtime First** | Runtime 拥有调度/重试/验证/记忆/策略/生命周期；Agent 只管执行 |
| 🏷️ **Capability First** | 分发由 Capability 驱动，不由 Agent 名字驱动——公开招标，不指定供应商 |
| 📋 **Execution Plan First** | 执行计划先于任何 Agent 调用而存在——先有法律，后有执法 |
| 📡 **Event Driven** | 每个状态变化都是一个不可变事件，组件间无直接调用 |
| 🔌 **Plugin Architecture** | Kernel 之上的一切皆可替换——宪法不改，机构可换 |
| 📐 **Specification First** | 规格先行，代码在后——先立法，后施工 |

**设计上的"宪法性约束"：**

> Runtime 拥有规划/调度/验证三种权力，Agent 只有执行权。
> 这套职责分割天然实现了一种**三权分立**——没有任何一个 Agent 能同时制定计划、执行操作、评判自己的产出。

**演讲者备注：**
这六大原则构成了 Zelos 的设计宪法。最重要的两条：Runtime First 意味着所有编排权在 Runtime，Agent 永远不能自己制定规则然后执行。Capability First 意味着按"能做什么"招标，而不是直接指定"让 Claude 做"。这套设计天然把规划权、执行调度权、验证权分到了三个独立组件——Planner、Scheduler、Verifier——没有任何一个 Agent 能同时拥有这三者。这恰好也是 NEF 白皮书中 "Agent Enterprise for Enterprise" 理念所强调的治理架构方向。

---

## Slide 6 — 核心概念：Runtime 与 Agent 的职责分割

**标题：** 职责分离：谁拥有什么

```
┌─────────────────────────────────────┐  ┌─────────────────────┐
│           RUNTIME 拥有              │  │    AGENT 拥有        │
│                                     │  │                      │
│  规划：Goal → ExecutionPlan         │  │  接收 Task           │
│  调度：匹配 Task → Agent            │  │  执行                │
│  验证：Artifact 质量审查             │  │  产出 Artifact       │
│  重试：决策/退避/Fallback           │  │                      │
│  记忆：6 层上下文管理               │  │  ❌ 制定计划          │
│  策略：Allow/Reject/Delay            │  │  ❌ 调用其他 Agent    │
│  生命周期：Task/Goal 完整管理        │  │  ❌ 管理记忆          │
│  审计：完整 Event 记录               │  │  ❌ 重试失败任务      │
│                                     │  │  ❌ 修改执行计划      │
│                                     │  │  ❌ 知道其他 Agent    │
└─────────────────────────────────────┘  └─────────────────────┘
```

**Agent 的 API 契约 — 只有 5 个方法：**

```python
register()    # 注册能力
heartbeat()   # 心跳保活
execute()     # 执行 Task，返回 Artifact
cancel()      # 取消正在执行的任务
shutdown()    # 优雅退出
```

**演讲者备注：**
这是 Zelos 架构中最核心的一张图。左边的所有职责都属于 Runtime，右边的 Agent 只需要实现 5 个方法。Agent 不能调用其他 Agent，不能自己重试，不能修改执行计划——它就像一个城市里的专业服务商，只管被分配的工作任务。这种极端的职责分离是实现规模化编排的基础，也是 Zelos 区别于所有 Agent 框架的根本特征。

---

## Slide 7 — 架构全景图

**标题：** 架构总览

```
                          ┌────────────────────────────┐
                          │          CLIENT             │
                          │  SDK / CLI / REST / gRPC    │
                          └─────────────┬──────────────┘
                                        │
                                        ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                             ZELOS RUNTIME                              │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                         API LAYER                                   │  │
│  │        Goal API  │  Agent API  │  Admin API  │  SDK Bindings       │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                    │                                     │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                        RUNTIME KERNEL  (宪法性核心，6 组件)         │  │
│  │                                                                    │  │
│  │  Goal → Planner → ExecutionPlan → TaskGraph → Scheduler            │  │
│  │         (制定计划)                  (管理依赖)    (招标匹配)         │  │
│  │                                    │                               │  │
│  │                                    ▼                               │  │
│  │                        Capability Registry                         │  │
│  │                        (能力黄页 — 谁能做什么)                       │  │
│  │                                    │                               │  │
│  │                                    ▼                               │  │
│  │                          Execution Engine                           │  │
│  │                       (派发/心跳监控/超时/取消)                      │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                    │                                     │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                     RUNTIME INFRASTRUCTURE                          │  │
│  │  EventBus (不可变公共记录) │ Memory │ Policy │ Verifier (质量审查)  │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                    │                                     │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                       PLUGIN INTERFACES (6 种可替换插件)            │  │
│  │ Planner │ Verifier │ Memory Provider │ Policy │ Storage │ Adapter   │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
                 │
                 ▼  通信协议层 (管道，不提供治理)
      HTTP / gRPC / MCP / A2A / stdio
                 │
                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                               AGENTS                                     │
│ Claude │ Gemini │ Codex │ Browser │ SQL │ Search │ Custom ...           │
└──────────────────────────────────────────────────────────────────────────┘
```

**演讲者备注：**
这是 Zelos 的架构全景图。从上到下：Client 接入层 → Runtime 核心（API → Kernel → Infrastructure → Plugin）→ 通信协议层 → Agent 执行层。注意中间 Kernel 只包含 6 个不可替换的组件——这是 Zelos 的宪法性核心。外面的 Plugin 层包含 Planner、Verifier、Policy 等 6 种可替换插件——你可以换不同的规划策略、验证策略，但不能绕过它们。而 MCP 和 A2A 协议在 Runtime 之下，是通信管道，不是治理层。

---

## Slide 8 — 深入 Kernel：六大核心组件

**标题：** Kernel：6 个不可替换的编排核心

```
┌────────────┐  ┌────────────┐  ┌────────────┐
│ Event Bus  │  │ Capability │  │ Task Graph │
│ 事件总线    │  │ Registry   │  │  Engine    │
│            │  │ 能力注册中心│  │ 任务图引擎  │
│ 所有通信的  │  │            │  │            │
│ 唯一通道    │  │ 按能力索引  │  │ DAG 状态机  │
│ 不可变追加  │  │ 所有 Agent  │  │ 依赖解析    │
└─────┬──────┘  └─────┬──────┘  └─────┬──────┘
      │               │               │
      └───────────────┼───────────────┘
                      │
      ┌───────────────┼───────────────┐
      │               │               │
┌─────▼──────┐  ┌─────▼──────┐  ┌─────▼──────┐
│ Scheduler  │  │ Execution  │  │   Plugin   │
│ 调度器      │  │  Engine    │  │  Lifecycle │
│            │  │ 执行引擎    │  │  Manager   │
│ 5 阶段决策  │  │            │  │ 插件生命周期│
│ 匹配 Task  │  │ 派发/心跳/  │  │ 管理        │
│ → Agent    │  │ 超时/取消  │  │            │
└────────────┘  └────────────┘  └────────────┘
```

**为什么它们在 Kernel？**

> "只有移除后会破坏多 Agent 编排能力，且无法作为可替换插件实现的东西，才属于 Kernel。"

**演讲者备注：**
Kernel 是 Zelos 的心脏，只有 6 个组件。Event Bus 是通信骨干——所有组件通过不可变事件通信，不直接调用。Capability Registry 维护所有 Agent 能力索引——你想知道"谁有 code-generation.python 能力？"就来这查。Task Graph Engine 管理任务 DAG 状态机和依赖——任务 B 必须等任务 A 完成才能开始。Scheduler 执行 5 阶段调度决策选出最佳 Agent。Execution Engine 负责与 Agent 的实际通信、心跳监控、超时和取消。Plugin Lifecycle Manager 管理所有插件的加载和健康检查。

---

## Slide 9 — 调度器：5 阶段智能匹配

**标题：** Scheduler：Task 与 Agent 的智能匹配引擎

```
Ready Tasks
    │
    ▼
┌──────────────────────────────────────────────────────────┐
│ Phase 1: ORDER   按优先级 > 截止时间 > 下游依赖数 > FIFO   │
├──────────────────────────────────────────────────────────┤
│ Phase 2: FILTER  硬约束过滤（11 项检查）                   │
│  能力匹配 · 版本兼容 · Agent 存活 · 容量充足               │
│  预算未超 · 截止可行 · 成功率门槛 · 标签匹配 · 策略放行    │
├──────────────────────────────────────────────────────────┤
│ Phase 3: SCORE   7 因子加权评分                           │
│  成功率 30% + 成本 20% + 负载 15% + 延迟 15%              │
│  + 可用性 10% + 亲和性 5% + 新鲜度 5%                     │
├──────────────────────────────────────────────────────────┤
│ Phase 4: POLICY  策略插件二次审查                         │
│  决策：Allow / Reject / Delay                             │
├──────────────────────────────────────────────────────────┤
│ Phase 5: SELECT  选出最高分候选 Agent                     │
└──────────────────────────────────────────────────────────┘
    │
    ▼
  Dispatch → Execution Engine
```

**设计亮点：**
- 成功率权重最高（30%）→ 声誉好的 Agent 积累更多机会，不诚实者自然淘汰
- 成本+延迟占 35% → 市场竞争，鼓励 Agent 提供更优服务
- Policy 门 → 合规约束可以否决效率优先的决策

**演讲者备注：**
调度器是 Zelos 的决策大脑。它不是简单的轮询或随机选择——而是一个 5 阶段流水线。最值得注意的是 30% 的权重给了历史成功率，这意味着声誉是最重要的竞争要素。这天然形成了一个基于信任的市场机制：表现好的 Agent 获得更多任务，表现差的被自然淘汰。这种基于声誉的调度机制，恰好能与 NEF 白皮书中描述的 "Agent 基于链上声誉竞标任务" 的市场模型无缝对接。

---

## Slide 10 — Event Bus：不可变的通信骨干

**标题：** Event Driven：一切状态变化都是不可变事件

**Event 的属性：**
- 🔒 **不可变** — 发布后不可修改，只能追加纠正事件
- ➕ **追加写入** — 只追加，永不删除
- 🏷️ **强类型** — `domain.entity.action` 层级命名（如 `task.completed`）
- ⏱️ **时间戳** — 精确记录发布时间
- 🔗 **关联 ID** — 同一条链上的事件通过 correlation_id 串联
- 🧬 **因果链** — causation_id 追踪前因后果

**事件类型（节选，共 30+ 种）：**

```
goal.submitted → goal.accepted → goal.planned → goal.executing → goal.completed
plan.created  → plan.validated  → plan.executing → plan.modified → plan.completed
task.created  → task.ready → task.assigned → task.started → task.completed
agent.registered → agent.connected → agent.heartbeat → agent.disconnected
artifact.created → artifact.validated → artifact.accepted
```

**为什么重要：**

> 从 Goal 提交到最终完成，每一个决策步骤、每一次 Agent 交互都形成一条不可篡改的完整记录。这既是调试工具，也是合规证据——当监管机构问"你的 Agent 为什么做了这个决定"，你可以精确还原整个推理链。

**演讲者备注：**
在 Zelos 中，一切通信都是事件。这提供了两个关键价值：第一，Event Store 天然支持事件溯源和故障恢复——崩溃后可以从最近的快照 + 事件重放恢复状态。第二，完整的审计追踪——从 Goal 提交到最终产出，每一步都有不可篡改的记录。这在欧盟 AI 法案等监管框架下，是合规的基础设施。

---

## Slide 11 — Plugin 生态：宪法不改，机构可换

**标题：** 插件架构：密封的 Kernel × 可替换的 Plugin

```
┌──────────────────────────────────────────────────────────┐
│                    PLUGIN ECOSYSTEM                       │
│                 (可替换的治理机构)                         │
│                                                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│  │ Planner  │ │ Verifier │ │  Policy  │ │  Memory  │    │
│  │ 规划器    │ │ 验证器    │ │  策略    │ │  记忆    │    │
│  │          │ │          │ │          │ │          │    │
│  │ LLM-based│ │ Code     │ │ Cost     │ │ In-Memory│    │
│  │ Template │ │ Security │ │ Rate     │ │ Redis    │    │
│  │ Human    │ │ Schema   │ │ Allowlist│ │ Vector DB│    │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘    │
│                                                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────────┐      │
│  │ Storage  │ │ Protocol │ │       Agent          │      │
│  │ 存储      │ │ Adapter  │ │     (也是 Plugin)    │      │
│  │          │ │ 协议适配 │ │                      │      │
│  │ PG/Kafka│ │ HTTP/gRPC│ │ 任意语言 任意框架     │      │
│  │ NATS/内存│ │ MCP/A2A  │ │                      │      │
│  └──────────┘ └──────────┘ └──────────────────────┘      │
│                                                           │
│  ┌────────────────────────────────────────────────────┐  │
│  │         SEALED KERNEL (不可替换的宪法性核心)        │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

**演讲者备注：**
Zelos 采用严格的插件架构。Kernel 是密封的——它只知道 Plugin 的接口，永远不知道具体实现。6 种插件类型都可以替换：你可以用 LLM Planner 也可以用模板 Planner；可以用内存做 Event Store，也可以接入 Kafka 做持久化；可以加一个成本控制策略，也可以加一个合规审核策略。Agent 本身在 Zelos 眼中也是一种插件——一个外部进程，通过标准 API 与 Runtime 交互。这种架构保证了系统既有宪法的稳定性，又有治理机构的灵活性。

---

## Slide 12 — Capability First 分发模型

**标题：** 按 Capability 分发：公开招标，不指定供应商

**分发链路：**

```
Task 需要: "code-generation.python"
       │
       ▼
┌─────────────────────┐
│ Capability Registry │  查找所有注册此能力的 Agent
│                     │
│  Provider A: 成功率  │
│  94%, $0.02/call    │
│  Provider B: 成功率  │
│  87%, $0.01/call    │
│  Provider C: 成功率  │
│  99%, $0.05/call    │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│     Scheduler       │  7 因子加权评分
│                     │
│  Provider C: 0.89 ★ │  ← 最高分，中标
│  Provider A: 0.82   │
│  Provider B: 0.71   │
└─────────┬───────────┘
          │
          ▼
    Provider C 收到 Task
    它不知道自己"被选中"——只知道被"派发"
```

**Capability 命名规范：**

```
✅ code-generation.python     描述：能做什么
✅ code-review.security        描述：审查什么
✅ research.web-search         描述：搜索什么

❌ claude-code                 绑定特定 Agent（禁止）
❌ gpt4-generation             绑定特定模型（禁止）
```

**演讲者备注：**
你永远不会说"把这个任务发给 Claude"。你说"我需要 code-generation.python 能力"，Capability Registry 找到所有提供这个能力的 Agent，Scheduler 根据成功率、成本、延迟等因素选择最优的。如果明天出现一个更好的 Code Agent，注册进来即可参与竞争。这实现了供应商中立——不被任何模型或 Agent 锁定。

---

## Slide 13 — 执行模型：Goal 的完整生命周期

**标题：** 一个 Goal 从提交到完成的完整旅程

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  GOAL    │───→│   PLAN   │───→│  TASK    │───→│ SCHEDULE │───→│ EXECUTE  │───→│  VERIFY  │
│SUBMISSION│    │CREATION  │    │  GRAPH   │    │          │    │          │    │          │
│          │    │          │    │          │    │          │    │          │    │          │
│ 提交目标  │    │ Planner  │    │ 任务 DAG │    │ Scheduler│    │Execution │    │ Verifier │
│          │    │ 分解为   │    │ 依赖管理 │    │ 招标匹配 │    │Engine    │    │ 质量审查 │
│          │    │ Task...  │    │          │    │          │    │ 派发监控 │    │          │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
     │               │               │               │               │               │
     ▼               ▼               ▼               ▼               ▼               ▼
   Goal           Planner          Task            Scheduler      Execution       Verifier
  Accepted       (Plugin)         Graph           (Kernel)        Engine         (Plugin)
                                  Engine                          (Kernel)
                                  (Kernel)
```

**完整事件链（Logic Pedigree）：**

```
goal.submitted → plan.created → task.ready → task.assigned →
task.started → artifact.created → artifact.validated →
artifact.accepted → task.completed → goal.completed
```

**故障处理机制：**

```
Task Failed
  → 指数退避重试（含随机抖动，防惊群效应）
  → Smart Retry（优先切换到不同 Agent，避免重复相同错误）
  → Fallback Capability（降级到备用能力）
  → 重试耗尽 → 触发 Planner 动态重规划
  → 最终失败 → 完整审计记录，可追溯责任
```

**演讲者备注：**
一个 Goal 从提交到完成，经历了 6 个阶段。每一步都产生不可变事件，形成完整的 Logic Pedigree——从最开始的 Goal 到最终的产出物，每一步都可追溯。故障处理机制内建了三层保护：指数退避重试、智能切换 Agent、备用能力降级，穷尽所有恢复手段后才标记失败——而且每一步都有审计记录。

---

## Slide 14 — Task 状态机

**标题：** Task：最小的原子调度单元

```
                         ┌──────────┐
                         │ Created  │  ← Planner 创建
                         └────┬─────┘
                              │ 依赖满足
                         ┌────▼─────┐
                    ┌───→│  Ready   │←──────────────┐  ← 可被 Scheduler 调度
                    │    └────┬─────┘               │
                    │         │ Scheduler 分配       │
                    │    ┌────▼─────┐               │
                    │    │ Assigned │               │
                    │    └────┬─────┘               │
                    │         │ Agent 接受          │
                    │    ┌────▼─────┐               │
                    │    │ Started  │               │
                    │    └────┬─────┘               │
                    │         │                     │
                    │    ┌────┼────────────┐        │
                    │    │    │            │        │
                    │    ▼    ▼            ▼        │
                    │ ┌────┐┌──────┐┌──────────┐   │
                    │ │Done││Failed││TimedOut  │   │
                    │ └──┬─┘└──┬───┘└────┬─────┘   │
                    │    │     │         │         │
                    │    ▼     ▼         ▼         │
                    │ ┌──────────────────────┐     │
                    │ │   Retry Evaluation   │─────┘
                    │ └──────────┬───────────┘
                    │            │ 重试耗尽
                    │            ▼
                    └────── Failed (Terminal)

                           ┌──────────┐
                           │Completed │ (Terminal)
                           └──────────┘
```

**关键约束：**
- 一个 Task = 一次 Agent 调用（原子性）
- Agent 不能产生子 Task（防止权力扩散）
- Agent 不能调用其他 Agent（防止不受控协同）
- Agent 不能修改 Task Graph（防止篡改规则）

**演讲者备注：**
Task 是 Zelos 中的原子调度单元。8 个状态覆盖从创建到终态的完整生命周期。关键约束是：一个 Task 等于一次 Agent 调用，Agent 执行期间不能产生子任务、不能调用其他 Agent、不能修改依赖图。这些约束确保了 Runtime 始终掌握全局编排权——任何一个 Agent 的行为都不会导致编排拓扑的不可控变化。

---

## Slide 15 — Phase 2 新能力：多层验证流水线

**标题：** Production-Grade Verifier Pipeline：代码进入系统前过四道关卡

**四级验证链：**

```
Agent 产出 Artifact
      │
      ▼
┌─────────────────────────────────────────────────────────┐
│  VERIFICATION GATE (顺序执行，首次失败即短路)             │
│                                                         │
│  1️⃣  SchemaVerifier   → JSON Schema 类型校验              │
│  2️⃣  CodeReviewer     → 语法错误 / eval() / 硬编码密码     │
│  3️⃣  SecurityScanner  → SQL 注入 / XSS / 命令注入 / 反序列化│
│  4️⃣  FactChecker      → 未来声明 / 不可验证主张            │
│                                                         │
│  全部通过 → Artifact Accepted → 下游 Task 可消费           │
│  任意失败 → Artifact Rejected → 触发重试 / 重规划          │
└─────────────────────────────────────────────────────────┘
```

**实际检测示例：**

| 代码 | 检测结果 |
|------|---------|
| `def hello(): return 'world'` | ✅ Passed |
| `x = eval(input())` | ❌ CodeReviewer: eval() is dangerous |
| `"SELECT * FROM users WHERE id=" + uid` | ❌ SecurityScanner: SQL injection |
| `password = "admin123"` | ❌ CodeReviewer: Hardcoded credential |

---

## Slide 16 — Phase 2 新能力：可观测性三件套

**标题：** Observability: Structured Logging + Metrics + Tracing

**三栏展示：**

```
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│  📝 结构化日志     │ │  📊 指标收集       │ │  🔍 分布式追踪     │
│  StructuredLogger │ │  MetricsCollector │ │  Tracer           │
│                  │ │                  │ │                  │
│  JSON 格式输出    │ │  Counter (累计)   │ │  Span 层级树       │
│  4 级别过滤       │ │  Gauge (瞬时)     │ │  parent-child     │
│  (debug→error)   │ │  Histogram (分布) │ │  关联              │
│                  │ │                  │ │                  │
│  可接 ELK/Loki   │ │  Prometheus 导出  │ │  OpenTelemetry    │
│                  │ │  p50/p95/p99     │ │  兼容格式          │
└──────────────────┘ └──────────────────┘ └──────────────────┘
```

**演讲者备注：**

Phase 2 补齐了生产环境所需的可观测性。结构化日志用 JSON 格式输出，支持 4 级过滤——可以直接接入 ELK 或 Loki。指标收集器提供 Counter / Gauge / Histogram 三种类型，支持 Prometheus 文本格式导出——可以直接接入 Grafana。追踪器支持 Span 层级和属性，格式兼容 OpenTelemetry。这三件套让 Zelos 从 "能跑" 变成 "能监控"。

---

## Slide 17 — Phase 2 新能力：协议适配器 + 插件隔离

**标题：** Protocol Adapters & Plugin Isolation：多协议接入 + 安全隔离

**四协议适配器：**

| Adapter | 协议 | 场景 |
|---------|------|------|
| **gRPC** | Protobuf / HTTP2 | 高性能服务间通信，SDK 底层协议 |
| **WebSocket** | 双向流 | 事件实时推送，Goal 进度订阅 |
| **MCP** | JSON-RPC | Agent 工具注册/调用，Tool Registry |
| **A2A** | Agent Card | 跨 Zelos Runtime 协作，外部 Agent 集成 |

**Plugin Isolation（子进程模式）：**

```
In-Process Mode        Sub-Process Mode (Phase 2)
───────────────        ──────────────────────────
Plugin 跑在 Runtime    Plugin 跑在独立进程
同一进程内              stdin/stdout JSON 协议
崩溃影响 Runtime       崩溃不影响 Runtime
延迟最低              隔离性最高
```

---

───

## Slide 18 — Phase 2 新能力：可插拔持久化存储

**标题：** Pluggable Storage：事件和状态不再丢失

**四种 Backend，统一接口：**

```
        ┌──────────────────────────────────┐
        │       StorageBackend (接口)       │
        │  connect / append / read / state │
        └──────────────┬───────────────────┘
                       │
        ┌──────────────┼──────────────┬──────────────┐
        ▼              ▼              ▼              ▼
   ┌─────────┐  ┌─────────┐  ┌───────────┐  ┌─────────┐
   │InMemory │  │  Redis  │  │PostgreSQL │  │  MySQL  │
   │  内存    │  │  List   │  │   JSONB   │  │  JSON   │
   │(开发/测试)│  │+ String │  │   events  │  │ events  │
   │         │  │         │  │  + state  │  │ + state │
   └─────────┘  └─────────┘  └───────────┘  └─────────┘
```

**zelos.yaml 一行切换：**

```yaml
# 开发环境 — 内存，重启丢失
storage:
  type: "memory"

# 生产环境 — PostgreSQL，持久化
storage:
  type: "postgresql"
  url: "postgresql://user:pass@host:5432/zelos"

# 高并发 — Redis，毫秒级读写
storage:
  type: "redis"
  url: "redis://localhost:6379/0"
```

**演讲者备注：**
Phase 2 补齐了持久化存储——所有 Event 和状态不再随重启丢失。开发者通过 zelos.yaml 一行配置即可在 InMemory / Redis / PostgreSQL / MySQL 之间切换——接口完全一致，代码零改动。生产环境用 PG 或 MySQL 做持久化，高并发场景用 Redis 做缓存加速。

---

## Slide 19 — 如何使用 Zelos

**标题：** 使用 Zelos 只需三步

**Step 1 — 构建一个 Agent：**

```python
from zelos_sdk.agent import Agent
from zelos_sdk.schema import Task, Artifact, CapabilityDeclaration

class MyCodingAgent(Agent):
    def declare_capabilities(self):
        return [
            CapabilityDeclaration(
                name="code-generation",
                version="1.0.0",
                description="Generates Python code",
                input_schema={"type": "object", "properties": {"spec": {"type": "string"}}},
                output_schema={"type": "object", "properties": {"code": {"type": "string"}}}
            )
        ]

    def execute(self, task: Task) -> Artifact:
        # 只需关注核心逻辑：收到什么 Task，产出什么 Artifact
        # 不需要关心谁派的、为什么要做、做完谁来验证
        code = self._call_my_llm(task.input.content["spec"])
        return Artifact(content_type="application/json", content={"code": code})
```

**Step 2 — 注册到 Runtime：**

```python
agent = MyCodingAgent(name="ClaudeCode", runtime_url="http://localhost:9876")
agent.run()  # SDK 自动处理：注册 → 心跳 → 接收 Task → 提交结果
```

**Step 3 — 提交 Goal：**

```python
from zelos_sdk.client import ZelosClient

client = ZelosClient(runtime_url="http://localhost:9876")
goal = client.submit_goal(
    description="Build an e-commerce website with React + FastAPI",
    budget=100.0,
    priority="high",
)
result = client.wait_for_goal(goal.goal_id)
print(f"Goal {result.status}: {result.progress.percent_complete:.0%}")
```

**演讲者备注：**
使用 Zelos 只需三步。第一步，继承 Agent 基类，重写两个方法：declare_capabilities() 和 execute()。第二步，启动 Agent——SDK 自动处理注册和心跳。第三步，通过 ZelosClient 提交一个 Goal，用自然语言描述你想要什么。剩下的——规划、调度、执行、重试、验证、审计——全部由 Runtime 处理。Agent 甚至不需要使用 Python SDK，可以用任何语言实现，只要实现 5 个 HTTP API 即可。

---

## Slide 16 — Zelos 的优势

**标题：** 为什么选择 Zelos？

| 优势 | 说明 |
|------|------|
| 🔓 **供应商中立** | Capability 分发不绑定任何 Agent 实现；Agent 可以用任何语言、任何模型 |
| 🏛️ **职责清晰** | Runtime 拥有全部编排权，Agent 只有执行权——极端解耦，各自独立演进 |
| 📡 **完全可观测** | 所有状态转换都是不可变 Event，形成完整审计链 |
| 🧩 **可组合性** | 不同来源、不同能力的 Agent 可以参与同一个 Goal 的执行 |
| 🔄 **弹性执行** | 内置重试、指数退避、Fallback 能力、Smart Retry、动态重规划 |
| 🌐 **协议无关** | 支持 HTTP / gRPC / MCP / A2A 多种协议，Agent 接入零摩擦 |
| 📐 **规格先行** | 15 条架构不变式 + ADR + Blueprint + RFC + Schema，设计与实现解耦 |
| 🔍 **多层验证** | SchemaVerifier → CodeReviewer → SecurityScanner → FactChecker 四级自动验证 |
| 📊 **可观测性** | 结构化 JSON 日志 + Prometheus 指标 + Span 层级追踪，即接即用 |
| 🌐 **多协议** | HTTP / gRPC / WebSocket / MCP / A2A，协议适配器即插即用 |
| 🚀 **生态友好** | Plugin 架构 + 子进程隔离 + 热加入/热退出 + 自定义评分策略 |

**演讲者备注：**
总结 Zelos 的核心优势：供应商中立意味着不被任何模型或 Agent 锁定；极端解耦允许 Runtime 和 Agent 独立演进；不可变 Event Store 提供完整的审计能力（在受监管行业这是刚需）；弹性执行机制保证系统可靠性；协议无关降低接入成本；规格先行保证架构一致性。

---

## Slide 19 — Zelos 的生态位

**标题：** Zelos 在 AI 技术栈中的位置

```
┌──────────────────────────────────────────────────────────┐
│                      APPLICATION                         │
│            (你的产品 —— Web App, API, Chatbot...)        │
└──────────────────────────┬───────────────────────────────┘
                           │ Submit Goal
                           ▼
┌──────────────────────────────────────────────────────────┐
│                   ★ ZELOS RUNTIME ★                      │
│                                                           │
│  规划 → 调度 → 派发 → 监控 → 验证 → 记忆 → 审计          │
│                                                           │
│  "Agent 世界的操作系统"                                    │
└────────┬──────────┬──────────┬──────────┬────────────────┘
         │          │          │          │
         ▼          ▼          ▼          ▼
    ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
    │ Claude │ │ Gemini │ │ Codex  │ │Custom  │
    │  Code  │ │ Coder  │ │        │ │ Agent  │
    └────────┘ └────────┘ └────────┘ └────────┘
```

**与现有方案的对比：**

| | LangChain/LangGraph | CrewAI/AutoGen | MCP / A2A | Temporal/Airflow | **Zelos** |
|---|---|---|---|---|---|
| 定位 | Agent 构建工具包 | Agent 角色协作 | Agent 通信协议 | 工作流执行引擎 | **Agent 编排 Runtime** |
| 抽象层级 | 链/图 | 角色/团队 | 传输协议 | 工作流/活动 | **Goal/Plan/Task** |
| Agent 模型 | 框架内耦合 | 框架内耦合 | 不涉及 | N/A (确定性代码) | **外部进程，任意语言** |
| 调度方式 | Prompt chain | 角色轮询 | N/A | 静态 DAG | **动态 Capability 匹配** |
| 审计追踪 | 无 | 无 | 无 | 有（确定性） | **不可变事件审计链** |
| 适用规模 | 1-5 Agent | 1-10 Agent | 不限（无治理） | 确定性工作流 | **100+ Agent** |

**演讲者备注：**
这张图展示了 Zelos 的生态位。它在 Application 和 Agent 之间，扮演着基础设施层的角色——就像 Linux 在 Application 和 Process 之间的位置。对比其他方案：LangGraph 和 CrewAI 是 Agent 构建工具包，它们定义 Agent 的行为方式；Temporal 是确定性工作流引擎；MCP 和 A2A 是通信协议，让 Agent 可以互操作——但它们都不提供治理。Zelos 是唯一一个把规划、调度、验证、审计整合在一个 Runtime 中的方案。

---

## Slide 18 — Zelos 带来的价值

**标题：** Zelos 带来的价值

**对开发团队：**
- 🎯 **聚焦业务逻辑** — 只需关注 Agent 的 execute() 方法，编排全部由 Runtime 处理
- 🧪 **可测试性** — SDK 提供 InMemoryRuntime 测试桩，Agent 可独立测试
- 🔧 **多语言支持** — Python / TypeScript / Go SDK，或直接用 HTTP

**对架构团队：**
- 📐 **架构一致性** — 15 条不变式保证所有组件遵循同一套设计约束
- 🔌 **技术无关** — Kernel 零 LLM 依赖，Agent 零 Runtime 依赖
- 📊 **全面可观测** — 每个状态变化都是不可变事件，天然支持 OpenTelemetry / Prometheus

**对业务决策者：**
- 💰 **成本可控** — Budget + Cost per call 约束 + Policy 强制
- 🔒 **供应商中立** — 不锁定任何模型或 Agent 提供商
- ⚖️ **合规原生** — 完整事件审计链，天然适配 EU AI Act 等监管要求
- 📈 **渐进式规模化** — 从单节点 (Phase 1) 到分布式集群 (Phase 3)
- 🏷️ **Apache 2.0 开源** — 基础设施不应被私有化

**底层价值：**

> Zelos 让你从"如何编排 Agent"的工程复杂性中解放出来，
> 将注意力重新聚焦到"Agent 应该做什么"的业务价值上。
> 同时，它的架构天然提供治理和审计——不需要事后补丁。

**演讲者备注：**
对开发者，它解放了你——你只写 execute()，Runtime 包办一切。对架构师，它给你宪法性保证——15 条不变式不会因为需求变更而腐化。对业务决策者，它给你合规原生——完整的审计链让监管报告自动生成。底层价值：Zelos 把 Agent 编排的工程复杂性变成 Runtime 的内置能力，让开发者回归到业务创新。

---

## Slide 19 — 延伸视角：Zelos 与 Agent City

**标题：** 延伸：Zelos 作为 Agent 数字文明的 Runtime 基础设施

> 本节为延展讨论——如果你关心的大图景是"成百上千个 Agent 构成的自主经济体"，
> Zelos 在其中扮演什么角色。

**NEF 白皮书描绘的愿景：**

NEF (NetX Enterprise Framework) 白皮书描绘了一个由自主 Agent 构成的数字文明——"Agent City"。这个文明需要四个层次：

| 层次 | 内容 | Zelos 的对应 |
|------|------|-------------|
| 🏛️ **宪法与法律** | System Constitution, Rules Hub | 15 条 Architecture Invariants |
| ⚙️ **执行引擎** | Task Hub, Scheduler, 8-Contract Stack | **← Zelos 的核心领域** |
| ⚖️ **司法与审计** | Judicial DAO, Logging Hub, Logic Pedigree | Event Bus + Verifier + Policy |
| 🌐 **经济与文化** | Agent Marketplace, $NETX, Social Layer | Capability Registry (能力市场基础) |

**核心关联：**

```
NEF 的核心观点：
  "当前 AI Agent 的危机不是技术 Bug，而是宪法性结构缺陷——
   一个 Agent 垄断了制定规则、执行操作、评判结果三种权力。"

Zelos 的架构回应：
  Planner (定规则) ≠ Scheduler (管执行) ≠ Verifier (判结果)
  三权分散在三个独立组件，Agent 只有执行权。
  这是架构层面的三权分立，而非事后添加的策略约束。
```

**Zelos 在 NEF 栈中的位置：**

NEF 描述的是一个完整文明蓝图——从硬件根信任到链上合约到社会治理。这个蓝图需要一个实际运转的 Runtime 来执行其核心循环（Goal → Plan → Task → Execute → Verify）。Zelos 提供的就是这一层。可以这样理解：

> **如果 NEF 是 Agent City 的宪法和蓝图，Zelos 就是它的操作系统。**

**演讲者备注（可选讲）：**
这一页是延伸视角。如果你关心的不只是"如何让 5 个 Agent 协同工作"，而是"一个由上百个 Agent 构成的自主经济体如何运转"——那 NEF 白皮书给出了一个宏大的蓝图。Zelos 在这个蓝图中的角色是 Runtime 层——它是让宪法和合约从文本变成可执行的软件系统的那一层。当然，这只是一个视角——Zelos 本身就是独立的基础设施，不依赖任何特定的上层框架。

---

## Slide 20 — 发展路线图

**标题：** 项目路线图

```
Phase 0  ✅  架构规格 (已完成 — 2026.07)
├─ 15 条架构不变式
├─ 6 个 ADR (架构决策记录)
├─ 12 个 Blueprint (架构蓝图)
├─ 4 个 RFC 骨架
├─ 6 个版本化的 JSON Schema
└─ 完整文档体系

Phase 1  ✅  Runtime Kernel (已完成 — 2026.07)
├─ 6 Kernel 组件 + Runtime API + HTTP Adapter
├─ LLM Planner (OpenAI/Anthropic/Google) + 自动编排循环
├─ SchemaVerifier + PolicyEngine (Cost/Rate/Allowlist)
├─ 6 层 Memory + zelos.yaml 配置加载
└─ Python SDK + 10 个可运行 Demo

Phase 2  ✅  Developer Platform (已完成 — 2026.07)
├─ Verifier Framework (CodeReviewer + SecurityScanner + FactChecker)
├─ Observability (StructuredLogger + Metrics + Tracing + Prometheus)
├─ Protocol Adapters (gRPC + WebSocket + MCP + A2A)
├─ Plugin Isolation (Sub-Process mode)
└─ 223 自动化测试 + 12 个 Demo

Phase 3  ⬜  Runtime Ecosystem
├─ 分布式 Runtime (多节点 / 工作窃取 / 领导者选举)
├─ 持久化存储 (Kafka / PostgreSQL / etcd)
├─ 安全 (mTLS / 审计日志)
├─ 多租户 + 热重载
└─ CLI / Dashboard / 文档站点
```

**演讲者备注：**
Zelos 目前 Phase 0/1/2 全部完成——223 个自动化测试、12 个可运行 Demo。Phase 3 将实现分布式 Runtime、持久化存储、安全机制、多租户。当前版本 v0.2.0。

---

## Slide 21 — 总结 & CTA

**标题：** 总结

**Zelos 是什么：**
> 一个开源的、面向多 Agent 协同的编排 Runtime。
> 它管理 Goal，如同 Linux 管理 Process，Kubernetes 管理 Container。

**为什么需要 Zelos：**
> 当 AI 应用从单模型进化到多 Agent 协同，
> 缺失的不是 Agent 构建工具，不是 Agent 通信协议——
> 而是能够可靠规划、调度、验证、审计上百个 Agent 的 Runtime。

**Zelos 的设计核心：**
> Runtime First · Capability First · Event Driven · Plugin Architecture · Specification First
> 天然实现规划/调度/验证的三权分立，Agent 只有执行权。

**Zelos 的愿景：**
> 成为多 Agent 系统运行时标准的基础设施。
> 开发者只需：1. 构建 Agent → 2. 声明 Capability → 3. 注册到 Zelos。
> 剩下的——规划、调度、协同、重试、验证、审计——交给 Runtime。

---

**🔗 链接 & 资源：**
- 项目仓库：[GitHub](https://github.com/zelos)
- License：Apache 2.0
- 当前版本：v0.2.0 (Phase 2 Complete)

**视觉建议：**
- 深色背景，中央大字 "Zelos"
- 下方三列分别展示：Problem · Solution · Vision
- 底部链接和版本信息

---

## 附录：PPT 制作建议

### 配色方案
- **背景色：** #0A0E17 (深空黑蓝)
- **主色调：** #00D4FF (霓虹蓝)
- **辅助色：** #7B61FF (紫罗兰)
- **强调色：** #00FF88 (成功绿) / #FF4757 (错误红)
- **文字色：** #E8E8E8 (主文字) / #8892B0 (次要文字)

### 字体建议
- 标题：JetBrains Mono / SF Mono (等宽科技感)
- 正文：Inter / SF Pro Display (现代无衬线)

### 图标风格
- 统一使用线条图标 (Feather Icons / Phosphor Icons)
- 架构图使用统一的圆角矩形 + 单色填充

### 动画建议
- 架构分层图：逐层渐入 (bottom → top)
- 数据流：带方向的发光路径动画
- 状态机：节点逐个点亮

---

> 📄 **此 PPT 脚本文件位置：** `docs/ppt-script-zelos-intro.md`
