"""
v0.8.0 REQ-01: Goal State Serialization & Recovery Tests.

Tests:
  - Task.to_dict() / Task.from_dict() round-trip
  - GoalState.to_dict() / GoalState.from_dict() round-trip
  - Runtime persistence: save before shutdown, restore after restart
  - Single Task recovery
  - DAG multi-task recovery
  - Retry-in-progress recovery
"""

import os
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.goal_state import GoalState
from zelos.runtime import ZelosRuntime
from zelos.storage import InMemoryStorageBackend
from zelos.task_graph import Task, TaskStatus


# ═══════════════════ REQ-01.1: Task serialization round-trip ═══════════════════

def test_task_to_dict_from_dict_round_trip():
    """Task.to_dict() and Task.from_dict() produce identical Task."""
    print("\n📦 REQ-01.1: Task serialization round-trip")

    task = Task(
        task_id="task-001",
        plan_id="plan-abc",
        description="Deploy to production",
        required_capability="deployment.k8s",
        status=TaskStatus.STARTED,
        dependencies=["task-000"],
        dependents=["task-002"],
        attempt=2,
        max_retries=5,
        backoff_base_ms=2000,
        timeout_ms=60000,
        assigned_agent_id="agent-xyz",
        priority="high",
        fallback_capability="deployment.docker",
        preferred_agent_id="agent-xyz",
        excluded_agent_ids=["agent-bad"],
        min_success_rate=0.8,
        required_tags=["production", "k8s"],
        max_cost_per_call=0.50,
        max_latency_ms=10000,
        non_retryable_errors=["ValidationError", "AuthError"],
        created_at=1000000.0,
        updated_at=1000001.0,
    )

    d = task.to_dict()
    restored = Task.from_dict(d)

    assert restored.task_id == task.task_id
    assert restored.plan_id == task.plan_id
    assert restored.description == task.description
    assert restored.required_capability == task.required_capability
    assert restored.status == task.status
    assert restored.dependencies == task.dependencies
    assert restored.attempt == task.attempt
    assert restored.max_retries == task.max_retries
    assert restored.backoff_base_ms == task.backoff_base_ms
    assert restored.timeout_ms == task.timeout_ms
    assert restored.assigned_agent_id == task.assigned_agent_id
    assert restored.priority == task.priority
    assert restored.fallback_capability == task.fallback_capability
    assert restored.preferred_agent_id == task.preferred_agent_id
    assert restored.excluded_agent_ids == task.excluded_agent_ids
    assert restored.min_success_rate == task.min_success_rate
    assert restored.required_tags == task.required_tags
    assert restored.max_cost_per_call == task.max_cost_per_call
    assert restored.max_latency_ms == task.max_latency_ms
    assert restored.non_retryable_errors == task.non_retryable_errors
    assert restored.created_at == task.created_at
    assert restored.updated_at == task.updated_at
    print("  ✅ Task.to_dict() ↔ Task.from_dict() round-trip identical")


def test_task_serialization_minimal_fields():
    """Task with only required fields round-trips correctly."""
    print("\n📦 REQ-01.1b: Task serialization — minimal fields")

    task = Task(
        task_id="minimal-task",
        plan_id="plan-min",
        description="Simple task",
        required_capability="echo",
    )

    d = task.to_dict()
    restored = Task.from_dict(d)

    assert restored.task_id == "minimal-task"
    assert restored.status == TaskStatus.CREATED
    assert restored.attempt == 0
    assert restored.max_retries == 3
    assert restored.non_retryable_errors == []
    assert restored.dependencies == []
    print("  ✅ Minimal Task round-trip OK")


# ═══════════════════ REQ-01.2: GoalState serialization round-trip ═══════════════════

def test_goal_state_to_dict_from_dict_round_trip():
    """GoalState.to_dict() and GoalState.from_dict() produce identical GoalState."""
    print("\n📦 REQ-01.2: GoalState serialization round-trip")

    tasks = [
        Task(task_id="t1", plan_id="plan-1", description="Task 1", required_capability="code",
             status=TaskStatus.COMPLETED, attempt=1),
        Task(task_id="t2", plan_id="plan-1", description="Task 2", required_capability="review",
             status=TaskStatus.STARTED, dependencies=["t1"], attempt=0),
    ]

    gs = GoalState(
        goal_id="goal-123",
        status="executing",
        description="Build and deploy API",
        tasks=tasks,
        event_position=42,
        plan_id="plan-1",
        budget=100.0,
        deadline="2026-12-31",
        priority="high",
        tenant_id="tenant-a",
        created_at=1000000.0,
        updated_at=1000001.0,
        completed_at=None,
    )

    d = gs.to_dict()
    restored = GoalState.from_dict(d)

    assert restored.goal_id == gs.goal_id
    assert restored.status == gs.status
    assert restored.description == gs.description
    assert restored.event_position == gs.event_position
    assert restored.plan_id == gs.plan_id
    assert restored.budget == gs.budget
    assert restored.deadline == gs.deadline
    assert restored.priority == gs.priority
    assert restored.tenant_id == gs.tenant_id
    assert restored.created_at == gs.created_at
    assert restored.updated_at == gs.updated_at
    assert restored.completed_at == gs.completed_at
    assert len(restored.tasks) == 2
    assert restored.tasks[0].task_id == "t1"
    assert restored.tasks[0].status == TaskStatus.COMPLETED
    assert restored.tasks[1].task_id == "t2"
    assert restored.tasks[1].status == TaskStatus.STARTED
    print("  ✅ GoalState.to_dict() ↔ GoalState.from_dict() round-trip identical")


def test_goal_state_empty_tasks():
    """GoalState with no tasks round-trips correctly."""
    print("\n📦 REQ-01.2b: GoalState — empty tasks")

    gs = GoalState(
        goal_id="g-empty",
        status="accepted",
        description="Empty goal",
        tasks=[],
        event_position=0,
    )

    d = gs.to_dict()
    restored = GoalState.from_dict(d)

    assert restored.goal_id == "g-empty"
    assert restored.tasks == []
    assert restored.event_position == 0
    print("  ✅ Empty GoalState round-trip OK")


# ═══════════════════ REQ-01.3: Runtime persistence & recovery ═══════════════════

def test_runtime_persistence_single_task():
    """Runtime saves GoalState → shutdown → new Runtime recovers → state matches."""
    print("\n🔄 REQ-01.3: Runtime persistence — single task recovery")

    storage = InMemoryStorageBackend()
    storage.connect()

    # Create and start Runtime 1
    rt1 = ZelosRuntime({"storage": {"type": "memory"}})
    rt1._storage_backend = storage
    rt1.add_agent(
        "RecoveryAgent",
        "test:Agent",
        [
            type("Cap", (), {
                "name": "code-generation.python", "version": "1.0",
                "description": "", "input_schema": {}, "output_schema": {}, "tags": [],
            })(),
        ],
    )
    rt1.start()

    # Submit a goal
    result = rt1.submit_goal("Recovery test goal")
    goal_id = result["goal_id"]

    # Persist goal state to storage
    gs = rt1._build_goal_state(goal_id)
    storage.set_state(f"goal:{goal_id}", gs.to_dict())

    # Verify persistence
    saved = storage.get_state(f"goal:{goal_id}")
    assert saved is not None
    assert saved["goal_id"] == goal_id
    assert saved["status"] in ("accepted", "planned")

    rt1.shutdown()

    # Simulate restart: create new Runtime, recover from storage
    rt2 = ZelosRuntime({"storage": {"type": "memory"}})
    rt2._storage_backend = storage
    recovered = rt2._recover_goal_from_storage(goal_id)
    assert recovered is not None, "Goal should be recovered from storage"
    assert recovered.goal_id == goal_id
    assert recovered.status in ("accepted", "planned")

    rt2.shutdown()
    storage.disconnect()
    print(f"  ✅ Single task persisted and recovered (goal={goal_id[:8]}...)")


def test_runtime_persistence_dag_multi_task():
    """DAG with multiple tasks: persist → recover → all tasks present."""
    print("\n🔄 REQ-01.4: Runtime persistence — DAG multi-task recovery")

    storage = InMemoryStorageBackend()
    storage.connect()

    rt1 = ZelosRuntime({"storage": {"type": "memory"}})
    rt1._storage_backend = storage
    rt1.add_agent(
        "DAGAgent",
        "test:Agent",
        [
            type("Cap", (), {
                "name": "code-generation.python", "version": "1.0",
                "description": "", "input_schema": {}, "output_schema": {}, "tags": [],
            })(),
        ],
    )
    rt1.start()

    result = rt1.submit_goal("DAG recovery test")
    goal_id = result["goal_id"]

    # The planner creates tasks like "t1", "t2", etc.
    # Get the existing task IDs to use as dependencies
    plan_id = rt1._goals[goal_id]["plan_id"]
    existing_tasks = [t for t in rt1._task_graph.list_tasks() if t.plan_id == plan_id]
    first_task_id = existing_tasks[0].task_id if existing_tasks else "t1"

    t2 = Task(task_id="dag-t2", plan_id=plan_id, description="Task 2",
              required_capability="code-generation.python", dependencies=[first_task_id])
    t3 = Task(task_id="dag-t3", plan_id=plan_id, description="Task 3",
              required_capability="code-generation.python", dependencies=[first_task_id])
    rt1._task_graph.add_task(t2)
    rt1._task_graph.add_task(t3)

    # Persist
    gs = rt1._build_goal_state(goal_id)
    storage.set_state(f"goal:{goal_id}", gs.to_dict())

    saved = storage.get_state(f"goal:{goal_id}")
    assert saved is not None
    restored_gs = GoalState.from_dict(saved)
    assert len(restored_gs.tasks) == 3, f"Expected 3 tasks, got {len(restored_gs.tasks)}"

    rt1.shutdown()

    # Recover
    rt2 = ZelosRuntime({"storage": {"type": "memory"}})
    rt2._storage_backend = storage
    recovered = rt2._recover_goal_from_storage(goal_id)
    assert recovered is not None
    assert len(recovered.tasks) == 3
    task_ids = {t.task_id for t in recovered.tasks}
    assert first_task_id in task_ids
    assert "dag-t2" in task_ids
    assert "dag-t3" in task_ids

    rt2.shutdown()
    storage.disconnect()
    print(f"  ✅ DAG multi-task persisted and recovered (3 tasks)")


def test_runtime_persistence_retry_in_progress():
    """Goal with a retrying task: persist → recover → retry state preserved."""
    print("\n🔄 REQ-01.5: Runtime persistence — retry in progress")

    storage = InMemoryStorageBackend()
    storage.connect()

    rt1 = ZelosRuntime({"storage": {"type": "memory"}})
    rt1._storage_backend = storage
    rt1.add_agent(
        "RetryAgent",
        "test:Agent",
        [
            type("Cap", (), {
                "name": "code-generation.python", "version": "1.0",
                "description": "", "input_schema": {}, "output_schema": {}, "tags": [],
            })(),
        ],
    )
    rt1.start()

    result = rt1.submit_goal("Retry recovery test")
    goal_id = result["goal_id"]

    # Simulate a task that has been retried
    tasks = rt1._task_graph.list_tasks()
    for t in tasks:
        if t.plan_id == rt1._goals[goal_id]["plan_id"]:
            t.attempt = 2
            t.status = TaskStatus.READY  # Ready for retry
            t.updated_at = time.time()

    # Persist
    gs = rt1._build_goal_state(goal_id)
    storage.set_state(f"goal:{goal_id}", gs.to_dict())

    rt1.shutdown()

    # Recover
    rt2 = ZelosRuntime({"storage": {"type": "memory"}})
    rt2._storage_backend = storage
    recovered = rt2._recover_goal_from_storage(goal_id)
    assert recovered is not None
    retried_task = [t for t in recovered.tasks if t.attempt > 0]
    assert len(retried_task) > 0, "Should find task with retry attempts"
    assert retried_task[0].attempt == 2

    rt2.shutdown()
    storage.disconnect()
    print(f"  ✅ Retry state preserved across restart (attempt={retried_task[0].attempt})")


def test_runtime_full_recovery_on_startup():
    """Runtime.start() automatically recovers all incomplete goals from storage."""
    print("\n🔄 REQ-01.6: Full recovery on startup")

    storage = InMemoryStorageBackend()
    storage.connect()

    # Pre-populate storage with two goals
    goal_a_id = f"goal-{uuid.uuid4().hex[:8]}"
    goal_b_id = f"goal-{uuid.uuid4().hex[:8]}"

    gs_a = GoalState(
        goal_id=goal_a_id, status="planned", description="Goal A",
        plan_id="plan-a", tasks=[
            Task(task_id="a-t1", plan_id="plan-a", description="A1",
                 required_capability="code", status=TaskStatus.READY),
        ], event_position=5,
    )
    gs_b = GoalState(
        goal_id=goal_b_id, status="executing", description="Goal B",
        plan_id="plan-b", tasks=[
            Task(task_id="b-t1", plan_id="plan-b", description="B1",
                 required_capability="code", status=TaskStatus.COMPLETED),
            Task(task_id="b-t2", plan_id="plan-b", description="B2",
                 required_capability="code", status=TaskStatus.STARTED,
                 dependencies=["b-t1"]),
        ], event_position=10,
    )

    storage.set_state(f"goal:{goal_a_id}", gs_a.to_dict())
    storage.set_state(f"goal:{goal_b_id}", gs_b.to_dict())

    # Also save a completed goal (should NOT be recovered)
    completed_gs = GoalState(
        goal_id="goal-completed", status="completed", description="Done",
        plan_id="plan-c", tasks=[
            Task(task_id="c-t1", plan_id="plan-c", description="C1",
                 required_capability="code", status=TaskStatus.COMPLETED),
        ], event_position=3, completed_at=time.time(),
    )
    storage.set_state("goal:goal-completed", completed_gs.to_dict())

    # Create runtime and trigger recovery
    rt = ZelosRuntime({"storage": {"type": "memory"}})
    rt._storage_backend = storage
    rt.add_agent(
        "RecoveryAgent2",
        "test:Agent",
        [
            type("Cap", (), {
                "name": "code", "version": "1.0",
                "description": "", "input_schema": {}, "output_schema": {}, "tags": [],
            })(),
        ],
    )
    rt.start()

    # Recovery should have loaded the two incomplete goals
    recovered_ids = set(rt._goals.keys())
    assert goal_a_id in recovered_ids, f"Goal A ({goal_a_id}) should be recovered"
    assert goal_b_id in recovered_ids, f"Goal B ({goal_b_id}) should be recovered"
    assert "goal-completed" not in recovered_ids, "Completed goal should NOT be recovered"

    # Verify task states
    assert rt._goals[goal_a_id]["status"] == "planned"
    assert rt._goals[goal_b_id]["status"] == "executing"
    assert rt._goals[goal_b_id]["plan_id"] == "plan-b"

    # Verify tasks were restored in task_graph
    all_tasks = rt._task_graph.list_tasks()
    task_ids = {t.task_id for t in all_tasks}
    assert "a-t1" in task_ids
    assert "b-t1" in task_ids
    assert "b-t2" in task_ids

    rt.shutdown()
    storage.disconnect()
    print(f"  ✅ Full recovery: {len(recovered_ids)} goals recovered, completed goals skipped")


if __name__ == "__main__":
    print("=" * 60)
    print("  ZELOS v0.8.0 — REQ-01 RECOVERY TESTS")
    print("=" * 60)
    test_task_to_dict_from_dict_round_trip()
    test_task_serialization_minimal_fields()
    test_goal_state_to_dict_from_dict_round_trip()
    test_goal_state_empty_tasks()
    test_runtime_persistence_single_task()
    test_runtime_persistence_dag_multi_task()
    test_runtime_persistence_retry_in_progress()
    test_runtime_full_recovery_on_startup()
    print(f"\n{'=' * 60}")
    print("  RESULTS: All REQ-01 recovery tests passed ✅")
    print(f"{'=' * 60}")
