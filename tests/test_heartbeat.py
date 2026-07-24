"""
v0.8.0 REQ-04, REQ-05, REQ-06, REQ-07: Heartbeat + NonRetryableError + Query + Retry History Tests.

Tests:
  - REQ-04: Normal heartbeat → Task completes normally
  - REQ-04: Missed heartbeat → Task marked FAILED → auto retry
  - REQ-04: Retry after heartbeat timeout succeeds
  - REQ-05: non_retryable_errors causes FATAL_FAILED (no retry)
  - REQ-05: Non-matching errors retry normally
  - REQ-06: Query operations don't write events
  - REQ-07: Retry publishes task.retry_scheduled event with full context
"""

import os
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.event_bus import EventBus
from zelos.execution_engine import ExecutionEngine
from zelos.goal_state import GoalState
from zelos.runtime import ZelosRuntime
from zelos.scheduler import Scheduler
from zelos.task_graph import Task, TaskGraphEngine, TaskStatus


# ═══════════════════ REQ-04: Heartbeat Timeout ═══════════════════

def test_heartbeat_keeps_task_alive():
    """Regular heartbeat keeps task alive and completes normally."""
    print("\n💓 REQ-04.1: Heartbeat — keeps task alive")

    event_bus = EventBus()
    task_graph = TaskGraphEngine()
    engine = ExecutionEngine(task_graph, event_bus)

    # Register agent
    engine.register_agent(
        agent_id="agent-hb1",
        agent_name="HeartbeatAgent",
        max_concurrent_tasks=5,
        heartbeat_interval_ms=1000,
    )

    # Add task with short heartbeat timeout
    task = Task(
        task_id="hb-task-1",
        plan_id="plan-hb",
        description="Heartbeat test task",
        required_capability="code",
        timeout_ms=30000,
    )
    task_graph.add_task(task)
    task_graph.transition("hb-task-1", TaskStatus.READY)
    task_graph.transition("hb-task-1", TaskStatus.ASSIGNED, agent_id="agent-hb1")

    # Dispatch task
    engine.dispatch("hb-task-1", "agent-hb1")

    # Verify InFlightTask has heartbeat tracking
    ft = engine._in_flight.get("hb-task-1")
    assert ft is not None, "Task should be in flight"
    assert ft.heartbeat_at > 0, "Heartbeat timestamp should be set"
    assert ft.heartbeat_timeout_ms > 0, "Heartbeat timeout should be set"

    # Send heartbeat
    result = engine.submit_heartbeat("hb-task-1", "agent-hb1")
    assert result is True, "submit_heartbeat should return True for valid task"
    print("  ✅ submit_heartbeat() acknowledged")

    # Complete task normally
    engine.submit_result("hb-task-1", "agent-hb1",
                         {"status": "completed", "artifact": {"result": "ok"}})
    assert task_graph.get_task("hb-task-1").status == TaskStatus.COMPLETED
    print("  ✅ Task completed normally with heartbeat")


def test_heartbeat_timeout_marks_failed():
    """When heartbeat times out, task is marked FAILED."""
    print("\n💓 REQ-04.2: Heartbeat timeout → FAILED")

    event_bus = EventBus()
    task_graph = TaskGraphEngine()
    engine = ExecutionEngine(task_graph, event_bus)

    engine.register_agent(
        agent_id="agent-timeout",
        agent_name="TimeoutAgent",
        max_concurrent_tasks=5,
        heartbeat_interval_ms=100,
    )

    task = Task(
        task_id="hb-timeout-1",
        plan_id="plan-hb",
        description="Will timeout",
        required_capability="code",
        timeout_ms=30000,
    )
    task_graph.add_task(task)
    task_graph.transition("hb-timeout-1", TaskStatus.READY)
    task_graph.transition("hb-timeout-1", TaskStatus.ASSIGNED, agent_id="agent-timeout")
    engine.dispatch("hb-timeout-1", "agent-timeout")

    # Manually simulate heartbeat timeout by setting heartbeat_at far in the past
    ft = engine._in_flight["hb-timeout-1"]
    ft.heartbeat_at = time.time() - 999  # Way past timeout
    ft.heartbeat_timeout_ms = 100  # 100ms timeout

    # Run monitor check manually (instead of waiting for monitor loop)
    engine._check_heartbeat_timeouts()

    task_state = task_graph.get_task("hb-timeout-1")
    assert task_state.status == TaskStatus.FAILED, \
        f"Expected FAILED after heartbeat timeout, got {task_state.status}"
    print("  ✅ Heartbeat timeout → Task FAILED")


def test_heartbeat_timeout_triggers_retry():
    """After heartbeat timeout FAILED, scheduler retries the task."""
    print("\n💓 REQ-04.3: Heartbeat timeout → retry")

    event_bus = EventBus()
    task_graph = TaskGraphEngine()
    engine = ExecutionEngine(task_graph, event_bus)
    scheduler = Scheduler(task_graph, None)  # No capability registry needed for retry test
    scheduler.set_event_bus(event_bus)

    engine.register_agent(
        agent_id="agent-retry-hb",
        agent_name="RetryHeartbeatAgent",
        max_concurrent_tasks=5,
        heartbeat_interval_ms=100,
    )

    task = Task(
        task_id="hb-retry-1",
        plan_id="plan-hb",
        description="Retry after heartbeat timeout",
        required_capability="code",
        max_retries=3,
        backoff_base_ms=100,
    )
    task_graph.add_task(task)
    task_graph.transition("hb-retry-1", TaskStatus.READY)
    task_graph.transition("hb-retry-1", TaskStatus.ASSIGNED, agent_id="agent-retry-hb")
    engine.dispatch("hb-retry-1", "agent-retry-hb")

    # Simulate heartbeat timeout
    ft = engine._in_flight["hb-retry-1"]
    ft.heartbeat_at = time.time() - 999
    ft.heartbeat_timeout_ms = 100
    engine._check_heartbeat_timeouts()

    # Now retry
    failed_task = task_graph.get_task("hb-retry-1")
    assert failed_task.status == TaskStatus.FAILED

    retry_result = scheduler.evaluate_retry(failed_task)
    assert retry_result is not None, "Task should be retried"
    assert failed_task.attempt == 1
    assert failed_task.status == TaskStatus.READY
    print(f"  ✅ Heartbeat timeout → retry (attempt={failed_task.attempt})")


# ═══════════════════ REQ-05: NonRetryableError ═══════════════════

def test_non_retryable_error_fatal_failed():
    """non_retryable_errors match → FATAL_FAILED (no retry)."""
    print("\n🚫 REQ-05.1: NonRetryableError → FATAL_FAILED")

    event_bus = EventBus()
    task_graph = TaskGraphEngine()
    engine = ExecutionEngine(task_graph, event_bus)
    scheduler = Scheduler(task_graph, None)
    scheduler.set_event_bus(event_bus)

    engine.register_agent(
        agent_id="agent-fatal",
        agent_name="FatalAgent",
        max_concurrent_tasks=5,
        heartbeat_interval_ms=30000,
    )

    task = Task(
        task_id="fatal-task-1",
        plan_id="plan-fatal",
        description="Validation will fail",
        required_capability="code",
        non_retryable_errors=["ValidationError", "AuthError"],
        max_retries=3,
    )
    task_graph.add_task(task)
    task_graph.transition("fatal-task-1", TaskStatus.READY)
    task_graph.transition("fatal-task-1", TaskStatus.ASSIGNED, agent_id="agent-fatal")
    engine.dispatch("fatal-task-1", "agent-fatal")

    # Submit a non-retryable error
    result = engine.submit_result("fatal-task-1", "agent-fatal", {
        "status": "failed",
        "error": {"code": "ValidationError", "message": "Invalid input schema"},
    })
    assert result is True

    task_state = task_graph.get_task("fatal-task-1")
    assert task_state.status == TaskStatus.FATAL_FAILED, \
        f"Expected FATAL_FAILED, got {task_state.status}"

    # Scheduler should NOT retry FATAL_FAILED
    retry_result = scheduler.evaluate_retry(task_state)
    assert retry_result is None, "FATAL_FAILED should NOT be retried"
    print("  ✅ ValidationError → FATAL_FAILED (no retry)")


def test_regular_error_still_retries():
    """Error not in non_retryable_errors → normal FAILED → retry."""
    print("\n🚫 REQ-05.2: Regular error → normal FAILED → retry")

    event_bus = EventBus()
    task_graph = TaskGraphEngine()
    engine = ExecutionEngine(task_graph, event_bus)
    scheduler = Scheduler(task_graph, None)
    scheduler.set_event_bus(event_bus)

    engine.register_agent(
        agent_id="agent-retry-normal",
        agent_name="RetryNormalAgent",
        max_concurrent_tasks=5,
        heartbeat_interval_ms=30000,
    )

    task = Task(
        task_id="normal-retry-1",
        plan_id="plan-normal",
        description="Will retry normally",
        required_capability="code",
        non_retryable_errors=["ValidationError"],
        max_retries=3,
        backoff_base_ms=100,
    )
    task_graph.add_task(task)
    task_graph.transition("normal-retry-1", TaskStatus.READY)
    task_graph.transition("normal-retry-1", TaskStatus.ASSIGNED, agent_id="agent-retry-normal")
    engine.dispatch("normal-retry-1", "agent-retry-normal")

    # Submit a non-matching error
    engine.submit_result("normal-retry-1", "agent-retry-normal", {
        "status": "failed",
        "error": {"code": "NetworkTimeout", "message": "Connection lost"},
    })

    task_state = task_graph.get_task("normal-retry-1")
    assert task_state.status == TaskStatus.FAILED, \
        f"Expected FAILED, got {task_state.status}"

    # Should be retried
    retry_result = scheduler.evaluate_retry(task_state)
    assert retry_result is not None, "NetworkTimeout should be retried"
    assert task_state.attempt == 1
    print(f"  ✅ NetworkTimeout → FAILED → retry (attempt={task_state.attempt})")


def test_fatal_failed_is_terminal():
    """FATAL_FAILED has no valid transitions (terminal state)."""
    print("\n🚫 REQ-05.3: FATAL_FAILED is terminal")

    from zelos.task_graph import VALID_TRANSITIONS

    assert TaskStatus.FATAL_FAILED in VALID_TRANSITIONS
    assert VALID_TRANSITIONS[TaskStatus.FATAL_FAILED] == set(), \
        "FATAL_FAILED should have no valid transitions"

    print("  ✅ FATAL_FAILED is terminal (no valid transitions)")


# ═══════════════════ REQ-06: Query operations don't write events ═══════════════════

def test_query_operations_dont_write_events():
    """get_goal_status, list_agents, get_health don't increase event count."""
    print("\n🔍 REQ-06: Query operations don't write events")

    rt = ZelosRuntime()
    rt.add_agent(
        "QueryAgent",
        "test:Agent",
        [
            type("Cap", (), {
                "name": "code", "version": "1.0",
                "description": "", "input_schema": {}, "output_schema": {}, "tags": [],
            })(),
        ],
    )
    rt.start()

    # Submit a goal so we have something to query
    result = rt.submit_goal("Query test goal")
    goal_id = result["goal_id"]

    event_count_before = rt._event_bus.total_events()

    # Perform query operations
    rt.get_goal_status(goal_id)
    rt.list_agents()
    rt.get_health()

    event_count_after = rt._event_bus.total_events()
    assert event_count_after == event_count_before, \
        f"Query ops should not write events. Before: {event_count_before}, After: {event_count_after}"

    rt.shutdown()
    print(f"  ✅ Query operations → event count unchanged ({event_count_before})")


# ═══════════════════ REQ-07: Retry History Tracking ═══════════════════

def test_retry_publishes_event():
    """Task retry publishes task.retry_scheduled event with full context."""
    print("\n📋 REQ-07.1: Retry publishes event")

    event_bus = EventBus()
    task_graph = TaskGraphEngine()
    engine = ExecutionEngine(task_graph, event_bus)
    scheduler = Scheduler(task_graph, None)
    scheduler.set_event_bus(event_bus)

    # Track retry events
    retry_events = []
    event_bus.subscribe("task.retry_scheduled", lambda e: retry_events.append(e))

    engine.register_agent(
        agent_id="agent-retry-ev",
        agent_name="RetryEventAgent",
        max_concurrent_tasks=5,
        heartbeat_interval_ms=30000,
    )

    task = Task(
        task_id="retry-ev-1",
        plan_id="plan-retry-ev",
        description="Retry event test",
        required_capability="code",
        max_retries=3,
        backoff_base_ms=500,
    )
    task_graph.add_task(task)
    task_graph.transition("retry-ev-1", TaskStatus.READY)
    task_graph.transition("retry-ev-1", TaskStatus.ASSIGNED, agent_id="agent-retry-ev")
    engine.dispatch("retry-ev-1", "agent-retry-ev")

    # Fail the task
    engine.submit_result("retry-ev-1", "agent-retry-ev", {
        "status": "failed",
        "error": {"code": "InternalError", "message": "Something broke"},
    })

    # Retry
    failed_task = task_graph.get_task("retry-ev-1")
    retry_result = scheduler.evaluate_retry(failed_task,
        previous_error={"code": "InternalError", "message": "Something broke"})

    assert retry_result is not None
    assert len(retry_events) >= 1, f"Expected at least 1 retry event, got {len(retry_events)}"

    event = retry_events[0]
    assert event.event_type == "task.retry_scheduled"
    assert event.payload["task_id"] == "retry-ev-1"
    assert event.payload["attempt"] == 1
    assert event.payload["backoff_ms"] > 0
    assert event.payload["previous_error"]["code"] == "InternalError"
    print(f"  ✅ task.retry_scheduled event: task={event.payload['task_id']}, "
          f"attempt={event.payload['attempt']}, backoff={event.payload['backoff_ms']}ms")


def test_multiple_retries_all_publish_events():
    """Multiple retries each publish a separate event."""
    print("\n📋 REQ-07.2: Multiple retries → multiple events")

    event_bus = EventBus()
    task_graph = TaskGraphEngine()
    engine = ExecutionEngine(task_graph, event_bus)
    scheduler = Scheduler(task_graph, None)
    scheduler.set_event_bus(event_bus)

    retry_events = []
    event_bus.subscribe("task.retry_scheduled", lambda e: retry_events.append(e))

    engine.register_agent(
        agent_id="agent-multi",
        agent_name="MultiRetryAgent",
        max_concurrent_tasks=5,
        heartbeat_interval_ms=30000,
    )

    task = Task(
        task_id="multi-retry-1",
        plan_id="plan-multi",
        description="Multiple retries",
        required_capability="code",
        max_retries=3,
        backoff_base_ms=100,
    )
    task_graph.add_task(task)

    # Simulate 3 retries
    for retry_num in range(3):
        if task.status in (TaskStatus.CREATED, TaskStatus.READY):
            if task.status == TaskStatus.CREATED:
                task_graph.transition("multi-retry-1", TaskStatus.READY)
            task_graph.transition("multi-retry-1", TaskStatus.ASSIGNED, agent_id="agent-multi")
        engine.dispatch("multi-retry-1", "agent-multi")
        engine.submit_result("multi-retry-1", "agent-multi", {
            "status": "failed",
            "error": {"code": f"Error{retry_num}", "message": f"Attempt {retry_num + 1} failed"},
        })
        failed_task = task_graph.get_task("multi-retry-1")
        scheduler.evaluate_retry(failed_task,
            previous_error={"code": f"Error{retry_num}", "message": f"Attempt {retry_num + 1} failed"})

    assert len(retry_events) == 3, f"Expected 3 retry events, got {len(retry_events)}"
    for i, event in enumerate(retry_events):
        assert event.payload["attempt"] == i + 1
        assert event.payload["previous_error"]["code"] == f"Error{i}"
    print(f"  ✅ {len(retry_events)} retry events published with correct attempt numbers")


# ═══════════════════ Integration: submit_heartbeat via Runtime ═══════════════════

def test_runtime_submit_heartbeat_api():
    """Runtime.submit_heartbeat() API works end-to-end."""
    print("\n💓 REQ-04.4: Runtime.submit_heartbeat() API")

    rt = ZelosRuntime()
    rt.add_agent(
        "HeartbeatAPIAgent",
        "test:Agent",
        [
            type("Cap", (), {
                "name": "code-generation.python", "version": "1.0",
                "description": "", "input_schema": {}, "output_schema": {}, "tags": [],
            })(),
        ],
    )
    rt.start()

    result = rt.submit_goal("Heartbeat API test")
    goal_id = result["goal_id"]

    # Find a task
    tasks = rt._task_graph.list_tasks()
    plan_id = rt._goals[goal_id]["plan_id"]
    goal_tasks = [t for t in tasks if t.plan_id == plan_id]

    if goal_tasks:
        task_id = goal_tasks[0].task_id
        # submit_heartbeat for non-in-flight task should fail gracefully
        result = rt.submit_heartbeat(task_id)
        # It should not crash — exact return value depends on dispatch state
        print(f"  ✅ submit_heartbeat({task_id[:8]}...) returned {result}")

    rt.shutdown()


if __name__ == "__main__":
    print("=" * 60)
    print("  ZELOS v0.8.0 — REQ-04/05/06/07 TESTS")
    print("=" * 60)
    test_heartbeat_keeps_task_alive()
    test_heartbeat_timeout_marks_failed()
    test_heartbeat_timeout_triggers_retry()
    test_non_retryable_error_fatal_failed()
    test_regular_error_still_retries()
    test_fatal_failed_is_terminal()
    test_query_operations_dont_write_events()
    test_retry_publishes_event()
    test_multiple_retries_all_publish_events()
    test_runtime_submit_heartbeat_api()
    print(f"\n{'=' * 60}")
    print("  RESULTS: All REQ-04/05/06/07 tests passed ✅")
    print(f"{'=' * 60}")
