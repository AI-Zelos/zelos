# Murmur vs Zelos：两种 Agent Runtime 的架构对比

> 分析日期：2026-07-21

---

## 一、先说结论

Murmur 是目前市场上**和 Zelos 最接近的项目**——两者都定位为 "Agent Runtime" 而非 "Agent Framework"。但两者有一个**根本性的架构分歧**：**Murmur 深度绑定 LLM，Zelos 刻意不绑定。**

这不是功能缺失，而是有意为之的架构选择。两者面向的场景不同，甚至可以互补。

---

## 二、Murmur 是什么

| 属性 | 内容 |
|------|------|
| 仓库 | `droidnoob/murmur-ai` |
| 版本 | v0.1.0（2026年5月发布） |
| 定位 | "A production runtime for multi-agent LLM systems" |
| 自称 | **"Hypervisor for LLM agents"** |
| 技术栈 | Python 3.11+，底层基于 PydanticAI + FastStream |
| 安装 | `pip install murmur-runtime` |

### 核心能力

- **Multi-Agent Coordination**: `AgentGroup` DAG + `runtime.gather()` fan-out + LLM-driven dynamic fan-out
- **Typed I/O**: 每个 Agent 的输入/输出是 Pydantic 模型，无裸文本跨 Agent 传输
- **Distribution**: 同一套代码，`AgentRuntime()` 本地跑，`AgentRuntime(broker="kafka://...")` 分布式跑
- **Trust Enforcement**: HIGH / MEDIUM / LOW / SANDBOX 四级信任，Runtime 层统一管控
- **MCP Support**: 消费 MCP Server 工具，也能把 Agent 暴露为 MCP Tool
- **Observability**: `RuntimeEvent` 类型系统 + structlog/SSE/OpenTelemetry emitter + React Dashboard
- **Cost-Aware**: `TokenBudget` pre-check/post-charge，级联 spawn 时传播预算约束
- **Persistence**: 可选 `RunStore`/`EventStore`（SQLite / RocksDB / Redis）

---

## 三、重叠的能力

| 能力 | Murmur | Zelos |
|------|--------|-------|
| 定位 | "Runtime 而非 Framework" | "Runtime 而非 Framework" |
| 多 Agent 协调 | ✅ AgentGroup DAG | ✅ ExecutionPlan → TaskGraph |
| 事件系统 | ✅ Typed RuntimeEvent | ✅ Event Bus（不可变、追加写入、causation_id） |
| 信任/安全分层 | ✅ Trust levels (4级) | ✅ Policy Plugin + Verifier Plugin |
| MCP 支持 | ✅ 消费 + 暴露 | ✅ Phase 2 计划 |
| 分布式支持 | ✅ Kafka/NATS/Redis/RabbitMQ | ✅ Phase 3 计划 |
| 单节点/分布式同代码 | ✅ 改 constructor 即可 | 规划中 |
| 类型化接口 | ✅ Pydantic | ✅ JSON Schema 版本化契约 |
| 可观测性 | ✅ OTel + Dashboard | ✅ 事件链路天然可追踪 |

---

## 四、根本差异：Agent 模型不同

这是两者**最核心的架构分歧**：

### Murmur 的 Agent 模型

```
Agent = PydanticAI Agent
  ↓
必须基于 LLM（Anthropic / OpenAI / Gemini / Bedrock）
  ↓
Runtime 知道 Agent 在用哪个 LLM provider
Runtime 可以监控 token 用量、控制 budget
Agent 的"思考过程"对 Runtime 可见
Agent 的实现语言必须是 Python
Agent 的 I/O 必须是 Pydantic 模型
```

### Zelos 的 Agent 模型

```
Agent = 外部进程（可以是任何东西）
  ↓
可以是 LLM Agent / Bash 脚本 / API 调用 / 人工节点 / 硬件设备
  ↓
Runtime 不知道、不关心 Agent 内部实现
Runtime 不知道 LLM 的存在（Invariant 13）
Agent 可以用任何语言、任何框架实现
Agent 只需要实现 5 个 API 方法：register / heartbeat / execute / cancel / shutdown
```

### 对比表

| 维度 | Murmur | Zelos |
|------|--------|-------|
| **Agent 类型** | 只支持 LLM Agent | 任意类型：LLM / 脚本 / API / 人工 / 硬件 |
| **Agent 实现语言** | 必须 Python + PydanticAI | 任意语言（5 个 HTTP API） |
| **LLM 依赖** | **深度绑定** | **零依赖**（Invariant 13） |
| **Agent 如何被调度** | 代码直接指定 Agent | Capability Registry → Scheduler 按能力匹配 |
| **Agent 发现机制** | 无（代码硬指定） | Capability Registry（Agent 注册能力 → 自动发现） |
| **规划/执行/验证分离** | 无显式分离 | Planner ≠ Scheduler ≠ Verifier |
| **审计追踪** | RuntimeEvent + OTel | Event Bus 不可变追加 + causation_id 因果链 |
| **Plugin 架构** | 无 | 6 种可替换 Plugin，Kernel 密封 |

---

## 五、打个比方

| | Murmur | Zelos |
|---|---|---|
| **类比** | 专门管理 LLM 虚拟机的 Hypervisor | 操作系统的通用进程调度器 |
| **管得好** | LLM Agent 的生命周期、token budget、trust levels | 任何类型 Agent 的注册、调度、验证、审计 |
| **管不了** | 非 LLM 的 Agent（Bash 脚本、浏览器自动化、人工审批） | ❌ 不关心 Agent 内部（token 用量、模型选择等） |

---

## 六、两者的关系：互补而非互斥

Murmur 和 Zelos 不是"谁替代谁"的关系。它们面向的问题层次不同：

```
┌────────────────────────────────────────────┐
│               Zelos Runtime                │
│   通用编排：Goal → Plan → TaskGraph         │
│   → Scheduler (Capability 匹配)            │
│   → Verifier (结果验证)                    │
│   → Event Bus (审计链)                     │
│                                            │
│   它管理的 Agent 可以包括：                 │
│   ┌──────────────────────────────┐         │
│   │  Murmur 管理的 LLM Agent     │         │
│   │  (作为一个 Agent 注册进来)    │         │
│   ├──────────────────────────────┤         │
│   │  Playwright 浏览器 Agent     │         │
│   ├──────────────────────────────┤         │
│   │  SQL 查询 Agent              │         │
│   ├──────────────────────────────┤         │
│   │  人工审批节点                │         │
│   ├──────────────────────────────┤         │
│   │  自定义 Bash 脚本 Agent      │         │
│   └──────────────────────────────┘         │
└────────────────────────────────────────────┘
```

**一个可能的协作方式：** 如果你需要精细管理 LLM Agent 的 token 用量和 model selection，可以用 Murmur 跑 LLM Agent。如果你需要协调 LLM Agent + 浏览器 Agent + 数据库 Agent + 人工审批组成一个 Goal，可以用 Zelos 做顶层编排——把 Murmur 作为一个 Capability Provider 注册进来。

---

## 七、Zelos 选择 LLM-agnostic 的理由

Murmur 的选择（深度绑定 LLM）有其合理性——它可以做更精细的 LLM 层优化（token budget、provider 切换、推理监控）。但 Zelos 刻意选择了另一条路线：

1. **Agent 不只是 LLM** — 浏览器自动化、数据库查询、代码执行、人工审批——这些都不是 LLM，但它们都是 Agent
2. **LLM 是 Agent 的内部实现细节** — Runtime 不需要知道 Agent 用了什么模型，就像 Linux 不需要知道进程是用什么语言写的
3. **供应商中立** — 不解绑 LLM，就无法实现真正的 Capability-based Marketplace
4. **面向未来** — 当 Agent 的形态从 LLM 扩展到更多类型时，LLM 耦合的 Runtime 会过时，LLM-agnostic 的 Runtime 不会

---

> 📄 **此文档位置：** `docs/murmur-vs-zelos.md`
