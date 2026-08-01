# SWE-bench 对 Zelos 的意义

> 编写日期：2026-08-01
>
> 目的：澄清 SWE-bench 在 Zelos 验证体系中的定位——它测什么、不测什么、怎么测才对、为什么对 Zelos 至关重要。

---

## 目录

1. [一个容易被误解的关系](#1-一个容易被误解的关系)
2. [Zelos 的两个价值层次](#2-zelos-的两个价值层次)
3. [v1.2 测评方式的问题](#3-v12-测评方式的问题)
4. [正确的测评方式：拆开 Task，压到全部核心路径](#4-正确的测评方式拆开-task压到全部核心路径)
5. [SWE-bench 能验证什么、不能验证什么](#5-swe-bench-能验证什么不能验证什么)
6. [核心方法论：Agent 是常量，Runtime 是变量](#6-核心方法论agent-是常量runtime-是变量)
7. [具体实施方案](#7-具体实施方案)
8. [结论](#8-结论)

---

## 1. 一个容易被误解的关系

对 Zelos 和 SWE-bench 的关系，有两个常见的误解：

**误解 A**："SWE-bench 测的是 Agent 代码能力，Zelos 是编排 Runtime，两者不搭。"

**误解 B**："Zelos 把 SWE-bench 跑好了，就证明 Zelos 做对了。"

两个都不对。SWE-bench 和 Zelos 的关系不是"搭不搭"，而是**怎么用**——用错了是噪音，用对了是恰好对齐 P0 核心闭环的完美验证场。

---

## 2. Zelos 的两个价值层次

```
Layer 1：执行质量管理
  Runtime 替代 LLM 做工程决策
  — 诊断日志、分类失败、决策重试方向
  — 让 Agent 的每一次执行都有 Runtime 级别的质量保障

Layer 2：多 Agent 编排治理
  Runtime 协调多个异构 Agent 完成复杂 Goal
  — Planner 拆解、Scheduler 调度、Verifier 验证、Event Bus 审计
  — 让 100 个 Agent 像 1 个团队一样工作
```

**SWE-bench 能充分验证 Layer 1，能部分验证 Layer 2。**

---

## 3. v1.2 测评方式的问题

v1.2 的 SWE-bench 测评做法是：

```
单个 Agent 生成 patch → Docker 跑测试
  → Diagnosis Engine 诊断日志
  → Failure Classifier 决定修/重试/放弃
  → Repair Orchestrator 定向修复
```

**这种方式的问题不是"没用"，而是"解释力有限"：**

| 问题 | 影响 |
|------|------|
| 只用了 1 个 Agent | Scheduler 没有选择空间，测不出 Agent 匹配能力 |
| Task 没有拆开 | Planner 没有参与，测不出 Goal 分解能力 |
| 没有多 Agent 协作 | 测不出 Agent 间依赖编排和 MPC 重规划 |
| 全量组件加载 | 6/17 的结果分不清瓶颈在 Planner/Scheduler/Verifier 还是 Agent 本身 |

**结论：v1.2 测评能拿到 Diagnosis Engine 和 Failure Classifier 的准确率数据（有价值），但回答不了"Zelos 的编排能力好不好"这个核心问题。**

---

## 4. 正确的测评方式：拆开 Task，压到全部核心路径

如果把一个 SWE-bench Task 按 Zelos 的架构拆开（而不是一个 Agent 从头做到尾），每一步恰好驱动一条 Zelos 核心路径：

```
SWE-bench Task 生命周期              驱动 Zelos 的哪条核心路径
─────────────────────               ──────────────────────────

Step 1: 提交 Goal                       Planner
  "修复 django issue #1234"               Goal → Plan [Search, Fix, Review, Test]
                                          验证：分解是否合理？粒度是否合适？

Step 2: 定位代码                         Scheduler
  Capability "code-search"               在 [Sonar定位, live-SWE定位, grep-agent]
                                          中选择最佳的
                                          验证：选择依据是否有数据支撑？

Step 3: 生成 patch                       Scheduler（多 Agent 选择）
  Capability "code-generation"           同一 Capability 有 2+ Agent 可选
                                          验证：Scheduler 是否选了对的那个？
                                          用后验数据验证决策质量

Step 4: 审查 patch                       MPC 增量验证
  Reviewer Agent 执行                    Reviewer 产出置信度 0.7 → 低于阈值
                                          Runtime 决定：继续 / 重做 / 切换 Agent
                                          验证：决策是否正确？

Step 5: 跑测试 + 诊断                    Diagnosis Engine + Failure Classifier
  Runtime 接管测试输出分析                结构化诊断 → 分类决策
                                          验证：诊断准确率 + 分类准确率

Step 6: 重规划                           MPC Replan
  Runtime 基于诊断决定下一步：              触发回溯 / 切换方案 / 定向修复
    "这个断言错，定向修复"                   验证：重规划决策是否正确？
    "全量爆炸，换方案"                      有没有避免无效重试？
    "方向对，继续加深"

Step 7: 产出 patch + Evidence             Event Bus 审计链
  完整 causation chain                    "为什么选 Agent B 而不是 A？"
                                          "为什么选择了回溯？"
                                          验证：每个决策都有可追溯的理由
```

**7 个步骤，驱动了 Planner / Scheduler / MPC Verifier / Diagnosis / Replan / Event Bus 六条核心路径。** 这才是"用 SWE-bench 验证 Zelos"的正确打开方式。

---

## 5. SWE-bench 能验证什么、不能验证什么

### 能充分验证的

| 核心能力 | 验证方式 | 量化指标 |
|---------|---------|---------|
| **Diagnosis Engine** | SWE-bench 的 pytest 输出天然是标准化的诊断输入 | 诊断准确率（字段提取正确率） |
| **Failure Classifier** | 诊断结论 → 分类决策，可与人工标注对比 | 分类准确率、误判率 |
| **Planner** | 拆开 4-5 个子任务，验证分解的合理性和粒度 | 分解步骤数是否合理、依赖关系是否正确 |
| **Scheduler（Agent 选择）** | 同一 Capability 多个 Agent → 有真正的选择空间 | 选择的后验准确率（选了的 Agent 确实比没选的好） |
| **MPC 增量验证** | 每步产出置信度 → 决定下一步 | 低置信度产出被重做的比例、高置信度产出被下游接受的比例 |
| **MPC Replan** | 测试失败 → 诊断 → 决定继续/换方案/放弃 | 重规划有效率（重规划后成功了 vs 白白重试了） |
| **Agent 热替换** | Agent A 失败 → 同 Capability 换 Agent B | 切换后的成功率 |
| **Event Bus 审计链** | 每次决策都有 Decision Event | causation chain 完整度 |

### 能部分验证的

| 核心能力 | 限制 |
|---------|------|
| **Belief State 多假设探索** | 可设计"2 个 Fix Agent 并行探索不同方案"，但 SWE-bench 不需要这个能力 |
| **MPC 长时间自适应** | SWE-bench 单题步数少（3-7 步），测不出长时间运行的自适应效果 |

### 不能验证的

| 核心能力 | 原因 |
|---------|------|
| **Policy Gate** | SWE-bench 没有治理需求（合规审批、预算控制、权限检查） |
| **大规模并发调度** | SWE-bench 单题独立，不涉及 10+ Agent 同时调度的场景 |
| **跨 Goal 学习** | SWE-bench 每个 Task 是独立的实例间不共享上下文 |

### 结论

SWE-bench 恰好覆盖 P0 阶段 A（核心调度闭环）需要验证的全部能力。不能验证的那些（Policy Gate、大规模并发）恰好是 P0 阶段 D、E 才需要的——**SWE-bench 作为 P0 阶段 A 的验证场，和 Zelos 的迭代路线完美对齐。**

---

## 6. 核心方法论：Agent 是常量，Runtime 是变量

v1.2 测评用了一个自己写的 Agent 跑 SWE-bench。这混淆了两个变量：Agent 质量和 Runtime 质量。你分不清 6/17 是因为 Agent 不会写代码，还是 Runtime 没调度好。

**正确的做法：**

```
Agent（常量，用已验证的）               Runtime（变量，我们要测的）
──────────────────────────             ──────────────────────────
live-SWE-agent 的定位能力                Planner：拆解是否合理
Sonar 的代码理解能力                     Scheduler：Agent 匹配是否准确
Claude Code 的代码生成能力               MPC Verifier：增量验证是否有效
另一模型的 Reviewer 审查能力             MPC Replan：重规划决策是否正确
                                        Event Bus：审计链是否完整
                                        Diagnosis Engine：诊断是否准确
```

**Agent 的代码能力是已知量（排行榜上有公开数据）。** 在这个基础上，Runtime 的任何贡献都是可量化的增量。

这一点非常关键：它直接把"Zelos 自己造 Agent"的问题变成了"Zelos 让已有 Agent 发挥更大价值"——这和 Invariant 13（Runtime 不依赖 LLM）是哲学上一致的。

---

## 7. 具体实施方案

### 7.1 三阶段验证

```
阶段 1：v1.2 数据复盘（当前测评数据，1 周）
  → 提取 Diagnosis Engine + Failure Classifier 的准确率
  → 不要求 17 题全跑完，已有数据够做分析

阶段 2：核心闭环验证（2-3 周）
  → P0 阶段 A：最薄组件 + 已验证 Agent
  → 跑通 3 个 SWE-bench 题的完整 7 步闭环
  → 产出：核心链路每个环节的量化评估

阶段 3：编排 PoC（2 周）
  → 5 个 SWE-bench 题，3 种跑法对比
```

### 7.2 编排 PoC 的三组对比实验

选 5 个 SWE-bench 题，每个分别用 3 种方式跑：

| 分组 | 做法 | 要验证的假设 |
|------|------|------------|
| **基线** | live-SWE-agent 原生单打（1 个 Agent 从头做到尾） | "最好的单体 Agent 能拿多少分" |
| **+Runtime 诊断** | 同上 Agent + Zelos Diagnosis Engine + Failure Classifier + Repair Orchestrator | "Runtime 的诊断和决策能力是否比 Agent 自己读日志更好" |
| **+编排** | 同一个 Task 拆成定位/生成/审查三步，分别用不同 Agent，中间 Runtime 做 MPC 决策 | "Runtime 编排多 Agent 是否比任何单体 Agent 更好" |

**每一组测量：**

| 指标 | 意义 |
|------|------|
| 是否通过（patch 通过全部测试） | 最终成功率 |
| 重试次数 | 无效重试越少越好 |
| Token 消耗 | Runtime 的诊断是否比全量日志丢给 LLM 更省 Token |
| Runtime 决策触达率 | MPC Verifier/Replan 是否实际被触发了（没触发说明场景太简单） |
| 决策后验准确率 | 触发了的决策事后看对不对 |

**如果"编排组"比"基线组"好——哪怕只好了 2 题——就证明了核心假设。**

---

## 8. 结论

### SWE-bench 对 Zelos 的真正意义

```
❌ 不是：Zelos 冲 SWE-bench 排行榜
         Zelos 不是 Agent，不该冲 Agent 的榜单

✅ 而是：SWE-bench 是 Zelos 核心闭环的最高效验证场
         7 步 Task 生命周期恰好驱动
         Planner / Scheduler / MPC / Diagnosis / Replan / Event Bus
         六条核心路径

❌ 不是：Zelos 自己造 Agent 去拿高分
         这是框架思维，不是 Runtime 思维

✅ 而是：Zelos 把最好的 Agent 编排起来
         Agent 是常量，Runtime 是变量
         证明组合拳 > 任何一个单体 Agent
```

### 一句话

**Zelos 不需要在 SWE-bench 上证明自己是最好的 Agent。Zelos 需要在 SWE-bench 上证明——有了 Zelos，任何 Agent 都能跑得比原来更好。**

---

> 📄 **此文档位置：** `docs/swebench-for-zelos.md`
