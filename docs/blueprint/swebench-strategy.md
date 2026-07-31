# Zelos SWE-bench Strategy — Fixer Loop

> **核心洞察：SWE-bench 的竞争不是"谁生成得更好"，是"谁从失败中救得回来"。** 目前没有人做第二件事。

---

## 一、当前格局

SWE-bench Verified（Standardized Harness），2026-07：

| 排名 | 方案 | 分数 |
|------|------|------|
| 1 | Claude 4.5 Opus + mini-SWE-agent | 76.8% |
| 2 | Gemini 3 Flash + mini-SWE-agent | 75.8% |
| 3 | MiniMax M2.5 + mini-SWE-agent | 75.8% |

所有人都用同一个 harss。所有人都用同一个模型。**差距在 agent 框架，不在模型。**

---

## 二、76.8% 的天花板怎么来的

mini-SWE-agent 做了三件事：
1. 多轮交互——不是一次生成，是多次对话（"看看这个文件""再看看那个"）
2. 文件导航——能读 repo 里的文件来理解上下文
3. 测试反馈——跑测试，知道 patch 过没过

但这三件事都是**"帮你写对"**——优化的是第一次生成的质量。

**没有人做"写错了以后怎么办"。**

当前第一名的流程：

```
生成 patch → 跑测试 → 过了 → 提交
                     → 没过 → 算了，这题放弃
```

那剩下的 23.2%——不是模型完全不会，是一些题"差一点就对了"。这些题被白白放弃了。

---

## 三、Fixer Loop：把"差一点"变成"过了"

**当 patch 没通过测试时，Zelos 不放弃。它把失败变成了新的输入。**

```
生成 patch → 跑测试 → 没过
                         │
                         ▼
              Zelos 提取失败报告：
                test_foo: FAIL, expected [1,2,3] got [1,2]
                Location: astropy/rst.py:147
                test_bar: FAIL, TypeError at astropy/core.py:24
                test_baz: FAIL, IndexError at django/models.py:89
                         │
                         ▼
              Fixer Agent 拿到精确坐标，定向修复
                         │
                         ▼
              重新评测 → 全过了 → 提交
```

Fixer Agent 和一个人类 debugger 知道的信息一样多——哪一行错了、期望什么、实际是什么。

---

## 四、为什么这个 win

| | mini-SWE-agent | Zelos Fixer Loop |
|---|---|---|
| patch 没过怎么办 | 放弃 | 分析失败 → 定向修复 → 再试 |
| 多轮对话 | 有 | 有 |
| 文件导航 | 有 | 有 |
| 失败信息给 Agent | 不给 | 精确到行号 |

**差距不在生成环节。在失败处理环节。** 所有人都优化"怎么写对"，没人优化"写错了怎么救"。

---

## 五、预期效果

```
基线（裸模型）:        ~45%
+ mini-SWE-agent:      ~76.8%（多轮对话+文件导航）
+ Zelos Fixer Loop:    ~83-86%（救回"差一点"的题）
```

如果在 23.2% 的失败中，有 30-40% 是"逻辑基本对、个别 case 没过"的题，Fixer Loop 能救回来：

```
保守：76.8% + (23.2% × 30%) = 83.8%
乐观：76.8% + (23.2% × 40%) = 86.1%
```

**领先第二名 7-9 个百分点。当前 Top 10 只差 0.4pp。7pp 是代际差距。**

---

## 六、实现复杂度

Fixer Loop 的核心组件：

| 组件 | 难度 | 说明 |
|------|------|------|
| 测试输出解析 | 低 | pytest 输出是结构化的，正则提取即可 |
| 失败报告生成 | 低 | 拼接解析结果 |
| Fixer prompt 模板 | 中 | 需要实验最优的 prompt 格式 |
| Docker 重跑 | 中 | SWE-bench 已有 Docker 环境，复用 |
| Zelos Orchestrator 编排 | 低 | Goal → Task → 重试，Runtime 已有 |

**全部加起来 ~300 行 Python。**

---

## 七、为什么别人没做

1. **mini-SWE-agent 是 benchmark 工具，不是 Runtime。** 它的设计目标是把模型接上 Docker 评测——不是为了最大化分数。它的"重试"是简单的 re-run。

2. **SWE-bench 的评测逻辑不鼓励修 retry。** 提交一次就出分，没人在乎你内部重试了多少次。但 Zelos 在乎——因为 Zelos 要证明 Runtime 的价值。

3. **失败修复听起来简单，做起来需要状态管理。** 每次 Fixer 迭代需要记住"上次改了啥""哪些测试还挂着""这是第几轮"——这正是 Zelos Event Sourcing 和 Task 状态机天然擅长的。

---

> **Zelos 不是更好的 Agent。Zelos 是让 Agent 能从失败中学习的 Runtime。**
