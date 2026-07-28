"""
v1.0.0 REQ-10: ChangeProposal Tests.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.change_proposal import (
    ChangeProposal, KnowledgeConstraints, StructuralConstraints,
    RiskSpec, VerificationCriteria,
)
from zelos.execution_report import IntentSpec


def test_cp_five_tuple():
    """CP = (I,K,S,R,E) five-tuple creation."""
    print("\n CP-01: Five-tuple creation")
    cp = ChangeProposal(
        goal_id="g-1",
        knowledge_constraints=KnowledgeConstraints(coding_standards=["pep8"]),
        structural_constraints=StructuralConstraints(modified_modules=["auth"]),
        risk_spec=RiskSpec(risk_level="low"),
        verification_criteria=VerificationCriteria(test_pass_rate=0.95),
    )
    t = cp.get_five_tuple()
    assert len(t) == 5
    assert t[0] is cp.intent
    assert t[1] is cp.knowledge_constraints
    assert t[2] is cp.structural_constraints
    assert t[3] is cp.risk_spec
    assert t[4] is cp.verification_criteria
    print("  ✅ get_five_tuple() returns (I,K,S,R,E)")


def test_cp_to_dict_from_dict():
    """ChangeProposal round-trip serialization."""
    print("\n CP-02: Serialization round-trip")
    cp = ChangeProposal(
        goal_id="g-2",
        knowledge_constraints=KnowledgeConstraints(
            coding_standards=["pep8", "pylint"],
            forbidden_patterns=["eval", "exec"],
            tech_stack_limits=["python>=3.10"],
        ),
        structural_constraints=StructuralConstraints(
            modified_modules=["auth"], protected_modules=["payment"],
            dependency_whitelist=["oauthlib>=3.0"],
        ),
        risk_spec=RiskSpec(risk_level="medium", security_requirements=["no-hardcoded-secrets"]),
        verification_criteria=VerificationCriteria(
            test_pass_rate=1.0, coverage_threshold_pct=80.0,
            required_verifiers=["schema"], security_scan_required=True,
        ),
    )
    d = cp.to_dict()
    restored = ChangeProposal.from_dict(d)
    assert restored.goal_id == "g-2"
    assert restored.knowledge_constraints.coding_standards == ["pep8", "pylint"]
    assert "eval" in restored.knowledge_constraints.forbidden_patterns
    assert restored.structural_constraints.protected_modules == ["payment"]
    assert restored.risk_spec.risk_level == "medium"
    assert restored.verification_criteria.coverage_threshold_pct == 80.0
    print("  ✅ CP round-trip: all 5 dimensions preserved")


def test_cp_from_intent():
    """from_intent() factory builds CP with sensible defaults."""
    print("\n CP-03: from_intent() factory")
    intent = IntentSpec(
        description="Add OAuth2", success_criteria=["Google login works"],
        constraints=["Don't break password login"], scope="single_module",
    )
    cp = ChangeProposal.from_intent("g-3", intent)
    assert cp.goal_id == "g-3"
    assert cp.intent is intent
    assert cp.risk_spec.risk_level == "low"  # single_module → low
    assert cp.verification_criteria.test_pass_rate == 1.0
    assert cp.verification_criteria.coverage_threshold_pct == 80.0
    print("  ✅ from_intent: risk=low (single_module), coverage=80%")


def test_cp_from_intent_multi_module():
    """from_intent with multi_module scope → medium risk."""
    print("\n CP-04: from_intent multi_module → medium risk")
    intent = IntentSpec(description="Big refactor", scope="system_wide")
    cp = ChangeProposal.from_intent("g-4", intent)
    assert cp.risk_spec.risk_level == "high"  # system_wide → high risk
    print("  ✅ system_wide → risk=high")


def test_cp_sub_dimensions_to_dict():
    """All sub-dimensions serialize correctly."""
    print("\n CP-05: Sub-dimension serialization")
    kc = KnowledgeConstraints(coding_standards=["pep8"], forbidden_patterns=["eval"])
    d = kc.to_dict()
    assert d["coding_standards"] == ["pep8"]
    restored = KnowledgeConstraints.from_dict(d)
    assert restored.forbidden_patterns == ["eval"]

    sc = StructuralConstraints(api_contracts=[{"endpoint": "GET /users", "schema": {}}])
    d2 = sc.to_dict()
    assert len(d2["api_contracts"]) == 1

    rs = RiskSpec(performance_baseline={"min_tps": 500})
    d3 = rs.to_dict()
    assert d3["performance_baseline"]["min_tps"] == 500

    vc = VerificationCriteria(benchmark_regression_limit_pct=5.0)
    d4 = vc.to_dict()
    assert d4["benchmark_regression_limit_pct"] == 5.0

    print("  ✅ All 4 sub-dimensions serialize correctly")


if __name__ == "__main__":
    print("=" * 60)
    print("  ZELOS v1.0.0 — REQ-10 CHANGEPROPOSAL TESTS")
    print("=" * 60)
    test_cp_five_tuple()
    test_cp_to_dict_from_dict()
    test_cp_from_intent()
    test_cp_from_intent_multi_module()
    test_cp_sub_dimensions_to_dict()
    print(f"\n{'=' * 60}")
    print("  RESULTS: All REQ-10 tests passed ✅")
    print(f"{'=' * 60}")
