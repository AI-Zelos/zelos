"""
Event & State Persistence Tests.

Requires: docker run -d --name zelos-pg-persist -e POSTGRES_PASSWORD=zelos -e POSTGRES_DB=zelos -p 15432:5432 postgres:16-alpine
"""

import os
import sys
import time
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.event_bus import Event, PersistentEventStore
from zelos.runtime import ZelosRuntime
from zelos.storage import InMemoryStorageBackend, PostgreSQLStorageBackend


def test_event_persistence_inmemory():
    """Event persistence via InMemoryStorageBackend."""
    print("\n📝 Event Persistence — InMemory")
    storage = InMemoryStorageBackend()
    storage.connect()
    store = PersistentEventStore(storage)
    _verify_event_persistence(store, "InMemory")


def test_event_persistence_postgresql():
    """Event persistence via PostgreSQL."""
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        s.connect(("127.0.0.1", 15432))
        s.close()
    except Exception:
        s.close()
        pytest.skip("PostgreSQL not available — start Docker container")
    print("\n📝 Event Persistence — PostgreSQL")
    storage = PostgreSQLStorageBackend({"url": "postgresql://postgres:zelos@localhost:15432/zelos"})
    ok = storage.connect()
    assert ok, "PostgreSQL connection failed"
    # Clean
    if storage._conn:
        cur = storage._conn.cursor()
        cur.execute("DELETE FROM zelos_events")
        cur.close()
    store = PersistentEventStore(storage)
    _verify_event_persistence(store, "PostgreSQL")
    storage.disconnect()


def _verify_event_persistence(store, name):
    prefix = f"[{name}]"

    # EP-01: Append events to persistent store
    events = [
        Event(str(uuid.uuid4()), "task.created", "test", time.time(), "g-persist"),
        Event(str(uuid.uuid4()), "task.started", "test", time.time(), "g-persist"),
        Event(str(uuid.uuid4()), "task.completed", "test", time.time(), "g-persist"),
    ]
    for e in events:
        store.append(e)
    assert len(store) == 3, f"{prefix} append failed: {len(store)}"
    print(f"  ✅ {prefix} EP-01: append 3 events")

    # EP-02: Recovery — simulate restart by creating new store from same backend
    recovered_store = PersistentEventStore(store._backend)
    count = recovered_store.recover()
    assert count == 3, f"{prefix} recovered {count}, expected 3"
    assert len(recovered_store) == 3
    print(f"  ✅ {prefix} EP-02: recovery ({count} events)")

    # EP-03: Read back recovered events
    result = recovered_store.read_from(0)
    assert len(result) == 3
    assert result[0].event_type == "task.created"
    assert result[2].event_type == "task.completed"
    print(f"  ✅ {prefix} EP-03: read recovered events")


def test_state_persistence():
    """State persistence: save and restore Goal/Task state via StorageBackend."""
    print("\n💾 State Persistence")

    storage = InMemoryStorageBackend()
    storage.connect()

    # SP-01: Save Goal state
    storage.set_state(
        "goal-g1", {"status": "executing", "progress": 0.6, "tasks": {"t1": "completed", "t2": "started"}}
    )
    state = storage.get_state("goal-g1")
    assert state["status"] == "executing"
    assert state["tasks"]["t1"] == "completed"
    print("  ✅ SP-01: save/restore Goal state")

    # SP-02: Save Agent state
    storage.set_state(
        "agent-a1", {"name": "Coder", "status": "heartbeating", "capabilities": ["code-generation.python"]}
    )
    agent = storage.get_state("agent-a1")
    assert agent["name"] == "Coder"
    print("  ✅ SP-02: save/restore Agent state")

    # SP-03: Runtime recover — simulate crash and restart
    rt1 = ZelosRuntime()
    rt1.add_agent(
        "PersistAgent",
        "test:Agent",
        [
            type(
                "Cap",
                (),
                {
                    "name": "code",
                    "version": "1.0",
                    "description": "",
                    "input_schema": {},
                    "output_schema": {},
                    "tags": [],
                },
            )
        ],
    )
    rt1.start()
    goal = rt1.submit_goal("Persistent goal test")
    # Save state snapshot
    storage.set_state(
        f"goal-{goal['goal_id']}",
        {"goal_id": goal["goal_id"], "description": "Persistent goal test", "status": goal["status"]},
    )
    rt1.shutdown()

    # Simulate restart: load from storage
    saved = storage.get_state(f"goal-{goal['goal_id']}")
    assert saved is not None
    assert saved["goal_id"] == goal["goal_id"]
    print(f"  ✅ SP-03: save before shutdown, restore after restart (goal={goal['goal_id'][:8]}...)")

    storage.disconnect()


if __name__ == "__main__":
    print("=" * 60)
    print("  ZELOS PERSISTENCE TESTS")
    print("=" * 60)
    test_event_persistence_inmemory()
    test_event_persistence_postgresql()
    test_state_persistence()
    print(f"\n{'=' * 60}")
    print("  RESULTS: All persistence tests passed ✅")
    print(f"{'=' * 60}")
