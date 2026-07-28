"""
Execution Report — Unified Change Evidence Package.

v0.9.0: The core deliverable. Aggregates Intent, Architecture Delta,
Execution Trace, Evidence Bag, Confidence Score, and Rollback Plan
into one structured report for human/system decision-making.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class IntentSpec:
    """Structured intent capture for a Goal.

    Describes what the user wants, success criteria, and constraints.
    Planner uses this to confirm understanding before execution.
    """

    description: str
    success_criteria: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    scope: str = "auto"  # auto | single_module | multi_module | system_wide
    rollback_on_failure: bool = True

    def to_dict(self) -> dict:
        return {
            "description": self.description,
            "success_criteria": list(self.success_criteria),
            "constraints": list(self.constraints),
            "scope": self.scope,
            "rollback_on_failure": self.rollback_on_failure,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "IntentSpec":
        return cls(
            description=d.get("description", ""),
            success_criteria=list(d.get("success_criteria", [])),
            constraints=list(d.get("constraints", [])),
            scope=d.get("scope", "auto"),
            rollback_on_failure=bool(d.get("rollback_on_failure", True)),
        )


@dataclass
class APIChange:
    """A single API change in the Architecture Delta."""
    endpoint: str
    change_type: str  # new | modified | deprecated | removed
    compatibility: str = "unknown"  # additive | backward_compatible | breaking


@dataclass
class ArchDelta:
    """Architecture impact analysis for a Goal execution.

    Produced by the Planner as part of the ExecutionPlan.
    Describes what changed in the system structure.
    """

    modified_modules: list[str] = field(default_factory=list)
    new_dependencies: list[str] = field(default_factory=list)
    removed_dependencies: list[str] = field(default_factory=list)
    api_changes: list[APIChange] = field(default_factory=list)
    data_model_changes: list[str] = field(default_factory=list)
    risk_level: str = "unknown"  # unknown | low | medium | high | critical
    explanation: str = ""

    def to_dict(self) -> dict:
        return {
            "modified_modules": list(self.modified_modules),
            "new_dependencies": list(self.new_dependencies),
            "removed_dependencies": list(self.removed_dependencies),
            "api_changes": [
                {"endpoint": a.endpoint, "change_type": a.change_type,
                 "compatibility": a.compatibility}
                for a in self.api_changes
            ],
            "data_model_changes": list(self.data_model_changes),
            "risk_level": self.risk_level,
            "explanation": self.explanation,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ArchDelta":
        api = [APIChange(**a) if isinstance(a, dict) else a for a in d.get("api_changes", [])]
        return cls(
            modified_modules=list(d.get("modified_modules", [])),
            new_dependencies=list(d.get("new_dependencies", [])),
            removed_dependencies=list(d.get("removed_dependencies", [])),
            api_changes=api,
            data_model_changes=list(d.get("data_model_changes", [])),
            risk_level=d.get("risk_level", "unknown"),
            explanation=d.get("explanation", ""),
        )


@dataclass
class RollbackPlan:
    """Rollback strategy for a Goal execution."""
    strategy: str = "none"  # event_sourcing_replay | manual | none
    restore_to_event_position: int | None = None
    estimated_downtime_s: float = 0.0
    steps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "strategy": self.strategy,
            "restore_to_event_position": self.restore_to_event_position,
            "estimated_downtime_s": self.estimated_downtime_s,
            "steps": list(self.steps),
        }


@dataclass
class ExecutionReport:
    """Unified Change Evidence Package for a completed Goal.

    The core v0.9.0 deliverable. Contains everything needed for a human
    or system to decide whether to approve or reject the change.
    """

    goal_id: str
    status: str = "unknown"

    # ── Intent ──
    intent: IntentSpec | None = None
    intent_confirmed: bool = False

    # ── Architecture Delta ──
    architecture_delta: ArchDelta | None = None

    # ── Execution Trace ──
    trace: Any = None  # ExecutionTrace

    # ── Evidence ──
    evidence_bag: Any = None  # EvidenceBag

    # ── Confidence ──
    confidence: Any = None  # ConfidenceResult

    # ── Risk & Rollback ──
    risk_level: str = "medium"
    rollback_plan: RollbackPlan | None = None

    # ── Summary ──
    changed_files: int = 0
    total_duration_ms: float = 0.0

    def to_dict(self) -> dict:
        result = {
            "goal_id": self.goal_id,
            "status": self.status,
            "intent": self.intent.to_dict() if self.intent else None,
            "intent_confirmed": self.intent_confirmed,
            "architecture_delta": self.architecture_delta.to_dict() if self.architecture_delta else None,
            "risk_level": self.risk_level,
            "rollback_plan": self.rollback_plan.to_dict() if self.rollback_plan else None,
            "changed_files": self.changed_files,
            "total_duration_ms": self.total_duration_ms,
        }
        # Add trace, evidence, confidence if available
        if self.trace:
            result["trace"] = self.trace.to_dict()
        if self.evidence_bag:
            result["evidence_bag"] = self.evidence_bag.to_dict()
        if self.confidence:
            result["confidence"] = self.confidence.to_dict()
        return result
