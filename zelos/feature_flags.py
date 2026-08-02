"""
Feature Flags — Controls which Zelos components are loaded at Runtime init.

v1.3.0: Enables phased verification from core scheduling loop outward.
Feature code is never deleted; flags control loading order.
"""

from dataclasses import dataclass


@dataclass
class FeatureFlags:
    """Controls which Zelos components are loaded at Runtime init."""

    # Stage A — Core scheduling loop (default: ON)
    planner: bool = True
    scheduler: bool = True
    execution_engine: bool = True
    verifier: bool = True
    capability_registry: bool = True
    task_graph_engine: bool = True
    event_bus: bool = True

    # Stage B — Audit chain (default: OFF)
    event_sourcing: bool = False
    execution_trace: bool = False

    # Stage C — Confidence & Evidence (default: OFF)
    evidence_collection: bool = False
    confidence_scoring: bool = False
    memory: bool = False

    # Stage D — Governance (default: OFF)
    policy_gate: bool = False
    cp_governance: bool = False
    car: bool = False
    diagnosis_engine: bool = False

    # Stage E — Full stack (default: OFF)
    credential_management: bool = False
    failure_classifier: bool = False
    repair_orchestrator: bool = False
    patch_ranker: bool = False
    arbiter: bool = False
    contest_dispatch: bool = False

    # MPC (v1.3.0, default: ON)
    mpc_replan: bool = True

    @classmethod
    def stage_a(cls) -> "FeatureFlags":
        """Minimal core scheduling loop only (7 components)."""
        return cls()

    @classmethod
    def stage_b(cls) -> "FeatureFlags":
        """Stage A + audit chain (event sourcing + execution trace)."""
        f = cls.stage_a()
        f.event_sourcing = True
        f.execution_trace = True
        return f

    @classmethod
    def stage_c(cls) -> "FeatureFlags":
        """Stage B + confidence scoring & evidence collection."""
        f = cls.stage_b()
        f.evidence_collection = True
        f.confidence_scoring = True
        f.memory = True
        return f

    @classmethod
    def stage_d(cls) -> "FeatureFlags":
        """Stage C + governance (policy gate + CP + CAR + diagnosis)."""
        f = cls.stage_c()
        f.policy_gate = True
        f.cp_governance = True
        f.car = True
        f.diagnosis_engine = True
        return f

    @classmethod
    def stage_e(cls) -> "FeatureFlags":
        """All 19 components enabled."""
        f = cls.stage_d()
        f.credential_management = True
        f.failure_classifier = True
        f.repair_orchestrator = True
        f.patch_ranker = True
        f.arbiter = True
        f.contest_dispatch = True
        return f
