#!/usr/bin/env python3
"""
Demo 12: 可观测性 — 结构化日志 + 指标 + 追踪

展示 StructuredLogger / MetricsCollector / Tracer 的实际产出。

用法: python3 demo/12_observability.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.observability import StructuredLogger, MetricsCollector, Tracer


def main():
    print("=" * 60)
    print("  Demo 12: 可观测性 — 日志 + 指标 + 追踪")
    print("=" * 60)

    # ── 结构化日志 ──
    print("\n📝 结构化日志 (JSON):")
    logger = StructuredLogger(level="info", format="json")
    log_lines = []
    for msg, ctx in [("Runtime started", {"version": "0.2.0"}),
                      ("Goal submitted", {"goal_id": "g-001", "priority": "high"}),
                      ("Task dispatched", {"task_id": "t1", "agent": "ClaudeCode"}),
                      ("Task completed", {"task_id": "t1", "duration_ms": 3500}),
                      ("Goal completed", {"goal_id": "g-001", "total_tasks": 3})]:
        line = logger.info(msg, **ctx)
        if line:
            parsed = json.loads(line)
            print(f"  [{parsed['level']}] {parsed['message']}")
            log_lines.append(parsed)
    print(f"  → {len(log_lines)} 条 JSON 日志")

    # ── 指标收集 ──
    print("\n📊 指标:")
    mc = MetricsCollector()

    c = mc.counter("task_completed_total", "Total completed tasks")
    for _ in range(42): c.inc()

    f = mc.counter("task_failed_total", "Total failed tasks")
    for _ in range(3): f.inc()

    g = mc.gauge("agents_connected", "Currently connected agents")
    g.set(4)

    h = mc.histogram("task_duration_ms", "Task execution duration")
    for v in [120, 180, 250, 400, 500, 600, 800, 1200, 2000, 3500]:
        h.observe(v)

    all_m = mc.get_all()
    print(f"  task_completed_total: {all_m['counters']['task_completed_total']}")
    print(f"  task_failed_total: {all_m['counters']['task_failed_total']}")
    print(f"  agents_connected: {all_m['gauges']['agents_connected']}")
    print(f"  task_duration p50: {all_m['histograms']['task_duration_ms']['p50']}ms")
    print(f"  task_duration p95: {all_m['histograms']['task_duration_ms']['p95']}ms")

    print("\n📈 Prometheus 格式:")
    prom = mc.export_prometheus()
    for line in prom.strip().split("\n")[:5]:
        print(f"  {line}")

    # ── 追踪 ──
    print("\n🔍 分布式追踪:")
    tracer = Tracer()

    root = tracer.start_span("goal.execute")
    root.set_attribute("goal_id", "g-001")
    root.add_event("planned", plan_id="p-001")

    child1 = tracer.start_span("task.dispatch")
    child1.set_attribute("task_id", "t1")
    child1.set_attribute("agent", "ClaudeCode")
    child1.add_event("dispatched")
    tracer.end_span()

    child2 = tracer.start_span("task.dispatch")
    child2.set_attribute("task_id", "t2")
    tracer.end_span()

    root.add_event("all_tasks_complete")
    tracer.end_span()

    for s in tracer.get_spans():
        indent = "  " if s.parent_id else ""
        print(f"  {indent}▸ {s.name} ({s.duration_ms:.1f}ms)")
        if s.parent_id:
            print(f"       parent={s.parent_id}")

    print(f"\n✅ Demo 12 完成")


if __name__ == "__main__":
    main()
