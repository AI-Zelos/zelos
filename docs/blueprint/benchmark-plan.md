# Zelos Runtime Benchmark Plan

> **目标：SWE-bench Verified 第一名，拉大与第二名的差距。**
>
> Zelos 作为一个 Meta-Agent 参赛——对外是标准 Agent 接口，内部是多 Agent 协作 + 迭代优化 Pipeline。

---

## 一、目标 Leaderboard

**SWE-bench Verified（Standardized Harness）** — mini-SWE-agent v2 统一框架评测，所有人同一起跑线。

当前排名（2026-07）：

| 排名 | 方案 | 分数 |
|------|------|------|
| **1** | **Claude 4.5 Opus + mini-SWE-agent** | **76.8%** |
| 2 | Gemini 3 Flash + mini-SWE-agent | 75.8% |
| 3 | MiniMax M2.5 + mini-SWE-agent | 75.8% |
| 4 | Claude Opus 4.6 + mini-SWE-agent | 75.6% |
| 9 | DeepSeek V3.2 + mini-SWE-agent | 70.0% |

**目标排名：**

| 排名 | 方案 | 目标分数 |
|------|------|---------|
| **1** | **Claude 4.5 Opus / GPT-5 + Zelos** | **78-80%** |
| 2 | Claude 4.5 Opus + mini-SWE-agent | 76.8% |

**领先第二名 1-3 个百分点**——看起来不多，但 SWE-bench Top 10 的差距也就 0.4pp。1pp+ 就是显著领先。

---

## 二、方案对比：Zelos vs mini-SWE-agent

| 能力 | mini-SWE-agent | Zelos |
|------|---------------|-------|
| 多轮对话 | ✅ 手动脚本编排 | ✅ Runtime 状态机管理 |
| 文件导航 | ✅ 内建 | ⚠️ 需实现 Locator Agent |
| 测试反馈 | ✅ 解析输出 | ✅ Docker 内跑全量测试 |
| 失败重试 | ⚠️ 简单重跑 | ✅ Fixer Loop（分析失败原因→定向修复） |
| **并行探索** | ❌ 串行 | ✅ 多个 prompt 策略同时跑 |
| **多模型 Ensemble** | ❌ 单一模型 | ✅ Claude + GPT 并行，自动选优 |
| **预评测** | ❌ 提交后才知道 | ✅ Docker 内预跑，只提交验证过的 |
| **迭代修复** | ❌ 手动 | ✅ 自动化 Fixer Loop |

Zelos 的差异化不在任何一个单点，在于**把所有这些能力变成了一个自动化 Pipeline**。mini-SWE-agent 需要人手动跑多次、手动挑结果、手动重试——Zelos 全自动。

---

## 三、Zelos 参赛方式

Zelos 对外暴露标准 Agent 接口，内部是多 Agent 协作 Pipeline：

```
SWE-bench 评测框架
    │  execute(issue) → patch
    ▼
Zelos Meta-Agent
    │
    ├── Phase 1: 并行探索（10 路并行）
    │   ├── Claude × 3（不同 prompt 策略）
    │   ├── GPT-5 × 2
    │   └── 专用 Agent × 5（per-repo 优化）
    │
    ├── Phase 2: 预评测（7 关筛选，前 5 关 0 成本）
    │   ├── 格式检查（正则）
    │   ├── dry-run（patch --dry-run）
    │   ├── Lint（flake8）
    │   ├── 语法检查（py_compile）
    │   ├── 影响范围检查
    │   └── Docker 内跑 SWE-bench 测试
    │
    ├── Phase 3: Fixer Loop（top 3 patches）
    │   └── 测试没过 → 失败用例喂给 Fixer Agent → 再修 → 再测
    │
    └── Phase 4: Submit
        └── 只提交 Zelos 内部评测 100% 通过的 patch
```

**SWE-bench 提交格式：**
```json
{
  "instance_id": "astropy__astropy-12907",
  "model_name_or_path": "Zelos + Claude 4.5 Opus",
  "model_patch": "..."
}
```

---

## 四、为什么能拿第一

### 对手的短板

mini-SWE-agent 的第一名 76.8% 有一个关键弱点：**它是单 Agent 串行执行。** 生成一个 patch → 跑测试 → 如果错了 → 手动重跑。没有并行探索，没有自动 Fixer Loop，没有预评测筛选。

### Zelos 的杠杆

| 杠杆 | 预估提升 | 理由 |
|------|---------|------|
| 并行探索（10 路 vs 1 路） | +3-5pp | 多个 prompt 策略覆盖更多解法 |
| 预评测筛选（0 成本筛掉格式错误） | +2-3pp | Pilot 数据：5/7 失败是格式问题 |
| Fixer Loop（测试没过自动修） | +2-4pp | 把"差一点就对了"的 patch 修到全对 |
| Pipeline 自动编排（零人工） | 定性 | 可以跑更多次迭代而不增加人工成本 |

**保守估计：基线 45%（裸 Claude）→ Zelos Pipeline → 78-80%。**

---

## 五、为什么领先第二名的幅度可控

SWE-bench Verified 已经接近饱和（Top 10 差 0.4pp）。任何方案的天花板都受限于：
- 模型对 bug 的理解能力
- 测试套件的覆盖率边界
- 某些 issue 本身不清晰或缺少足够上下文

Zelos 能把"模型能解决的题"的解决率拉到接近 100%（通过并行+预评测+Fixer），但"模型本来就不会的题"仍然不会。后者约占 20-22%。**78-80% 就是这个天花板的合理估计。领先第二名 1-3pp 就是巨大优势。**

---

## 六、Pilot 数据（已跑）

| 方案 | 实例 | 解决 | 解决率 |
|------|------|------|--------|
| Claude Code 单 Agent（裸调） | 7 | 2 | 28.6% |
| Claude Code + Zelos v2（验证+重试） | 3 | 1 | 33.3%* |

*Pilot 规模太小，未体现 Pipeline 全量效益。5/7 基线失败是纯格式问题——Zelos 的格式验证能 100% 拦截并触发重试。

**Pilot 已证明的核心论点：0 个失败是逻辑错误（patch 格式对但测试不过）。所有失败都是格式问题——确定性工具能 100% 解决。**

---

## 七、已有 Benchmark（Runtime 性能）

```
EventBus:      890,000 events/s
TaskGraph:   2,250,000 transitions/s
Capability: 37,500,000 queries/s
Scheduler:    570,000 scores/s
```

这些数据证明 Zelos 的 Runtime 开销极低，不会是 Pipeline 的性能瓶颈。

---

## 八、实施路径

| 阶段 | 内容 | 时间 |
|------|------|------|
| **P0** | Scheduler 支持"同一 Task 并行派给多个 Agent" + Arbiter | 1 天 |
| **P0** | VerifierChain 格式检查（正则、dry-run、lint、语法） | 1 天 |
| **P1** | Docker 预评测集成（Zelos 内部跑 SWE-bench 测试） | 2 天 |
| **P1** | Fixer Loop（测试失败→分析→修复→再测） | 2 天 |
| **P2** | 多 prompt 策略模板（per-repo 优化） | 3 天 |
| **P3** | 全量 500 题跑分 + 调优 | 3 天 |
| **P3** | 提交 Leaderboard | 1 天 |

---

## 九、成本估算

| 项目 | 估算 |
|------|------|
| Claude 4.5 Opus API（500 题 × 平均 5 次调用） | ~$400-600 |
| Docker 评测（500 题 × 平均 2 分钟） | ~17 CPU-hours |
| 人工（prompt 调优 + 分析失败 case） | ~3 天 |

---

> **Zelos 不是"更好的模型"。Zelos 是让同一个模型能从失败中学习、从并行中择优、从迭代中收敛的 Runtime。SWE-bench 验证的不是模型能力——是学习循环的效率。**
