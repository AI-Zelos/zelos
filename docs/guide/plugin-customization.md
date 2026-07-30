# Zelos Plugin Customization Guide

> 如何自定义 Zelos 的插件、什么时候需要、注意事项。所有示例均基于 v1.0.0 实测接口。

---

## 概述

Zelos 的 Kernel 是封闭的，所有行为通过可替换的插件实现。目前有 7 类可自定义的插件：

| 插件 | 接口 | 默认实现 | 什么时候需要自定义 |
|------|------|---------|-------------------|
| **Verifier** | `Verifier` ABC | `SchemaVerifier` | 需要自定义验证逻辑（如检查业务规范、合规要求） |
| **ConfidenceScorer** | `ConfidenceScorer` ABC | `WeightedConfidenceScorer` | 需要自定义置信度评分算法（如安全优先、合规优先） |
| **PolicyGate** | `PolicyGate` ABC | `EvidenceBasedPolicyGate` | 需要自定义决策规则（如多级审批流、行业合规检查） |
| **ScoringStrategy** | `ScoringStrategy` ABC | `DefaultScoringStrategy` | 需要自定义 Agent 选择排名逻辑（如成本优先、延迟优先） |
| **Planner** | LLM 可替换 | `LLMPlanner` | 需要用不同 LLM 或纯规则引擎做 Goal 分解 |
| **Evidence** | 开放 dataclass | — | 需要自定义证据类型（如合规审计、A/B 测试结果） |
| **ConstraintEngine** | `ConstraintEngine` 可扩展 | 默认实现 | 需要自定义 K/S/R/E 各维度的约束规则 |

---

## 1. Verifier — 自定义验证器

### 接口

```python
from zelos.verifier import Verifier, Verdict, VerificationCriteria

class Verifier(ABC):
    def __init__(self, verifier_id: str = "base-verifier", config: dict | None = None):
        self.verifier_id = verifier_id
        self.config = config or {}

    @abstractmethod
    def verify(self, artifact_content: Any, criteria: VerificationCriteria) -> Verdict:
        """验证 artifact 是否满足 criteria。"""
```

### Verdict 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `verdict` | str | `"passed"` / `"failed"` / `"needs_review"` |
| `score` | float | 0.0–1.0 置信度 |
| `issues` | list[dict] | 发现的问题列表 |
| `summary` | str | 人类可读摘要 |

### VerificationCriteria 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `expected_output_schema` | dict | 期望的 JSON Schema |
| `severity` | str | `"error"` / `"warning"` — error 级别失败阻断链 |
| `constraints` | list[str] | 额外约束 |

### 示例：自定义代码复杂度验证器

```python
from zelos.verifier import Verifier, Verdict, VerificationCriteria

class ComplexityVerifier(Verifier):
    """检查代码复杂度是否超标。"""

    def __init__(self, max_complexity: int = 10):
        super().__init__(verifier_id="complexity-checker")
        self.max_complexity = max_complexity

    def verify(self, artifact_content, criteria):
        # 从 artifact 中提取函数列表
        functions = artifact_content.get("functions", [])
        issues = []

        for fn in functions:
            if fn.get("cyclomatic_complexity", 0) > self.max_complexity:
                issues.append({
                    "function": fn["name"],
                    "complexity": fn["cyclomatic_complexity"],
                    "threshold": self.max_complexity,
                })

        if issues:
            return Verdict(
                verdict="failed",
                score=0.3,
                issues=issues,
                summary=f"{len(issues)} functions exceed complexity threshold of {self.max_complexity}"
            )
        return Verdict(
            verdict="passed",
            score=1.0,
            summary=f"All functions within complexity threshold"
        )

# 注册到 VerifierChain
from zelos.verifier_chain import VerifierChain
chain = VerifierChain()
chain.register("complexity", ComplexityVerifier(max_complexity=15))
```

### 注意事项

- `verdict` 值为 `"passed"` / `"failed"` / `"needs_review"`（小写），不是 `"PASS"` / `"FAIL"`
- `failed` 会阻断 VerifierChain，后续 Verifier 不再执行
- 构造 `Verdict` 时至少给 `verdict` 和 `summary`，其他字段可选

---

## 2. ConfidenceScorer — 自定义置信度评分

### 接口

```python
from zelos.confidence import ConfidenceScorer, ConfidenceResult

class ConfidenceScorer(ABC):
    @abstractmethod
    def score(self, evidence: EvidenceBag, arch_delta=None) -> ConfidenceResult:
        """基于证据计算置信度。"""
```

### ConfidenceResult 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `score` | float | 0.0–1.0 |
| `breakdown` | dict[str, float] | 各维度得分明细 |
| `recommendation` | str | `"approve"` / `"reject"` / `"need_human"` |
| `reasoning` | str | 评分逻辑解释 |

### 示例：安全优先评分器

```python
from zelos.confidence import ConfidenceScorer, ConfidenceResult
from zelos.evidence import EvidenceBag

class SecurityFirstScorer(ConfidenceScorer):
    """安全扫描失败 → 直接 0 分。其他按正常权重。"""

    def score(self, evidence, arch_delta=None):
        # 安全扫描有失败 → 直接零分
        sec_items = [e for e in evidence.items
                     if e.type == "security_scan" and e.result == "FAIL"]
        if sec_items:
            return ConfidenceResult(
                score=0.0,
                breakdown={"security": 0.0},
                recommendation="reject",
                reasoning=f"Security scan failed: {sec_items[0].summary}"
            )

        # 正常评分逻辑
        test_pass = sum(1 for e in evidence.items
                       if e.type == "test_result" and e.result == "PASS")
        total_tests = sum(1 for e in evidence.items if e.type == "test_result")
        test_score = test_pass / max(total_tests, 1)

        score = test_score * 0.7  # 测试权重 70%
        return ConfidenceResult(
            score=min(1.0, score),
            breakdown={"test_pass": test_score * 0.7},
            recommendation="approve" if score > 0.8 else "need_human",
            reasoning=f"Security-first scoring: test_score={test_score:.0%}"
        )

# 使用：替换默认评分器
runtime._confidence_scorer = SecurityFirstScorer()
```

### 注意事项

- `recommendation` 必须是 `"approve"` / `"reject"` / `"need_human"` 之一
- 无证据时返回 `score=0.0, recommendation="need_human"`
- `arch_delta` 可能为 `None`，做空值检查

---

## 3. PolicyGate — 自定义决策规则

### 接口

```python
from zelos.policy_gate import PolicyGate, GateDecision

class PolicyGate(ABC):
    @abstractmethod
    def evaluate(self, report) -> GateDecision:
        """根据 ExecutionReport 做出决策。"""
```

### GateDecision 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `action` | str | `"auto_approve"` / `"auto_reject"` / `"require_human"` |
| `reason` | str | 决策理由 |
| `required_approvers` | list[str] | 需要谁审批（action=require_human 时） |

### 示例：合规优先策略门

```python
from zelos.policy_gate import PolicyGate, GateDecision

class CompliancePolicyGate(PolicyGate):
    """金融合规场景：任何涉及 payment 模块 → 强制人工审批。"""

    def evaluate(self, report):
        # 检查架构变更是否涉及敏感模块
        arch = report.architecture_delta
        if arch:
            sensitive = {"payment", "settlement", "auth", "user-data"}
            touched = set(arch.modified_modules) & sensitive
            if touched:
                return GateDecision(
                    action="require_human",
                    reason=f"Changes touch sensitive modules: {touched}",
                    required_approvers=["security-lead", "compliance-officer"],
                )

        # 否则走默认逻辑
        if report.confidence and report.confidence.score >= 0.95:
            return GateDecision(
                action="auto_approve",
                reason=f"Confidence {report.confidence.score:.0%}"
            )
        return GateDecision(
            action="require_human",
            reason="Standard review required"
        )

# 使用
runtime._policy_gate = CompliancePolicyGate()
```

### 注意事项

- `report` 是 `ExecutionReport` 对象，首次访问可能为 `None` 的属性要做空值检查
- `action` 的三个值必须精确匹配 `"auto_approve"` / `"auto_reject"` / `"require_human"`
- `require_human` 时建议提供 `required_approvers` 列表

---

## 4. ScoringStrategy — 自定义 Agent 排名

### 接口

```python
from zelos.scheduler import ScoringStrategy, AgentCandidate, ScoredCandidate

class ScoringStrategy(ABC):
    @abstractmethod
    def score(self, task: Task, candidates: list[AgentCandidate]) -> list[ScoredCandidate]:
        """对候选 Agent 打分排序。"""
```

### AgentCandidate 字段（传入）

| 字段 | 类型 | 说明 |
|------|------|------|
| `agent_id` | str | Agent 标识 |
| `agent_name` | str | Agent 名称 |
| `success_rate` | float | 历史成功率 |
| `cost_per_call` | float | 单次调用成本 |
| `avg_latency_ms` | float | 平均延迟 |
| `availability` | float | 可用性 |
| `current_load` | float | 当前负载 |
| `tags` | list[str] | 能力标签 |

### ScoredCandidate 字段（返回）

| 字段 | 类型 | 说明 |
|------|------|------|
| `candidate` | AgentCandidate | 原始候选 |
| `score` | float | 0.0–1.0 得分 |
| `reason` | str | 打分理由 |

### 示例：成本优先策略

```python
from zelos.scheduler import ScoringStrategy, ScoredCandidate

class CostFirstStrategy(ScoringStrategy):
    """成本最低且可用的 Agent 优先。"""

    def score(self, task, candidates):
        results = []
        for c in candidates:
            # 不可用 → 0 分
            if c.availability < 0.9:
                results.append(ScoredCandidate(c, score=0, reason="Unavailable"))
                continue

            # 成本驱动：成本越低分数越高
            max_cost = task.max_cost_per_call or 1.0
            cost_score = max(0, 1.0 - c.cost_per_call / max_cost)
            results.append(ScoredCandidate(
                c,
                score=cost_score,
                reason=f"cost={c.cost_per_call:.3f}, available={c.availability:.0%}"
            ))

        return sorted(results, key=lambda r: r.score, reverse=True)
```

### 注意事项

- 返回的列表必须按 `score` 降序排列（最高分在前）
- `score` 为 0 的候选不会被选中
- `AgentCandidate` 是 dataclass，直接读字段即可

---

## 5. Evidence — 自定义证据类型

### 接口

```python
from zelos.evidence import Evidence

Evidence(
    type: str,       # 证据类型；用 "custom" 表示自定义
    tool: str,       # 产生证据的工具名
    result: str,     # "PASS" / "FAIL" / "WARN" / "SKIP"
    data: dict,      # 详细数据
    summary: str,    # 人类可读摘要
)
```

### 示例：A/B 测试证据

```python
from zelos.evidence import Evidence

ab_evidence = Evidence(
    type="custom",              # 自定义类型
    tool="ab-test-platform",
    result="PASS",
    data={
        "experiment_id": "exp-042",
        "variant": "B",
        "metric": "conversion_rate",
        "control": 0.032,
        "treatment": 0.041,
        "p_value": 0.003,
        "sample_size": 50000,
    },
    summary="Variant B: +28% conversion (p=0.003, significant)"
)

runtime.add_evidence(goal_id, ab_evidence)
```

### 注意事项

- `type` 建议用预定义类型（`test_result`, `benchmark`, `security_scan`, `api_diff`, `canary`, `code_review`）以便 ConfidenceScorer 自动识别
- 不匹配预定义类型时用 `"custom"`，但 ConfidenceScorer 不会自动为其计算分数
- `result` 必须是 `"PASS"` / `"FAIL"` / `"WARN"` / `"SKIP"`（大写）

---

## 6. ConstraintEngine — 自定义约束

### 接口

```python
from zelos.constraint_engine import ConstraintEngine, ExecutableConstraints

class ConstraintEngine:
    def apply(self, cp: ChangeProposal) -> ExecutableConstraints:
        """将 CP 五元模型固化为可执行约束。"""
```

### ChangeProposal 五元

| 维度 | 字段 | 说明 |
|------|------|------|
| I | `cp.intent` | 意图（IntentSpec） |
| K | `cp.knowledge_constraints` | 知识约束（编码规范、禁用模式、技术栈限制） |
| S | `cp.structural_constraints` | 结构约束（模块边界、依赖白名单、API 契约） |
| R | `cp.risk_spec` | 风险规范（风险等级、安全要求、性能基线） |
| E | `cp.verification_criteria` | 验证准则（测试通过率、覆盖率门槛、必选 Verifier） |

### 示例：扩展约束引擎添加自定义编码规范

```python
from zelos.constraint_engine import ConstraintEngine, ExecutableConstraints
from zelos.change_proposal import ChangeProposal, KnowledgeConstraints

class MyConstraintEngine(ConstraintEngine):
    """在默认约束基础上，追加团队自定义规范。"""

    def apply(self, cp):
        ec = super().apply(cp)  # 先走默认逻辑

        # 追加团队自定义规范
        ec.coding_rules.extend([
            "REQUIRED: all public functions must have type hints",
            "REQUIRED: no function exceeds 50 lines",
            "FORBIDDEN: print() statements in production code",
        ])

        # 追加自定义架构边界
        if "core" not in ec.architecture_boundaries.get("protected_modules", []):
            ec.architecture_boundaries.setdefault("protected_modules", []).append("core")

        return ec

# 使用
runtime._constraint_engine = MyConstraintEngine()
```

### 注意事项

- `ExecutableConstraints.to_context_dict()` 是注入到 Agent 执行上下文的格式
- 约束在 dispatch 时自动注入 `Task.constraints` 字段
- KnowledgeConstraints / StructuralConstraints / RiskSpec / VerificationCriteria 都有 `from_dict()` 工厂方法

---

## 7. Planner — 自定义规划器

### 接口

LLMPlanner 是默认实现，支持通过配置切换 LLM Provider：

```python
from zelos.planner import LLMPlanner

planner = LLMPlanner({
    "provider": "openai",           # openai / anthropic / google / mock
    "model": "gpt-4o",
    "api_key": "${OPENAI_API_KEY}",
    "temperature": 0.3,
})
```

### 自定义 Planner（非 LLM）

可以实现自己的 Planner 替代 LLM：

```python
from zelos.planner import PlannerPlan, PlannerTask

class RuleBasedPlanner:
    """基于模板规则的 Planner，不依赖 LLM。"""

    def __init__(self, config=None):
        self.planner_id = "rule-based"
        self.planner_version = "1.0.0"

    def plan(self, goal_description, goal_id="", context=None):
        plan = PlannerPlan(goal_id=goal_id, planner_id=self.planner_id)
        # 基于规则拆解 Goal
        if "deploy" in goal_description.lower():
            plan.tasks = [
                PlannerTask("t1", "Run tests", "verification.unit-test"),
                PlannerTask("t2", "Build image", "automation.docker"),
                PlannerTask("t3", "Deploy to K8s", "automation.k8s", dependencies=["t1", "t2"]),
            ]
        else:
            plan.tasks = [
                PlannerTask("t1", goal_description, "code-generation.python"),
            ]
        return plan

# 使用
runtime._planner = RuleBasedPlanner()
```

### 注意事项

- `PlannerTask` 字段：`task_id`, `description`, `required_capability`, `dependencies`（list）, `priority`, `timeout_ms`
- 返回 `PlannerPlan` 即可，Runtime 负责后续调度
- Planner 是插件，替换不影响 Runtime 其他模块

---

## 快速参考：什么时候自定义什么

| 需求 | 自定义什么 |
|------|-----------|
| 验证 Agent 输出是否符合业务规范 | `Verifier` → `VerifierChain.register()` |
| 改变"能不能上线"的评分标准 | `ConfidenceScorer` |
| 改变审批流程（多级、合规等） | `PolicyGate` |
| 改变"选哪个 Agent 执行任务"的排名规则 | `ScoringStrategy` |
| 不用 LLM 做 Goal 分解 | 自定义 `Planner` |
| 增加新的证据类型 | `Evidence(type="custom", ...)` |
| 增加编码规范、架构边界约束 | 扩展 `ConstraintEngine` 或配置 `ChangeProposal` |

---

> 所有接口均基于 v1.0.0 代码验证，示例可运行。
