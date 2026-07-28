"""
Change Proposal — First-class CP governance object (v1.0.0).

Implements the paper's five-dimensional information model:
  CP = (I, K, S, R, E)
  I: Intent — what problem, what success, what scope
  K: Knowledge Constraints — coding standards, tech stack limits
  S: Structural Constraints — architecture boundaries, dependency whitelist
  R: Risk Specification — risk thresholds, security requirements
  E: Verification Criteria — test pass rate, coverage, benchmark baselines

CP is an executable governance object, not a static document.
"""

from dataclasses import dataclass, field


@dataclass
class KnowledgeConstraints:
    """K-dimension: knowledge-level coding and tech constraints."""
    coding_standards: list[str] = field(default_factory=list)  # lint rules, style guides
    tech_stack_limits: list[str] = field(default_factory=list)  # allowed languages, frameworks, libs
    forbidden_patterns: list[str] = field(default_factory=list)  # anti-patterns to reject

    def to_dict(self) -> dict:
        return {
            "coding_standards": list(self.coding_standards),
            "tech_stack_limits": list(self.tech_stack_limits),
            "forbidden_patterns": list(self.forbidden_patterns),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "KnowledgeConstraints":
        return cls(
            coding_standards=d.get("coding_standards", []),
            tech_stack_limits=d.get("tech_stack_limits", []),
            forbidden_patterns=d.get("forbidden_patterns", []),
        )


@dataclass
class StructuralConstraints:
    """S-dimension: architecture boundaries and structural rules."""
    modified_modules: list[str] = field(default_factory=list)
    protected_modules: list[str] = field(default_factory=list)  # must NOT be changed
    dependency_whitelist: list[str] = field(default_factory=list)
    api_contracts: list[dict] = field(default_factory=list)  # must-maintain API schemas

    def to_dict(self) -> dict:
        return {
            "modified_modules": list(self.modified_modules),
            "protected_modules": list(self.protected_modules),
            "dependency_whitelist": list(self.dependency_whitelist),
            "api_contracts": list(self.api_contracts),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "StructuralConstraints":
        return cls(
            modified_modules=d.get("modified_modules", []),
            protected_modules=d.get("protected_modules", []),
            dependency_whitelist=d.get("dependency_whitelist", []),
            api_contracts=d.get("api_contracts", []),
        )


@dataclass
class RiskSpec:
    """R-dimension: risk thresholds and security requirements."""
    risk_level: str = "medium"  # low | medium | high | critical
    security_requirements: list[str] = field(default_factory=list)
    performance_baseline: dict = field(default_factory=dict)  # min TPS, max latency
    data_integrity_required: bool = False

    def to_dict(self) -> dict:
        return {
            "risk_level": self.risk_level,
            "security_requirements": list(self.security_requirements),
            "performance_baseline": dict(self.performance_baseline),
            "data_integrity_required": self.data_integrity_required,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RiskSpec":
        return cls(
            risk_level=d.get("risk_level", "medium"),
            security_requirements=d.get("security_requirements", []),
            performance_baseline=d.get("performance_baseline", {}),
            data_integrity_required=d.get("data_integrity_required", False),
        )


@dataclass
class VerificationCriteria:
    """E-dimension: verification standards and thresholds."""
    test_pass_rate: float = 1.0  # required pass rate (0.0-1.0)
    coverage_threshold_pct: float = 0.0  # minimum code coverage
    benchmark_regression_limit_pct: float = 10.0  # max allowed regression
    required_verifiers: list[str] = field(default_factory=list)  # verifier types required
    security_scan_required: bool = True

    def to_dict(self) -> dict:
        return {
            "test_pass_rate": self.test_pass_rate,
            "coverage_threshold_pct": self.coverage_threshold_pct,
            "benchmark_regression_limit_pct": self.benchmark_regression_limit_pct,
            "required_verifiers": list(self.required_verifiers),
            "security_scan_required": self.security_scan_required,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "VerificationCriteria":
        return cls(
            test_pass_rate=d.get("test_pass_rate", 1.0),
            coverage_threshold_pct=d.get("coverage_threshold_pct", 0.0),
            benchmark_regression_limit_pct=d.get("benchmark_regression_limit_pct", 10.0),
            required_verifiers=d.get("required_verifiers", []),
            security_scan_required=d.get("security_scan_required", True),
        )


@dataclass
class ChangeProposal:
    """CP = (I, K, S, R, E) — five-dimensional executable governance object.

    This is the paper's core definition: an instantiated element of the
    Cartesian product space ℂ = I × K × S × R × E. It authoritatively
    constrains the full workflow lifecycle.
    """

    goal_id: str = ""
    intent: "IntentSpec | None" = None  # I-dimension (from execution_report)
    knowledge_constraints: KnowledgeConstraints = field(default_factory=KnowledgeConstraints)
    structural_constraints: StructuralConstraints = field(default_factory=StructuralConstraints)
    risk_spec: RiskSpec = field(default_factory=RiskSpec)
    verification_criteria: VerificationCriteria = field(default_factory=VerificationCriteria)

    def to_dict(self) -> dict:
        result = {"goal_id": self.goal_id}
        if self.intent:
            result["intent"] = self.intent.to_dict() if hasattr(self.intent, 'to_dict') else {}
        result.update({
            "knowledge_constraints": self.knowledge_constraints.to_dict(),
            "structural_constraints": self.structural_constraints.to_dict(),
            "risk_spec": self.risk_spec.to_dict(),
            "verification_criteria": self.verification_criteria.to_dict(),
        })
        return result

    @classmethod
    def from_dict(cls, d: dict) -> "ChangeProposal":
        return cls(
            goal_id=d.get("goal_id", ""),
            knowledge_constraints=KnowledgeConstraints.from_dict(d.get("knowledge_constraints", {})),
            structural_constraints=StructuralConstraints.from_dict(d.get("structural_constraints", {})),
            risk_spec=RiskSpec.from_dict(d.get("risk_spec", {})),
            verification_criteria=VerificationCriteria.from_dict(d.get("verification_criteria", {})),
        )

    @classmethod
    def from_intent(cls, goal_id: str, intent: "IntentSpec | None" = None) -> "ChangeProposal":
        """Factory: build CP from an IntentSpec with sensible defaults.

        Derives constraints from intent metadata:
        - scope → risk level (single_module=low, multi_module=medium, system_wide=high)
        - constraints → knowledge constraints (coding standards, forbidden patterns)
        - success_criteria → verification criteria (test_pass_rate, required_verifiers)
        """
        cp = cls(goal_id=goal_id, intent=intent)
        if not intent:
            return cp

        # Risk: scope-based derivation
        risk_map = {"single_module": "low", "multi_module": "medium",
                     "system_wide": "high", "auto": "medium"}
        cp.risk_spec = RiskSpec(risk_level=risk_map.get(intent.scope, "medium"))

        # Structural: scope → module boundaries
        cp.structural_constraints = StructuralConstraints(
            modified_modules=[] if intent.scope in ("auto", "single_module") else [intent.scope],
        )

        # Knowledge: constraints → coding rules
        coding_rules = []
        forbidden = []
        for c in intent.constraints:
            if any(kw in c.lower() for kw in ["standard", "规范", "library", "库", "protocol", "协议"]):
                coding_rules.append(c)
            elif any(kw in c.lower() for kw in ["must not", "禁止", "don't", "no ", "forbidden"]):
                forbidden.append(c)
        cp.knowledge_constraints = KnowledgeConstraints(
            coding_standards=coding_rules if coding_rules else ["follow existing code style"],
            forbidden_patterns=forbidden,
        )

        # Verification: success_criteria → verification requirements
        cp.verification_criteria = VerificationCriteria(
            test_pass_rate=1.0,
            coverage_threshold_pct=80.0 if intent.scope != "system_wide" else 70.0,
            required_verifiers=["schema"],
            security_scan_required=intent.scope in ("multi_module", "system_wide"),
        )

        return cp

    def get_five_tuple(self) -> tuple:
        """Return the canonical five-tuple (I, K, S, R, E) per the paper."""
        return (
            self.intent,
            self.knowledge_constraints,
            self.structural_constraints,
            self.risk_spec,
            self.verification_criteria,
        )
