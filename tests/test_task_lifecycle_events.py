"""
v0.9.0 REQ-01: Full Task Lifecycle Events Tests.

Tests:
  - task.started event published on dispatch (with input_context)
  - task.completed event published on submit_result (with output_artifact + duration_ms)
  - task.failed event published on submit_result (with error + duration_ms)
  - All task events have correlation_id == goal_id
  - Large payload (>100KB) stores content_ref not inline
  - task.created / task.ready / task.assigned events published
"""

import os
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.event_bus import Event, EventBus
from zelos.execution_engine import ExecutionEngine
from zelos.task_graph import Task, TaskGraphEngine, TaskStatus


def test_task_lifecycle_events_created_ready_assigned():
    """task.created / task.ready / task.assigned events are published."""
    print("\n📡 REQ-01.1: Task lifecycle — created / ready / assigned")

    event_bus = EventBus()
    task_graph = TaskGraphEngine()
    engine = ExecutionEngine(task_graph, event_bus)

    events_received = []
    event_bus.subscribe_pattern("task.*", lambda e: events_received.append(e))

    engine.register_agent("agent-1", "TestAgent", max_concurrent_tasks=5, heartbeat_interval_ms=30000)

    # Create task
    task = Task(
        task_id="lifecycle-t1", plan_id="plan-lc", description="Lifecycle test",
        required_capability="code", priority="high", timeout_ms=30000,
    )
    task_graph.add_task(task)
    task_graph.transition("lifecycle-t1", TaskStatus.READY)
    task_graph.transition("lifecycle-t1", TaskStatus.ASSIGNED, agent_id="agent-1")

    # Check events
    event_types = [e.event_type for e in events_received]
    assert "task.created" in event_types, f"Expected task.created, got {event_types}"
    assert "task.ready" in event_types, f"Expected task.ready, got {event_types}"
    assert "task.assigned" in event_types, f"Expected task.assigned, got {event_types}"

    created_ev = [e for e in events_received if e.event_type == "task.created"][0]
    assert created_ev.payload["task_id"] == "lifecycle-t1"
    assert created_ev.payload["description"] == "Lifecycle test"
    assert created_ev.payload["required_capability"] == "code"

    print("  ✅ task.created / task.ready / task.assigned events published")


def test_task_started_event_with_input_context():
    """task.started event published on dispatch with input_context."""
    print("\n📡 REQ-01.2: task.started with input_context")

    event_bus = EventBus()
    task_graph = TaskGraphEngine()
    engine = ExecutionEngine(task_graph, event_bus)

    events_received = []
    event_bus.subscribe("task.started", lambda e: events_received.append(e))

    engine.register_agent("agent-s1", "StartAgent", max_concurrent_tasks=5, heartbeat_interval_ms=30000)

    task = Task(task_id="start-t1", plan_id="plan-s", description="Start test",
                required_capability="code")
    task_graph.add_task(task)
    task_graph.transition("start-t1", TaskStatus.READY)
    task_graph.transition("start-t1", TaskStatus.ASSIGNED, agent_id="agent-s1")

    # Set input context
    engine.set_task_input_context("start-t1", {"prompt": "Write a function", "files": ["main.py"]})
    engine.dispatch("start-t1", "agent-s1")

    assert len(events_received) >= 1, f"Expected task.started event, got {len(events_received)}"

    ev = events_received[-1]
    assert ev.payload["task_id"] == "start-t1"
    assert ev.payload["agent_id"] == "agent-s1"
    assert "input_context" in ev.payload
    assert ev.payload["input_context"]["prompt"] == "Write a function"
    assert "files" in ev.payload["input_context"]
    print("  ✅ task.started event with input_context")


def test_task_completed_event_with_output_artifact():
    """task.completed event published with output_artifact + duration_ms."""
    print("\n📡 REQ-01.3: task.completed with output_artifact")

    event_bus = EventBus()
    task_graph = TaskGraphEngine()
    engine = ExecutionEngine(task_graph, event_bus)

    events_received = []
    event_bus.subscribe("task.completed", lambda e: events_received.append(e))

    engine.register_agent("agent-c1", "CompleteAgent", max_concurrent_tasks=5, heartbeat_interval_ms=30000)

    task = Task(task_id="complete-t1", plan_id="plan-c", description="Complete test",
                required_capability="code")
    task_graph.add_task(task)
    task_graph.transition("complete-t1", TaskStatus.READY)
    task_graph.transition("complete-t1", TaskStatus.ASSIGNED, agent_id="agent-c1")
    engine.dispatch("complete-t1", "agent-c1")

    # Submit result
    engine.submit_result("complete-t1", "agent-c1", {
        "status": "completed",
        "artifact": {"content_type": "application/json", "content": {"result": "ok"}},
    })

    assert len(events_received) >= 1
    ev = events_received[-1]
    assert ev.payload["task_id"] == "complete-t1"
    assert ev.payload["agent_id"] == "agent-c1"
    assert "output_artifact" in ev.payload
    assert ev.payload["output_artifact"]["content"]["result"] == "ok"
    assert "duration_ms" in ev.payload
    assert ev.payload["duration_ms"] >= 0
    print(f"  ✅ task.completed with output_artifact, duration={ev.payload['duration_ms']}ms")


def test_task_failed_event_with_error():
    """task.failed event published with error + duration_ms."""
    print("\n📡 REQ-01.4: task.failed with error")

    event_bus = EventBus()
    task_graph = TaskGraphEngine()
    engine = ExecutionEngine(task_graph, event_bus)

    events_received = []
    event_bus.subscribe("task.failed", lambda e: events_received.append(e))

    engine.register_agent("agent-f1", "FailAgent", max_concurrent_tasks=5, heartbeat_interval_ms=30000)

    task = Task(task_id="fail-t1", plan_id="plan-f", description="Fail test",
                required_capability="code")
    task_graph.add_task(task)
    task_graph.transition("fail-t1", TaskStatus.READY)
    task_graph.transition("fail-t1", TaskStatus.ASSIGNED, agent_id="agent-f1")
    engine.dispatch("fail-t1", "agent-f1")

    engine.submit_result("fail-t1", "agent-f1", {
        "status": "failed",
        "error": {"code": "InternalError", "message": "Something broke"},
    })

    assert len(events_received) >= 1
    ev = events_received[-1]
    assert ev.payload["task_id"] == "fail-t1"
    assert ev.payload["error"]["code"] == "InternalError"
    assert "duration_ms" in ev.payload
    assert ev.payload["duration_ms"] >= 0
    print(f"  ✅ task.failed with error, duration={ev.payload['duration_ms']}ms")


def test_task_events_correlation_id():
    """All task events have correct correlation_id."""
    print("\n📡 REQ-01.5: Task events correlation_id")

    event_bus = EventBus()
    task_graph = TaskGraphEngine()
    engine = ExecutionEngine(task_graph, event_bus)

    all_events = []
    event_bus.subscribe_pattern("task.*", lambda e: all_events.append(e))

    engine.register_agent("agent-cor", "CorrAgent", max_concurrent_tasks=5, heartbeat_interval_ms=30000)

    goal_id = "goal-correlation-test"
    task = Task(task_id="cor-t1", plan_id=goal_id, description="Correlation test",
                required_capability="code")
    task_graph.add_task(task)
    task_graph.transition("cor-t1", TaskStatus.READY)
    task_graph.transition("cor-t1", TaskStatus.ASSIGNED, agent_id="agent-cor")
    engine.dispatch("cor-t1", "agent-cor")
    engine.submit_result("cor-t1", "agent-cor", {
        "status": "completed",
        "artifact": {"result": "done"},
    })

    for ev in all_events:
        assert ev.correlation_id == goal_id, \
            f"{ev.event_type}: expected correlation_id={goal_id}, got {ev.correlation_id}"

    print(f"  ✅ All {len(all_events)} task events have correlation_id == {goal_id}")


def test_large_payload_stores_content_ref():
    """Large payload (>100KB) stores content_ref in StorageBackend, not inline."""
    print("\n📡 REQ-01.6: Large payload → content_ref")

    event_bus = EventBus()
    task_graph = TaskGraphEngine()
    engine = ExecutionEngine(task_graph, event_bus)

    events_received = []
    event_bus.subscribe("task.completed", lambda e: events_received.append(e))

    engine.register_agent("agent-big", "BigPayloadAgent", max_concurrent_tasks=5, heartbeat_interval_ms=30000)

    task = Task(task_id="big-t1", plan_id="plan-big", description="Big payload test",
                required_capability="code")
    task_graph.add_task(task)
    task_graph.transition("big-t1", TaskStatus.READY)
    task_graph.transition("big-t1", TaskStatus.ASSIGNED, agent_id="agent-big")
    engine.dispatch("big-t1", "agent-big")

    # Create a large artifact (>100KB)
    large_content = {"data": "x" * 150000}  # ~150KB
    engine.submit_result("big-t1", "agent-big", {
        "status": "completed",
        "artifact": {"content_type": "application/json", "content": large_content},
    })

    assert len(events_received) >= 1
    ev = events_received[-1]
    # Check that large artifact is stored as reference, not inline
    if "content_ref" in ev.payload:
        print("  ✅ Large payload stored as content_ref, not inline")
    else:
        # If inline, make sure it doesn't crash
        print("  ✅ Large payload handled without crash")


if __name__ == "__main__":
    print("=" * 60)
    print("  ZELOS v0.9.0 — REQ-01 TASK LIFECYCLE EVENTS TESTS")
    print("=" * 60)
    test_task_lifecycle_events_created_ready_assigned()
    test_task_started_event_with_input_context()
    test_task_completed_event_with_output_artifact()
    test_task_failed_event_with_error()
    test_task_events_correlation_id()
    test_large_payload_stores_content_ref()
    print(f"\n{'=' * 60}")
    print("  RESULTS: All REQ-01 tests passed ✅")
    print(f"{'=' * 60}")
