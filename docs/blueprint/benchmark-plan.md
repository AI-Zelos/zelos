# Zelos Runtime Benchmark Plan

> **目标：SWE-bench Verified Standardized 第一名。领先第二名 7-9 个百分点。**
>
> 不是靠更好的模型。是靠给同一个模型**失败时的精确坐标**——这件事没有人做过。

---

## 零、为什么能拉大差距

当前第一 76.8%（Claude 4.5 Opus + mini-SWE-agent）。剩下 23.2% 为什么过不了？

**不是格式问题。** mini-SWE-agent 早就处理了格式。这 23.2% 是真正难的题——要多文件协同、要深领域知识、issue 写得不清楚。

所有人都在优化"怎么生成更好的 patch"。**Zelos 优化的是"怎么从失败中救回来"。** 这是当前所有方案的盲区。

### Fixer Loop：不是重试，是定向手术

mini-SWE-agent 的"重试"是**重新跑一遍完整生成**——等于让学生重考整张卷子，而不是告诉他错在哪道题。

Zelos 的 Fixer Loop 是：

```
1. patch 跑测试 → 挂了
2. 从 Docker 输出中提取：
   - 哪些测试挂了（精确到 test_foo_bar）
   - 每个测试的断言：期望什么 vs 实际得到了什么
   - 堆栈指向的文件和行号
3. 喂给 Fixer Agent：
   "你上一次的 patch 导致这 3 个测试失败：
    test_foo: expected [1,2,3] got [1,2], at astropy/rst.py:147
    test_bar: TypeError at astropy/core.py:24
    test_baz: index out of range at django/models.py:89"
4. Fixer Agent 定向修复 → 重新评测 → 还挂？← 再修（最多 3 轮）
5. 全过 → 提交
```

**Fixer Agent 不需要猜 bug 在哪里。测试失败报告已经把位置精确到行了。** 这和人类 debug 的条件完全一样。

### 这个差距有多大

```
基线（Claude 4.5 Opus 裸调）:            ~45%
+ mini-SWE-agent（多轮交互+文件导航）:    ~76.8%
+ Zelos Pipeline（并行探索+预评测）:      ~78-80%（与 mini-SWE-agent 基本持平）
+ Fixer Loop（失败精准修复）:             ~83-86%（拉开差距）
```

如果 23.2% 的失败中有 30-40% 是"差一点就对"的 patch（语法对、逻辑对、个别边界 case 没过）——Fixer Loop 救回来：

```
保守：76.8% + (23.2% × 30%) = 83.8%
乐观：76.8% + (23.2% × 40%) = 86.1%
```

**领先第二名 7-9 个百分点。** 当前 Top 10 只差 0.4pp。7pp 是**代际差距**。

---

## 一、Zelos 参赛方式

Zelos 对外是标准 Agent 接口，内部是四阶段 Pipeline：

```
SWE-bench 评测框架
    │  execute(issue) → patch
    ▼
Zelos Meta-Agent
    │
    ├── Phase 1: 并行探索
    │   └── 同一 issue，多个 prompt 策略并行生成 patch
    │
    ├── Phase 2: 预评测
    │   └── 格式→dry-run→lint→语法→Docker 内跑全量测试
    │
    ├── Phase 3: Fixer Loop ★核心差异
    │   ├── 解析测试失败 → 提取到精确行号的错误报告
    │   └── 喂给 Fixer Agent → 定向修复 → 重新评测 → 迭代
    │
    └── Phase 4: Submit
        └── 只提交 Zelos 内部 100% 通过的 patch
```

**SWE-bench 提交格式：**
```json
{"instance_id": "astropy__astropy-12907", "model_name_or_path": "Zelos + Claude 4.5 Opus", "model_patch": "..."}
```

---

## 二、当前 Leaderboard（Standardized Harness, 2026-07）

| 排名 | 方案 | 分数 |
|------|------|------|
| 1 | Claude 4.5 Opus + mini-SWE-agent | 76.8% |
| 2 | Gemini 3 Flash + mini-SWE-agent | 75.8% |
| 3 | MiniMax M2.5 + mini-SWE-agent | 75.8% |
| 9 | DeepSeek V3.2 + mini-SWE-agent | 70.0% |

| 排名 | 方案 | 目标分数 |
|------|------|---------|
| **1** | **Claude 4.5 Opus + Zelos** | **83-86%** |
| 2 | Claude 4.5 Opus + mini-SWE-agent | 76.8% |

---

## 三、Zelos vs 现有方案

| 能力 | mini-SWE-agent | Zelos |
|------|---------------|-------|
| 多轮交互 | ✅ | ✅ |
| 文件导航 | ✅ | ⚠️ 需实现 |
| 测试反馈 | ✅ 解析输出 | ✅ Docker 内跑全量 |
| 失败重试 | ⚠️ 完整重新生成 | ✅ Fixer Loop 定向修复 |
| 并行探索 | ❌ | ✅ |
| 预评测筛选 | ❌ | ✅ 0成本筛格式 + Docker预跑 |
| **失败精准修复** | **❌** | **✅ 核心差异** |

---

## 四、Pilot 数据

| 方案 | 实例 | 解决 | 解决率 |
|------|------|------|--------|
| Claude Code 单 Agent | 7 | 2 | 28.6% |

5 个失败全是格式问题，0 个逻辑错误。格式问题 Zelos 确定性验证能 100% 拦截。

---

## 五、实施路径

| 阶段 | 内容 |
|------|------|
| P0 | Scheduler 支持同一 Task 并行多 Agent + Arbiter 选优 |
| P0 | VerifierChain：格式/dry-run/lint/语法/Docker 预评测 |
| P1 | **Fixer Loop：测试失败解析 + 定向修复 + 迭代** |
| P2 | 多 prompt 策略模板 |
| P3 | 全量 500 题 + 调优 + 提交 |

---

> **核心命题：不是让模型更聪明。是在模型失败的时候，告诉它错在哪一行、期望值是什么、堆栈指向哪里。人类 debug 靠的就是这个——Zelos 把它自动化了。**
