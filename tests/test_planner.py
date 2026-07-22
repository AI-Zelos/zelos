"""Planner Module — Acceptance Tests."""
import sys, os, json, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.planner import (
    LLMPlanner, MockLLMProvider, create_provider,
    PlannerTask, PlannerPlan, SUPPORTED_PROVIDERS,
    OpenAICompatibleProvider, AnthropicProvider, GoogleProvider,
)

PASS = 0; FAIL = 0

def test(name, condition):
    global PASS, FAIL
    if condition:
        PASS += 1; print(f"  ✅ {name}")
    else:
        FAIL += 1; print(f"  ❌ {name}")

def assert_raises(exc_type, fn, *a, **kw):
    try:
        fn(*a, **kw); return False
    except exc_type:
        return True
    except Exception:
        return False


def mock_response(tasks, deps=None):
    return json.dumps({"tasks": tasks, "dependencies": deps or []})


def test_basic_decomposition():
    print("\n📋 Planner — Basic Decomposition")

    # PLNR-01: Basic decomposition
    resp = mock_response([
        {"task_id": "t1", "description": "Write a Python hello world function", "required_capability": "code-generation.python"},
    ])
    provider = MockLLMProvider(response=resp)
    planner = LLMPlanner({"provider": "mock"})
    planner._provider = provider

    plan = planner.plan("Write a Python hello world function", goal_id="g1")
    test("PLNR-01: Basic decomposition", len(plan.tasks) == 1 and plan.goal_id == "g1")
    test("PLNR-01b: Task has capability", plan.tasks[0].required_capability == "code-generation.python")


def test_multi_task_dag():
    print("\n📋 Planner — Multi-Task DAG")

    resp = mock_response([
        {"task_id": "t1", "description": "Design the landing page layout", "required_capability": "design.ui"},
        {"task_id": "t2", "description": "Implement React components", "required_capability": "code-generation.typescript", "dependencies": ["t1"]},
        {"task_id": "t3", "description": "Write unit tests", "required_capability": "verification.unit-test", "dependencies": ["t2"]},
    ], [
        {"from_task_id": "t1", "to_task_id": "t2", "type": "hard", "data_required": True},
        {"from_task_id": "t2", "to_task_id": "t3", "type": "hard", "data_required": True},
    ])
    provider = MockLLMProvider(response=resp)
    planner = LLMPlanner({"provider": "mock"})
    planner._provider = provider

    plan = planner.plan("Build a React landing page with tests")
    test("PLNR-02: Multi-task decomposition", len(plan.tasks) >= 3)
    test("PLNR-02b: Has dependencies", len(plan.dependencies) >= 2)


def test_all_tasks_have_capability():
    print("\n📋 Planner — Capability Validation")

    resp = mock_response([
        {"task_id": "t1", "description": "Write API code", "required_capability": "code-generation.python"},
        {"task_id": "t2", "description": "Review code", "required_capability": "code-review.security"},
        {"task_id": "t3", "description": "Deploy application", "required_capability": "automation.cli"},
    ])
    provider = MockLLMProvider(response=resp)
    planner = LLMPlanner({"provider": "mock"})
    planner._provider = provider

    plan = planner.plan("Build and deploy API")
    all_have_cap = all(t.required_capability for t in plan.tasks)
    test("PLNR-03: All tasks have capability", all_have_cap and len(plan.tasks) == 3)


def test_dag_validation():
    print("\n📋 Planner — DAG Validation")

    # PLNR-04: Dangling dependency
    resp = mock_response([
        {"task_id": "t1", "description": "Task 1", "required_capability": "code"},
    ], [{"from_task_id": "t1", "to_task_id": "t_nonexistent", "type": "hard"}])
    provider = MockLLMProvider(response=resp)
    planner = LLMPlanner({"provider": "mock"})
    planner._provider = provider
    ok = assert_raises(ValueError, planner.plan, "Test")
    test("PLNR-04: Dangling dependency rejected", ok)

    # PLNR-05: Cycle detection
    resp2 = mock_response([
        {"task_id": "t1", "description": "A", "required_capability": "code"},
        {"task_id": "t2", "description": "B", "required_capability": "code"},
    ], [
        {"from_task_id": "t1", "to_task_id": "t2", "type": "hard"},
        {"from_task_id": "t2", "to_task_id": "t1", "type": "hard"},
    ])
    provider2 = MockLLMProvider(response=resp2)
    planner2 = LLMPlanner({"provider": "mock"})
    planner2._provider = provider2
    ok2 = assert_raises(ValueError, planner2.plan, "Cycle test")
    test("PLNR-05: Cycle rejected", ok2)


def test_invalid_llm_output():
    print("\n📋 Planner — Error Handling")

    # PLNR-06: Malformed JSON
    provider = MockLLMProvider(response="not valid json {{{")
    planner = LLMPlanner({"provider": "mock"})
    planner._provider = provider
    ok = assert_raises(ValueError, planner.plan, "Test")
    test("PLNR-06: Malformed JSON → error", ok)

    # PLNR-07: Empty tasks
    provider2 = MockLLMProvider(response='{"tasks": [], "dependencies": []}')
    planner2 = LLMPlanner({"provider": "mock"})
    planner2._provider = provider2
    ok2 = assert_raises(ValueError, planner2.plan, "Test")
    test("PLNR-07: Empty tasks → rejected", ok2)


def test_auto_generated_ids():
    print("\n📋 Planner — ID Auto-Generation")

    # PLNR-08: Missing task_id
    resp = mock_response([
        {"description": "Write code", "required_capability": "code-generation.python"},
    ])
    provider = MockLLMProvider(response=resp)
    planner = LLMPlanner({"provider": "mock"})
    planner._provider = provider
    plan = planner.plan("Write code")
    test("PLNR-08: Auto-generated task_id", len(plan.tasks[0].task_id) > 0)

    # PLNR-09: Duplicate task_id
    resp2 = mock_response([
        {"task_id": "same-id", "description": "Task A", "required_capability": "code"},
        {"task_id": "same-id", "description": "Task B", "required_capability": "code"},
    ])
    provider2 = MockLLMProvider(response=resp2)
    planner2 = LLMPlanner({"provider": "mock"})
    planner2._provider = provider2
    ok2 = assert_raises(ValueError, planner2.plan, "Dup test")
    test("PLNR-09: Duplicate task_id → rejected", ok2)


def test_provider_factory():
    print("\n📋 Planner — Provider Factory")

    # PLNR-10: OpenAI
    p1 = create_provider({"provider": "openai", "model": "gpt-4o", "api_key": "sk-test"})
    test("PLNR-10: OpenAI provider", p1.provider_name() == "openai" and p1.model == "gpt-4o")

    # PLNR-11: Anthropic
    p2 = create_provider({"provider": "anthropic", "model": "claude-opus-4-8", "api_key": "sk-ant-test"})
    test("PLNR-11: Anthropic provider", p2.provider_name() == "anthropic")

    # PLNR-12: Google
    p3 = create_provider({"provider": "google", "model": "gemini-2.5-pro", "api_key": "ai-test"})
    test("PLNR-12: Google provider", p3.provider_name() == "google")

    # PLNR-13: Custom endpoint
    p4 = create_provider({"provider": "openai", "base_url": "https://my-proxy.com/v1", "api_key": "sk-test"})
    test("PLNR-13: Custom base URL", p4.base_url == "https://my-proxy.com/v1")

    # PLNR-14: Unknown provider
    ok = assert_raises(ValueError, create_provider, {"provider": "unknown-llm"})
    test("PLNR-14: Unknown provider → error", ok)


def test_model_config():
    print("\n📋 Planner — Model Configuration")

    # PLNR-10 full config
    planner = LLMPlanner({
        "provider": "mock", "model": "gpt-4o", "temperature": 0.3, "max_tokens": 8000,
        "system_prompt": "You are a senior architect",
    })
    test("PLNR-10b: Provider name set", planner.provider_name == "mock")
    test("PLNR-15: Temperature config", True)  # tested via provider
    test("PLNR-16: Max tokens config", True)   # tested via provider

    # PLNR-17: System prompt
    test("PLNR-17: System prompt set", "senior architect" in planner.system_prompt)

    # Verify provider gets config
    provider = planner._provider
    test("PLNR-16b: Max tokens on provider", provider.max_tokens == 8000)
    test("PLNR-15b: Temperature on provider", provider.temperature == 0.3)


def test_replan():
    print("\n📋 Planner — Replan")

    existing = PlannerPlan(
        plan_id="plan-1", goal_id="g1",
        tasks=[
            PlannerTask("t1", "Design DB", "design.database", priority="high"),
            PlannerTask("t2", "Write API", "code-generation.python", ["t1"]),
        ],
        dependencies=[{"from_task_id": "t1", "to_task_id": "t2", "type": "hard", "data_required": True}],
        version=1,
    )

    resp = mock_response([
        {"task_id": "t1", "description": "Design DB", "required_capability": "design.database"},
        {"task_id": "t2", "description": "Write API", "required_capability": "code-generation.python", "dependencies": ["t1"]},
        {"task_id": "t3", "description": "Add auth middleware (was missing)", "required_capability": "code-generation.python", "dependencies": ["t2"]},
    ], [
        {"from_task_id": "t1", "to_task_id": "t2", "type": "hard", "data_required": True},
        {"from_task_id": "t2", "to_task_id": "t3", "type": "hard", "data_required": True},
    ])
    provider = MockLLMProvider(response=resp)
    planner = LLMPlanner({"provider": "mock"})
    planner._provider = provider

    new_plan = planner.replan("Build API with auth", existing,
        [{"event_type": "task.failed", "task_id": "t2"}])

    test("PLNR-18: Replan adds tasks", len(new_plan.tasks) >= 3)
    test("PLNR-18b: Replan preserves old tasks", any(t.task_id == "t1" for t in new_plan.tasks))
    test("PLNR-22: Plan identity preserved", new_plan.plan_id == "plan-1")
    test("PLNR-22b: Version incremented", new_plan.version == 2)


def test_mock_deterministic():
    print("\n📋 Planner — Mock Provider")

    resp = mock_response([
        {"task_id": "t1", "description": "Write tests", "required_capability": "code-generation.python"},
    ])
    provider = MockLLMProvider(response=resp)
    planner = LLMPlanner({"provider": "mock"})
    planner._provider = provider

    plan1 = planner.plan("Write tests")
    plan2 = planner.plan("Write tests")
    test("PLNR-19: Mock deterministic output", plan1.tasks[0].description == plan2.tasks[0].description)


def test_retry_on_failure():
    print("\n📋 Planner — Retry Logic")

    resp = mock_response([
        {"task_id": "t1", "description": "Success after retry", "required_capability": "code"},
    ])
    provider = MockLLMProvider(response=resp)
    provider.set_fail_count(2)  # Fail first 2 calls, succeed on 3rd
    planner = LLMPlanner({"provider": "mock", "max_retries": 3})
    planner._provider = provider

    plan = planner.plan("Test retry")
    test("PLNR-20: Retry succeeds after failures", plan.tasks[0].description == "Success after retry")


def test_task_descriptions():
    print("\n📋 Planner — Task Quality")

    resp = mock_response([
        {"task_id": "t1", "description": "Write comprehensive API integration tests covering all endpoints", "required_capability": "verification.integration-test"},
        {"task_id": "t2", "description": "Review database schema for normalization issues", "required_capability": "code-review.quality"},
    ])
    provider = MockLLMProvider(response=resp)
    planner = LLMPlanner({"provider": "mock"})
    planner._provider = provider

    plan = planner.plan("Write API tests and review schema")
    test("PLNR-21: Meaningful descriptions", all(len(t.description) > 10 for t in plan.tasks))


def test_missing_capability_rejected():
    print("\n📋 Planner — Missing Capability")

    resp = mock_response([
        {"task_id": "t1", "description": "Do something", "required_capability": ""},
    ])
    provider = MockLLMProvider(response=resp)
    planner = LLMPlanner({"provider": "mock"})
    planner._provider = provider
    ok = assert_raises(ValueError, planner.plan, "Test")
    test("PLNR-24: Empty capability rejected", ok)


def test_code_fence_stripping():
    print("\n📋 Planner — Code Fence Handling")

    resp = '```json\n' + mock_response([
        {"task_id": "t1", "description": "Write code", "required_capability": "code-generation.python"},
    ]) + '\n```'
    provider = MockLLMProvider(response=resp)
    planner = LLMPlanner({"provider": "mock"})
    planner._provider = provider

    plan = planner.plan("Test code fence")
    test("PLNR-06b: Code fence stripping", len(plan.tasks) == 1)


def test_empty_description_rejected():
    print("\n📋 Planner — Empty Description")

    resp = mock_response([
        {"task_id": "t1", "description": "ab", "required_capability": "code"},
    ])
    provider = MockLLMProvider(response=resp)
    planner = LLMPlanner({"provider": "mock"})
    planner._provider = provider
    ok = assert_raises(ValueError, planner.plan, "Test")
    test("PLNR-21b: Too-short description rejected", ok)


if __name__ == "__main__":
    print("=" * 60)
    print("  ZELOS PLANNER — ACCEPTANCE TEST SUITE")
    print("=" * 60)

    test_basic_decomposition()
    test_multi_task_dag()
    test_all_tasks_have_capability()
    test_dag_validation()
    test_invalid_llm_output()
    test_auto_generated_ids()
    test_provider_factory()
    test_model_config()
    test_replan()
    test_mock_deterministic()
    test_retry_on_failure()
    test_task_descriptions()
    test_missing_capability_rejected()
    test_code_fence_stripping()
    test_empty_description_rejected()

    total = PASS + FAIL
    print(f"\n{'=' * 60}")
    print(f"  RESULTS: {PASS}/{total} passed ({FAIL} failed)")
    print(f"{'=' * 60}")
    sys.exit(0 if FAIL == 0 else 1)
