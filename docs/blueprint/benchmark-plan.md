# Zelos Runtime Benchmark Plan

> **目标：SWE-bench Verified Standardized 第一名。领先第二名 4–6 个百分点。**
>
> 非靠更强基础模型。通过向模型提供**测试失败精确结构化诊断信息**实现增益——该反馈闭环在现有方案中未被系统性落地。

---

## 零、为什么能拉开差距

当前榜首：**Claude 4.5 Opus + mini-SWE-agent = 76.8%**。剩余 23.2% 并非全不可解。

行业现状：几乎所有方案优化重心集中于"首次如何生成更高质量 patch"。mini-SWE-agent 内置重试本质是**全局重启生成**——测试失败后回到起点重新理解 issue、重读代码、从零产出补丁，等于"整张试卷重做"，无定向调试回路。

**Zelos 核心创新：Fixer Loop 定向手术迭代**

不是无差别重试，而是模拟人类程序员调试流程：

```
1. Patch 送入 Docker 执行全量测试
2. 日志解析器提取结构化失败证据：
   - 失败测试用例标识（test_xxx）
   - 断言信息：期望值 vs 实际输出
   - 异常堆栈、精确文件与行号
3. 将精简结构化报错交付 Fixer Agent
4. Fixer 基于原有修复思路做局部定向修正，输出新版补丁
5. 重新评测；最多迭代 3 轮
6. 迭代上限仍失败 → 废弃当前候选，切换并行池内其他修复思路
```

**Fixer Agent 无需重新猜测缺陷位置——运行时测试日志已经给出精确故障坐标。这是和现有方案最本质的分水岭。**

### 收益区间（基于失败样本分布约束）

失败样本分类：
- **A 类（可抢救）**：首轮修复方向正确，仅边界条件、类型、索引等局部缺陷；占失败样本 **15%–25%**
- **B 类（不可抢救）**：首轮对需求/架构理解完全跑偏，定向迭代只会持续恶化

量化测算：

```
基线：76.8%
保守：76.8% + (23.2% × 15%) = 80.3%
乐观：76.8% + (23.2% × 25%) = 82.6%
```

叠加并行多候选探索 + 前置预评测额外 1–2pp：

**主力目标：80%–82% ｜ 理论上限：83%**

当前第二名 75.8%，稳定到 81% 即可拉开 5pp。头部差 0.4pp 的榜单环境下，4–6pp 是代际级差距。

> 原始预估 83–86% 已修正为乐观上限，不做硬性考核指标。

---

## 一、Zelos 参赛架构

对外兼容标准 SWE-bench Agent 接口：`execute(instance_id) → final_patch`

内部四阶段流水线：

```
SWE-bench Harness
    │
    ▼
Zelos Meta-Agent
    │
    ├── Phase 1：并行多策略探索
    │    同一任务多组 Prompt 策略，并行生成多条候选 Patch
    │
    ├── Phase 2：前置预评测
    │    格式校验 → Patch 可应用性 → Lint/语法 → Docker 轻量测试
    │    Arbiter 过滤无效候选，排序可用 patch 送入 Fixer 回路
    │
    ├── Phase 3：Fixer Loop ★核心差异化
    │    ├─ Docker 执行完整测试套件
    │    ├─ 日志结构化解析器：压缩原始输出，提取行号、断言、异常摘要
    │    ├─ Fixer Agent 定向迭代修复（上限 3 轮）
    │    └─ 迭代耗尽仍失败 → 废弃，取回并行池下一条候选
    │
    └── Phase 4：Submit
         仅输出 Zelos 内部全过的最优补丁
```

SWE-bench 提交格式：`{"instance_id": "...", "model_name_or_path": "Zelos + Claude 4.5 Opus", "model_patch": "..."}`

全部并行、迭代、内部测试均属推理时扩展（Test-Time Scaling），符合 SWE-bench 规则。

---

## 二、基准榜单（Standardized Harness, 2026-07）

| 排名 | 方案 | Verified |
|------|------|----------|
| 1 | Claude 4.5 Opus + mini-SWE-agent | 76.8% |
| 2 | Gemini 3 Flash + mini-SWE-agent | 75.8% |
| 3 | MiniMax M2.5 + mini-SWE-agent | 75.8% |
| 9 | DeepSeek V3.2 + mini-SWE-agent | 70.0% |

| 方案 | 目标区间 |
|------|----------|
| **Claude 4.5 Opus + Zelos** | **80%–82%（乐观上限 83%）** |
| Claude 4.5 Opus + mini-SWE-agent | 76.8% |

---

## 三、Zelos vs mini-SWE-agent

| 能力 | mini-SWE-agent | Zelos |
|------|---------------|-------|
| 多轮对话 | ✅ | ✅ |
| 文件导航 | ✅ | ✅ 复用模型原生能力 |
| 测试日志接收 | ✅ 原始日志 | ✅ 结构化压缩 + 精准提取 |
| 失败重试 | ⚠️ 全局从头生成 | ✅ Fixer 定向局部迭代 |
| 并行多候选 | ❌ | ✅ |
| 前置预评测过滤 | ❌ | ✅ |
| **失败结构化定向修复** | ❌ | ✅ **核心差异** |

---

## 四、风险清单

| # | 风险 | 应对 |
|---|------|------|
| 1 | **上下文膨胀**：多轮迭代累积 issue+历史patch+报错，token 开销飙升 | 日志压缩模块：只传 `测试名 + 文件:行号 + Expected/Actual + 精简堆栈` |
| 2 | **Hunk 冲突**：Fixer 基于旧 patch 修改，多轮后行号偏移导致 apply 失败 | Fixer 每次基于**原始仓库快照**生成全新 patch，非增量修改 |
| 3 | **无效迭代死循环**：B 类失败在错误路径来回微调 | 迭代上限停损 + 自动切换并行池下一条候选 |
| 4 | **API 成本**：并行多路 + Docker + Fixer 循环，单任务 token 估为基线 2.5-4× | 先跑 50 例消融实验验证收益，确认后再全量 |
| 5 | **边际递减**：并行 >4 路后成本暴涨、收益微弱 | 上限设 3-4 路 |

---

## 五、现状 vs 目标

### 已有

| 组件 | 路径 | 用途 |
|------|------|------|
| Scheduler | `zelos/scheduler.py` | 多 Agent 调度，已有 |
| VerifierChain | `zelos/verifier_chain.py` | 链式验证框架，已有 |
| Event Sourcing | `zelos/event_sourcing.py` | Fixer 全轮状态保存回放，已有 |
| Task 状态机 | `zelos/task_graph.py` | FAILED↔READY 流转（Fixer 骨架），已有 |
| EvidenceBag | `zelos/evidence.py` | 每轮诊断证据收集，已有 |
| Format Verifiers | `zelos/verifier_formats.py` | ✅ P0 已完成 |
| Arbiter | `zelos/arbiter.py` | ✅ P0 已完成 |
| Contest Dispatch | `zelos/scheduler.py` | ✅ P0 已完成 |

### 待实现

| 模块 | 改造 | 量级 |
|------|------|------|
| 日志解析器 | Docker 输出 → 结构化失败证据压缩（**核心护城河**） | P0 |
| Fixer Loop 编排 | Runtime 加状态流转：测试失败 → 提取日志 → FixerTask → 重调度 | ~50 行 |
| Docker 预评测 | Verifier 内调 shell 跑容器测试 | 轻量封装 |
| 迭代失败切换 | 耗尽后自动切换并行池下一条候选 | ~30 行 |
| 消融实验脚本 | 可关闭并行/关闭 Fixer 做对照 | P2 |

---

## 六、实施阶段

| 阶段 | 内容 | 状态 |
|------|------|------|
| P0 ✅ | 并行 dispatch + Arbiter + 格式 Verifier | 已完成 |
| P0 | **结构化日志解析器**（核心护城河） | 待做 |
| P1 | Docker 预评测 + Fixer Loop + 失败切换 | 待做 |
| P2 | 多 Prompt 策略 + 消融实验脚本 | 待做 |
| P3 | SWE-bench Verified 全量 500 题 + 提交 | 待做 |

---

## 七、学术附加价值

整套系统天然支持消融实验：
1. 量化各模块独立贡献：并行候选收益、Fixer 迭代收益、最大迭代次数影响
2. 失败案例二元分类统计：B 类（根本理解偏差）vs A 类（局部实现缺陷）
3. 可产出 FSE/ICSE 级结论：**结构化运行时诊断反馈显著提升真实仓库 Bug 修复率**

---

> **核心命题：不是让模型更聪明。是模型生成错误补丁时，自动交付精确调试信息——报错位置、期望值、运行时堆栈，复刻人类程序员调试条件。Zelos 将这回路工程化自动化——也是现有方案普遍缺失的一环。**
