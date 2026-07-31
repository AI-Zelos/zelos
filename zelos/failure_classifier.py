"""
Failure Classifier — Runtime decides: repair, retry, or abandon.

v1.2.0: Takes DiagnosisResult, outputs ClassificationResult with action + reason.
"""
from dataclasses import dataclass, field

from .diagnosis_engine import DiagnosisResult


@dataclass
class ClassificationResult:
    """Decision from failure classification."""
    action: str = "retry"       # repair | retry | abandon
    reason: str = ""
    salvageable: bool = False   # Is Fixer worth trying?
    failure_type: str = "unknown"


class FailureClassifier:
    """Classifies test failures into repair/retry/abandon decisions.

    Rules are deterministic — Runtime decides, not LLM.
    """

    def __init__(self, max_retries_before_abandon: int = 3):
        self._retry_count: dict[str, int] = {}  # test_name → consecutive failures

    def classify(self, diagnosis: DiagnosisResult) -> ClassificationResult:
        """Classify a diagnosis result into action decision."""
        # All passing
        if diagnosis.recommendation == "all_passed":
            return ClassificationResult(
                action="done", reason="All tests passed", salvageable=False
            )

        # Full explosion → abandon immediately
        if diagnosis.impact_scope == "full_explosion":
            return ClassificationResult(
                action="abandon",
                reason=f"Full explosion: {diagnosis.failed}/{diagnosis.total_tests} tests failed",
                salvageable=False, failure_type="full_explosion",
            )

        # Check for salvageable failures
        salvageable_types = {"AssertionError", "TypeError", "AttributeError"}
        primary_type = diagnosis.failures[0].failure_type if diagnosis.failures else "unknown"

        salvageable = all(
            f.failure_type in salvageable_types
            for f in diagnosis.failures[:5]
        )

        if salvageable:
            return ClassificationResult(
                action="repair",
                reason=f"Salvageable: {primary_type}, {diagnosis.failed} failures in {diagnosis.impact_scope}",
                salvageable=True, failure_type=primary_type,
            )

        # Mixed failure types → retry once
        unsalvageable_types = {"ImportError", "ModuleNotFoundError", "Timeout"}
        if any(f.failure_type in unsalvageable_types for f in diagnosis.failures[:5]):
            # Import/Timeout errors → try fixing or abandon
            if len(diagnosis.failures) <= 2:
                return ClassificationResult(
                    action="repair",
                    reason=f"Fixable: {', '.join(f.failure_type for f in diagnosis.failures[:3])}",
                    salvageable=True, failure_type=primary_type,
                )
            return ClassificationResult(
                action="abandon",
                reason=f"Too many infrastructure failures: {diagnosis.failed} errors",
                salvageable=False, failure_type=primary_type,
            )

        # Default: retry
        return ClassificationResult(
            action="retry",
            reason=f"Mixed failures: {diagnosis.failed} failed, {diagnosis.errors} errors",
            salvageable=True, failure_type=primary_type,
        )

    def track_retry(self, test_name: str) -> ClassificationResult | None:
        """Track retry count. Returns abandon decision if exceeded."""
        count = self._retry_count.get(test_name, 0) + 1
        self._retry_count[test_name] = count
        if count >= 3:
            return ClassificationResult(
                action="abandon",
                reason=f"Same test failed {count} consecutive times — stop loss",
                salvageable=False, failure_type="consecutive_failure",
            )
        return None
