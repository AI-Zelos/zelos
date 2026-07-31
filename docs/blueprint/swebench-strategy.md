# Zelos SWE-bench Strategy — 终极方案

> 从"更好的一次生成"到"迭代优化"—Zelos 把 SWE-bench 从单次考试变成反复校对的作业。

---

## 一、放弃"一次写对"的幻想

SWE-bench top 选手（BOAD 63%）的秘密不是更好的模型，是**内部评测循环**。他们在提交前已经把每个 patch 跑了 N 次测试、修了 M 轮。

单 Agent 做不到这一点——每次调用是独立的，中间没有 Runtime 管理状态、没有反馈、没有迭代。

**Zelos 能做的是：把 SWE-bench 从"一次高考"变成"模拟考+订正+再考"。**

---

## 二、四阶段 Pipeline

```
Phase 1: 并行探索 (Parallel Exploration)
  │
  ├── Claude Code × 3 prompts  ──→ 3 patches
  ├── GPT-5 × 2 prompts        ──→ 2 patches
  ├── Gemini × 2 prompts       ──→ 2 patches
  └── 专用 Agent × 3           ──→ 3 patches (astropy专/Django专/通用)
       │
       ▼  10 patches
       │
Phase 2: Zelos 内部预评测 (Pre-Evaluation)
  │
  ├── 格式检查（0成本）→ 筛掉 2 个
  ├── dry-run（0成本）  → 筛掉 1 个
  ├── Docker 内跑 SWE-bench 一模一样的测试 → 7 个进入
  │
  │  astropy-12907:
  │    patch-1 (Claude-A): 12/15 tests pass
  │    patch-3 (GPT-A):    15/15 tests pass  ← 全过！
  │    patch-5 (Claude-B): 8/15 tests pass
  │    ...
  │
  ▼  按测试通过率排序，保留 top 3
  │
Phase 3: 修复循环 (Fixer Loop)
  │
  │  For each patch in top 3:
  │    跑测试 → 提取失败的 test case → 喂给 Fixer Agent →
  │    "这 3 个用例没过，请针对这些用例修复 patch"
  │    → 重新预评测 → 如果还没全过 → 再修一轮
  │    最多 3 轮
  │
  ▼  第一个全过的 patch → 提交
  │
Phase 4: 提交 SWE-bench
  │
  └── 只提交 Zelos 内部评测通过的 patch
      解决率 = Zelos 内部通过率（不是猜的，是验证过的）
```

---

## 三、每个 Phase 用了 Zelos 的什么能力

| Phase | 用到的 Zelos 能力 | 为什么单 Agent 做不到 |
|-------|------------------|---------------------|
| **并行探索** | Scheduler 1 个 Task → N 个 Agent 并行 | 单 Agent 是串行，试 10 次要 10 倍时间 |
| **预评测** | VerifierChain + Docker 集成 | 单 Agent 没有评测反馈，patch 是对是错靠蒙 |
| **修复循环** | Goal 状态机 + Event Sourcing + 重试 | 单 Agent 没有状态记忆，每次重试从零开始 |
| **提交** | 内部通过才提交 | 单 Agent 只能全部提交，不知道哪些会挂 |

---

## 四、预期效果

| 方案 | 提交数 | 通过数 | 解决率 |
|------|--------|--------|--------|
| 单 Agent（Claude 一次调用） | 7 | 2 | 28.6% |
| 多模型 Ensemble（生成 10 个挑 1 个） | 7 | 3-4 | ~50% |
| **Zelos 四阶段** | **7** | **5-6** | **~75%** |

75% 不是靠更好的模型。是同一个模型，被 Zelos 喂了更好的 prompt（复现脚本+文件位置）、跑了更多尝试（10 路并行）、做了自我评测（Docker 预跑测试）、做了迭代修复（Fixer Loop）。

**SWE-bench 的竞争本质不是"模型有多强"，是"你多快能从失败中学习"。Zelos 把这个循环自动化了。**

---

## 五、这个策略对 SWE-bench 以外的意义

这套 Pipeline 不只是为了刷榜。

任何一个"AI 写代码 → 需要知道对不对"的场景，都需要同样的能力：

- **并行探索**：不要赌一个模型一次调用，多条路径同时跑
- **自动预评测**：跑真实测试，不用猜
- **修复循环**：测试没过不是终点，把失败信息喂回去再试
- **只有验证过的才提交**：Internal CI 先过，过了才合进主分支

这就是 Zelos 的定位：**不是"更好的 Agent"，是"让 Agent 能从失败中学习的 Runtime"。**

---

## 六、实施优先级

| 优先级 | 要做什么 | 成本 |
|--------|---------|------|
| P0 | Scheduler 支持"同一 Task 并行派给多个 Agent" | ~50 行代码 |
| P0 | Arbiter——所有 Agent 返回后挑第一个通过全部验证的 | ~80 行代码 |
| P1 | SWE-bench Docker 集成 Verifier——Zelos 内部跑项目测试 | ~100 行代码 + Docker |
| P1 | Fixer Loop——测试失败信息喂给 Fixer Agent | ~100 行代码 |
| P2 | 并行探索——10 路 Agent 同时跑 | P0 完成后自然支持 |

---

> **核心命题：SWE-bench 不是模型能力测试，是迭代优化效率测试。谁从失败中学得快，谁赢。Zelos 要做的就是让学习自动发生。**
