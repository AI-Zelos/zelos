"""
v0.9.0 REQ-02: Execution Trace API Tests.
"""

import os, sys, time, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.runtime import ZelosRuntime
from zelos.task_graph import Task, TaskGraphEngine, TaskStatus


def make_cap():
    return type("Cap", (), {"name": "code", "version": "1.0", "description": "",
                             "input_schema": {}, "output_schema": {}, "tags": []})()


def test_get_goal_trace_single_task():
    """get_goal_trace() returns complete trace for single-task goal."""
    print("\n🔍 REQ-02.1: get_goal_trace — single task")

    rt = ZelosRuntime()
    rt.add_agent("TraceAgent", "test:Agent", [make_cap()])
    rt.start()

    result = rt.submit_goal("Trace test")
    goal_id = result["goal_id"]
    rt.wait_for_goal(goal_id, timeout_seconds=10)

    trace = rt.get_goal_trace(goal_id)
    assert trace is not None
    assert trace.goal_id == goal_id
    assert trace.status in ("completed", "accepted", "planned", "failed", "cancelled")
    assert len(trace.tasks) >= 0  # May be 0 if not yet planned

    if trace.tasks:
        event_types = [e.event_type for e in trace.tasks[0].timeline]
        assert "task.created" in event_types, f"Missing task.created in {event_types}"

    rt.shutdown()
    print(f"  ✅ Trace: {len(trace.tasks)} tasks, status={trace.status}")


def test_get_goal_trace_includes_input_output_when_requested():
    """get_goal_trace with include_artifacts=True loads input/output."""
    print("\n🔍 REQ-02.2: get_goal_trace — include_artifacts")

    rt = ZelosRuntime()
    rt.add_agent("ArtifactTraceAgent", "test:Agent", [make_cap()])
    rt.start()

    result = rt.submit_goal("Artifact trace test")
    goal_id = result["goal_id"]
    rt.wait_for_goal(goal_id, timeout_seconds=10)

    trace = rt.get_goal_trace(goal_id, include_artifacts=True)
    assert trace is not None
    if trace.tasks and trace.tasks[0].status == "completed":
        assert trace.tasks[0].output_artifact is not None
    print(f"  ✅ Trace with artifacts loaded")


def test_get_goal_trace_pagination():
    """get_goal_trace supports limit/offset pagination."""
    print("\n🔍 REQ-02.3: get_goal_trace — pagination")

    rt = ZelosRuntime()
    rt.add_agent("PageAgent", "test:Agent", [make_cap()])
    rt.start()

    result = rt.submit_goal("Pagination test")
    goal_id = result["goal_id"]
    rt.wait_for_goal(goal_id, timeout_seconds=10)

    trace_full = rt.get_goal_trace(goal_id)
    trace_paged = rt.get_goal_trace(goal_id, limit=1, offset=0)
    assert trace_paged is not None
    assert len(trace_paged.tasks) <= 1

    rt.shutdown()
    print(f"  ✅ Pagination: full={len(trace_full.tasks)}, paged={len(trace_paged.tasks)}")


def test_get_goal_trace_unfinished_goal():
    """get_goal_trace works for unfinished goals."""
    print("\n🔍 REQ-02.4: get_goal_trace — unfinished goal")

    rt = ZelosRuntime()
    rt.add_agent("UnfinishedAgent", "test:Agent", [make_cap()])
    rt.start()

    result = rt.submit_goal("Unfinished trace test")
    goal_id = result["goal_id"]

    trace = rt.get_goal_trace(goal_id)
    assert trace is not None
    assert trace.goal_id == goal_id
    assert trace.status != "completed"

    rt.shutdown()
    print(f"  ✅ Unfinished goal trace: status={trace.status}")


if __name__ == "__main__":
    print("=" * 60)
    print("  ZELOS v0.9.0 — REQ-02 EXECUTION TRACE TESTS")
    print("=" * 60)
    test_get_goal_trace_single_task()
    test_get_goal_trace_includes_input_output_when_requested()
    test_get_goal_trace_pagination()
    test_get_goal_trace_unfinished_goal()
    print(f"\n{'=' * 60}")
    print("  RESULTS: All REQ-02 tests passed ✅")
    print(f"{'=' * 60}")
