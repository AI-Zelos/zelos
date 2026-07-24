"""
v0.8.0 REQ-02 & REQ-03: Event Sourcing + Monotonic sequence_id Tests.

Tests:
  - apply_event() for each core event type updates GoalState correctly
  - Full rebuild from event chain matches original state
  - Snapshot + incremental recovery produces correct state
  - 100-event replay performance < 100ms
  - sequence_id monotonic assignment (0-99 for 100 events)
  - replay_from(sequence_id) returns correct subset
  - Backward compatibility: old events w/o sequence_id default to -1
"""

import os
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.event_bus import Event, EventBus, InMemoryEventStore
from zelos.event_sourcing import EventSourcingEngine
from zelos.goal_state import GoalState
from zelos.storage import InMemoryStorageBackend
from zelos.task_graph import Task, TaskStatus


# ═══════════════════ Helper ═══════════════════

def _make_event(event_type: str, payload: dict, correlation_id: str = "goal-1",
                source: str = "test", seq_id: int | None = None) -> Event:
    """Create a test event."""
    e = Event(
        event_id=str(uuid.uuid4()),
        event_type=event_type,
        source=source,
        timestamp=time.time(),
        correlation_id=correlation_id,
        payload=payload,
        sequence_id=seq_id if seq_id is not None else -1,
    )
    return e


# ═══════════════════ REQ-02.1: apply_event for each event type ═══════════════════

def test_apply_event_goal_submitted():
    """apply_event('goal.submitted') creates initial GoalState."""
    print("\n📊 REQ-02.1a: apply_event — goal.submitted")

    engine = EventSourcingEngine()
    event = _make_event("goal.submitted", {
        "goal_id": "goal-1",
        "description": "Test goal",
        "priority": "high",
        "budget": 50.0,
    })

    state = engine.apply_event(event, None)
    assert state is not None
    assert state.goal_id == "goal-1"
    assert state.status == "accepted"
    assert state.description == "Test goal"
    assert state.priority == "high"
    assert state.budget == 50.0
    # sequence_id=-1 means event_position stays at default (0, from GoalState init)
    assert state.event_position == 0
    print("  ✅ goal.submitted → GoalState created")


def test_apply_event_plan_created():
    """apply_event('plan.created') updates plan_id."""
    print("\n📊 REQ-02.1b: apply_event — plan.created")

    engine = EventSourcingEngine()
    state = GoalState(goal_id="goal-1", status="accepted", description="Test",
                      tasks=[], event_position=0)

    event = _make_event("plan.created", {
        "goal_id": "goal-1",
        "plan_id": "plan-abc",
    })

    state = engine.apply_event(event, state)
    assert state.status == "planned"
    assert state.plan_id == "plan-abc"
    print("  ✅ plan.created → status=planned, plan_id set")


def test_apply_event_task_created():
    """apply_event('task.created') adds task to state."""
    print("\n📊 REQ-02.1c: apply_event — task.created")

    engine = EventSourcingEngine()
    state = GoalState(goal_id="goal-1", status="planned", description="Test",
                      tasks=[], plan_id="plan-abc", event_position=1)

    event = _make_event("task.created", {
        "goal_id": "goal-1",
        "task_id": "task-1",
        "plan_id": "plan-abc",
        "description": "Write code",
        "required_capability": "coding",
        "dependencies": [],
        "priority": "high",
        "timeout_ms": 30000,
    })

    state = engine.apply_event(event, state)
    assert len(state.tasks) == 1
    t = state.tasks[0]
    assert t.task_id == "task-1"
    assert t.description == "Write code"
    assert t.required_capability == "coding"
    assert t.status == TaskStatus.CREATED
    print("  ✅ task.created → task added to state")


def test_apply_event_task_completed():
    """apply_event('task.completed') marks task as COMPLETED."""
    print("\n📊 REQ-02.1d: apply_event — task.completed")

    engine = EventSourcingEngine()
    task = Task(task_id="task-1", plan_id="plan-abc", description="Write code",
                required_capability="coding", status=TaskStatus.STARTED)
    state = GoalState(goal_id="goal-1", status="executing", description="Test",
                      tasks=[task], plan_id="plan-abc", event_position=2)

    event = _make_event("task.completed", {
        "goal_id": "goal-1",
        "task_id": "task-1",
    })

    state = engine.apply_event(event, state)
    assert state.tasks[0].status == TaskStatus.COMPLETED
    print("  ✅ task.completed → task status=COMPLETED")


def test_apply_event_task_failed():
    """apply_event('task.failed') marks task as FAILED."""
    print("\n📊 REQ-02.1e: apply_event — task.failed")

    engine = EventSourcingEngine()
    task = Task(task_id="task-1", plan_id="plan-abc", description="Write code",
                required_capability="coding", status=TaskStatus.STARTED)
    state = GoalState(goal_id="goal-1", status="executing", description="Test",
                      tasks=[task], plan_id="plan-abc", event_position=3)

    event = _make_event("task.failed", {
        "goal_id": "goal-1",
        "task_id": "task-1",
        "error": {"code": "timeout", "message": "Connection lost"},
    })

    state = engine.apply_event(event, state)
    assert state.tasks[0].status == TaskStatus.FAILED
    print("  ✅ task.failed → task status=FAILED")


def test_apply_event_goal_completed():
    """apply_event('goal.completed') sets terminal status."""
    print("\n📊 REQ-02.1f: apply_event — goal.completed")

    engine = EventSourcingEngine()
    task = Task(task_id="task-1", plan_id="plan-abc", description="Write code",
                required_capability="coding", status=TaskStatus.COMPLETED)
    state = GoalState(goal_id="goal-1", status="executing", description="Test",
                      tasks=[task], plan_id="plan-abc", event_position=4)

    event = _make_event("goal.completed", {
        "goal_id": "goal-1",
    })

    state = engine.apply_event(event, state)
    assert state.status == "completed"
    assert state.completed_at is not None
    print("  ✅ goal.completed → status=completed")


def test_apply_event_task_retry_scheduled():
    """apply_event('task.retry_scheduled') increments attempt count."""
    print("\n📊 REQ-02.1g: apply_event — task.retry_scheduled")

    engine = EventSourcingEngine()
    task = Task(task_id="task-1", plan_id="plan-abc", description="Write code",
                required_capability="coding", status=TaskStatus.FAILED, attempt=1)
    state = GoalState(goal_id="goal-1", status="executing", description="Test",
                      tasks=[task], plan_id="plan-abc", event_position=5)

    event = _make_event("task.retry_scheduled", {
        "goal_id": "goal-1",
        "task_id": "task-1",
        "attempt": 2,
        "backoff_ms": 2000,
        "previous_error": {"code": "timeout", "message": "timed out"},
    })

    state = engine.apply_event(event, state)
    assert state.tasks[0].attempt == 2
    assert state.tasks[0].status == TaskStatus.READY  # Ready for retry
    print("  ✅ task.retry_scheduled → attempt incremented, status=READY")


def test_apply_event_unknown_type_noop():
    """apply_event with unknown event type is a no-op."""
    print("\n📊 REQ-02.1h: apply_event — unknown type (no-op)")

    engine = EventSourcingEngine()
    state = GoalState(goal_id="goal-1", status="executing", description="Test",
                      tasks=[], event_position=0)

    event = _make_event("unknown.event.type", {"foo": "bar"})
    new_state = engine.apply_event(event, state)
    assert new_state is state  # Same object returned
    assert new_state.status == "executing"
    print("  ✅ unknown event type → no-op")


# ═══════════════════ REQ-02.2: Full rebuild from event chain ═══════════════════

def test_full_rebuild_from_event_chain():
    """Full state rebuild from complete event chain matches original."""
    print("\n📊 REQ-02.2: Full rebuild from event chain")

    # Build events for a complete goal lifecycle
    events = [
        _make_event("goal.submitted", {"goal_id": "goal-rb", "description": "Rebuild test",
                                        "priority": "medium", "budget": 100.0}),
        _make_event("plan.created", {"goal_id": "goal-rb", "plan_id": "plan-rb"}),
        _make_event("task.created", {"goal_id": "goal-rb", "task_id": "rb-t1",
                                      "plan_id": "plan-rb", "description": "Step 1",
                                      "required_capability": "code",
                                      "dependencies": [], "priority": "medium", "timeout_ms": 30000}),
        _make_event("task.created", {"goal_id": "goal-rb", "task_id": "rb-t2",
                                      "plan_id": "plan-rb", "description": "Step 2",
                                      "required_capability": "review",
                                      "dependencies": ["rb-t1"], "priority": "medium", "timeout_ms": 30000}),
        _make_event("task.started", {"goal_id": "goal-rb", "task_id": "rb-t1"}),
        _make_event("task.completed", {"goal_id": "goal-rb", "task_id": "rb-t1"}),
        _make_event("task.started", {"goal_id": "goal-rb", "task_id": "rb-t2"}),
        _make_event("task.completed", {"goal_id": "goal-rb", "task_id": "rb-t2"}),
        _make_event("goal.completed", {"goal_id": "goal-rb"}),
    ]

    engine = EventSourcingEngine()
    state = engine.rebuild_from_events("goal-rb", events)

    assert state is not None
    assert state.goal_id == "goal-rb"
    assert state.status == "completed"
    assert state.plan_id == "plan-rb"
    assert len(state.tasks) == 2
    assert state.tasks[0].task_id == "rb-t1"
    assert state.tasks[0].status == TaskStatus.COMPLETED
    assert state.tasks[1].task_id == "rb-t2"
    assert state.tasks[1].status == TaskStatus.COMPLETED
    assert state.tasks[1].dependencies == ["rb-t1"]
    print("  ✅ Full rebuild from 9 events — state matches original")


def test_rebuild_empty_event_chain():
    """Rebuild from empty event chain returns None."""
    print("\n📊 REQ-02.2b: Rebuild from empty event chain")

    engine = EventSourcingEngine()
    state = engine.rebuild_from_events("goal-nonexistent", [])
    assert state is None
    print("  ✅ Empty event chain → None")


# ═══════════════════ REQ-02.3: Snapshot + incremental recovery ═══════════════════

def test_snapshot_plus_incremental_recovery():
    """Snapshot at position 5 + replay events 6-9 → reconstruct correct state."""
    print("\n📊 REQ-02.3: Snapshot + incremental recovery")

    storage = InMemoryStorageBackend()
    storage.connect()

    all_events = [
        _make_event("goal.submitted", {"goal_id": "goal-si", "description": "Snap+Inc"},
                    seq_id=0),
        _make_event("plan.created", {"goal_id": "goal-si", "plan_id": "plan-si"},
                    seq_id=1),
        _make_event("task.created", {"goal_id": "goal-si", "task_id": "si-t1",
                                      "plan_id": "plan-si", "description": "T1",
                                      "required_capability": "code",
                                      "dependencies": [], "priority": "high", "timeout_ms": 30000},
                    seq_id=2),
        _make_event("task.created", {"goal_id": "goal-si", "task_id": "si-t2",
                                      "plan_id": "plan-si", "description": "T2",
                                      "required_capability": "review",
                                      "dependencies": ["si-t1"], "priority": "medium", "timeout_ms": 30000},
                    seq_id=3),
        _make_event("task.started", {"goal_id": "goal-si", "task_id": "si-t1"},
                    seq_id=4),
        # ── Snapshot taken here (position 4) ──
        _make_event("task.completed", {"goal_id": "goal-si", "task_id": "si-t1"},
                    seq_id=5),
        _make_event("task.started", {"goal_id": "goal-si", "task_id": "si-t2"},
                    seq_id=6),
        _make_event("task.completed", {"goal_id": "goal-si", "task_id": "si-t2"},
                    seq_id=7),
        _make_event("goal.completed", {"goal_id": "goal-si"}, seq_id=8),
    ]

    # Build the snapshot state (what things look like at position 4)
    engine = EventSourcingEngine()
    snapshot_state = engine.rebuild_from_events("goal-si", all_events[:5])
    assert snapshot_state.event_position == 4
    assert len(snapshot_state.tasks) == 2
    assert snapshot_state.tasks[0].status == TaskStatus.STARTED

    # Save snapshot
    storage.create_snapshot("goal-si", events_position=4, state=snapshot_state.to_dict())

    # Now simulate recovery: get snapshot + replay remaining events
    restored = engine.restore_goal("goal-si", storage, all_events[5:])
    assert restored is not None
    assert restored.goal_id == "goal-si"
    assert restored.status == "completed"
    assert restored.tasks[0].status == TaskStatus.COMPLETED
    assert restored.tasks[1].status == TaskStatus.COMPLETED
    assert restored.event_position == 8  # Latest event position

    storage.disconnect()
    print("  ✅ Snapshot(4) + replay(5→8) → correct final state")


# ═══════════════════ REQ-02.4: 100-event replay performance ═══════════════════

def test_event_replay_performance():
    """100 events replay in < 100ms."""
    print("\n⚡ REQ-02.4: 100-event replay performance")

    events = []
    events.append(_make_event("goal.submitted", {"goal_id": "goal-perf", "description": "Perf test"},
                              seq_id=0))
    events.append(_make_event("plan.created", {"goal_id": "goal-perf", "plan_id": "plan-perf"},
                              seq_id=1))

    for i in range(49):
        events.append(_make_event("task.created", {
            "goal_id": "goal-perf", "task_id": f"perf-t{i}",
            "plan_id": "plan-perf", "description": f"Task {i}",
            "required_capability": "code",
            "dependencies": [], "priority": "medium", "timeout_ms": 30000,
        }, seq_id=2 + i * 2))
        events.append(_make_event("task.completed", {
            "goal_id": "goal-perf", "task_id": f"perf-t{i}",
        }, seq_id=3 + i * 2))

    events.append(_make_event("goal.completed", {"goal_id": "goal-perf"}, seq_id=100))

    assert len(events) == 101  # 1 submit + 1 plan + 49*2 task events + 1 complete

    engine = EventSourcingEngine()
    start = time.perf_counter()
    state = engine.rebuild_from_events("goal-perf", events)
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert state is not None
    assert state.status == "completed"
    assert len(state.tasks) == 49
    assert elapsed_ms < 100, f"Replay took {elapsed_ms:.1f}ms, expected < 100ms"
    print(f"  ✅ 101 events replayed in {elapsed_ms:.1f}ms (< 100ms)")


# ═══════════════════ REQ-03.1: sequence_id monotonic ═══════════════════

def test_sequence_id_monotonic():
    """100 events get sequence_id 0-99."""
    print("\n🔢 REQ-03.1: sequence_id monotonic assignment")

    store = InMemoryEventStore(max_events=200)

    for i in range(100):
        e = Event(
            event_id=f"evt-{i}",
            event_type="test.event",
            source="test",
            timestamp=time.time(),
            correlation_id="test-seq",
            payload={"index": i},
        )
        store.append(e)

    # Verify sequence_ids are 0-99
    assert len(store._events) == 100
    for i, event in enumerate(store._events):
        assert event.sequence_id == i, f"Event {i} has sequence_id {event.sequence_id}, expected {i}"

    print("  ✅ 100 events → sequence_id 0-99 monotonic")


def test_replay_from_sequence_id():
    """replay_from(50) returns events with sequence_id >= 50."""
    print("\n🔢 REQ-03.2: replay_from(sequence_id)")

    store = InMemoryEventStore(max_events=200)
    for i in range(100):
        e = Event(
            event_id=f"evt-{i}",
            event_type="test.event",
            source="test",
            timestamp=time.time(),
            correlation_id="test-replay",
            payload={"index": i},
        )
        store.append(e)

    # replay_from(50) should return events with sequence_id >= 50
    result = store.replay_from(50)
    assert len(result) == 50, f"Expected 50 events from seq 50+, got {len(result)}"
    assert result[0].sequence_id == 50
    assert result[-1].sequence_id == 99

    # replay_from(0) should return all 100
    result_all = store.replay_from(0)
    assert len(result_all) == 100

    # replay_from(999) should return empty
    result_empty = store.replay_from(999)
    assert len(result_empty) == 0

    print("  ✅ replay_from(50) → 50 events, replay_from(999) → empty")


def test_sequence_id_backward_compat():
    """Old events without sequence_id default to -1."""
    print("\n🔢 REQ-03.3: sequence_id backward compatibility")

    # Create an event without specifying sequence_id
    e = Event(
        event_id="old-event",
        event_type="legacy.event",
        source="legacy",
        timestamp=time.time(),
        correlation_id="legacy-1",
        payload={"version": "0.7.0"},
    )

    assert e.sequence_id == -1, f"Legacy event should default to -1, got {e.sequence_id}"

    # to_dict should include sequence_id
    d = e.to_dict()
    assert d["sequence_id"] == -1

    # Store it — old events in store won't disrupt newer ones
    store = InMemoryEventStore(max_events=100)
    store.append(e)  # Will get sequence_id assigned by store: 0
    assert store._events[0].sequence_id == 0  # Store auto-assigns

    print("  ✅ Legacy events default sequence_id=-1; store auto-assigns new IDs")


# ═══════════════════ REQ-02.5: Partial rebuild (only goal events) ═══════════════════

def test_rebuild_filters_by_goal_id():
    """rebuild_from_events only processes events for the given goal_id."""
    print("\n📊 REQ-02.5: Rebuild filters by goal_id")

    # Mix events from two different goals
    events = [
        _make_event("goal.submitted", {"goal_id": "goal-a", "description": "Goal A"}),
        _make_event("goal.submitted", {"goal_id": "goal-b", "description": "Goal B"}),
        _make_event("plan.created", {"goal_id": "goal-a", "plan_id": "plan-a"}),
        _make_event("plan.created", {"goal_id": "goal-b", "plan_id": "plan-b"}),
        _make_event("task.created", {"goal_id": "goal-a", "task_id": "a-t1",
                                      "plan_id": "plan-a", "description": "A1",
                                      "required_capability": "code",
                                      "dependencies": [], "priority": "medium", "timeout_ms": 30000}),
        _make_event("task.created", {"goal_id": "goal-b", "task_id": "b-t1",
                                      "plan_id": "plan-b", "description": "B1",
                                      "required_capability": "code",
                                      "dependencies": [], "priority": "medium", "timeout_ms": 30000}),
    ]

    engine = EventSourcingEngine()
    state_a = engine.rebuild_from_events("goal-a", events)
    state_b = engine.rebuild_from_events("goal-b", events)

    assert state_a is not None
    assert state_a.goal_id == "goal-a"
    assert len(state_a.tasks) == 1
    assert state_a.tasks[0].task_id == "a-t1"

    assert state_b is not None
    assert state_b.goal_id == "goal-b"
    assert len(state_b.tasks) == 1
    assert state_b.tasks[0].task_id == "b-t1"

    print("  ✅ Multi-goal events correctly filtered by goal_id")


if __name__ == "__main__":
    print("=" * 60)
    print("  ZELOS v0.8.0 — REQ-02/03 EVENT SOURCING TESTS")
    print("=" * 60)
    test_apply_event_goal_submitted()
    test_apply_event_plan_created()
    test_apply_event_task_created()
    test_apply_event_task_completed()
    test_apply_event_task_failed()
    test_apply_event_goal_completed()
    test_apply_event_task_retry_scheduled()
    test_apply_event_unknown_type_noop()
    test_full_rebuild_from_event_chain()
    test_rebuild_empty_event_chain()
    test_snapshot_plus_incremental_recovery()
    test_event_replay_performance()
    test_rebuild_filters_by_goal_id()
    test_sequence_id_monotonic()
    test_replay_from_sequence_id()
    test_sequence_id_backward_compat()
    print(f"\n{'=' * 60}")
    print("  RESULTS: All REQ-02/03 event sourcing tests passed ✅")
    print(f"{'=' * 60}")
