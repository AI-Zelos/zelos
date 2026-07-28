"""
Constraint Engine — Solidifies Change Proposal into executable constraints.

v1.0.0: Parses CP five-tuple (I,K,S,R,E) and produces ExecutableConstraints
that can be injected into Agent execution context for constrained generation.
"""

from dataclasses import dataclass, field

from .change_proposal import ChangeProposal


@dataclass
class ExecutableConstraints:
    """Constraints ready for injection into Agent execution context."""

    coding_rules: list[str] = field(default_factory=list)
    architecture_boundaries: dict = field(default_factory=dict)
    risk_thresholds: dict = field(default_factory=dict)
    api_contracts: list[dict] = field(default_factory=list)
    verification_requirements: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)  # Full raw constraint set

    def to_context_dict(self) -> dict:
        """Format constraints for injection into Task input_context."""
        return {
            "constraints": {
                "coding_rules": self.coding_rules,
                "architecture_boundaries": self.architecture_boundaries,
                "risk_thresholds": self.risk_thresholds,
                "api_contracts": self.api_contracts,
                "verification_requirements": self.verification_requirements,
            }
        }

    def to_dict(self) -> dict:
        return {
            "coding_rules": self.coding_rules,
            "architecture_boundaries": self.architecture_boundaries,
            "risk_thresholds": self.risk_thresholds,
            "api_contracts": self.api_contracts,
            "verification_requirements": self.verification_requirements,
        }


class ConstraintEngine:
    """Parses a ChangeProposal and produces ExecutableConstraints.

    This is the implementation of the paper's 'Constraint Solidification' stage.
    It takes the formal CP five-tuple and translates it into concrete rules
    that agents and verifiers can parse and enforce.
    """

    def apply(self, cp: ChangeProposal) -> ExecutableConstraints:
        """Solidify a ChangeProposal into executable constraints.

        Args:
            cp: The ChangeProposal to solidify.

        Returns:
            ExecutableConstraints ready for agent injection.
        """
        constraints = ExecutableConstraints()

        # K-dimension: Knowledge constraints → coding rules
        if cp.knowledge_constraints:
            constraints.coding_rules = list(cp.knowledge_constraints.coding_standards)
            if cp.knowledge_constraints.forbidden_patterns:
                constraints.coding_rules.extend(
                    [f"FORBIDDEN: {p}" for p in cp.knowledge_constraints.forbidden_patterns]
                )
            if cp.knowledge_constraints.tech_stack_limits:
                constraints.coding_rules.append(
                    f"TECH_STACK: {', '.join(cp.knowledge_constraints.tech_stack_limits)}"
                )

        # S-dimension: Structural constraints → architecture boundaries
        if cp.structural_constraints:
            constraints.architecture_boundaries = {
                "modified_modules": cp.structural_constraints.modified_modules,
                "protected_modules": cp.structural_constraints.protected_modules,
                "dependency_whitelist": cp.structural_constraints.dependency_whitelist,
                "api_contracts": cp.structural_constraints.api_contracts,
            }

        # R-dimension: Risk spec → risk thresholds
        if cp.risk_spec:
            constraints.risk_thresholds = {
                "risk_level": cp.risk_spec.risk_level,
                "security_requirements": cp.risk_spec.security_requirements,
                "performance_baseline": cp.risk_spec.performance_baseline,
                "data_integrity_required": cp.risk_spec.data_integrity_required,
            }

        # E-dimension: Verification criteria → verification requirements
        if cp.verification_criteria:
            constraints.verification_requirements = {
                "test_pass_rate": cp.verification_criteria.test_pass_rate,
                "coverage_threshold_pct": cp.verification_criteria.coverage_threshold_pct,
                "benchmark_regression_limit_pct": cp.verification_criteria.benchmark_regression_limit_pct,
                "required_verifiers": cp.verification_criteria.required_verifiers,
                "security_scan_required": cp.verification_criteria.security_scan_required,
            }

        # Store raw for debugging
        constraints.raw = cp.to_dict()
        return constraints
