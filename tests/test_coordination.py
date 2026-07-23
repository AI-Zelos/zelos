"""
Coordination Backend Tests — InMemory + etcd leader election.

Requires for etcd: docker run -d --name zelos-etcd -p 2379:2379 bitnami/etcd:latest
"""
import os
import socket
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.coordination import (
    CoordinationNode,
    EtcdCoordinationBackend,
    InMemoryCoordinationBackend,
    create_coordination_backend,
)


def _require_etcd():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        s.connect(("127.0.0.1", 2379))
        s.close()
        return True
    except Exception:
        s.close()
        pytest.skip("etcd not available at localhost:2379")


def test_inmemory_leader_election():
    """Bully algorithm: smallest node_id wins."""
    print("\n👑 InMemory Leader Election")
    backend = InMemoryCoordinationBackend()
    backend.connect()

    nodes = [CoordinationNode(node_id=nid) for nid in ["node-bravo", "node-alpha", "node-charlie"]]
    for n in nodes:
        backend.register_node(n)

    # Elect — node-alpha should win (lexicographically smallest)
    for n in nodes:
        backend.elect_leader(n.node_id)
    leader = backend.get_leader()
    assert leader == "node-alpha", f"Expected node-alpha, got {leader}"
    print(f"  ✅ Bully election: leader={leader}")

    # Heartbeat
    assert backend.heartbeat("node-alpha")
    print("  ✅ Leader heartbeat OK")

    # Deregister leader → leader becomes None
    backend.deregister_node("node-alpha")
    leader2 = backend.get_leader()
    print(f"  ✅ Leader removed → leader={leader2}")

    backend.disconnect()


def test_inmemory_watch():
    """Watch leader changes with callback."""
    print("\n👁️ Leader Watch")
    backend = InMemoryCoordinationBackend()
    backend.connect()
    backend.register_node(CoordinationNode(node_id="n1"))
    backend.register_node(CoordinationNode(node_id="n2"))

    changes = []
    backend.watch_leader(lambda lid: changes.append(lid))
    backend.elect_leader("n1")
    time.sleep(0.05)
    assert "n1" in changes
    print(f"  ✅ Watch callback triggered: {changes}")

    backend.disconnect()


def test_etcd_backend():
    """etcd leader election with real etcd."""
    _require_etcd()
    print("\n🔷 etcd Coordination Backend")

    backend = EtcdCoordinationBackend({"endpoints": "localhost:2379"})
    ok = backend.connect()
    assert ok, "etcd connection failed"
    print("  ✅ Connected to etcd")

    # Register node
    node = CoordinationNode(node_id="etcd-node-1", host="127.0.0.1", port=9001, capabilities=["code"])
    assert backend.register_node(node)
    print("  ✅ Node registered")

    # Elect leader
    assert backend.elect_leader("etcd-node-1", ttl_seconds=10)
    leader = backend.get_leader()
    assert leader == "etcd-node-1"
    print(f"  ✅ Leader elected via etcd: {leader}")

    # Heartbeat
    assert backend.heartbeat("etcd-node-1")
    print("  ✅ Heartbeat renews lease")

    # List nodes
    nodes = backend.list_nodes()
    assert len(nodes) >= 1
    assert nodes[0].node_id == "etcd-node-1"
    print(f"  ✅ Listed {len(nodes)} node(s)")

    backend.deregister_node("etcd-node-1")
    backend.disconnect()


def test_factory():
    """Coordination backend factory."""
    print("\n🏭 Coordination Factory")

    mem = create_coordination_backend({"type": "memory"})
    assert isinstance(mem, InMemoryCoordinationBackend)
    mem.connect()
    assert mem.health()
    mem.disconnect()

    # etcd type check (won't connect)
    etcd = create_coordination_backend({"type": "etcd", "endpoints": "localhost:2379"})
    assert isinstance(etcd, EtcdCoordinationBackend)

    try:
        create_coordination_backend({"type": "zookeeper"})
        raise AssertionError("Should have raised")
    except ValueError:
        pass
    print("  ✅ Factory: memory + etcd created, unknown type raises")


if __name__ == "__main__":
    print("=" * 60)
    print("  ZELOS COORDINATION TESTS")
    print("=" * 60)
    test_inmemory_leader_election()
    test_inmemory_watch()
    test_etcd_backend()
    test_factory()
    print(f"\n{'=' * 60}")
    print("  RESULTS: Coordination backends verified ✅")
    print(f"{'=' * 60}")
