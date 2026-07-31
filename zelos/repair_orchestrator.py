"""
Repair Orchestrator — Runtime-Guided Repair with Hypothesis Tracker.

v1.2.0: Not "retry from scratch." Take diagnosis → tell Fixer exactly what's wrong → fix.
Tracks attempted repair directions to avoid LLM repeating guesses.
"""

from dataclasses import dataclass, field

from .diagnosis_engine import DiagnosisResult


@dataclass
class HypothesisRecord:
    """One repair attempt direction."""
    attempt: int
    hypothesis: str = ""       # LLM's stated fix direction
    result: str = "unknown"    # still_failing | new_failures | passed


@dataclass
class RepairContext:
    """Context passed to Fixer Agent for targeted repair."""
    issue_description: str
    current_patch: str
    diagnosis: DiagnosisResult
    # Structured failure summary (for LLM prompt)
    failure_summary: str = ""
    # Hypothesis tracker
    tried_hypotheses: list[HypothesisRecord] = field(default_factory=list)
    max_attempts: int = 3

    def build_fixer_prompt(self) -> str:
        """Build a prompt for the Fixer Agent with precise diagnostic info."""
        failures_text = ""
        for i, f in enumerate(self.diagnosis.failures[:5]):
            loc = f"{f.location_file}:{f.location_line}" if f.location_file else "unknown"
            failures_text += (
                f"\n  {i+1}. {f.test_name} — {f.failure_type}\n"
                f"     Location: {loc}\n"
            )
            if f.expected:
                failures_text += f"     Expected: {f.expected}\n"
            if f.actual:
                failures_text += f"     Actual: {f.actual}\n"

        hypo_text = ""
        if self.tried_hypotheses:
            hypo_text = "\nPreviously tried (and failed) approaches:\n"
            for h in self.tried_hypotheses:
                hypo_text += f"  - [{h.hypothesis}] → {h.result}\n"
            hypo_text += "Do NOT repeat any of these approaches.\n"

        return (
            f"The previous patch failed {self.diagnosis.failed} tests.\n"
            f"Impact scope: {self.diagnosis.impact_scope}\n"
            f"Recommendation: {self.diagnosis.recommendation}\n"
            f"\nFailing tests:{failures_text}\n"
            f"{hypo_text}"
            f"\nIssue: {self.issue_description[:1000]}\n"
            f"\nCurrent patch:\n{self.current_patch[:3000]}\n"
            f"\nFix ONLY the failing tests listed above. Output a complete unified diff patch."
        )

    @property
    def should_abandon(self) -> bool:
        return len(self.tried_hypotheses) >= self.max_attempts


class RepairOrchestrator:
    """Orchestrates Runtime-Guided Repair cycles.

    Workflow:
      1. Diagnosis → FailureClassifier → repair
      2. Build RepairContext with precise failure locations
      3. Call Fixer Agent with targeted prompt
      4. Re-evaluate in Docker
      5. Repeat up to max_attempts (3)
    """

    def __init__(self, max_attempts: int = 3):
        self.max_attempts = max_attempts

    def should_repair(self, classification_result) -> bool:
        """Check if classifier says this is worth repairing."""
        return (classification_result.action == "repair"
                and classification_result.salvageable)

    def build_context(self, issue: str, patch: str, diagnosis: DiagnosisResult,
                      previous_hypotheses: list[HypothesisRecord] | None = None) -> RepairContext:
        """Build RepairContext for the current repair attempt."""
        ctx = RepairContext(
            issue_description=issue,
            current_patch=patch,
            diagnosis=diagnosis,
            tried_hypotheses=previous_hypotheses or [],
            max_attempts=self.max_attempts,
        )
        ctx.failure_summary = ctx.build_fixer_prompt()
        return ctx

    def record_hypothesis(self, attempt: int, hypothesis: str,
                          result: str = "still_failing") -> HypothesisRecord:
        """Record a repair attempt direction."""
        return HypothesisRecord(attempt=attempt, hypothesis=hypothesis, result=result)
