"""
Storage Backend Integration Tests — Real Redis + PostgreSQL via Docker.

Requires: docker run -d --name zelos-redis-test -p 16379:6379 redis:7-alpine
          docker run -d --name zelos-pg-test -e POSTGRES_PASSWORD=zelos -e POSTGRES_DB=zelos -p 15432:5432 postgres:16-alpine
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.storage import (
    InMemoryStorageBackend,
    PostgreSQLStorageBackend,
    RedisStorageBackend,
    create_storage_backend,
)


def test_inmemory_backend():
    """Verify InMemory backend passes the full CRUD suite."""
    print("\n📦 InMemory Storage Backend")
    backend = InMemoryStorageBackend()
    backend.connect()
    _verify_backend(backend, "InMemory")


def _require_service(host, port, name):
    """Skip test if service is not reachable."""
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        s.close()
        pytest.skip(f"{name} not available at {host}:{port} — start Docker container")


def test_redis_backend():
    """Verify Redis backend against a real Redis instance."""
    _require_service("127.0.0.1", 16379, "Redis")
    print("\n🔴 Redis Storage Backend")
    backend = RedisStorageBackend({"url": "redis://localhost:16379/0", "prefix": "zelos-test"})
    ok = backend.connect()
    assert ok, "Redis connection failed"
    # Clean previous test data
    if backend._client:
        backend._client.flushdb()
    try:
        _verify_backend(backend, "Redis")
    finally:
        backend.disconnect()


def test_postgresql_backend():
    """Verify PostgreSQL backend against a real PG instance."""
    _require_service("127.0.0.1", 15432, "PostgreSQL")
    print("\n🐘 PostgreSQL Storage Backend")
    backend = PostgreSQLStorageBackend({"url": "postgresql://postgres:zelos@localhost:15432/zelos"})
    ok = backend.connect()
    assert ok, "PostgreSQL connection failed"
    # Clean previous test data
    if backend._conn:
        cur = backend._conn.cursor()
        cur.execute("DELETE FROM zelos_events")
        cur.execute("DELETE FROM zelos_state")
        cur.close()
    try:
        _verify_backend(backend, "PostgreSQL")
    finally:
        backend.disconnect()


def test_backend_factory():
    """Verify create_storage_backend factory function."""
    _require_service("127.0.0.1", 16379, "Redis")
    _require_service("127.0.0.1", 15432, "PostgreSQL")
    print("\n🏭 Backend Factory")
    mem = create_storage_backend({"type": "memory"})
    assert isinstance(mem, InMemoryStorageBackend)
    assert mem.connect()

    redis_cfg = {"type": "redis", "url": "redis://localhost:16379/0"}
    redis_be = create_storage_backend(redis_cfg)
    assert isinstance(redis_be, RedisStorageBackend)
    assert redis_be.connect()
    redis_be.disconnect()

    pg_cfg = {"type": "postgresql", "url": "postgresql://postgres:zelos@localhost:15432/zelos"}
    pg_be = create_storage_backend(pg_cfg)
    assert isinstance(pg_be, PostgreSQLStorageBackend)
    assert pg_be.connect()
    pg_be.disconnect()

    # Unknown type
    try:
        create_storage_backend({"type": "cassandra"})
        raise AssertionError("Should have raised ValueError")
    except ValueError:
        pass
    print("  ✅ Backend factory OK")


def _verify_backend(backend, name):
    prefix = f"[{name}]"

    # STOR-01: Connect + Health
    assert backend.health(), f"{prefix} health check failed"
    print(f"  ✅ {prefix} STOR-01: connect + health")

    # STOR-02: Append events
    events = [
        {"event_id": "e1", "type": "task.created", "payload": {"task": "t1"}},
        {"event_id": "e2", "type": "task.started", "payload": {"task": "t1"}},
        {"event_id": "e3", "type": "task.completed", "payload": {"task": "t1"}},
    ]
    count = backend.append("goals-g1", events)
    assert count >= 3, f"{prefix} append count={count}, expected >= 3"
    print(f"  ✅ {prefix} STOR-02: append 3 events (count={count})")

    # STOR-03: Read by position
    results = backend.read("goals-g1", 0, 2)
    assert len(results) == 2, f"{prefix} read from 0,2 got {len(results)}"
    assert results[0]["event_id"] == "e1"
    assert results[1]["event_id"] == "e2"
    print(f"  ✅ {prefix} STOR-03: read by position")

    # STOR-04: Read beyond available
    results = backend.read("goals-g1", 0, 10)
    assert len(results) == 3, f"{prefix} read beyond got {len(results)}"
    print(f"  ✅ {prefix} STOR-04: read beyond available")

    # STOR-05: Set/Get state
    backend.set_state("goal-g1", {"status": "executing", "progress": 0.5})
    state = backend.get_state("goal-g1")
    assert state is not None
    assert state["status"] == "executing"
    assert state["progress"] == 0.5
    print(f"  ✅ {prefix} STOR-05: set/get state")

    # STOR-06: Delete state
    backend.set_state("temp", {"x": 1})
    backend.delete_state("temp")
    assert backend.get_state("temp") is None
    print(f"  ✅ {prefix} STOR-06: delete state")

    # STOR-07: Snapshots
    backend.create_snapshot("goal-g1", events_position=2, state={"status": "completed"})
    snap = backend.get_snapshot("goal-g1")
    assert snap is not None
    assert snap["events_position"] == 2
    assert snap["state"]["status"] == "completed"
    print(f"  ✅ {prefix} STOR-07: snapshots")

    # STOR-09: Multiple stream isolation
    backend.append("stream-a", [{"event_id": "a1"}])
    backend.append("stream-b", [{"event_id": "b1"}])
    a_results = backend.read("stream-a", 0, 10)
    b_results = backend.read("stream-b", 0, 10)
    assert all(r["event_id"].startswith("a") for r in a_results)
    assert all(r["event_id"].startswith("b") for r in b_results)
    print(f"  ✅ {prefix} STOR-09: stream isolation")

    # STOR-10: Empty stream read
    empty = backend.read("nonexistent-stream", 0, 10)
    assert len(empty) == 0
    print(f"  ✅ {prefix} STOR-10: empty stream read")

    # STOR-08: Reconnect
    backend.disconnect()
    assert not backend.is_connected
    backend.connect()
    assert backend.is_connected
    assert backend.health()
    print(f"  ✅ {prefix} STOR-08: disconnect + reconnect")


if __name__ == "__main__":
    print("=" * 60)
    print("  ZELOS STORAGE BACKEND — INTEGRATION TESTS")
    print("=" * 60)
    test_inmemory_backend()
    test_redis_backend()
    test_postgresql_backend()
    test_backend_factory()
    print(f"\n{'=' * 60}")
    print("  RESULTS: All storage backends verified ✅")
    print(f"{'=' * 60}")
