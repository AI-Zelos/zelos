# SWE-bench PoC 实验设计方案

> 版本：v1.0
> 编写日期：2026-08-02
> 依赖：Zelos v1.3.0（MPC 自适应调度闭环已完成）

---

## 目录

1. [实验目的](#1-实验目的)
2. [核心假设](#2-核心假设)
3. [实验分组](#3-实验分组)
4. [实例选择](#4-实例选择)
5. [测量指标](#5-测量指标)
6. [执行流程](#6-执行流程)
7. [数据收集与分析](#7-数据收集与分析)
8. [有效性威胁](#8-有效性威胁)
9. [实施步骤](#9-实施步骤)

---

## 1. 实验目的

回答一个问题：

> **Zelos Runtime 的编排和诊断能力，是否能比单体 Agent 自己从头做到尾更好？**

这不是 SWE-bench 排行榜评测。这是**控制变量实验**：Agent 质量是常量，Runtime 质量是变量。

---

## 2. 核心假设

**H₁（主假设）**: 将 SWE-bench 任务拆解为定位 → 生成 → 审查三个子任务，由 Zelos Runtime 编排不同 Agent 执行，端到端通过率高于单个 Agent 独立执行。

**H₂（辅助假设）**: Zelos Diagnosis Engine 的结构化诊断（file:line、expected vs actual）比 Agent 自己解析 500 行 pytest 输出更高效：Runtime 的诊断开销 Token 远小于 Agent 为理解日志而消耗的额外上下文 Token。

### 假设可证伪条件

| 假设 | 被证伪的情况 |
|------|------------|
| H₁ | 编排组通过率 ≤ 基线组通过率 |
| H₂ | +诊断组的 Runtime 开销 + Agent Token ≥ 基线组 Agent 总 Token |

---

## 3. 实验分组

选 5 个 SWE-bench verified 实例，每个跑 3 组：

### 3.1 基线组：单体 Agent 原生执行

```
1 个 Agent（Claude Code 或 GPT-Engineer）
  → 接收 issue 描述 + repo
  → 自主定位 → 生成 patch → 跑测试
  → 如果失败，Agent 自己读日志、自己决定怎么修复
  → 输出最终 patch
```

**测量**：最终 pass/fail、总 Token 消耗、总耗时、重试次数

**关键问题**：Agent 自己读日志做决策——这是"Agent 质量"的上限。

### 3.2 +Runtime 诊断组：单 Agent + Zelos 诊断回路

```
1 个 Agent（同基线组 Agent）
  → 接收 issue + repo
  → 生成 patch
  → Runtime 在 Docker 中跑测试
  → 如果失败：
      Diagnosis Engine 解析 pytest 输出
        → 提取 file:line、expected vs actual
      Failure Classifier 决策：repair / retry / abandon
      → 如果 repair：将结构化诊断传给 Agent（不是全量日志）
      → Agent 基于诊断定向修复
  → 输出最终 patch
```

**与基线组的唯一变量**：Agent 收到的失败反馈是"结构化诊断"还是"全量 pytest 输出"。

**测量**：最终 pass/fail、Agent Token（含诊断反馈）、Runtime 诊断开销 Token、重试次数

### 3.3 +编排组：三 Agent + MPC 编排

```
Task A: Search Agent（定位代码）
  → 产出：受影响文件和行号

Task B: Fix Agent（生成 patch）
  → 接收 Task A 的定位结果 + issue
  → 产出：diff patch

Task C: Test + Review（Runtime 执行）
  → Runtime 在 Docker 中跑测试
  → 如果失败：
      Diagnosis Engine → Failure Classifier
      → MPC Replan：创建新的 Fix Task（含诊断信息）
      → 循环直到通过或放弃（最多 5 次 replan）
  → 如果通过：
      Reviewer Agent 审查 patch
      → 通过 → 输出最终 patch
      → 不通过 → 创建新的 Fix Task
```

**与基线组的差异**：
- 定位和修复由不同 Agent 完成（各用最强）
- Runtime 做 MPC 决策，而非 Agent 自己决策
- 审查步骤独立

**测量**：最终 pass/fail、各 Agent Token 总和、Runtime 开销 Token、replan 次数、决策触达率、决策后验准确率

---

## 4. 实例选择

### 4.1 选择标准

| 维度 | 标准 | 理由 |
|------|------|------|
| 难度梯度 | 单文件修改 ×2、多文件修改 ×2、跨模块 ×1 | 覆盖不同复杂度 |
| 确定性 | 有明确 fail→pass 测试，非 flaky | 排除随机因素 |
| 可访问性 | repo 可 clone，Docker 镜像可用 | 本地可复现 |
| 多样性 | 至少来自 3 个不同项目 | 避免项目特定偏差 |
| 已知基准 | SWE-bench 排行榜上有至少 2 个 Agent 的通过记录 | 校准预期 |

### 4.2 候选实例（从 SWE-bench verified 子集筛选）

筛选步骤：
```bash
# 1. 只取 SWE-bench verified 子集
# 2. 排除需要复杂环境配置的（如需要数据库迁移的 Django migration 实例）
# 3. 按 repo 分组，每 repo 最多选 2 个
# 4. 手动检查每个实例的 FAIL_TO_PASS / PASS_TO_PASS 测试是否明确
```

初选 8 个，终选 5 个（在实验执行前最终确认）：

| 实例 ID | 仓库 | 估算难度 | 文件数 | 选择理由 |
|---------|------|---------|--------|---------|
| 待定-1 | astropy | 简单 | 1 | 单文件逻辑修复 |
| 待定-2 | django | 简单 | 1-2 | 单文件参数修复 |
| 待定-3 | django | 中等 | 3-5 | 多文件 API 变更 |
| 待定-4 | sympy | 中等 | 3-5 | 多文件算法修复 |
| 待定-5 | sphinx | 困难 | 5+ | 跨模块重构 |

> **TODO**: 实际选择需要读取 SWE-bench 数据集，按 FAIL_TO_PASS 测试数量和文件变更范围自动排序后人工确认。

### 4.3 实例排除标准

- flaky 测试（同一 patch 多次运行结果不一致）
- 需要修改超过 10 个文件（定位和修复过于分散，Agent 随机性太大）
- 需要修改 Docker 配置或环境变量（不是纯代码修复）

---

## 5. 测量指标

### 5.1 主要指标

| # | 指标 | 定义 | 收集方式 |
|---|------|------|---------|
| 1 | **通过率** | patch 通过所有 FAIL_TO_PASS 测试且不破坏 PASS_TO_PASS 测试 | SWE-bench eval harness 判定 |
| 2 | **总 Token 消耗** | 全部 LLM API 调用的 prompt + completion tokens 之和 | 各 Agent API wrapper 上报 |
| 3 | **重试/Replan 次数** | 基线组=Agent 自我修复次数；诊断组=Runtime 修复循环次数；编排组=MPC replan 次数 | 每组内部计数器 |

### 5.2 辅助指标（仅编排组）

| # | 指标 | 定义 | 收集方式 |
|---|------|------|---------|
| 4 | **决策触达率** | 触发 MPC replan 的 Task 数 / 总失败 Task 数 | Event Bus `execution_plan.modified` 计数 |
| 5 | **诊断准确率** | Diagnosis Engine 给出的 file:line 与实际需要修改的位置一致的比例 | 人工对照 SWE-bench 标准 patch |

### 5.3 Token 收集说明（如实记录局限性）

**Token 收集存在精度损失**，因为 live-SWE-agent / Claude Code 的内部调用链不完全透明：

- **基线组**: Agent 的 LLM 调用由 Agent 自身管理，只能在 Agent wrapper 层估算
- **+诊断组**: 额外记录 Diagnosis Engine 输出字符串的等效 Token 数（字符数 / 4），作为 `runtime_diag_overhead`
- **+编排组**: Planner.replan_path() 的 LLM 调用 Token 可从 provider 返回值获取；各 Agent Token 与基线组同方式估算

所有 Token 数据标注为"估算值"，非精确 API 计量。

---

## 6. 执行流程

### 6.1 整体 Pipeline

```
Step 0: 确认 5 个实例 + Docker 环境就绪
  │
Step 1: 跑基线组（5 实例 × 1 次 = 5 次执行）
  │
Step 2: 跑 +诊断组（5 实例 × 1 次 = 5 次执行）
  │
Step 3: 跑 +编排组（5 实例 × 1 次 = 5 次执行）
  │
Step 4: 收集 15 个 JSON 结果 → report.py 生成对比报告
```

### 6.2 基线组执行

```python
# scripts/swebench_poc/baseline.py (伪代码)

def run_baseline(instance_id: str) -> dict:
    """
    1. 准备 SWE-bench Docker 环境
    2. 启动 Agent（Claude Code），传入 issue 描述
    3. Agent 自主执行：定位 → 生成 patch → 跑测试 → 修复
    4. Agent 完成后，SWE-bench eval 判定 pass/fail
    5. 收集指标 → 返回 JSON
    """
    env = swebench_env(instance_id)
    agent = create_agent("claude-code")  # 或其他选定的 Agent
    
    # Agent 全权控制，Runtime 不介入
    result = agent.solve(
        issue=env.issue_text,
        repo_path=env.repo_path,
    )
    
    # SWE-bench eval
    eval_result = swebench_eval(instance_id, result.patch)
    
    return {
        "instance_id": instance_id,
        "group": "baseline",
        "pass": eval_result.passed,
        "patch": result.patch,
        "total_tokens": result.token_usage,  # Agent 上报的估算值
        "retry_count": result.self_repair_count,
        "total_time_seconds": result.elapsed,
    }
```

### 6.3 +Runtime 诊断组执行

```python
# scripts/swebench_poc/runtime_diag.py (伪代码)

def run_runtime_diag(instance_id: str) -> dict:
    """
    1. 准备环境
    2. 启动 Agent
    3. Agent 生成 patch
    4. Runtime 在 Docker 中跑测试
    5. 如果失败：
       - Diagnosis Engine 解析输出
       - Failure Classifier 决策
       - 如果 repair：将诊断传给 Agent，Agent 修复
       - 循环最多 3 次
    6. SWE-bench eval
    """
    env = swebench_env(instance_id)
    agent = create_agent("claude-code")
    diagnosis_engine = DiagnosisEngine()
    classifier = FailureClassifier()
    
    max_rounds = 3
    for round_num in range(max_rounds):
        # Agent 生成 patch
        if round_num == 0:
            patch = agent.generate_patch(env.issue_text, env.repo_path)
        else:
            # 传入结构化诊断，不是全量日志
            patch = agent.repair_patch(
                issue=env.issue_text,
                repo_path=env.repo_path,
                diagnosis=diagnosis_result,  # ← 结构化诊断
                previous_patch=patch,
            )
        
        # Runtime 跑测试
        test_output = env.run_tests(patch)
        
        if test_output.all_passed:
            break
        
        # Diagnosis Engine 解析
        diagnosis_result = diagnosis_engine.diagnose(test_output.raw)
        
        # Failure Classifier 决策
        classification = classifier.classify(diagnosis_result)
        if classification.action == "abandon":
            break
        # repair → 下一轮循环
    
    eval_result = swebench_eval(instance_id, patch)
    
    return {
        "instance_id": instance_id,
        "group": "runtime_diag",
        "pass": eval_result.passed,
        "patch": patch,
        "total_tokens": agent.total_tokens,
        "runtime_diag_overhead_tokens": estimate_tokens(
            diagnosis_result.to_dict()
        ),
        "retry_count": round_num,
        "diagnosis_rounds": round_num,
        "total_time_seconds": elapsed,
    }
```

### 6.4 +编排组执行

```python
# scripts/swebench_poc/orchestrated.py (伪代码)

def run_orchestrated(instance_id: str) -> dict:
    """
    1. 初始化 Zelos Runtime (Stage A + diagnosis_engine)
    2. 注册 3 个 Agent（Search / Fix / Review）
    3. Planner 生成 3 步 Plan
    4. Runtime 执行 + MPC replan
    5. SWE-bench eval
    """
    runtime = ZelosRuntime({
        "features": {**FeatureFlags.stage_a().__dict__,
                     "diagnosis_engine": True,
                     "failure_classifier": True},
    })
    runtime._planner = LLMPlanner({
        "provider": "openai_compatible",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
    })
    
    # 注册 Agent
    search_agent = create_agent("claude-code", capability="code-search")
    fix_agent = create_agent("claude-code", capability="code-generation")
    review_agent = create_agent("claude-code", capability="code-review")
    
    runtime.add_agent("search", search_agent, capabilities=["code-search"])
    runtime.add_agent("fix", fix_agent, capabilities=["code-generation"])
    runtime.add_agent("review", review_agent, capabilities=["code-review"])
    
    # 提交 Goal
    env = swebench_env(instance_id)
    goal_result = runtime.submit_goal(
        f"Fix issue in {env.repo_name}: {env.issue_text}",
        plan_template="search → fix → test → review",
    )
    
    # 执行
    runtime.start()
    result = runtime.wait_for_goal(goal_result["goal_id"], timeout_seconds=3600)
    runtime.shutdown()
    
    # 收集指标
    trace = runtime.get_goal_trace(goal_result["goal_id"])
    replan_events = count_replan_events(trace)
    decision_reach_rate = replan_events / len(trace.tasks) if trace.tasks else 0
    
    return {
        "instance_id": instance_id,
        "group": "orchestrated",
        "pass": result.get("status") == "completed",
        "patch": extract_patch(result),
        "total_tokens": sum_agent_tokens(trace),
        "token_breakdown": token_by_agent(trace),
        "replan_count": replan_events,
        "decision_reach_rate": decision_reach_rate,
        "total_time_seconds": elapsed,
        "trace_summary": trace.to_summary(),
    }
```

---

## 7. 数据收集与分析

### 7.1 结果数据格式

每个实例的每组实验产出一个 JSON，15 个文件放入 `logs/poc_results/`：

```
logs/poc_results/
  baseline/
    astropy__astropy-XXXXX.json
    django__django-XXXXX.json
    ...
  runtime_diag/
    astropy__astropy-XXXXX.json
    ...
  orchestrated/
    astropy__astropy-XXXXX.json
    ...
```

### 7.2 分析脚本

```python
# scripts/swebench_poc/report.py (伪代码)

def generate_report(results_dir: str) -> str:
    """
    汇总 15 个 JSON → Markdown 对比报告
    
    输出：
    - 汇总表：每组通过率、平均 Token、平均重试次数
    - 逐实例对比表
    - 编排组专项：决策触达率、诊断准确率
    - 定性观察：每个实例的 Runtime 决策是否合理
    """
```

### 7.3 结果判断（定性为主，定量为辅）

n=5 样本量太小，不做统计显著性检验。判断标准：

| 结果模式 | 结论 |
|---------|------|
| 编排组通过数 > 基线组通过数（哪怕只多 1 题） | **H₁ 被初步支持**——编排有正向效果，但需要更大样本验证 |
| 编排组通过数 ≤ 基线组通过数 | **H₁ 未被支持**——编排没有带来可观测的提升 |
| +诊断组 Agent Token < 基线组 Agent Token | **H₂ 被初步支持**——结构化诊断比全量日志更省 Token |
| +诊断组通过数 > 基线组通过数 | 诊断反馈质量高于 Agent 自己读日志 |
| 编排组决策触达率 = 0 | 场景太简单，无需 MPC 介入；应换更难的实例 |

### 7.4 定性分析（必做，比数字更重要）

每个实例逐组检查：

1. **为什么失败？** Agent 找不到正确文件？Agent 生成的 patch 逻辑错误？环境问题？
2. **Runtime 介入了吗？** 如果失败了但 Runtime 没触发 replan——说明规则引擎没检测到问题
3. **Runtime 的决策对吗？** 如果触发了 replan，新的修复方向对吗？还是把 Agent 引向了错误方向？
4. **哪一步最耗时？** 定位？生成？测试？修复循环？

---

## 8. 有效性威胁

| 威胁 | 严重度 | 缓解措施 |
|------|--------|---------|
| **样本量小 (n=5)** | 高 | 诚实定性：这是 PoC 而非正式实验。结论是"初步证据"级别。如果效果好，扩大样本到 20-50 题做正式评测 |
| **Token 收集精度** | 中 | 所有 Token 数据标注为"估算值"。Agent 内部调用不透明时，用 API key 级别的 usage 汇总。文档如实说明误差范围 |
| **Agent 行为非确定性** | 中 | 同一组同一实例不重复跑（浪费 Token）。如果某组结果可疑（如基线全部 0/5），换一个 Agent 重跑 |
| **编排组使用多 Agent = 多 Token** | 中 | 不对编排组的"总 Token 更少"做假设。H₂ 只在诊断组测试。编排组的 Token 数据仅用于分析"Runtime 开销占比" |
| **实验者偏差（选简单题）** | 低 | 实例选择标准预先定义（难度梯度 + 多项目），执行前锁定 5 个实例 |
| **Docker 环境波动** | 低 | 所有组使用相同 Docker 镜像；执行前验证镜像可用 |

---

## 9. 实施步骤

### Step 1: 选定 5 个实例（1 小时）

```bash
# 从 SWE-bench verified 子集中筛选
python scripts/swebench_poc/select_instances.py \
  --dataset princeton-nlp/SWE-bench_Verified \
  --min-fail-tests 1 \
  --max-fail-tests 10 \
  --max-files-changed 10 \
  --output logs/poc/selected_instances.json
```

### Step 2: 实现实验脚本（2-3 天）

按优先级：
1. `baseline.py` — 最优先，单 Agent 基线
2. `runtime_diag.py` — 依赖 baseline 的 Agent wrapper
3. `orchestrated.py` — 依赖 v1.3 Runtime
4. `metrics.py` + `report.py` — 数据收集和报告

### Step 3: 跑实验（1-2 天）

```bash
python scripts/swebench_poc/runner.py \
  --instances logs/poc/selected_instances.json \
  --groups baseline runtime_diag orchestrated \
  --output-dir logs/poc_results/
```

预估时间：15 次执行 × 5-15 分钟/次 = 1.5-4 小时（取决于实例复杂度）

### Step 4: 分析报告（半天）

```bash
python scripts/swebench_poc/report.py \
  --results-dir logs/poc_results/ \
  --output docs/swebench-poc-report.md
```

---

## 附录 A：需要的外部依赖

---

## 附录 B：实施注意事项（诚实检查结果）

以下 3 个 gap 是实验设计文档定稿后，对照 Zelos 实际代码和 SWE-bench 实际环境发现的实施层面问题。

### B.1 Agent 集成：伪代码 vs 现实

设计文档中的 `agent.generate_patch()` 是抽象接口，现实中不存在：

| 伪代码 | 现实 |
|--------|------|
| `agent.generate_patch(issue, repo_path)` | Claude Code 是 CLI 工具，无 Python API |
| `agent.repair_patch(issue, repo_path, diagnosis, patch)` | 同上 |
| `runtime.add_agent("search", agent_obj, capabilities=[...])` | `add_agent()` 第二个参数是 `entrypoint: str`（模块路径），非对象 |

**解决方案**：三组统一用 Claude Code CLI + prompt 模板。核心流程：

```bash
# 不是 Python API，是 shell + prompt
claude --print "You are a bug-fixing agent. Issue: {issue_text}. 
  The repo is at {repo_path}. Generate a unified diff patch to fix the issue."
```

- **基线组**: prompt → patch → test → 如果失败，把全量日志追加到新 prompt → 循环
- **+诊断组**: prompt → patch → test → 如果失败，Diagnosis Engine 解析日志 → 只把结构化诊断追加到新 prompt → 循环
- **+编排组**: 3 个独立 Claude Code 调用（定位/生成/审查），Runtime 管理流程

Agent wrapper 需要实现的最小接口：

```python
class ClaudeCodeAgentWrapper:
    def generate_patch(self, issue: str, repo_path: str) -> str: ...
    def repair_patch(self, issue: str, repo_path: str,
                    diagnosis: DiagnosisResult, prev_patch: str) -> str: ...
    @property
    def total_tokens(self) -> int: ...  # 从 Claude Code 输出解析或估算
```

### B.2 +编排组：Runtime API 集成工作量

编排组的伪代码假设了一个简化的 API，实际需要：

1. **Agent Wrapper**（见 B.1）——把 Claude Code CLI 包装为可被 Runtime 调用的执行单元
2. **Capability 注册**——`add_agent()` 需要 `entrypoint` 路径，指向 wrapper 模块
3. **Planner 配置**——`LLMPlanner` 需要能生成 `search → fix → review` 三步 Plan 的 system prompt
4. **`_on_dispatch` 适配**——Runtime 当前的 dispatch 回调调用 `agent.execute(task)`，需要确保 wrapper 实现了这个接口
5. **Test Task 在 Plan 中的位置**——当前 MPC 流程中，测试执行在 `_mpc_replan_check` 之后，但 SWE-bench 的测试需要在 Docker 中运行。需要将"跑测试"作为一个独立的 Task 或作为 Fix Task 完成后的 Runtime 钩子

**建议实施顺序**：
1. 先写 `ClaudeCodeAgentWrapper`（3 组共用）
2. 跑通基线组 + 诊断组验证 wrapper 正确
3. 最后实现编排组（需要完整的 Zelos Runtime 集成）

### B.3 基线组 go/no-go 检查

**风险**：如果选的 5 个实例对基线 Agent 来说全都不通过，三组对比失去意义。

**中止条件**：
- 基线组通过率 ≤ 1/5 → 换更简单的实例或换更强的 Agent
- 基线组通过率 ≥ 3/5 → 天花板太高，编排组很难超越 → 考虑换更难的实例
- 基线组通过率 = 2/5 → **理想区间**，有足够的改进空间

**检查时机**：Step 1（基线组）跑完后立即检查，不满足条件则中止后续实验。

---

## 附录 C：与原设计（v1.3.0-requirements.md）的差异

| 依赖 | 用途 | 状态 |
|------|------|------|
| SWE-bench 数据集 (verified split) | 实例来源 | 需下载 |
| live-SWE-agent / Claude Code | 基线 + 诊断组 Agent | 需确认可用 |
| DeepSeek API key | Planner LLM（编排组） | 需配置 |
| Docker | SWE-bench 测试环境 | 已安装 |
| Zelos v1.3.0 | 诊断组 + 编排组 Runtime | ✅ 已完成 |

## 附录 B：与原设计（v1.3.0-requirements.md）的差异

| 原设计 | 修正 | 原因 |
|--------|------|------|
| Token 消耗精确收集 | 标注为"估算值" | Agent 内部调用不透明 |
| 编排组更省 Token | 移除该假设，H₂ 仅在诊断组测试 | 多 Agent 编排天然多 Token |
| 每组跑 2 次取最优 | 每组跑 1 次 | PoC 阶段控制成本 |
| "决策后验准确率" | 改为"诊断准确率" | 更易测量（对照标准 patch 验证 file:line） |
| 5 个实例未指定 | 提供筛选脚本 + 选择标准 | 可操作化 |
