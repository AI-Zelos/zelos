# Zelos Runtime Benchmark Plan

> **目标：SWE-bench Verified Standardized 第一名。**
>
> 非靠更强模型。靠 Runtime 替 LLM 做工程决策——Runtime 理解执行反馈、分类失败、诊断根因、知道什么时候该修什么时候该放弃。目前没有人这样做。

---

## 零、为什么能赢

当前榜首：**Claude 4.5 Opus + mini-SWE-agent = 76.8%**。

所有方案的共同盲区：**Runtime 产生的执行信息没有被 Runtime 自己消费。** Agent 跑完 pytest，把 stdout 原样贴给 Claude——Runtime 什么都没干。

Zelos 的差异化：**LLM 负责产生候选方案。Runtime 负责所有可以程序化完成的工程决策。**

```
Docker
    │
    ▼
Zelos Runtime ──────────────────────┐
  ├── Test Runner（跑全量测试）       │
  ├── Diagnosis Engine（理解日志）★   │  ← LLM 不管这些
  ├── Failure Classifier（分类）★     │
  ├── Patch Ranker（候选评分）        │
  └── Scheduler（修/重试/放弃）★     │
    │                                │
    ▼                                │
Fixer Agent ← 只拿诊断结论 ──────────┘
```

### 核心竞争力

不是"压缩日志"——是**理解日志**。

| 原始信息 | Runtime 诊断 | 策略 |
|---------|-------------|------|
| `FAILED test_xxx, AssertionError: expected [1,2,3] got [1,2]` | 断言失败，单模块影响，方向正确 | → 继续 Fixer |
| 50 个 test 全炸 | Patch 方向根本错误 | → 立即放弃，切换候选 |
| `ImportError: No module named 'xxx'` | 依赖缺失 | → 尝试补 import |
| 同一测试连续 3 轮失败 | 死循环 | → 止损，标记 B 类 |
| `Timeout after 300s` | 算法复杂度过高 | → 建议降复杂度 |

**这不是 Compression。这是 Diagnosis + Decision。**

### 目标

按对 Pass@1 的预期贡献排序：

| 优先级 | 模块 | 预期贡献 | 说明 |
|--------|------|---------|------|
| ⭐⭐⭐⭐⭐ | **Diagnosis Engine**（日志→诊断结论） | 最高 | 当前没有人做 |
| ⭐⭐⭐⭐⭐ | **Failure Classifier**（分类→策略） | 很高 | 消除无效重试 |
| ⭐⭐⭐⭐☆ | **Runtime-Guided Repair**（基于诊断的修复） | 很高 | 区别于简单的 Retry |
| ⭐⭐⭐⭐☆ | **Repository Knowledge**（调用图/依赖图） | 很高 | 提升首次生成质量 |
| ⭐⭐⭐☆☆ | **Patch Ranking**（多因子候选评分） | 中等 | 提升候选筛选 |
| ⭐⭐☆☆☆ | 多 Prompt 并行 | 中等偏低 | 成本高、边际递减 |
| ⭐⭐☆☆☆ | Reflection / Debate | 较低 | 已被卷烂 |
| ⭐☆☆☆☆ | Prompt 微调 | 很低 | 不是 Runtime 的战场 |

---

## 一、Zelos 参赛架构

对外：标准 SWE-bench Agent 接口 `execute(instance_id) → patch`

内部：

```
SWE-bench Harness
    │
    ▼
Zelos Meta-Agent
    │
    ├── Phase 1：并行探索（多 Prompt 策略，最多 3-4 路）
    │
    ├── Phase 2：预筛选（格式、dry-run、语法 + 多因子评分）
    │    评分维度：修改文件数、修改 LOC、是否改测试、
    │              是否跨 package、是否影响 issue 提及的模块
    │
    ├── Phase 3：Runtime-Guided Repair ★
    │    ├─ Docker 执行完整测试
    │    ├─ Diagnosis Engine：日志 → 诊断结论（非压缩）
    │    ├─ Failure Classifier：判定修/重试/放弃
    │    ├─ Runtime 跟踪已尝试的 Hypothesis，避免重复
    │    └─ Fixer 拿诊断结论定向修复（上限 3 轮）
    │
    └── Phase 4：Submit
         仅输出内部全过的 patch
```

---

## 二、基准榜单（Standardized Harness, 2026-07）

| 排名 | 方案 | Verified |
|------|------|----------|
| 1 | Claude 4.5 Opus + mini-SWE-agent | 76.8% |
| 2 | Gemini 3 Flash + mini-SWE-agent | 75.8% |
| 9 | DeepSeek V3.2 + mini-SWE-agent | 70.0% |

**内部目标**：80-82% 设计方案。工程里程碑逐个验证，不以预估分数为硬指标。

---

## 三、核心模块详述

### Diagnosis Engine（P0，最高优先级）

输入：Docker 测试原始输出
输出：结构化诊断结论

```
原始 pytest 输出（80KB）
    │
    ▼
Diagnosis Engine:
  ├── 提取 FAILED 测试（test name + assertion + expected/actual）
  ├── 提取 ERROR 测试（exception type + traceback + file:line）
  ├── 统计：总测试数、失败数、错误数、通过率
  ├── 判断影响范围：单 module / 跨 module / 全量爆炸
  └── 输出诊断结论（~200 tokens）
```

**与"压缩"的本质区别**：压缩只是删掉安装日志。诊断是**给出结论**——"方向对，局部修"vs"方向错，放弃"。

### Failure Classifier（P0，最高优先级）

输入：Diagnosis Engine 的诊断结论
输出：三态策略

| 失败模式 | 信号 | 策略 |
|---------|------|------|
| `AssertionError`、单 module | 方向对，边界 case | **Repair**（定向 Fixer） |
| `TypeError`、`AttributeError` | 接口级错误 | **Repair** |
| `ImportError`、`ModuleNotFoundError` | 环境/依赖 | **Repair**（补依赖） |
| 全量测试爆炸（>50% FAIL） | 方向根本错误 | **Abandon**（切换候选） |
| 同一测试连续 3 轮失败 | 死循环 | **Abandon**（止损） |
| `Timeout`、`OOM` | 性能问题 | **Abandon**（或降复杂度后重试） |

### Runtime-Guided Repair（P1）

与简单的 Retry 的本质区别：**LLM 不是在修 bug，是在执行 Runtime 的诊断结论。**

```
普通 Retry：
  测试挂了 → "Please fix the bug" → 从头生成

Runtime-Guided Repair：
  测试挂了 → Diagnosis Engine → "AssertionError at rst.py:147,
  expected [1,2,3] got [1,2]。方向对，修这一行。" → Fixer 定向修复
```

同时 Runtime 维护 Hypothesis Tracker——记录已尝试的修复方向，避免 LLM 重复猜测。

### Repository Knowledge（P1）

提升**首次生成**质量：

| 知识 | 用途 |
|------|------|
| Call Graph | "这个函数的调用者是谁" |
| Import Graph | "哪些模块依赖这个文件" |
| Module Ownership | "Issue 提到的模块实际影响哪些文件" |
| Change History | "这个文件最近被谁改过、关联哪些 issue" |

如果 Runtime 在 Planner 阶段就提供这些知识，第一次 patch 就会更准——减少对 Repair 的依赖。

### Patch Ranking（P2）

不仅是 compile/lint。多因子评分：

| 因子 | 高分信号 | 低分信号 |
|------|---------|---------|
| 修改文件数 | 1-3 个 | >10 个 |
| 修改 LOC | <50 行 | >500 行 |
| 是否修改测试 | 是 | 否 |
| 是否跨 package | 否 | 是 |
| 是否影响 issue 提及的模块 | 是 | 否 |
| 是否删除 API | 否 | 是 |

---

## 四、不投入的方向（明确放弃）

| 方向 | 原因 |
|------|------|
| Reflection | 已被卷烂，边际收益低 |
| Debate（两个 LLM 互相讨论） | 成本翻倍，收益微弱 |
| Tree Search | 越来越贵，递减 |
| Prompt 微调 | 不是 Runtime 的战场 |
| 5+ 路并行 | >4 路后递减严重，成本暴涨 |

---

## 五、里程碑（可独立验证）

| 里程碑 | 内容 | 验证方式 |
|--------|------|---------|
| M1 | Diagnosis Engine 正确提取结构化诊断 | 50 个失败样本，人工检查诊断质量 |
| M2 | Failure Classifier 分类准确率 | 50 个样本，对比人工分类 |
| M3 | Runtime-Guided Repair 收益 | 消融：开/关 Fixer 对比 |
| M4 | Repository Knowledge 收益 | 消融：有/无知识库对比 |
| M5 | 全模块组合 | 全量 500 题 |

每个里程碑可独立验证贡献，不把希望押在单一模块上。

---

## 六、已有 vs 待实现

### 已完成（P0）

| 组件 | 路径 |
|------|------|
| Format Verifier | `zelos/verifier_formats.py` |
| Arbiter | `zelos/arbiter.py` |
| Contest Dispatch | `zelos/scheduler.py` |

### 待实现

| 优先级 | 模块 | 估计量级 |
|--------|------|---------|
| P0 | Diagnosis Engine | ~150 行 |
| P0 | Failure Classifier | ~100 行 |
| P1 | Runtime-Guided Repair（含 Hypothesis Tracker） | ~200 行 |
| P1 | Repository Knowledge（静态分析集成） | ~200 行 |
| P2 | Patch Ranking（多因子评分） | ~100 行 |
| P2 | 消融实验脚本 | ~3 天 |

---

> **核心命题：LLM 负责产生候选方案。Runtime 负责所有可以程序化完成的工程决策。榜单差距不来自模型，来自 Runtime 对执行信息的消费深度。**
