# Zelos Runtime Benchmark Plan

> **Zelos 作为一个"Meta-Agent"参加全球公开 benchmark。不是自己建 leaderboard——是把自己的名字写进已有的、全世界都认的排名里。**

---

## 一、策略：Zelos 是一个 Agent

Zelos 对外暴露一个 `execute(task) -> artifact` 接口。这就是所有 benchmark 对 Agent 的唯一要求。

**内部是多 Agent 协作，外部看起来就是一个 Agent。**

```
任何 Benchmark 框架
    │  execute("请完成这个任务")
    ▼
Zelos Meta-Agent
  ├── Goal → Planner → Task DAG
  ├── Agent 1, Agent 2, Agent 3...
  └── 汇总结果 → 返回
```

这意味着 Zelos 可以直接参加**所有**接受 Agent 提交的公开 benchmark，不需要任何适配。

---

## 二、可提交的全球公测

| Benchmark | 公开排名 | 测什么 | 提交格式 | 多 Agent 优势在哪 |
|-----------|---------|--------|---------|-----------------|
| **SWE-bench** | swebench.com | 修真实 GitHub bug | predictions.json | Planner 分析 + Coder 修 + Reviewer 验证 |
| **WebArena** | webarena.dev | 网页浏览完成任务 | Agent 接口 | Navigator 找 + Operator 执行 + Verifier 检查 |
| **GAIA** | HuggingFace leaderboard | 多步推理问答 | Agent 接口 | Researcher + Analyst + Writer 协作 |

所有三个 benchmark 的排名都是**公开可查的**。提交后你的名字（Zelos + Claude Code）会出现在 leaderboard 上，和 OpenAI、Anthropic、Google 的模型排在一起。

---

## 三、SWE-bench（首选）

### 为什么选它

- 最权威的 AI 编程评测（Princeton + Stanford，NeurIPS 2025）
- 公开 leaderboard：https://www.swebench.com/
- 大家都在刷：OpenAI、Anthropic、Google、DeepSeek 全部在上面
- **Zelos 要证明的不是"模型更好"，是"编排更好"**

### 参赛方式

```python
# Zelos 作为一个 SWE-bench 求解器
def solve_swebench_instance(instance):
    """输入：一个 SWE-bench 实例。输出：patch。"""
    rt = ZelosRuntime()
    rt.add_agent("Planner", "planner:agent", [cap("planning")])
    rt.add_agent("Coder", "claude:code", [cap("code-generation")])
    rt.add_agent("Reviewer", "claude:review", [cap("code-review")])
    rt.start()

    # Zelos 内部多 Agent 协作
    goal = rt.submit_goal(f"Fix: {instance['problem_statement']}")
    rt.wait_for_goal(goal["goal_id"])
    trace = rt.get_goal_trace(goal["goal_id"])

    # 从 trace 中提取最终 patch
    patch = extract_patch_from_trace(trace)
    rt.shutdown()
    return patch

# 批量跑全部 500 题
predictions = {}
for instance in swebench_verified:
    predictions[instance["instance_id"]] = solve_swebench_instance(instance)

# 提交到 SWE-bench
# → 出现在 swebench.com leaderboard
```

### 预期 Leaderboard 效果

```
SWE-bench Verified Leaderboard (swebench.com)

排名  求解器                      解决率
1    BOAD + GPT-5.5              63.0%
2    Zelos + Claude Code          54.2%  ← 多 Agent 编排
3    SWE-agent + Claude Code      49.1%
4    Claude Code (单 Agent)       45.0%  ← 同一个模型，单打独斗
```

**同一模型（Claude Code），加 Zelos 编排后解决率 +9%。这就是 Runtime 的价值。**

### 实验组设计

| 提交名称 | 底层模型 | 内部编排 | 目的 |
|---------|---------|---------|------|
| `Zelos + Claude Code` | Claude Code | Planner → Coder → Reviewer | 主实验组 |
| `Claude Code (baseline)` | Claude Code | 单 Agent | 基线 |
| `Zelos + GPT-5` | GPT-5 | Planner → Coder → Reviewer | 跨模型验证 |

**如果 Zelos + GPT-5 > GPT-5 单 Agent，且 Zelos + Claude > Claude 单 Agent——那就证明了多 Agent 编排的价值与底层模型无关，是 Runtime 本身的能力。**

---

## 四、WebArena（次选）

### 为什么选它

- 网页浏览 Agent 的主流评测
- 公开 leaderboard：https://webarena.dev/
- 多 Agent 协作在复杂网页任务上有天然优势（一个 Agent 导航、一个 Agent 操作）

### 多 Agent 分工

```
WebArena 任务："在 Reddit 找到某帖子并回复"
  ├── Agent 1 (Navigator)：搜索帖子、理解页面结构
  ├── Agent 2 (Operator)：点击、输入、提交
  └── Agent 3 (Verifier)：确认操作结果正确
```

### 预期效果

| 求解器 | WebArena 得分 |
|--------|-------------|
| GPT-5 单 Agent | 35.8% |
| **Zelos + GPT-5** | **42.1%** |

---

## 五、GAIA（三选）

### 为什么选它

- 多步推理 Agent 的通用评测
- HuggingFace 公开 leaderboard
- 问题形式天然适合多 Agent（查资料 → 分析 → 写答案）

---

## 六、实施路径

### Phase 1：SWE-bench Pilot（1 周）

1. 装 SWE-bench + 跑通 Claude Code 单 Agent 基线（验证环境）
2. 实现 `ZelosMetaAgent` 包装器——对外一个 `execute()`，内部多 Agent
3. 跑 10 题 pilot，对比单 Agent vs Zelos 多 Agent
4. 如果多 Agent 解决率 > 单 Agent，继续 Phase 2

### Phase 2：全量 500 题（1 周）

1. 跑完 SWE-bench Verified 全部 500 题
2. 如果时间够，加跑 WebArena
3. 提交到 swebench.com leaderboard

### Phase 3：发布（3 天）

1. Leaderboard 截图 + 分析博客
2. arXiv 技术报告："Multi-Agent Orchestration Improves SWE-bench Performance"
3. Hacker News / Reddit / 知乎发布

---

## 七、对比表（最终产出）

| 求解器 | SWE-bench 解决率 | 单/多 Agent | Runtime | Leaderboard 链接 |
|--------|-----------------|------------|---------|-----------------|
| BOAD + GPT-5.5 | 63.0% | 单 | 自有 | swebench.com |
| **Zelos + Claude Code** | **?%** | **多** | **Zelos** | swebench.com |
| Claude Code | 45.0% | 单 | 无 | swebench.com |
| **Zelos + GPT-5** | **?%** | **多** | **Zelos** | swebench.com |
| GPT-5 | ?% | 单 | 无 | swebench.com |

---

> **一句话：不需要自己做 leaderboard。把 Zelos 的名字写进 swebench.com 就行。**
