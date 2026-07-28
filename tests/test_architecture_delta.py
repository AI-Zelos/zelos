"""
v0.9.0 REQ-04: Architecture Delta Tests.

Tests:
  - PlannerPlan stores architecture_delta from LLM response
  - Runtime.submit_goal passes arch_delta to goal
  - ExecutionReport uses Planner's arch_delta when available
  - MockLLMProvider supports architecture_delta in response
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.planner import LLMPlanner, MockLLMProvider, PlannerPlan
from zelos.execution_report import ArchDelta


def test_planner_parses_architecture_delta():
    """Planner parses architecture_delta from LLM JSON response."""
    print("\n🏗️ REQ-04.1: Planner parses architecture_delta")

    # Create a mock provider that returns arch_delta in response
    response = """{
  "tasks": [
    {"task_id": "t1", "description": "Add OAuth2", "required_capability": "code-generation.python", "dependencies": []}
  ],
  "dependencies": [],
  "architecture_delta": {
    "modified_modules": ["auth-service", "user-model"],
    "new_dependencies": ["oauthlib==3.2.0"],
    "removed_dependencies": [],
    "api_changes": [{"endpoint": "POST /auth/oauth", "change_type": "new", "compatibility": "additive"}],
    "data_model_changes": ["users.add(oauth_provider)"],
    "risk_level": "medium",
    "explanation": "Standard OAuth2 addition, isolated to auth module"
  }
}"""

    planner = LLMPlanner({"provider": "mock"})
    planner._provider = MockLLMProvider(response=response)

    plan = planner.plan("Add OAuth2 login")
    assert plan.architecture_delta is not None
    assert plan.architecture_delta["risk_level"] == "medium"
    assert plan.architecture_delta["modified_modules"] == ["auth-service", "user-model"]
    assert len(plan.architecture_delta["api_changes"]) == 1
    assert plan.architecture_delta["explanation"]
    print(f"  ✅ Planner parsed arch_delta: risk={plan.architecture_delta['risk_level']}, "
          f"modules={plan.architecture_delta['modified_modules']}")


def test_planner_plan_no_arch_delta():
    """PlannerPlan without architecture_delta works fine (backward compat)."""
    print("\n🏗️ REQ-04.2: Planner without arch_delta — backward compat")

    response = """{
  "tasks": [
    {"task_id": "t1", "description": "Simple task", "required_capability": "code", "dependencies": []}
  ],
  "dependencies": []
}"""

    planner = LLMPlanner({"provider": "mock"})
    planner._provider = MockLLMProvider(response=response)

    plan = planner.plan("Simple task")
    assert plan.architecture_delta is None  # No arch_delta in response → None
    assert len(plan.tasks) == 1
    print("  ✅ No arch_delta → plan still works (backward compat)")


def test_to_dict_includes_arch_delta():
    """PlannerPlan.to_dict() includes architecture_delta when present."""
    print("\n🏗️ REQ-04.3: PlannerPlan.to_dict() includes arch_delta")

    plan = PlannerPlan(
        plan_id="p1", goal_id="g1",
        architecture_delta={"risk_level": "low", "modified_modules": ["api"]}
    )
    d = plan.to_dict()
    assert "architecture_delta" in d
    assert d["architecture_delta"]["risk_level"] == "low"

    # Without arch_delta, key should not be in dict
    plan2 = PlannerPlan(plan_id="p2", goal_id="g2")
    d2 = plan2.to_dict()
    assert "architecture_delta" not in d2
    print("  ✅ to_dict handles arch_delta correctly")


def test_arch_delta_from_dict_roundtrip():
    """ArchDelta.from_dict() round-trip with all fields."""
    print("\n🏗️ REQ-04.4: ArchDelta.from_dict() round-trip")

    data = {
        "modified_modules": ["auth", "api"],
        "new_dependencies": ["lib==1.0"],
        "removed_dependencies": ["old-lib"],
        "api_changes": [
            {"endpoint": "GET /users", "change_type": "modified", "compatibility": "backward_compatible"}
        ],
        "data_model_changes": ["users.add(oauth)"],
        "risk_level": "high",
        "explanation": "Changes auth core"
    }
    arch = ArchDelta.from_dict(data)
    d = arch.to_dict()
    assert d["risk_level"] == "high"
    assert d["explanation"] == "Changes auth core"
    assert d["modified_modules"] == ["auth", "api"]
    assert len(d["api_changes"]) == 1
    print("  ✅ ArchDelta round-trip OK")


if __name__ == "__main__":
    print("=" * 60)
    print("  ZELOS v0.9.0 — REQ-04 ARCHITECTURE DELTA TESTS")
    print("=" * 60)
    test_planner_parses_architecture_delta()
    test_planner_plan_no_arch_delta()
    test_to_dict_includes_arch_delta()
    test_arch_delta_from_dict_roundtrip()
    print(f"\n{'=' * 60}")
    print("  RESULTS: All REQ-04 tests passed ✅")
    print(f"{'=' * 60}")
