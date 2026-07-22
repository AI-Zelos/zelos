# Zelos 竞争格局分析

> 调研日期：2026-07-21
> 目的：确认 Zelos 在现有技术生态中的定位，评估差异化优势与竞争风险

---

## 一、总体判断

**Zelos 的定位（"面向多 Agent 的编排 Runtime，LLM 无关，宪法性三权分立"）在目前市场上没有完全对标的竞品。** 但有多个项目在部分维度上与 Zelos 重叠。以下按相似度从高到低分析。

---

## 二、最相似的项目（存在部分重叠）

### 1. Murmur — "LLM Agent 的 Hypervisor"

| 维度 | Murmur | Zelos |
|------|--------|-------|
| 定位 | Production runtime for multi-agent LLM systems | Open Multi-Agent Orchestration Runtime |
| 核心理念 | "Hypervisor for LLM agents" | "Linux for Agents" |
| 语言 | Python only | 语言无关（Agent 可用任意语言） |
| Agent 模型 | 基于 PydanticAI 的 LLM Agent | 外部进程，任意实现，5 个 API 方法 |
| 多 Agent 协调 | AgentGroup DAG + fan-out/gather | ExecutionPlan → TaskGraph → Scheduler |
| 类型系统 | Pydantic 强类型 I/O | JSON Schema 版本化契约 |
| 事件系统 | Typed RuntimeEvent + 多种 emitter | Event Bus 不可变追加写入 + 因果链 |
| 信任/安全 | Trust levels (HIGH/MEDIUM/LOW/SANDBOX) | Policy Plugin + Verifier Plugin |
| 分发模型 | 直接指定 Agent | **Capability-based 匹配** |
| LLM 依赖 | **深度依赖**（基于 PydanticAI + LLM provider） | **零依赖**（Invariant 13：Runtime 不知道 LLM 存在） |
| 三权分立 | 无显式分离 | Planner ≠ Scheduler ≠ Verifier |
| 发布状态 | v0.1.0 (2026.05) | Architecture Phase (未实现) |

**重叠：** "Runtime 而非 Framework"的定位理念、DAG 协调、事件驱动、Trust 分层
**Zelos 的差异化：** LLM 无关（Murmur 深度绑定 LLM）、Capability 分发（Murmur 直接指定 Agent）、三权分立架构

### 2. meta-agent (Rust) — Capability 分发 + DAG 调度

| 维度 | meta-agent | Zelos |
|------|-----------|-------|
| 定位 | Capability-based task dispatcher + DAG scheduler | 完整 Runtime |
| 语言 | Rust | 语言无关 |
| 核心能力 | AgentPool + TaskQueue + Dispatcher + WorkGraph + Simulation | 全套 Runtime（+ Planner/Verifier/Policy/EventBus/Memory） |
| Capability 匹配 | ✅ `best_agent()` 按 load/speed 评分 | ✅ Scheduler 5 阶段 7 因子评分 |
| DAG 调度 | ✅ petgraph 依赖图 + 关键路径分析 | ✅ Task Graph Engine 状态机 |
| 重试/容错 | HealthMonitor 检测卡住 Agent | 完整重试策略（退避/Smart Retry/Fallback/重规划） |
| Planner | 无 | ✅ Plugin（Goal → ExecutionPlan） |
| Verifier | 无 | ✅ Plugin（Artifact 验证门） |
| Event Bus | 无 | ✅ 不可变事件总线 |
| 审计追踪 | 无 | ✅ 完整 Logic Pedigree |
| 规模 | 单一调度库 | 完整 Runtime 平台 |

**重叠：** Capability-based dispatch、DAG 调度、负载感知评分
**Zelos 的差异化：** meta-agent 只是一个调度器库，Zelos 是包含规划/调度/验证/审计/策略的完整 Runtime

### 3. ESAA — Event Sourcing for Autonomous Agents

| 维度 | ESAA | Zelos |
|------|------|-------|
| 定位 | 学术论文/概念验证 | 完整 Runtime 产品 |
| 核心概念 | Append-only event store + deterministic orchestrator + boundary contracts | Event Bus 不可变追加写入 + 15 条 Architecture Invariants |
| 事件模型 | activity.jsonl + SHA-256 hash verified replay | Event Bus: typed, immutable, correlation_id, causation_id |
| 契约约束 | AGENT_CONTRACT.yaml | JSON Schema 版本化契约 (Invariant 11) |
| "Done" 不可变 | ✅ completed tasks 不能回归 | ✅ Artifact 不可变 (Invariant 8) |
| 验证 | Schema 契约验证 | Verifier Plugin (可替换，多类型) |
| 规划/调度 | 无 | ✅ Planner + Scheduler |

**重叠：** 不可变事件溯源、契约约束、"Done" 不可变性
**Zelos 的差异化：** ESAA 是学术概念验证（50 tasks），Zelos 是面向生产的完整 Runtime 架构

### 4. Auton Framework — Cognitive Blueprint vs Runtime Engine

| 维度 | Auton | Zelos |
|------|-------|-------|
| 定位 | Declarative agent specification framework | Runtime for multi-agent orchestration |
| 核心分离 | Cognitive Blueprint (声明式规约) vs Runtime Engine (执行) | Spec → Architecture Invariants → Runtime Kernel |
| 声明式规约 | AgenticFormat YAML/JSON | JSON Schema 版本化契约 |
| 安全模型 | Constraint Manifold (不安全 action 概率归零) | Policy Plugin (Allow/Reject/Delay) + Verifier Plugin |
| Agent 模型 | 框架内定义的 Agent（基于 LLM） | 外部进程，任意语言，任意实现 |
| LLM 依赖 | **深度依赖**（POMDP 模型、推理空间 Z、STaR/GRPO 训练） | **零依赖** |
| 多 Agent 编排 | 有限（主要单 Agent + 认知 Map-Reduce） | 核心能力（Goal → Plan → TaskGraph → Schedule） |

**重叠：** 规约先行、声明式契约、安全由架构保证而非事后修补
**Zelos 的差异化：** Auton 更偏向单 Agent 的标准化规约框架，Zelos 是完整的多 Agent 编排 Runtime

### 5. Agent-OS Blueprint (2025 学术论文)

一个 5 层架构蓝图：Kernel → Resource/Service → Agent Runtime → Orchestration/Workflow → User/Application。提出了延迟分级、Agent Contracts 等概念。

**重叠：** 分层架构思想、Agent-as-contract 理念
**差异化：** 纯学术蓝图，无实现；Zelos 有完整可实施的 Blueprint + Schema + RFC + 不变式体系

---

## 三、部分重叠的项目（不同赛道）

| 项目 | 做什么 | 与 Zelos 的关系 |
|------|--------|----------------|
| **OpenNodeX** | TypeScript Agent 框架，capability routing + DAG workflow | Capability 路由概念重叠，但它是 Agent 构建框架，不是 Runtime |
| **AgentMesh (Microsoft)** | Agent governance toolkit，4 层权限环 + HypervisorEventBus | EventBus 概念重叠，但它是安全治理层，不是编排 Runtime |
| **Tutti** | TypeScript 多 Agent 编排，DAG routing + HITL gate | 编排概念重叠，但定位是应用框架，不支持任意语言 Agent |
| **AgentOS** | TypeScript Agent 运行时，37 channel adapters + 认知记忆 | 功能丰富但深度绑定 TypeScript 生态和 LLM |
| **AgnosAI** | Rust Agent 编排引擎，高性能替代 Python/CrewAI | 编排引擎概念重叠，但更偏向 Agent 构建，非语言无关 Runtime |
| **ClawsomeFlow** | Python DAG 工作流，active scheduler + leader convergence | Scheduler 概念重叠，但更偏传统工作流引擎 |
| **DeerFlow (ByteDance)** | 事件溯源记忆 + 跨框架事件 Schema | Event sourcing 概念重叠，但定位是工作流平台 |

---

## 四、Zelos 的独特差异化

经过全面调研，以下能力组合在目前市场上**没有任何一个项目同时具备**：

| 差异化维度 | 说明 |
|-----------|------|
| **1. LLM 零依赖** | Invariant 13：Runtime 不知道 Claude/GPT/Gemini 的存在。所有竞品都深度绑定 LLM |
| **2. 宪法性三权分立** | Planner ≠ Scheduler ≠ Verifier，Agent 只有执行权。没有竞品在架构层面做这种权力分割 |
| **3. Capability 分发** | 按"能做什么"招标而非指定供应商。meta-agent 有类似概念但只是调度库，不是完整 Runtime |
| **4. 语言无关 Agent** | Agent 是外部进程，只需实现 5 个 API。所有竞品 Agent 都需要特定语言 SDK |
| **5. 不可变事件审计链** | Event Bus: 追加写入、不可变、correlation_id + causation_id。ESAA 有类似概念但是学术项目 |
| **6. Plugin 宪法性分离** | Kernel 密封不可替换，6 种 Plugin 可替换。类似"宪法不改，政府可换" |
| **7. 15 条 Architecture Invariants** | 宪法级设计约束，任何实现冲突以 Invariant 为准。无竞品有同等级别的架构约束力 |
| **8. 纯 Runtime 定位** | "不构建 Agent，只运行 Agent"。Murmur 最接近但深度绑定 LLM |

---

## 五、竞争风险评估

| 风险 | 等级 | 说明 |
|------|------|------|
| **Murmur 扩展覆盖 Zelos 的定位** | 🟡 中 | Murmur 如果去掉 LLM 依赖、增加 Capability 分发，可能成为直接竞品。但它目前深度绑定 PydanticAI/LLM，这条路径有架构性障碍 |
| **meta-agent 扩展为完整 Runtime** | 🟢 低 | 目前只是一个 Rust 调度库，扩展到完整 Runtime 需要大量工作 |
| **LangGraph/LangChain 增加 Runtime 能力** | 🟡 中 | LangChain 生态庞大，随时可能向 Runtime 方向扩展。但它们的"Agent 框架"基因与 Zelos 的"纯 Runtime"定位有根本性架构冲突 |
| **Google ADK / OpenAI Agents SDK** | 🟢 低 | 大厂的 Agent SDK 深度绑定自家模型，不可能做到 LLM 无关 |
| **微软 AgentMesh + 生态** | 🟡 中 | 微软有完整的安全治理方案，如果加上编排层可能形成竞争。但目前 AgentMesh 聚焦安全，不解决编排 |
| **新进入者** | 🟡 中 | "Agent Runtime"概念正在升温（Murmur 2026.05 发布），预计会有更多项目出现 |

---

## 六、时机判断

**Zelos 选择的切入时机是正确的：**

1. **MCP/A2A 协议已稳定** — Agent 通信管道已铺好，治理层需求明确
2. **"Runtime"概念正在被市场教育** — Murmur、Agent-OS、Auton 等都在推动"Agent 需要 Runtime"的认知
3. **但目前还没有人去碰 Zelos 的核心定位** — LLM 无关 + Capability 分发 + 三权分立 + 不可变审计 = 空白赛道
4. **窗口期有限** — 预计 2026 H2 到 2027 H1 是最佳切入窗口，之后会有更多竞争者进入

---

> 📄 **此文档位置：** `docs/competitive-analysis.md`
