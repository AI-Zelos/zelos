"""
Policy Gate v2 — Evidence-based approval/rejection decisions.

v0.9.0: Beyond cost/rate limits — makes auto-approve/reject/require_human decisions
based on ExecutionReport evidence and confidence score.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class GateDecision:
    """Policy gate decision for a Goal execution.

    Fields:
        action: auto_approve / auto_reject / require_human
        reason: Human-readable explanation
        required_approvers: List of approver IDs when require_human
    """

    action: str = "require_human"
    reason: str = ""
    required_approvers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "reason": self.reason,
            "required_approvers": list(self.required_approvers),
        }


class PolicyGate(ABC):
    """Plugin interface for evidence-based policy decisions."""

    @abstractmethod
    def evaluate(self, report) -> GateDecision:
        """Evaluate an ExecutionReport and return a GateDecision."""
        ...


class EvidenceBasedPolicyGate(PolicyGate):
    """Default policy gate: rule-based decisions from confidence + risk + evidence.

    Rules (configurable):
    - Critical risk → require_human (with architect + security-lead)
    - Evidence has failures → require_human
    - Confidence >= 0.95 AND risk = low → auto_approve
    - Confidence < 0.40 → auto_reject
    - Default → require_human
    """

    def evaluate(self, report) -> GateDecision:
        confidence_score = report.confidence.score if report.confidence else 0.0
        risk_level = getattr(report, "risk_level", "medium")
        all_pass = report.evidence_bag.all_pass if report.evidence_bag else True

        return self._evaluate_rules(
            confidence_score=confidence_score,
            risk_level=risk_level,
            all_pass=all_pass,
        )

    def _evaluate_rules(self, confidence_score: float, risk_level: str,
                        all_pass: bool) -> GateDecision:
        # Rule 1: Critical risk always requires human
        if risk_level == "critical":
            return GateDecision(
                action="require_human",
                reason="Critical risk level — requires human approval",
                required_approvers=["architect", "security-lead"],
            )

        # Rule 2: Evidence failures require human review
        if not all_pass:
            return GateDecision(
                action="require_human",
                reason="Evidence has failures — requires human review",
            )

        # Rule 3: High confidence + low risk → auto approve
        if confidence_score >= 0.95 and risk_level == "low":
            return GateDecision(
                action="auto_approve",
                reason=f"Confidence {confidence_score:.0%}, low risk — auto-approved",
            )

        # Rule 4: Very low confidence → auto reject
        if confidence_score < 0.40:
            return GateDecision(
                action="auto_reject",
                reason=f"Confidence {confidence_score:.0%} below threshold — auto-rejected",
            )

        # Rule 5: High confidence + medium risk → auto approve (with caution)
        if confidence_score >= 0.90 and risk_level in ("low", "medium"):
            return GateDecision(
                action="auto_approve",
                reason=f"Confidence {confidence_score:.0%}, {risk_level} risk — auto-approved",
            )

        # Default: require human
        return GateDecision(
            action="require_human",
            reason=f"Confidence {confidence_score:.0%}, {risk_level} risk — default to human review",
        )
