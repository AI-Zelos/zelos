# Change Evidence Package — Agent Era Software Governance

> 基于一篇关于 Agent 时代 Code Review 演进的深度讨论，提炼 Zelos 下一步的核心竞争力。

---

## 一、背景：为什么 Code Review 会失效？

过去软件工程的流程：

```
Human → Write Code → Review Code → Merge → Deploy
```

Review 的目的是：有没有 Bug？有没有写错？有没有违反规范？

但当 Agent 一小时产出 35,000 行代码时，人不可能逐行审查。即使让 GPT / Gemini / Claude 互相 Review，最后还是有一个问题——**谁来相信最后那个结果？**

**问题不是效率，而是输入量已经超过人的带宽。**

---

## 二、结论：人不应该审查代码，人应该审查这三件事

### 第一层：Intent Review（意图审查）

不是 Review Code，而是 Review Goal。

Agent 收到"实现登录"，人真正应该确认的是：

- 需求是什么？
- 支持哪些登录方式？
- 是否支持 OAuth？
- 失败怎么办？
- Token 生命周期？
- 权限模型？

### 第二层：Architecture Review（架构审查）

Agent 生成之前，必须先声明：

- 准备修改哪些模块？
- 影响范围多大？
- 新增什么依赖？
- 删除什么旧逻辑？
- 预计风险等级？
- 为什么这么设计？为什么不选另一种？Tradeoff 是什么？

人只需要：Approve / Reject / Explain。

### 第三层：Evidence Review（证据审查）

Agent 不应该说"我觉得可以"，应该给证据：

- 测试：47 passed, 0 failed, coverage 89%
- 性能：Before 850 TPS → After 1120 TPS
- 安全：SAST PASS, Dependency PASS
- 兼容：API Diff backward compatible
- 金丝雀：PASS

最后输出：**Confidence 97.3%**

人看的是证据，不是代码。

---

## 三、未来 PR 形态：Change Evidence Package

今天的 PR：

```
Changed Files +233
Diff
Comments
```

未来的 Change Proposal（变更提案）：

```
Intent         — 为什么做这次变更？
Architecture Delta — 系统结构发生了什么变化？
Impact Analysis    — 影响了哪些接口、数据模型、依赖？
Evidence           — 测试、Benchmark、安全扫描、回归
Risk & Rollback    — 风险评级、回滚方案、兼容性
Confidence         — 综合置信度评分
Changed Files      — 按需展开（Debug Artifact）
```

人类的角色从 **Code Reviewer** → **System Governor（系统治理者）**。

---

## 四、Zelos 当前状态 vs. 目标状态

### v0.8.1 已有

| 能力 | 现状 |
|------|------|
| Event Sourcing | ✅ 事件链可重建任意时刻状态 |
| Goal → Plan → Execute | ✅ Planner 分解，Scheduler 调度 |
| Verification | ✅ SchemaVerifier, CodeReviewer, SecurityScanner |
| Policy | ✅ CostLimit, RateLimit, Allowlist |
| HITL Approval | ✅ Task 级别审批 |
| Retry + NonRetryableError | ✅ 可靠性完整 |
| Audit Trail | ✅ 不可变事件链 |

### 核心差距

```
当前 Zelos:
  Goal → Plan → Tasks → Artifacts → Done

需要的:
  Intent → Architecture Delta → Impact Analysis
  → Evidence Collection → Confidence Score
  → Policy Gate → Change Evidence Package → Approve → Deploy
```

**Zelos 当前是一个"执行引擎"，还不是一个"治理引擎"。**

---

## 五、v0.9.0 实现路径：四大模块

### 5.1 ExecutionReport — 结构化执行报告

```python
@dataclass
class ExecutionReport:
    goal_id: str
    intent: IntentSpec              # 人确认过的意图
    plan: ExecutionPlan              # Planner 输出
    architecture_delta: ArchDelta    # 变更影响分析
    evidence: EvidenceBag            # 收集到的所有证据
    confidence: float                # 综合置信度 (0.0-1.0)
    recommendation: Decision         # approve / reject / need_human
    rollback: RollbackPlan           # 回滚方案
```

### 5.2 EvidenceBag — 可扩展证据收集框架

Agent 不再只返回 `{"status": "completed", "artifact": ...}`，而是：

```python
{
    "status": "completed",
    "artifact": {...},
    "evidence": [
        {"type": "test_result", "tool": "pytest", "passed": 47, "failed": 0},
        {"type": "benchmark", "metric": "tps", "baseline": 850, "actual": 1120},
        {"type": "security_scan", "tool": "bandit", "result": "PASS"},
        {"type": "api_diff", "result": "backward_compatible"},
        {"type": "canary", "result": "PASS", "duration_s": 300},
    ]
}
```

Runtime 收集所有 Task 的 evidence，归并成一份 `EvidenceBag`。

### 5.3 ConfidenceScorer — 信心评分引擎

```python
class ConfidenceScorer:
    def score(self, evidence: EvidenceBag, policy: Policy) -> float:
        # 加权计算
        # 测试全过    +30%
        # 性能不下降  +15%
        # 安全扫描通过 +20%
        # API 兼容    +10%
        # 金丝雀通过  +25%
        # → 0.97
```

权重可在 `zelos.yaml` 中配置：

```yaml
evidence:
  weights:
    test_pass: 0.30
    benchmark: 0.15
    security: 0.20
    api_compat: 0.10
    canary: 0.25
```

### 5.4 PolicyGate v2 — 基于证据的人审批

```yaml
policy:
  auto_approve:
    min_confidence: 0.95
    max_risk: "low"
  require_human:
    max_confidence: 0.80
    min_risk: "medium"
  auto_reject:
    max_confidence: 0.50
```

或者更细粒度：

```yaml
policy:
  rules:
    - if: "evidence.security_scan.result != 'PASS'"
      then: "auto_reject"
      reason: "安全扫描未通过"

    - if: "confidence >= 0.95 AND risk == 'low'"
      then: "auto_approve"

    - if: "confidence < 0.80"
      then: "require_human"
      approvers: ["senior-engineer", "architect"]
```

---

## 六、新的 API 形态

### 当前 `get_goal_status()` 返回值

```python
{
    "goal_id": "g-001",
    "status": "completed",
    "plan_id": "plan-abc",
    "progress": {...},
    "retry_history": [...],
}
```

### 重构后的返回值

```python
{
    "goal_id": "g-001",
    "status": "completed",

    # ── Intent ──
    "intent": {
        "description": "实现 OAuth2 登录",
        "accepted": "支持 Google/GitHub OAuth2，Token 24h 过期，失败回退密码",
        "confirmed_by": "alice@example.com",
    },

    # ── Architecture Delta ──
    "architecture_delta": {
        "modified_modules": ["auth-service", "user-model"],
        "new_dependencies": ["oauth2-client-lib==3.2.0"],
        "api_changes": [
            {"endpoint": "POST /auth/oauth", "type": "new", "compat": "additive"},
        ],
        "deleted_components": [],
        "risk_level": "medium",
        "explanation": "OAuth2 是标准增量，不改变已有登录逻辑",
    },

    # ── Evidence Bag ──
    "evidence": {
        "tests": {"framework": "pytest", "passed": 47, "failed": 0, "skipped": 0, "coverage_pct": 89},
        "benchmark": {"metric": "auth_tps", "baseline": 850, "actual": 1120, "delta_pct": +31.8},
        "security": {"sast": "PASS", "dependency_scan": "PASS", "secret_scan": "PASS"},
        "api_compat": {"diff": "backward_compatible", "breaking_changes": 0},
        "canary": {"result": "PASS", "duration_s": 300, "error_rate": 0.001},
    },

    # ── Decision ──
    "confidence": 0.97,
    "recommendation": "approve",
    "reason": "所有证据通过，风险中等但可接受，Confidence 97%",
    "auto_approved": False,
    "approved_by": "alice@example.com",

    # ── Rollback ──
    "rollback_plan": {
        "strategy": "event_sourcing_replay",
        "restore_to_event_position": 42,
        "estimated_downtime_s": 5,
        "risk": "low",
    },

    # ── Code (按需展开) ──
    "changed_files": 18,
    "lines_added": 1200,
    "lines_deleted": 80,
}
```

---

## 七、技术要点

### 7.1 与 Event Sourcing 的协同

`ExecutionReport` 本身也是一个 Event，可被 EventSourcingEngine 回放：

```
ExecutionReportCreated → EvidenceCollected → ConfidenceScored → DecisionMade
```

这保证了**审批决策的过程本身也是可审计的**。

### 7.2 Rollback 能力

Zelos 已经支持 Event Sourcing — 从快照 + 增量事件恢复 Goal 状态。这意味着：

- **Rollback = 将 Goal 状态恢复到 event_position=N**
- 不需要传统意义上的 "revert PR"
- Runtime 拥有原子级的状态回退能力

### 7.3 Agent 协议升级

Agent SDK 需要新增 Evidence 输出：

```python
from zelos_sdk.schema import Artifact, Evidence

class MyAgent(BaseAgent):
    def execute(self, task: Task) -> ExecutionResult:
        result = self._do_work(task)

        return ExecutionResult(
            status="completed",
            artifact=Artifact(content=result),
            evidence=[
                Evidence(type="test_result", data={"passed": 47, "failed": 0}),
                Evidence(type="benchmark", data={"metric": "tps", "before": 850, "after": 1120}),
                Evidence(type="security_scan", data={"tool": "bandit", "result": "PASS"}),
            ],
        )
```

---

## 八、里程碑建议

```
v0.9.0 - Evidence Framework
├── ExecutionReport 数据结构
├── EvidenceBag 收集与归并
├── ConfidenceScorer 插件接口
└── Runtime.get_execution_report() API

v0.9.1 - Policy Gate v2
├── 基于 evidence + confidence 的自动审批规则
├── PolicyGate 插件
└── Decision 事件链 (EvidenceCollected → ConfidenceScored → DecisionMade)

v0.10.0 - Full Change Evidence Package
├── Architecture Delta 自动生成（从 Plan + Event History 提取）
├── IntentSpec 结构化定义
├── Rollback 计划自动生成
└── 新的 get_goal_status() API
```

---

## 九、总结

| 维度 | 当前 Zelos (v0.8.1) | 目标 Zelos (v0.10.0) |
|------|---------------------|----------------------|
| 职责 | 执行引擎 | **治理平台** |
| 输出 | Task Artifacts | **Change Evidence Package** |
| 人的角色 | 看 Task 结果 | 看 Intent + Evidence + Confidence |
| 审批依据 | 人工判断 | **证据驱动的自动决策** |
| 回滚 | 手动 | **Event Sourcing 原子回退** |

一句话：

> **当前 Zelos 回答："Agent 能不能执行这个 Goal？"**
> **下一步 Zelos 回答："Agent 执行的这次变更，值不值得被接受？"**
