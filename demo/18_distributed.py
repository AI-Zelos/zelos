"""
Demo 18: Distributed Runtime — Leader Election + Work Stealing + Node Registry

Demonstrates Phase 3 distributed runtime features:
  - Leader election with heartbeat
  - Work stealing across nodes
  - Node registry and cluster health

Run: python3 demo/18_distributed.py
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.distributed import (
    LeaderElection, WorkStealing, NodeRegistry, ClusterNode, LeaderState,
)


def main():
    print("=" * 60)
    print("  DEMO 18: Distributed Runtime — Cluster Coordination")
    print("=" * 60)

    # ── 1. Leader Election ──
    print("\n👑 1. Leader Election")

    # Simulate 3-node cluster
    nodes = {
        "zelos-01": LeaderElection("zelos-01", heartbeat_interval_ms=200),
        "zelos-02": LeaderElection("zelos-02", heartbeat_interval_ms=200),
        "zelos-03": LeaderElection("zelos-03", heartbeat_interval_ms=200),
    }

    # Register peers
    for nid, node in nodes.items():
        for other_id in nodes:
            if other_id != nid:
                node.register_peer(other_id)

    # Start all nodes
    for node in nodes.values():
        node.start()

    time.sleep(0.5)

    # Check election results
    print("   Cluster election results:")
    for nid, node in nodes.items():
        crown = "👑 LEADER" if node.is_leader() else "  follower"
        print(f"     {nid}: {node.state.value:12s} {crown}")

    # Find leader
    leader = next((nid for nid, n in nodes.items() if n.is_leader()), None)
    print(f"\n   Elected leader: {leader}")

    # ── 2. Work Stealing ──
    print("\n🔄 2. Work Stealing — Load Balancing")

    # Three worker nodes with different loads
    worker_a = WorkStealing("worker-a", max_concurrent_tasks=10)
    worker_b = WorkStealing("worker-b", max_concurrent_tasks=10)
    worker_c = WorkStealing("worker-c", max_concurrent_tasks=10)

    # Worker A: heavily loaded (8 tasks)
    for i in range(8):
        worker_a.enqueue_task(f"heavy-{i}", "code-generation.python", priority="high")
    print(f"   worker-a load: {worker_a.queue_size()} tasks ({worker_a.get_load_percent():.0f}%)")

    # Worker B: idle (0 tasks)
    print(f"   worker-b load: {worker_b.queue_size()} tasks ({worker_b.get_load_percent():.0f}%)")

    # Worker C: moderately loaded (3 tasks)
    for i in range(3):
        worker_c.enqueue_task(f"moderate-{i}", "automation.browser", priority="medium")
    print(f"   worker-c load: {worker_c.queue_size()} tasks ({worker_c.get_load_percent():.0f}%)")

    # Worker B steals from Worker A
    print(f"\n   worker-b steals from worker-a...")
    stolen = worker_b.steal_from(worker_a, max_count=4)
    print(f"   Stolen tasks: {len(stolen)}")
    print(f"   worker-a after: {worker_a.queue_size()} tasks ({worker_a.get_load_percent():.0f}%)")
    print(f"   worker-b after: {worker_b.queue_size()} tasks ({worker_b.get_load_percent():.0f}%)")

    # Worker C also steals
    stolen2 = worker_c.steal_from(worker_a, max_count=2)
    print(f"\n   worker-c steals from worker-a...")
    print(f"   Stolen tasks: {len(stolen2)}")
    print(f"   worker-a after: {worker_a.queue_size()} tasks ({worker_a.get_load_percent():.0f}%)")
    print(f"   worker-c after: {worker_c.queue_size()} tasks ({worker_c.get_load_percent():.0f}%)")

    # ── 3. Node Registry ──
    print("\n📋 3. Node Registry & Cluster Health")

    nr = NodeRegistry()

    # Register cluster nodes
    cluster_nodes = [
        ("zelos-primary", "10.0.1.10", 9876,
         ["code-generation.python", "code-generation.typescript", "code-review.security"],
         20),
        ("zelos-worker-1", "10.0.1.11", 9876,
         ["automation.browser", "data-analysis.sql"], 10),
        ("zelos-worker-2", "10.0.1.12", 9876,
         ["code-generation.python", "research.analysis"], 10),
        ("zelos-worker-3", "10.0.1.13", 9876,
         ["code-review.security", "automation.browser", "code-generation.rust"], 15),
    ]

    for nid, host, port, caps, cap in cluster_nodes:
        node = ClusterNode(
            node_id=nid, host=host, port=port,
            capabilities=caps, capacity=cap,
        )
        nr.register(node)
        nr.heartbeat(nid)

    # Simulate one dead node
    nr.heartbeat("zelos-worker-2",
                 timestamp=time.time() - 3600)

    print(f"   Cluster size: {nr.node_count()} nodes")
    print(f"\n   Node details:")
    for node in nr.list_nodes():
        status_icon = {"healthy": "🟢", "degraded": "🟡", "dead": "🔴", "unknown": "⚪"}
        print(f"     {status_icon.get(node.status, '⚪')} {node.node_id:16s} "
              f"({node.host}:{node.port}) — {node.status:8s} "
              f"capacity={node.capacity}")

    # Dead node detection
    dead = nr.detect_dead_nodes(timeout_seconds=60)
    print(f"\n   Dead nodes detected: {dead}")

    # Capability lookup
    print(f"\n   Capability: 'code-generation.python'")
    python_nodes = nr.find_by_capability("code-generation.python")
    for n in python_nodes:
        print(f"     → {n.node_id} ({n.host}:{n.port}) — status: {n.status}")

    # Cluster status
    status = nr.cluster_status()
    print(f"\n   Cluster status:")
    print(f"     Total: {status['total_nodes']} nodes")
    print(f"     Healthy: {status['healthy_nodes']} | Degraded: {status['degraded_nodes']} | Dead: {status['dead_nodes']}")
    print(f"     Capacity: {status['total_capacity']} concurrent tasks")
    print(f"     Capabilities: {', '.join(status['cluster_capabilities'])}")

    # ── 4. Shutdown ──
    for node in nodes.values():
        node.stop()

    print(f"\n{'=' * 60}")
    print(f"  Demo complete. Distributed runtime primitives working.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
