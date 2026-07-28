"""
v0.9.0 REQ-08: Policy Gate v2 Tests.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.policy_gate import EvidenceBasedPolicyGate, GateDecision
from zelos.evidence import Evidence, EvidenceBag
from zelos.confidence import ConfidenceResult


def test_policy_gate_auto_approve():
    """High confidence + low risk → auto_approve."""
    print("\n🚦 REQ-08.1: PolicyGate — auto_approve")

    gate = EvidenceBasedPolicyGate()
    decision = gate._evaluate_rules(confidence_score=0.97, risk_level="low", all_pass=True)
    assert decision.action == "auto_approve"
    print(f"  ✅ confidence=0.97, risk=low → {decision.action}")


def test_policy_gate_auto_reject():
    """Low confidence → auto_reject."""
    print("\n🚦 REQ-08.2: PolicyGate — auto_reject")

    gate = EvidenceBasedPolicyGate()
    decision = gate._evaluate_rules(confidence_score=0.30, risk_level="medium", all_pass=True)
    assert decision.action == "auto_reject", f"Expected auto_reject, got {decision.action}"
    print(f"  ✅ confidence=0.30 → {decision.action}")


def test_policy_gate_require_human():
    """Medium confidence or high risk → require_human."""
    print("\n🚦 REQ-08.3: PolicyGate — require_human")

    gate = EvidenceBasedPolicyGate()

    d1 = gate._evaluate_rules(confidence_score=0.75, risk_level="medium", all_pass=True)
    assert d1.action == "require_human"

    d2 = gate._evaluate_rules(confidence_score=0.90, risk_level="critical", all_pass=True)
    assert d2.action == "require_human"
    assert d2.required_approvers

    print(f"  ✅ medium confidence → {d1.action}, critical risk → {d2.action}")


def test_policy_gate_default():
    """Default rule: require_human."""
    print("\n🚦 REQ-08.4: PolicyGate — default rule")

    gate = EvidenceBasedPolicyGate()
    decision = gate._evaluate_rules(confidence_score=0.50, risk_level="low", all_pass=True)
    assert decision.action == "require_human"
    print(f"  ✅ default → {decision.action}")


def test_policy_gate_failed_evidence():
    """Evidence failure → require_human regardless of confidence."""
    print("\n🚦 REQ-08.5: PolicyGate — failed evidence")

    gate = EvidenceBasedPolicyGate()
    decision = gate._evaluate_rules(confidence_score=0.95, risk_level="low", all_pass=False)
    assert decision.action == "require_human"
    print(f"  ✅ evidence failed → {decision.action}")


if __name__ == "__main__":
    print("=" * 60)
    print("  ZELOS v0.9.0 — REQ-08 POLICY GATE V2 TESTS")
    print("=" * 60)
    test_policy_gate_auto_approve()
    test_policy_gate_auto_reject()
    test_policy_gate_require_human()
    test_policy_gate_default()
    test_policy_gate_failed_evidence()
    print(f"\n{'=' * 60}")
    print("  RESULTS: All REQ-08 tests passed ✅")
    print(f"{'=' * 60}")
