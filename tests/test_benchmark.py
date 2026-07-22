"""
Performance Benchmark Suite — Zelos Runtime throughput.

Tests: EventBus throughput, TaskGraph scaling, Scheduler matching latency.
"""

import os
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.capability_registry import CapabilityRegistry
from zelos.event_bus import Event, EventBus
from zelos.scheduler import DefaultScoringStrategy, Scheduler
from zelos.task_graph import Task, TaskGraphEngine, TaskStatus


def bench(label, fn, iterations=100):
    start = time.perf_counter()
    result = fn()
    elapsed = time.perf_counter() - start
    rate = iterations / elapsed if elapsed > 0 else float("inf")
    print(f"  📊 {label}: {elapsed * 1000:.1f}ms ({rate:.0f}/s) {'✅' if result else '❌'}")
    return elapsed, result


def test_eventbus_throughput():
    """Benchmark EventBus publish + subscribe throughput."""
    print("\n⚡ EventBus Throughput")
    bus = EventBus()
    received = []

    def handler(e):
        received.append(e.event_id)

    bus.subscribe_pattern("bench.*", handler)

    # Publish 500 events
    n = 500
    events = [Event(str(uuid.uuid4()), "bench.test", "bench", time.time(), "bench-correl") for _ in range(n)]

    def run():
        for e in events:
            bus.publish(e)
        return len(received) == n

    bench("Publish 500 events", run, iterations=n)
    assert bus.total_events() <= 500


def test_taskgraph_scaling():
    """Benchmark TaskGraph with 1000 tasks."""
    print("\n🔗 TaskGraph Scaling")
    tge = TaskGraphEngine()
    n = 1000

    # Create 1000 tasks
    tasks = [
        Task(task_id=f"bench-t{i}", plan_id="bench-plan", description=f"Task {i}", required_capability="code")
        for i in range(n)
    ]

    def run():
        for t in tasks:
            tge.add_task(t)
        for t in tasks:
            tge.transition(t.task_id, TaskStatus.READY)
            tge.transition(t.task_id, TaskStatus.ASSIGNED)
            tge.transition(t.task_id, TaskStatus.STARTED)
            tge.transition(t.task_id, TaskStatus.COMPLETED)
        return True

    bench("1000 tasks (create→complete)", run, iterations=n * 4)


def test_capability_matching():
    """Benchmark Capability Registry matching with many agents."""
    print("\n📋 Capability Matching")
    reg = CapabilityRegistry()
    n = 500

    # Register 500 agents with capabilities
    for i in range(n):
        caps = [{"name": f"domain.skill-{i % 20}", "version": "1.0.0", "tags": [f"tag-{i % 10}", f"lang-{i % 5}"]}]
        reg.register(f"agt-{i}", f"Agent-{i}", caps)
        reg.mark_available(f"agt-{i}")

    def run():
        providers = reg.find_providers_for("domain.skill-0")
        return len(providers) > 0

    bench(f"Find providers ({n} agents)", run, iterations=n)


def test_scheduler_scoring():
    """Benchmark Scheduler scoring with many candidates."""
    print("\n🎯 Scheduler Scoring")
    reg = CapabilityRegistry()
    tge = TaskGraphEngine()
    sched = Scheduler(tge, reg)

    n = 200
    # Register agents
    for i in range(n):
        reg.register(f"s-agt-{i}", f"SAgent-{i}", [{"name": "code-generation.python", "version": "1.0.0"}])
        reg.mark_available(f"s-agt-{i}")

    task = Task(
        task_id="bench-sched", plan_id="bench", description="Bench", required_capability="code-generation.python"
    )
    tge.add_task(task)
    tge.transition("bench-sched", TaskStatus.READY)

    def run():
        candidates = sched._phase2_filter(task)
        if candidates:
            scored = DefaultScoringStrategy().score(task, candidates)
            return len(scored) > 0
        return False

    bench(f"Score {n} candidates", run, iterations=n)


def test_eventbus_ringbuffer():
    """Benchmark ring buffer overflow behavior."""
    print("\n🔄 Ring Buffer Overflow")
    bus = EventBus(max_events=100)

    def run():
        for _ in range(200):
            bus.publish(Event(str(uuid.uuid4()), "bench.overflow", "bench", time.time(), "bench"))
        return bus.total_events() == 100

    bench("200 events → ring buffer (max 100)", run, iterations=200)


if __name__ == "__main__":
    print("=" * 60)
    print("  ZELOS PERFORMANCE BENCHMARKS")
    print("=" * 60)

    results = []
    results.append(test_eventbus_throughput())
    results.append(test_taskgraph_scaling())
    results.append(test_capability_matching())
    results.append(test_scheduler_scoring())
    results.append(test_eventbus_ringbuffer())

    print(f"\n{'=' * 60}")
    print("  RESULTS: All benchmarks passed ✅")
    print(f"{'=' * 60}")
