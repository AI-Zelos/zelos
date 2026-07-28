"""
Confidence Scoring — Pluggable scorer that computes confidence from Evidence.

v0.9.0: WeightedConfidenceScorer computes a 0.0-1.0 score from EvidenceBag.
Configurable weights and thresholds via zelos.yaml.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from .evidence import EvidenceBag


@dataclass
class ConfidenceResult:
    """Result of confidence scoring for a Goal execution.

    Fields:
        score: 0.0 - 1.0 confidence score
        breakdown: Per-category score contributions
        recommendation: approve / reject / need_human
        reasoning: Human-readable explanation
    """

    score: float
    breakdown: dict[str, float] = field(default_factory=dict)
    recommendation: str = "need_human"
    reasoning: str = ""

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "breakdown": dict(self.breakdown),
            "recommendation": self.recommendation,
            "reasoning": self.reasoning,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ConfidenceResult":
        return cls(
            score=float(d.get("score", 0.0)),
            breakdown=dict(d.get("breakdown", {})),
            recommendation=d.get("recommendation", "need_human"),
            reasoning=d.get("reasoning", ""),
        )


class ConfidenceScorer(ABC):
    """Plugin interface for confidence scoring."""

    @abstractmethod
    def score(self, evidence: EvidenceBag, arch_delta=None) -> ConfidenceResult:
        """Compute confidence score from evidence and architecture delta."""
        ...


class WeightedConfidenceScorer(ConfidenceScorer):
    """Default weighted multi-factor confidence scorer.

    Weights can be configured via constructor or zelos.yaml:

    ```yaml
    confidence:
      weights:
        test_pass: 0.30
        benchmark: 0.15
        security: 0.20
        api_compat: 0.10
        canary: 0.15
        code_review: 0.10
      thresholds:
        auto_approve: 0.95
        require_human: 0.70
        auto_reject: 0.40
    ```
    """

    def __init__(self, weights: dict[str, float] | None = None,
                 thresholds: dict[str, float] | None = None):
        self.weights = weights or {
            "test_pass": 0.30,
            "benchmark": 0.15,
            "security": 0.20,
            "api_compat": 0.10,
            "code_review": 0.10,
            "canary": 0.15,
        }
        self.thresholds = thresholds or {
            "auto_approve": 0.95,
            "require_human": 0.70,
            "auto_reject": 0.40,
        }

    def score(self, evidence: EvidenceBag, arch_delta=None) -> ConfidenceResult:
        if not evidence.items:
            return ConfidenceResult(
                score=0.0, recommendation="need_human",
                reasoning="No evidence collected — cannot assess confidence",
            )

        breakdown = {}
        total = 0.0
        active_weight = 0.0

        for ev_type, weight in self.weights.items():
            score_contrib = 0.0
            has_items = False
            if ev_type == "test_pass":
                has_items = any(e.type == "test_result" for e in evidence.items)
                score_contrib = self._score_test_results(evidence)
            elif ev_type == "benchmark":
                has_items = any(e.type == "benchmark" for e in evidence.items)
                score_contrib = self._score_benchmarks(evidence)
            elif ev_type == "security":
                has_items = any(e.type == "security_scan" for e in evidence.items)
                score_contrib = self._score_security(evidence)
            elif ev_type == "api_compat":
                has_items = any(e.type == "api_diff" for e in evidence.items)
                score_contrib = self._score_api_compat(evidence)
            elif ev_type == "canary":
                has_items = any(e.type == "canary" for e in evidence.items)
                score_contrib = self._score_canary(evidence)
            elif ev_type == "code_review":
                has_items = any(e.type == "code_review" for e in evidence.items)
                score_contrib = self._score_code_review(evidence)

            weighted = score_contrib * weight
            breakdown[ev_type] = weighted
            total += weighted
            if has_items:
                active_weight += weight

        # Normalize by active weights (evidence types that were actually collected)
        if active_weight > 0:
            score = min(1.0, total / active_weight)
        else:
            score = 0.0

        # Recommendation based on thresholds
        if score >= self.thresholds.get("auto_approve", 0.95):
            recommendation = "approve"
            reasoning = f"Confidence {score:.0%} exceeds auto-approve threshold"
        elif score < self.thresholds.get("auto_reject", 0.40):
            recommendation = "reject"
            reasoning = f"Confidence {score:.0%} below auto-reject threshold"
        else:
            recommendation = "need_human"
            reasoning = f"Confidence {score:.0%} requires human review"

        return ConfidenceResult(
            score=score, breakdown=breakdown,
            recommendation=recommendation, reasoning=reasoning,
        )

    def _score_test_results(self, evidence: EvidenceBag) -> float:
        test_items = [e for e in evidence.items if e.type == "test_result"]
        if not test_items:
            return 0.0
        passed = sum(1 for e in test_items if e.result == "PASS")
        return passed / len(test_items)

    def _score_benchmarks(self, evidence: EvidenceBag) -> float:
        bench_items = [e for e in evidence.items if e.type == "benchmark"]
        if not bench_items:
            return 0.0
        passed = sum(1 for e in bench_items if e.result == "PASS")
        # Check if any benchmark shows regression
        for b in bench_items:
            baseline = b.data.get("baseline", 0)
            actual = b.data.get("actual", b.data.get("tps", 0))
            if baseline > 0 and actual < baseline * 0.9:
                return 0.0  # >10% regression = fail
        return passed / len(bench_items)

    def _score_security(self, evidence: EvidenceBag) -> float:
        sec_items = [e for e in evidence.items if e.type == "security_scan"]
        if not sec_items:
            return 0.0
        passed = sum(1 for e in sec_items if e.result == "PASS")
        return passed / len(sec_items)

    def _score_api_compat(self, evidence: EvidenceBag) -> float:
        api_items = [e for e in evidence.items if e.type == "api_diff"]
        if not api_items:
            return 0.0
        passed = sum(1 for e in api_items if e.result == "PASS")
        return passed / len(api_items)

    def _score_canary(self, evidence: EvidenceBag) -> float:
        canary_items = [e for e in evidence.items if e.type == "canary"]
        if not canary_items:
            return 0.0
        passed = sum(1 for e in canary_items if e.result == "PASS")
        return passed / len(canary_items)

    def _score_code_review(self, evidence: EvidenceBag) -> float:
        cr_items = [e for e in evidence.items if e.type == "code_review"]
        if not cr_items:
            return 0.0
        passed = sum(1 for e in cr_items if e.result == "PASS")
        return passed / len(cr_items)
