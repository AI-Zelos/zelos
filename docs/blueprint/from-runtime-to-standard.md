# From Runtime to Standard — Zelos 下一阶段最重要的事

> 基于对 v0.9.0 的深度评审。核心判断：**Zelos 最大的价值已经不是 Multi-Agent Runtime，而是它开始在定义一套 Agent 时代的软件工程方法论。下一步不是继续加功能，而是把这件事做深、做标准。**

---

## 一、一句话重新定义 Zelos

当前定位：

> Multi-Agent Orchestration Runtime

问题：一年以后，所有人都是 Multi-Agent。这不是壁垒。

建议的下一阶段定位：

> **Zelos orchestrates trustworthy software changes produced by AI.**
>
> （Zelos 编排的是 AI 产生的、可信的软件变更。）

或者更简洁：

> **Trustworthy Change Runtime**

关键词不是 Agent，是 **Trustworthy Change（可信变更）**。

**为什么这个定位更好？**

| 维度 | Multi-Agent Runtime | Trustworthy Change Runtime |
|------|---------------------|---------------------------|
| 解决什么问题 | Agent 之间怎么协作 | AI 写完代码以后，怎么相信它 |
| 谁关心 | Agent 开发者 | 企业 CTO、架构师、安全团队 |
| 壁垒 | 调度算法（会被追上） | 软件工程规范（很难被追上） |
| 对标 | LangGraph, CrewAI | 还没有人在做 |
| 一句话 | "我帮你管理 Agent" | "我帮你证明这次变更可以上线" |

企业真正购买的从来不是 Agent，而是**对 AI 产生的软件变更的信任**。

---

## 二、五件最重要的事（按优先级）

### ⭐⭐⭐⭐⭐ #1：重写 Vision

**不是改 README。是定义世界观。**

花一周时间，只做一件事：回答下面四个问题，并且每个问题的答案只能是一句话。

| 问题 | 必须一句话回答 |
|------|---------------|
| What is Zelos? | Zelos orchestrates trustworthy software changes produced by AI. |
| Why does it exist? | Because AI can write code faster than humans can verify it. |
| Why now? | Agents are producing 35,000+ lines/hour; traditional review is broken. |
| What is NOT Zelos? | Not an agent framework. Not a workflow engine. Not a prompt tool. Not a SaaS. |

输出物：一份 `VISION.md`，不超过 500 字。

**世界顶级项目首先输出的是世界观，而不是功能列表。**

---

### ⭐⭐⭐⭐⭐ #2：建立 Agent Engineering Handbook

**不是 API 文档。是方法论。**

当前 `docs/` 已经有了很好的架构文档，但缺少一本"教科书"。

建议的结构：

```
docs/handbook/
├── 01-what-is-agent-engineering.md    ← 定义这个新领域
├── 02-intent-specification.md         ← 如何定义一个 Goal
├── 03-execution-plan.md               ← 从 Goal 到 Task DAG
├── 04-verification-and-evidence.md    ← 如何证明 Agent 做对了
├── 05-confidence-and-decision.md      ← 从证据到决策
├── 06-architecture-delta.md           ← 变更影响分析
├── 07-risk-and-rollback.md            ← 风险与回滚
├── 08-change-approval-request.md      ← CAR 规范
├── 09-policy-and-governance.md        ← 治理策略
└── 10-from-code-review-to-change-review.md ← 范式升级
```

**为什么这比继续写代码重要？**

因为 AI 首先要读的是 Documentation。Documentation 的质量 = Framework 的质量。

而且，如果这些概念（Intent、Evidence、Confidence、CAR）被社区接受，Zelos 就不是一个实现，而是**定义了一套语言**——就像 Kubernetes 定义了 Pod、Deployment、Service 一样。

---

### ⭐⭐⭐⭐☆ #3：把 Verification / Evidence 提升为 Runtime 第一公民

当前 Runtime 的核心是：

```
Goal → Plan → Schedule → Dispatch → Done
```

建议下一阶段的核心是：

```
Goal → Plan → Execute → Verify → Collect Evidence → Score Confidence → Decide → Done
```

**具体变化：**

1. **所有 Agent 输出必须有 Evidence**，不只是 Artifact
2. **Verifier 数量 > Executor 数量**。AI 最大的问题不是不会写，而是怎么证明它写的是对的
3. **Confidence 低于阈值 → 自动触发更多 Verifier**，形成验证闭环
4. **Policy 在 Evidence 之后执行**，不是之前

```
当前 Runtime:
  Planner → Executor → Done

目标 Runtime:
  Planner → Executor → Verifier → Verifier → Verifier → Evidence Collector → Confidence Scorer → Policy Gate → Done
```

Agent 会越来越便宜。**Verification 永远不会。**

---

### ⭐⭐⭐⭐☆ #4：定义 ZEIP（Zelos Enhancement Proposal）规范体系

像 Python 的 PEP、Kubernetes 的 KEP、Rust 的 RFC 一样，Zelos 应该有一套规范体系。

建议第一批 ZEIP：

| 编号 | 主题 | 内容 |
|------|------|------|
| ZEIP-0001 | Intent | Goal 的结构化定义、成功标准、约束 |
| ZEIP-0002 | Artifact | Agent 产出的标准格式、版本化 |
| ZEIP-0003 | Evidence | 证据类型、收集方式、可信度分级 |
| ZEIP-0004 | Verification | 验证器接口、验证链、通过/失败标准 |
| ZEIP-0005 | Capability | 能力注册、发现、匹配的语义规范 |
| ZEIP-0006 | Policy | 策略定义语言、执行时机、优先级 |
| ZEIP-0007 | Change Proposal | CAR 的标准格式、必填字段、审批流 |

**为什么这比增加新功能重要？**

标准一旦被别人采用，Runtime 只是实现。**真正的护城河不是代码，是协议。**

---

### ⭐⭐⭐☆☆ #5：发布最小可运行的 Reference Project

一个让用户在 10 分钟内体验 Zelos 完整理念的 Demo。不追求功能丰富，而是展示完整工作流：

```
1. User submits a Goal with Intent
2. Planner decomposes into Architecture Delta + Tasks
3. Agents execute, each returns Evidence
4. Runtime collects Evidence → scores Confidence (e.g., 0.97)
5. Policy Gate: auto-approve (confidence > 0.95)
6. Execution Report generated — ready for human sign-off
7. Change merged, Rollback Plan on standby
```

用户 10 分钟内就能理解："原来这就是 AI 变更治理。"

---

## 三、坚决不要做的事

这些是很多项目死掉的原因——一直在加功能，却没有加深护城河。

| 不要做 | 为什么 |
|--------|--------|
| Agent Marketplace | 不是基础设施层的职责 |
| SaaS / Cloud Platform | 分散精力，开源社区不会为 SaaS 贡献 |
| Low-Code / No-Code | 完全不同的方向，稀释定位 |
| Prompt IDE | 市场饱和，且不是 Runtime 的职责 |
| Workflow Designer | 已经有太多人做 |
| Tool Calling 竞争 | 一年后所有框架都一样 |

**聚焦一句话：Trustworthy Change。不做任何偏离这条线的事。**

---

## 四、1.0 之前不建议再增加 Runtime Feature

当前 Runtime 内核（Scheduler、Planner、TaskGraph、EventBus、Storage）已经足够完整。

1.0 之前应该：

- ✅ 停止增加 Runtime Feature
- ✅ 开始增加 Specification（ZEIP）
- ✅ 把 Vision 写到一句话
- ✅ 把方法论写成 Handbook
- ✅ 发布一个 Reference Project 证明完整理念

---

## 五、长期愿景

如果 Zelos 只做 Multi-Agent Runtime，它的天花板是 Temporal for Agents。

如果 Zelos 定义 AI-Native Software Engineering，它的天花板是 **一个时代的基础设施**——就像 Linux 定义了 OS、Kubernetes 定义了容器编排、Git 定义了版本控制一样。

**Zelos 的长期定位应该是：**

> **AI 软件工程的基础设施层。它不写代码，它证明代码可信。**

---

## 六、讨论的核心观点回顾

| 观点 | 含义 |
|------|------|
| "Zelos 最大的价值已经不是 Runtime，而是方法论" | 代码会过时，世界观不会 |
| "Trustworthy Change > Agent Orchestration" | 企业买的是信任，不是 Agent |
| "Verification 永远不会便宜" | Agent 会越来越便宜，这是永恒价值 |
| "标准就是护城河" | Kubernetes 不是因为代码好，是因为 Pod 被所有人接受了 |
| "不做 30 件事，只做 5 件" | 减法比加法更难，但更重要 |
| "文档不是 README，是世界观" | AI 第一件事是读文档，不是读源码 |

---

> **下一步行动：不是继续写代码，而是定义世界。**
