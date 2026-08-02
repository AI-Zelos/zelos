"""
Replan Rules Engine — Deterministic triggers for MPC replan decisions.

v1.3.0: Rule-based replan (Level 1). Each rule evaluates a ReplanContext
and returns True if the Runtime should replan the current execution path.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .verifier import Verdict
    from .planner import PlannerPlan


@dataclass
class ReplanContext:
    """Snapshot of current execution state for replan rule evaluation."""

    task_id: str
    artifact: dict | None
    verdict: "Verdict"
    current_plan: "PlannerPlan | None" = None


class ReplanRule(ABC):
    """Abstract base for replan trigger rules."""

    @property
    @abstractmethod
    def trigger_reason(self) -> str:
        """Human-readable trigger description (e.g., 'verdict_rejected')."""
        ...

    @abstractmethod
    def should_replan(self, ctx: ReplanContext) -> bool:
        """Return True if the current state warrants a replan."""
        ...


class VerdictRejectedRule(ReplanRule):
    """Verifier returned rejected → replan."""

    trigger_reason = "verdict_rejected"

    def should_replan(self, ctx: ReplanContext) -> bool:
        return ctx.verdict.verdict == "failed"


class ConfidenceLowRule(ReplanRule):
    """Verifier confidence below threshold → trigger replan."""

    trigger_reason = "confidence_low"

    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold

    def should_replan(self, ctx: ReplanContext) -> bool:
        return ctx.verdict.score < self.threshold


class SchemaMismatchRule(ReplanRule):
    """Artifact schema doesn't match expected output schema → replan."""

    trigger_reason = "schema_mismatch"

    def should_replan(self, ctx: ReplanContext) -> bool:
        if ctx.current_plan is None:
            return False
        task = ctx.current_plan.get_task(ctx.task_id)
        if not task:
            return False
        expected_schema = getattr(task, 'expected_output_schema', None)
        if not expected_schema:
            return False
        artifact_type = type(ctx.artifact).__name__
        expected_type = expected_schema.get("type", "")
        return artifact_type != expected_type


class EmptyArtifactRule(ReplanRule):
    """Artifact is empty or None → replan."""

    trigger_reason = "empty_artifact"

    def should_replan(self, ctx: ReplanContext) -> bool:
        if ctx.artifact is None:
            return True
        if isinstance(ctx.artifact, dict) and not ctx.artifact:
            return True
        return False


DEFAULT_REPLAN_RULES: list[ReplanRule] = [
    VerdictRejectedRule(),
    ConfidenceLowRule(threshold=0.5),
    SchemaMismatchRule(),
    EmptyArtifactRule(),
]
