"""
Message Bus Tests — InMemory + NATS pub/sub, pattern matching, request-reply.

Requires for NATS: docker run -d --name zelos-nats -p 4222:4222 nats:latest
"""
import os
import socket
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.messaging_nats import (
    InMemoryMessageBus,
    NatsMessageBus,
    create_message_bus,
)


def _require_nats():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        s.connect(("127.0.0.1", 4222))
        s.close()
        return True
    except Exception:
        s.close()
        pytest.skip("NATS not available at localhost:4222")


def test_inmemory_pub_sub():
    """Basic publish-subscribe with InMemory bus."""
    print("\n📨 InMemory Pub/Sub")
    bus = InMemoryMessageBus()
    bus.connect()

    received = []
    bus.subscribe("task.created", lambda d, h: received.append(d))
    bus.publish("task.created", {"task_id": "t1", "capability": "code"})
    bus.publish("task.completed", {"task_id": "t1"})

    assert len(received) == 1
    assert received[0]["task_id"] == "t1"
    print(f"  ✅ Exact match: 1/2 events received ({received[0]['task_id']})")
    bus.disconnect()


def test_inmemory_pattern():
    """Wildcard pattern subscription."""
    print("\n🔍 Pattern Matching")
    bus = InMemoryMessageBus()
    bus.connect()

    received = []
    bus.subscribe("task.*", lambda d, h: received.append(d))

    for etype in ["task.created", "task.started", "task.completed", "goal.submitted"]:
        bus.publish(etype, {"event": etype})

    assert len(received) == 3  # task.* matches 3, goal.* doesn't
    print(f"  ✅ Pattern 'task.*': {len(received)}/4 matched (goal.submitted excluded)")
    bus.disconnect()


def test_inmemory_request_reply():
    """Request-reply pattern."""
    print("\n🔄 Request-Reply")
    bus = InMemoryMessageBus()
    bus.connect()

    def handler(data, headers):
        reply = headers.get("reply")
        if reply:
            bus.publish(reply, {"answer": f"Processed: {data.get('question')}"})

    bus.subscribe("query", handler)
    result = bus.request("query", {"question": "status?"}, timeout=1.0)

    assert result is not None
    assert "Processed" in result["answer"]
    print(f"  ✅ Request-reply: {result['answer']}")
    bus.disconnect()


def test_inmemory_multi_subscriber():
    """Multiple subscribers to same subject — all receive."""
    print("\n👥 Multi-Subscriber")
    bus = InMemoryMessageBus()
    bus.connect()

    results = [[], []]
    bus.subscribe("alert", lambda d, h: results[0].append(d))
    bus.subscribe("alert", lambda d, h: results[1].append(d))
    bus.publish("alert", {"msg": "fire!"})

    assert len(results[0]) == 1 and len(results[1]) == 1
    print("  ✅ Both subscribers received the event")
    bus.disconnect()


def test_nats_backend():
    """NATS pub/sub with real NATS server."""
    _require_nats()
    print("\n🔷 NATS Message Bus")

    bus = NatsMessageBus({"servers": ["nats://localhost:4222"]})
    ok = bus.connect()
    assert ok, "NATS connection failed"
    print("  ✅ Connected to NATS")

    received = []
    bus.subscribe("zelos.test", lambda d, h: received.append(d))
    bus.publish("zelos.test", {"event": "test", "value": 42})
    time.sleep(0.2)

    assert len(received) >= 1
    assert received[0]["value"] == 42
    print(f"  ✅ NATS pub/sub: received {len(received)} message(s)")

    assert bus.health()
    bus.disconnect()
    assert not bus.health()


def test_factory():
    """Message bus factory."""
    print("\n🏭 Message Bus Factory")

    mem = create_message_bus({"type": "memory"})
    assert isinstance(mem, InMemoryMessageBus)
    mem.connect()
    assert mem.health()
    mem.disconnect()

    nats = create_message_bus({"type": "nats"})
    assert isinstance(nats, NatsMessageBus)

    try:
        create_message_bus({"type": "rabbitmq"})
        raise AssertionError("Should have raised")
    except ValueError:
        pass
    print("  ✅ Factory: memory + nats, unknown type raises")


if __name__ == "__main__":
    print("=" * 60)
    print("  ZELOS MESSAGE BUS TESTS")
    print("=" * 60)
    test_inmemory_pub_sub()
    test_inmemory_pattern()
    test_inmemory_request_reply()
    test_inmemory_multi_subscriber()
    test_nats_backend()
    test_factory()
    print(f"\n{'=' * 60}")
    print("  RESULTS: Message bus verified ✅")
    print(f"{'=' * 60}")
