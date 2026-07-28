"""
v1.0.0 REQ-11/12/14: Constraint Engine + Injection + Merge Tests.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.change_proposal import (
    ChangeProposal, KnowledgeConstraints, StructuralConstraints, RiskSpec, VerificationCriteria,
)
from zelos.constraint_engine import ConstraintEngine, ExecutableConstraints
from zelos.merge_executor import MergeExecutor, MergeResult
from zelos.runtime import ZelosRuntime
from zelos.task_graph import Task, TaskStatus


def make_cap():
    return type("Cap", (), {"name": "code", "version": "1.0", "description": "",
                             "input_schema": {}, "output_schema": {}, "tags": []})()


def test_constraint_engine_coding_rules():
    """ConstraintEngine produces coding rules from K-dimension."""
    print("\n🔧 REQ-11.1: ConstraintEngine — coding rules")
    cp = ChangeProposal(
        goal_id="g-1",
        knowledge_constraints=KnowledgeConstraints(
            coding_standards=["pep8", "pylint"],
            forbidden_patterns=["eval", "exec"],
            tech_stack_limits=["python>=3.10"],
        ),
        structural_constraints=StructuralConstraints(protected_modules=["payment"]),
        risk_spec=RiskSpec(risk_level="medium", security_requirements=["no-hardcoded-secrets"]),
        verification_criteria=VerificationCriteria(test_pass_rate=1.0),
    )
    engine = ConstraintEngine()
    ec = engine.apply(cp)

    assert isinstance(ec, ExecutableConstraints)
    assert "pep8" in ec.coding_rules
    assert any("FORBIDDEN: eval" in r for r in ec.coding_rules)
    assert any("TECH_STACK: python" in r for r in ec.coding_rules)
    assert ec.architecture_boundaries["protected_modules"] == ["payment"]
    assert ec.risk_thresholds["risk_level"] == "medium"
    assert ec.verification_requirements["test_pass_rate"] == 1.0
    print("  ✅ All 4 dimensions correctly translated to constraints")


def test_constraint_to_context_dict():
    """ExecutableConstraints.to_context_dict() format."""
    print("\n🔧 REQ-11.2: to_context_dict() format")
    cp = ChangeProposal(goal_id="g-2")
    engine = ConstraintEngine()
    ec = engine.apply(cp)
    d = ec.to_context_dict()
    assert "constraints" in d
    assert "coding_rules" in d["constraints"]
    assert "architecture_boundaries" in d["constraints"]
    assert "risk_thresholds" in d["constraints"]
    assert "verification_requirements" in d["constraints"]
    print("  ✅ to_context_dict has all 4 constraint categories")


def test_task_constraints_field():
    """Task.constraints field works."""
    print("\n📋 REQ-12.1: Task.constraints field")
    t = Task(task_id="t1", plan_id="p1", description="test", required_capability="code",
             constraints={"coding_rules": ["pep8"]})
    assert t.constraints is not None
    assert t.constraints["coding_rules"] == ["pep8"]
    d = t.to_dict()
    assert d["constraints"] == {"coding_rules": ["pep8"]}
    restored = Task.from_dict(d)
    assert restored.constraints == {"coding_rules": ["pep8"]}
    print("  ✅ Task.constraints serialized correctly")


def test_runtime_constraint_injection():
    """Runtime injects constraints on dispatch."""
    print("\n📋 REQ-12.2: Runtime constraint injection")
    rt = ZelosRuntime()
    rt.add_agent("ConstraintAgent", "test:Agent", [make_cap()])
    rt.start()

    from zelos.execution_report import IntentSpec
    intent = IntentSpec(description="Test", scope="single_module")
    result = rt.submit_goal("Constraint injection test", intent=intent)

    # Verify CP was built
    cp = rt._active_cps.get(result["goal_id"])
    assert cp is not None
    assert cp.goal_id == result["goal_id"]

    rt.shutdown()
    print("  ✅ CP auto-built from IntentSpec in submit_goal")


def test_merge_executor_event_sourcing():
    """MergeExecutor with event_sourcing_apply."""
    print("\n🔀 REQ-14.1: MergeExecutor event_sourcing_apply")
    me = MergeExecutor(strategy="event_sourcing_apply")
    r = me.execute("g-test")
    assert isinstance(r, MergeResult)
    assert r.success is True
    assert r.strategy == "event_sourcing_apply"
    assert r.duration_ms >= 0
    print(f"  ✅ event_sourcing_apply: success={r.success}, {r.duration_ms:.0f}ms")


def test_merge_executor_git_no_git():
    """MergeExecutor git strategy handles missing git gracefully."""
    print("\n🔀 REQ-14.2: MergeExecutor git_merge (no git)")
    me = MergeExecutor(strategy="git_merge")
    r = me.execute("g-test")
    # Git merge may fail if no remote/branch configured — that's OK
    # The key is: it doesn't crash and returns a proper MergeResult
    assert isinstance(r, MergeResult)
    print(f"  ✅ git_merge: success={r.success}, message={r.message[:50]}...")


def test_merge_executor_rollback():
    """MergeExecutor rollback."""
    print("\n🔀 REQ-14.3: MergeExecutor rollback")
    me = MergeExecutor()
    r = me.rollback("g-test", snapshot_position=42)
    assert r.success is True
    assert r.rollback_applied is True
    print(f"  ✅ rollback: {r.message}")


if __name__ == "__main__":
    print("=" * 60)
    print("  ZELOS v1.0.0 — REQ-11/12/14 TESTS")
    print("=" * 60)
    test_constraint_engine_coding_rules()
    test_constraint_to_context_dict()
    test_task_constraints_field()
    test_runtime_constraint_injection()
    test_merge_executor_event_sourcing()
    test_merge_executor_git_no_git()
    test_merge_executor_rollback()
    print(f"\n{'=' * 60}")
    print("  RESULTS: All REQ-11/12/14 tests passed ✅")
    print(f"{'=' * 60}")
