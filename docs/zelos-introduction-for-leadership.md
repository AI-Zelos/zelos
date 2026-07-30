# Zelos 项目全面介绍（供领导层阅读）

> 2026-07-30 | v1.0.0

---

## 一句话说清楚

**Zelos 是一个 AI Agent Runtime。Linux 管进程，Kubernetes 管容器，Zelos 管 AI Agent——不止调度它们，还验证它们。**

---

## 一、Zelos 解决什么问题

### 问题 1：Agent 多了以后，谁管它们？

现在一个用户请求可能要经过：规划 → 研究 → 编码 → 浏览器自动化 → 数据库查询 → 安全审查 → 人工审批。每一步是一个不同的 AI Agent。

当你有 50 个 Agent 在生产环境同时跑的时候：
- 哪个 Agent 做哪个任务？
- 某个 Agent 挂了怎么办？
- 谁来决定要不要重试？
- 怎么知道所有 Agent 的输出加起来是正确的？

这不是"再招几个人"能解决的问题。这是基础设施缺失。

### 问题 2：AI 写的代码，谁审查？

AI 每小时能产出 5,000+ 行代码。人一天认真读 2,000 行就不错了。

**带宽已经错配了。** 这不是"怎么让 Review 更高效"的问题——这是 PR（Pull Request）这套流程本身在数学上不可扩展。

---

## 二、Zelos 的解决方案

### 核心洞察：AI Agent Runtime 和传统 Runtime 有一个本质区别

Linux 只需要保证进程跑对了——`gcc` 编译出来的二进制不用 Linux 再验证一遍。

但 AI Agent 会出错、会幻觉、会越界。所以 **AI Agent Runtime 天然必须包含验证**。这不是附加功能，是分内之事。

### Zelos 做的三件事

```
1. 管执行（Orchestrate）
   Goal → Planner 拆成 Task DAG → Scheduler 按 Capability 匹配 Agent → 调度执行 → 心跳检测/超时重试

2. 管验证（Verify）
   Agent 执行完不是 "Done"，是 "Done + 证据"
   测试结果、安全扫描、Benchmark、API 兼容性 —— 全部自动收集

3. 管决策（Decide）
   所有证据 → 置信度评分（0-100%）
   ≥95% + 低风险 → 自动上线
   <40% → 自动驳回
   中间 → 推给人审批
```

**人不再逐行读代码。人看的是证据报告。**

---

## 三、实验数据

我们做了对照实验：20 个统一任务，同一台机器，同一个 AI 模型（Claude Code）。

| 指标 | 传统 PR | AI 辅助 PR | Zelos CP 流程 |
|------|---------|-----------|-------------|
| 返工率 | 35% | 20% | **5%** |
| 约束违规率 | 30% | 15% | **0%** |
| 人工依赖度 | 100% | 100% | **0%** |
| 人均耗时 | 11.7 min | ~10 min | **3.2 min** |

关键发现：**AI 辅助 PR**（AI 预审代码 + 人最终确认）虽然降低了返工率，但人工依赖度纹丝不动——还是 100%。瓶颈不是工具的问题，是 PR 流程拓扑的问题。

---

## 四、Zelos 与 AgentCity 的关系

AgentCity（ `/ac_test` 项目）是一个 **AI Agent 市场协议**——Agent 注册、组队竞标 Mission、链上治理选出优胜方案、三阶段工作流执行、区块链结算支付。

Zelos 和 AgentCity 是互补的，两个不同的层：

| | AgentCity | Zelos |
|---|---|---|
| 什么层 | 市场 / 协议层 | 执行 / 治理层 |
| 管什么 | Agent 的注册、竞标、支付 | Agent 的调度、验证、决策 |
| 技术栈 | 区块链（NETX testnet, MCP） | Python Runtime（事件溯源、证据收集） |

**AgentCity 现在的 verify 节点是脚本化模拟的（项目自己披露了 "scripted governance decisions"）。如果换成 Zelos 做 verify 节点，就是真实验证 + 证据报告 + 自动决策。**

一句话：**AgentCity 解决"AI Agent 去哪接单、怎么拿钱"。Zelos 解决"Agent 接完单以后怎么证明自己做对了"。两者拼在一起是完整闭环。**

---

## 五、技术栈与工程规模

| 维度 | 数据 |
|------|------|
| 语言 | Python 3.10+（核心零外部依赖） |
| 模块数 | 37 个 Python 源文件 |
| 自动化测试 | 151 个（139 passed + 12 new v1.0），7 skipped（需 Docker） |
| Benchmark | EventBus 89 万 events/s，TaskGraph 225 万 transitions/s |
| SDK | Python / Go / TypeScript |
| 协议适配 | HTTP REST / gRPC / MCP / A2A / WebSocket |
| 存储后端 | InMemory / Redis / PostgreSQL / MySQL（可插拔） |
| 许可证 | Apache 2.0 |
| PyPI | `pip install zelos-runtime`（v1.0.0 已发布） |
| GitHub | github.com/AI-Zelos/zelos |

---

## 六、学术支撑

团队同时在推进两篇论文（目标 ICSE/FSE 2027）：

| 论文 | 内容 | 状态 |
|------|------|------|
| **Beyond Code** | 形式化证明：传统代码审查在 AI 时代数学上不可扩展。11 条定理、形式化理论框架 | 稿件就绪 |
| **从 PR 到 CP** | 提出 Change Proposal 治理范式替代 PR。实验数据 35%→5% 返工率。三组形式化命题证明 | 稿件就绪，已完成多轮审稿反馈修改 |

Zelos v1.0.0 是第二篇论文的完整参考实现。

---

## 七、行业定位

现在 AI 基础设施市场有三个明显的洞：

1. **Agent 构造层**（LangGraph, CrewAI, AutoGen）已经卷成红海——大家都在抢"怎么 build Agent"
2. **Agent 治理层**——没人做。这是空白
3. **Agent 市场**——刚开始有雏形（AgentCity）

**Zelos 卡在第二层。** 就像 Kubernetes 在 2014 年定义了容器编排，Zelos 想定义 AI Agent 的治理层。

**差异化定位**：Zelos 不和 LangGraph/CrewAI 竞争（他们是 Agent 构造工具，Zelos 是 Agent 治理平台，就像 Spring 和 Kubernetes 不是竞争关系）。

---

## 八、项目当前阶段

**v1.0.0，开源，生产级原型，不是 Demo。**

- 核心 Runtime（调度/重试/心跳/事件溯源）→ 完整
- 治理层（证据/置信度/策略门/CP）→ 完整
- 形式化理论论文 → 2 篇，投稿准备中
- 文档体系 → README / VISION / Handbook / ZEIP 规范 / 中英文手册 / API 文档 / 论文
- 推广 → 知乎文章 2 篇，博客/Reddit/HN 待发布

---

## 九、下一步

| 优先级 | 事项 |
|--------|------|
| P0 | 投递两篇论文（ICSE/FSE 2027） |
| P0 | 发布推广文章（知乎/HN/Reddit） |
| P1 | 录制 Demo 视频 |
| P1 | 与 AgentCity 做集成 PoC（Zelos 替代 scripted verify 节点） |
| P2 | 更多工业场景实验数据 |
| P2 | 社区运营（GitHub Discussions/Discord） |

---

> **Zelos 不是 Agent 框架。它是 AI Agent 的基础设施——一个管执行、管验证、管决策的 Runtime。如果 AI Agent 是未来十年的软件形态，那总得有一个东西来治理它们。我们希望 Zelos 是那个东西。**
