# Zelos SWE-bench Strategy — Runtime-First

> **榜单第一名没有做到的地方，就是我们的机会。**
>
> Top 10 停在了 76% 左右，不是模型不够好。是所有人都在优化同一个方向——Prompt、多轮对话、工具调用。真正还没人做的是：**让 Runtime 消费执行反馈信息，替代 LLM 做工程决策。**

---

## 一、Top 10 的五类失败模式

几乎所有 Agent 的失败，本质只有五类：

| # | 失败模式 | 现象 | 根因 |
|---|---------|------|------|
| 1 | **一次性生成** | 测试挂了 → 从头重新生成，没有 debug | Agent 没有"定位-修复"循环，只有"重猜"循环 |
| 2 | **浪费 Runtime 信息** | 把 200KB 原始 log 整份塞给 Claude | Runtime 产生的精确错误信息（断言值、文件行号）没有被提取 |
| 3 | **搜索能力不足** | grep 找到 `serializer.py`，但 bug 在 `validation.py` | Agent 没有代码图（call graph/import graph）辅助定位 |
| 4 | **不会止损** | Fail → Fix → Fail → Fix → 死循环 | 没有 Failure Classifier 判断"这题还值不值得修" |
| 5 | **无跨实例学习** | 每道题从零开始，重复犯相同模式的错误 | 没有历史失败数据库 |

**其中 1-4 是 Runtime 可以解决的。5 是长期方向，暂不投入。**

---

## 二、还值得投入的三个方向（按优先级）

### ⭐⭐⭐⭐⭐ Evidence Compression（结构化测试证据）

**当前做法**：Agent 跑完 pytest，把整个输出（含安装日志、构建输出、200KB+）原样塞给 Claude。

**Zelos 做法**：Runtime 消费测试输出 → 提取结构化 Evidence：

```
原始 pytest 输出（80KB）
    │
    ▼
Zelos Evidence Extractor
    │
    ▼
结构化证据（~300 tokens）：
  FAILED tests/test_rst.py::test_header_rows - AssertionError
    Expected: [1, 2, 3]
    Actual:   [1, 2]
    Location: astropy/io/ascii/rst.py:147

  FAILED tests/test_core.py::test_init - TypeError
    RST.__init__() missing 1 required positional argument: 'header_rows'
    Location: astropy/io/ascii/core.py:24
```

**为什么这是最大杠杆**：
- 减少了 99% 的无效 token（200KB → 300 tokens）
- LLM 不再需要从噪音里找信号
- 多轮 Fixer 迭代的上下文膨胀问题从根本上解决

### ⭐⭐⭐⭐⭐ Failure Classification（失败分类器）

**当前做法**：任何测试失败都触发重试，不管失败原因是什么。

**Zelos 做法**：Runtime 对失败分类，决定不同策略：

| 失败类型 | 信号 | 策略 |
|---------|------|------|
| `TypeError` / `AttributeError` | 语法/接口级错误 | ✅ 值得修 |
| `AssertionError` | 逻辑偏差 | ✅ 值得修（最多 3 轮） |
| `ImportError` / `ModuleNotFoundError` | 环境/依赖问题 | ⚠️ 尝试修复 import/install |
| 全量测试爆炸（>50% FAIL） | 方向根本错误 | ❌ 立即放弃，切换候选 |
| 同一测试连续失败 3 轮 | 死循环 | ❌ 止损 |

**为什么重要**：B 类失败（方向根本错误）的持续修复不仅浪费 token，还会产生越改越错的负收益。Runtime 识别 B 类并止损，等于消除了无效消耗。

### ⭐⭐⭐⭐☆ Patch Ranking（多候选预筛选）

**当前做法**：Arbiter 取第一个通过全部验证的 patch。

**Zelos 做法**：并行池内的所有候选先经过**低成本预筛选**，排名后只送 top-2 进 Docker 完整测试：

```
并行池 5 个候选
    │
    ▼
预筛选（0 成本，秒级）：
  ├── 格式检查（正则）
  ├── dry-run（patch 命令）
  ├── py_compile（语法）
  └── 影响范围合理性（改动的文件是否在 issue 提到的模块里）
    │
    ▼
排名 → 选 top-2 → 送 Docker 完整测试
```

---

## 三、明确不投入的方向

这些方向 Top 10 已经卷烂了，继续投入边际收益接近零：

| 方向 | 为什么不投 |
|------|-----------|
| Reflection | 已有大量工作，收益递减 |
| Debate（两个 LLM 互相讨论） | 成本翻倍，收益微弱 |
| Tree Search | 越来越贵，递减 |
| 更多 Prompt 工程 | 已经被榨干 |
| Planner 优化 | 不是瓶颈 |

**Zelos 的差异化不在这些领域。差异化在于 Runtime 替 LLM 做工程决策。**

---

## 四、实现优先级重新排序

基于上面的分析，P0/P1 重新排：

| 优先级 | 模块 | 为什么 |
|--------|------|--------|
| P0 ✅ | 格式 Verifier + Arbiter + 并行 dispatch | 已完成 |
| **P0** | **Evidence Compressor（日志解析器）** | **最大杠杆，当前无人做** |
| **P0** | **Failure Classifier（失败分类器）** | **消除 B 类无效消耗** |
| P1 | Patch Ranking（预筛选排名） | 提升候选质量 |
| P1 | Fixer Loop（定向修复） | 依赖 P0 的 Evidence Compressor |
| P2 | 消融实验 + 多 Prompt 策略 | 学术输出 + 调优 |

---

## 五、Zelos Runtime 架构（更新后）

```
Issue
    │
    ▼
Planner Agent（LLM）
    │
    ▼
Candidate Patches（并行池）
    │
    ▼
Zelos Runtime ──────────────────────────┐
  ├── Format Checker                     │
  ├── Apply Checker（dry-run）           │
  ├── Build Checker（py_compile）        │
  ├── Test Runner（Docker）              │  ← LLM 不管这些
  ├── Evidence Extractor ★               │
  ├── Failure Classifier ★               │
  ├── Patch Ranker                       │
  └── Scheduler（Repair / Retry / Stop） │
    │                                    │
    ▼                                    │
Fixer Agent（LLM）← 只拿结构化证据 ─────┘
    │
    ▼
Runtime（再次全量验证）
    │
    ▼
Submit（仅通过全部检查的 patch）
```

**核心思想：LLM 负责产生候选方案。Runtime 负责所有可以程序化完成的工程决策。**

---

> **SWE-bench 前几名的差距，不会来自更强的大模型，而会来自 Runtime 如何利用执行过程中的反馈信息。这和我们把 Zelos 做成 Runtime 而非 Agent Framework 的定位完全一致。**
