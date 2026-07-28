"""
v0.9.0 REQ-03: Intent Specification Tests.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.runtime import ZelosRuntime, IntentSpec


def make_cap():
    return type("Cap", (), {"name": "code", "version": "1.0", "description": "",
                             "input_schema": {}, "output_schema": {}, "tags": []})()


def test_intent_spec_submit():
    """submit_goal with IntentSpec works."""
    print("\n📝 REQ-03.1: IntentSpec — submit with intent")

    rt = ZelosRuntime()
    rt.add_agent("IntentAgent", "test:Agent", [make_cap()])
    rt.start()

    intent = IntentSpec(
        description="Implement OAuth2 login",
        success_criteria=["Users can login with Google", "Token expires in 24h"],
        constraints=["Must not break existing password login", "Use standard OAuth2 library"],
    )
    result = rt.submit_goal("OAuth2 login", intent=intent)
    assert result["status"] in ("accepted", "planned")
    rt.shutdown()
    print(f"  ✅ IntentSpec submitted: status={result['status']}")


def test_intent_spec_backward_compat():
    """submit_goal without IntentSpec still works (backward compat)."""
    print("\n📝 REQ-03.2: IntentSpec — backward compat")

    rt = ZelosRuntime()
    rt.add_agent("CompatAgent", "test:Agent", [make_cap()])
    rt.start()

    result = rt.submit_goal("Just a description")
    assert result["status"] in ("accepted", "planned")
    assert result["goal_id"]
    rt.shutdown()
    print(f"  ✅ Backward compat: no IntentSpec works fine")


def test_intent_spec_to_dict_roundtrip():
    """IntentSpec serialization round-trip."""
    print("\n📝 REQ-03.3: IntentSpec — serialization")

    intent = IntentSpec(
        description="Test intent",
        success_criteria=["Criterion 1", "Criterion 2"],
        constraints=["Constraint A"],
        scope="single_module",
    )
    d = intent.to_dict()
    restored = IntentSpec.from_dict(d)
    assert restored.description == intent.description
    assert restored.success_criteria == intent.success_criteria
    assert restored.constraints == intent.constraints
    assert restored.scope == "single_module"
    print("  ✅ IntentSpec round-trip OK")


if __name__ == "__main__":
    print("=" * 60)
    print("  ZELOS v0.9.0 — REQ-03 INTENT SPEC TESTS")
    print("=" * 60)
    test_intent_spec_submit()
    test_intent_spec_backward_compat()
    test_intent_spec_to_dict_roundtrip()
    print(f"\n{'=' * 60}")
    print("  RESULTS: All REQ-03 tests passed ✅")
    print(f"{'=' * 60}")
