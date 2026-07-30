# Zelos Governance Benchmark Plan

> 用 SWE-bench 证明：AI 写完代码以后，Zelos 能在零人工干预下做出和人类 Review 同等或更优的 accept/reject 决策。

---

## 一、为什么选 SWE-bench

SWE-bench（Princeton + Stanford）是 AI 编程能力的事实标准评测。2300 个真实 GitHub issue，Docker 隔离验证，无人为主观偏差。

当前所有参赛者都只比 **"谁解的题多"**。Zelos 第一个问 **"解出来以后你敢不敢上线"**——这才是差异化。

---

## 二、实验设计

### 2.1 数据集

**SWE-bench Verified（500 实例）** 或 **SWE-bench Lite（300 实例）**。

建议先用 10 个实例做 pilot，验证流程后再跑全量。

### 2.2 三组对照

同一批任务，同一个 AI 模型（Claude Code 或 GPT-5），只变量是治理方式：

| 组别 | AI 行为 | 人行为 | Zelos 行为 |
|------|--------|--------|-----------|
| **PR 组**（基线） | 生成 patch | 读 diff、审代码、决定是否合并 | 无 |
| **AI-PR 组** | 生成 patch + 自审 | 看 AI 建议 + 最终决定 | 无 |
| **Zelos 组** | 生成 patch | 不看代码 | 自动跑验证 → 算 Confidence → PolicyGate 自动 approve/reject |

### 2.3 统一环境

| 项目 | 规格 |
|------|------|
| AI 模型 | Claude Code（固定版本） |
| 硬件 | 同一台机器 / 同规格云实例 |
| SWE-bench 版本 | Verified v1.0 |
| 超时 | 每任务 1800 秒 |
| 评测 | Docker 容器内跑项目自带测试 |

---

## 三、评测指标

### 核心指标

| 指标 | 定义 | 怎么算 |
|------|------|--------|
| **解决率 (Resolved %)** | patch 通过 SWE-bench 测试的占比 | SWE-bench 自带 |
| **人工耗时** | 人类完成 Review 的平均时间 | 计时（PR 组/AI-PR 组）/ Zelos 组 = 0 |
| **误批率 (False Accept)** | Zelos approved 但实际 FAIL 的占比 | approved ∩ failed / approved |
| **误拒率 (False Reject)** | Zelos rejected 但实际 PASS 的占比 | rejected ∩ passed / rejected |
| **置信度准确率** | Confidence ≥ 0.95 的实例中实际 PASS 的占比 | TP / (TP + FP) at threshold=0.95 |

### 辅助指标

| 指标 | 意义 |
|------|------|
| 返工次数 | 每任务平均修改轮数 |
| Evidence 覆盖率 | 每个 Task 平均产生几条 Evidence |
| 决策分布 | auto_approve / auto_reject / require_human 的比例 |

---

## 四、Zelos 组的具体流程

```
1. SWE-bench 给一个 issue
     ↓
2. Claude Code 生成 patch
     ↓
3. Zelos Runtime：
   ├── 自动跑 lint（代码规范）
   ├── 自动跑项目测试（SWE-bench Docker）
   ├── 自动跑安全扫描（bandit）
   ├── 收集 Evidence
   ├── 算 Confidence（WeightedConfidenceScorer）
   └── PolicyGate 决策：
       ├── Confidence ≥ 0.95 → auto_approve
       ├── Confidence < 0.40 → auto_reject
       └── 其他 → require_human（本实验中记入 reject）
     ↓
4. 对比 SWE-bench 真实结果：
   ├── Zelos approved + SWE-bench PASS → ✅ 正确批准
   ├── Zelos approved + SWE-bench FAIL → ❌ 误批
   ├── Zelos rejected + SWE-bench PASS → ❌ 误拒
   └── Zelos rejected + SWE-bench FAIL → ✅ 正确拒绝
```

---

## 五、成功标准

| 指标 | 目标 | 说明 |
|------|------|------|
| 解决率 | ≥ PR 组的 90% | 不比人审差太多 |
| 人工耗时 | **0** | Zelos 组零人工 |
| 误批率 | < 5% | 批准的不合格 patch < 5% |
| 误拒率 | < 20% | 拒绝的合格 patch < 20%（宁可误拒，不可误批） |
| 置信度准确率 | > 80% | Confidence ≥ 0.95 时有 80%+ 是真的 PASS |

---

## 六、实施步骤

### Phase 1：Pilot（1-2 天）

```bash
# 1. 装 SWE-bench
pip install swebench datasets
git clone https://github.com/princeton-nlp/SWE-bench.git

# 2. 跑 10 个实例的 baseline（PR 组）
# 手动 Review，记录耗时和结果

# 3. 跑 10 个实例的 Zelos 组
# 脚本自动化，记录所有指标
```

输出：Pilot 报告 + 流程验证 + 指标初值。

### Phase 2：全量（3-5 天）

```bash
# 跑全部 300 个实例
# 三组各自完成
# 统计显著性检验（Mann-Whitney U）
```

### Phase 3：论文/Blog（1-2 天）

输出：
- 一篇 arXiv preprint（Benchmark 论文）
- 一篇博客（带对比表的推广文章）
- README 更新（Benchmark 数据放首页）

---

## 七、脚本框架

```python
# run_zelos_swebench.py — 骨架
import subprocess, json, time
from zelos.runtime import ZelosRuntime

def evaluate_single_instance(instance):
    """跑一个 SWE-bench 实例的 Zelos 治理流程。"""
    issue = instance["problem_statement"]
    repo = instance["repo"]

    # 1. Claude Code 生成 patch
    patch = generate_patch_with_claude_code(issue, repo)

    # 2. Zelos 治理
    rt = ZelosRuntime()
    rt.add_agent("ClaudeCode", "claude:cli", [capability("code-generation")])
    rt.start()
    goal = rt.submit_goal(
        f"Fix: {issue[:100]}",
        intent=IntentSpec(description=issue, scope="single_module"),
    )

    # 3. 自动验证
    rt.add_evidence(goal["goal_id"], run_tests(patch, repo))
    rt.add_evidence(goal["goal_id"], run_lint(patch))
    rt.add_evidence(goal["goal_id"], run_security_scan(patch))

    # 4. 等待完成 + 决策
    rt.wait_for_goal(goal["goal_id"])
    report = rt.get_execution_report(goal["goal_id"])
    decision = rt.auto_decide(goal["goal_id"])

    # 5. 返回结果
    rt.shutdown()
    return {
        "instance_id": instance["instance_id"],
        "zelos_decision": decision["action"],
        "confidence": report.confidence.score,
        "evidence_all_pass": report.evidence_bag.all_pass,
        "swebench_result": evaluate_on_swebench(patch, instance),  # Docker 内跑测试
    }
```

---

## 八、成本估算

| 项目 | 估算 |
|------|------|
| 300 × Claude Code API 调用 | ~$150-300（取决于 prompt 长度） |
| Docker 镜像存储 | ~120 GB |
| 机时（300 × 30min） | ~150 CPU-hours |
| 人工 Review 时间（PR 组） | ~50 小时（300 × 10min） |

---

> 下一步：决定是否开始 Pilot。10 个实例，1 天能出初步数据。
