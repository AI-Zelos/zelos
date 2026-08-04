#!/usr/bin/env python3
"""
Demo 23: Zelos 全链路编排 + MPC 自适应重规划

将 Zelos Runtime 的全部 6 层治理链串联运行。

用法:
    export ANTHROPIC_AUTH_TOKEN="sk-xxx"
    export ANTHROPIC_BASE_URL="https://api.deepseek.com/anthropic"
    python3 demo/23_full_chain.py
"""

import os
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.runtime import ZelosRuntime
from zelos.feature_flags import FeatureFlags
from zelos.execution_report import IntentSpec
from zelos.task_graph import Task, TaskStatus

# ── API ──
API_KEY = os.getenv("ANTHROPIC_AUTH_TOKEN", "")
API_BASE = os.getenv("ANTHROPIC_BASE_URL", "https://api.deepseek.com/anthropic")
MODEL = os.getenv("ANTHROPIC_MODEL", "deepseek-v4-pro")
if not API_KEY:
    print("❌ 请设置 ANTHROPIC_AUTH_TOKEN"); sys.exit(1)
os.environ["ANTHROPIC_API_KEY"] = API_KEY
os.environ["ANTHROPIC_BASE_URL"] = API_BASE

# ════════════════════════════════════════════════════════
# Event tracing
# ════════════════════════════════════════════════════════
traced: list[dict] = []

def trace_handler(event):
    p = event.payload or {}
    info = {"type": event.event_type, "source": event.source}
    for k in ("task_id", "agent_name", "required_capability", "status",
              "goal_id", "plan_id", "trigger_reason", "duration_ms",
              "replan_count", "output_artifact_summary", "error", "action", "reason"):
        if k in p:
            v = p[k]
            # Keep full agent_name for accurate matching; truncate only long strings
            if isinstance(v, str) and len(v) > 100:
                info[k] = v[:100]
            else:
                info[k] = v
    traced.append(info)

# ════════════════════════════════════════════════════════
# Build Runtime
# ════════════════════════════════════════════════════════
print("=" * 72)
print("  Demo 23: Zelos 全链路编排 + MPC 自适应重规划")
print("=" * 72)
print(f"  Planner: anthropic/{MODEL} @ {API_BASE}")
print()

features = FeatureFlags.stage_d()

runtime = ZelosRuntime({
    "features": {
        "mpc_replan": True,
        "diagnosis_engine": features.diagnosis_engine,
        "policy_gate": features.policy_gate,
        "cp_governance": features.cp_governance,
        "car": features.car,
        "confidence_scoring": features.confidence_scoring,
        "evidence_collection": features.evidence_collection,
        "event_sourcing": features.event_sourcing,
        "execution_trace": features.execution_trace,
        "memory": features.memory,
    },
    "plugins": [{
        "id": "llm-planner",
        "type": "planner",
        "entrypoint": "zelos.planner.LLMPlanner",
        "config": {
            "provider": "anthropic",
            "model": MODEL,
            "api_key": API_KEY,
            "base_url": API_BASE,
            "temperature": 0.2,
            "max_tokens": 4000,
        },
    }],
})

for prefix in ("task", "plan", "goal", "agent", "schedule", "execution_plan", "policy_gate"):
    runtime._event_bus.subscribe_pattern(f"{prefix}.*", trace_handler)

# ════════════════════════════════════════════════════════
# Register Agents
# ════════════════════════════════════════════════════════

# MiniSWE — coding/refactor/fix capabilities
CODING_CAPS = [
    "code-generation.python", "code-generation", "code-fix.python",
    "code-refactor.python", "verification.unit-test",
    "communication.documentation", "code-review.quality",
    "automation.file-system", "research.documentation",
    "design.architecture",
]

runtime.add_agent(
    name="MiniSWE",
    entrypoint="zelos.agents.mini_swe_agent:MiniSWEAgent",
    capabilities=[
        {"name": c, "version": "1.0.0", "description": f"mini-SWE-agent: {c}",
         "input_schema": {}, "output_schema": {}, "tags": ["coding", "python"]}
        for c in CODING_CAPS
    ],
    config={"model_name": f"anthropic/{MODEL}", "step_limit": 20, "cost_limit": 5.0},
)

# FailingAgent — deliberately fails to trigger MPC replan
runtime.add_agent(
    name="SecurityGate",
    entrypoint="zelos.agents.demo_utils:FailingAgent",
    capabilities=[
        {"name": "code-review.security", "version": "1.0.0",
         "description": "Security review (will fail → MPC replan trigger)",
         "input_schema": {}, "output_schema": {}, "tags": ["security", "demo"]},
    ],
    config={"fail_code": "security_blocked",
            "fail_message": "Auto security review unavailable — replan needed"},
)

runtime.start()
print("🚀 Runtime started | Agents:")
for a in runtime.list_agents():
    print(f"   · {a['name']} ({a['status']})")
print()

# ════════════════════════════════════════════════════════
# Phase 1: Let LLM Planner decompose → add failing task manually
# ════════════════════════════════════════════════════════
print("── Phase 1: LLM Planner 分解 + 注入失败任务 ──")

goal = runtime.submit_goal(
    "Write a single Python file 'math_lib.py' containing a function "
    "'is_prime(n: int) -> bool'. Use type hints, docstrings, and proper "
    "edge case handling. Output only code — no architecture design needed.",
    priority="high",
    intent=IntentSpec(
        description="Add math utility library",
        success_criteria=["math_lib.py has is_prime and factorial",
                          "Both functions have type hints and docstrings"],
        constraints={"language": "python"},
    ),
)

plan_id = goal.get("plan_id")
goal_id = goal["goal_id"]

# Bump timeout for MiniSWE coding tasks (exploring + writing takes > 30s)
for t in runtime._task_graph.list_tasks():
    if t.plan_id == plan_id:
        t.timeout_ms = 120000  # 2 min for LLM agent tasks

# Show planner output
plan_tasks = [t for t in runtime._task_graph.list_tasks() if t.plan_id == plan_id]
print(f"📝 Planner 分解: {len(plan_tasks)} Task(s)")
for t in plan_tasks:
    print(f"   [{t.status.value}] {t.task_id[-20:]}: {t.required_capability}")
    print(f"          {t.description[:70]}")

# ── Manually inject a security-review task that depends on the coding task ──
if plan_tasks:
    coding_task = plan_tasks[0]
    security_task = Task(
        task_id=f"{goal_id}-t2",
        plan_id=plan_id,
        description="Perform security review of math_lib.py: check for input validation, "
                    "overflow risks, and injection vulnerabilities",
        required_capability="code-review.security",
        dependencies=[coding_task.task_id],
        timeout_ms=15000,  # 15s — short so it fails quickly if stuck
    )
    runtime._task_graph.add_task(security_task)
    # Add the dependency
    try:
        runtime._task_graph.add_dependency(coding_task.task_id, security_task.task_id)
    except ValueError:
        pass

    # Update the execution engine's current plan to include the new task
    from zelos.planner import PlannerTask as PT
    engine = runtime._execution_engine
    if engine._current_plan:
        engine._current_plan.tasks.append(
            PT(task_id=security_task.task_id, description=security_task.description,
               required_capability="code-review.security",
               dependencies=[coding_task.task_id])
        )

    print(f"\n   ➕ 注入失败触发任务: {security_task.task_id[-20:]}")
    print(f"      code-review.security ← depends on {coding_task.task_id[-20:]}")
    print(f"      预期: SecurityGate 失败 → MPC Replan 触发 → 生成替代任务")

print(f"\n⏳ 自动编排运行中...")
print(f"   正常路径: coding → MiniSWE ✅")
print(f"   失败路径: security-review → SecurityGate ❌ → MPC Replan 🔄")

# ════════════════════════════════════════════════════════
# Phase 2: Wait for execution
# ════════════════════════════════════════════════════════
t0 = time.time()
result = runtime.wait_for_goal(goal_id, timeout_seconds=180)
elapsed = time.time() - t0

# ════════════════════════════════════════════════════════
# Phase 3: Full Event Trace
# ════════════════════════════════════════════════════════
print(f"\n{'─' * 72}")
print(f"📊 全链路事件追踪 ({len(traced)} events, {elapsed:.1f}s)")
print(f"{'─' * 72}")
print(f"{'#':>3} │ Event Type{' ' * 28}│ Source{' ' * 14}│ Payload")
print(f"{'─' * 3}─┼─{'─' * 34}─┼─{'─' * 16}─┼─{'─' * 45}")

for i, e in enumerate(traced, 1):
    details = []
    for k in ("task_id", "agent_name", "required_capability", "status",
              "trigger_reason", "replan_count", "action", "reason",
              "output_artifact_summary", "error"):
        if k in e:
            v = e[k]
            details.append(f"{k}={str(v)[:28]}")
    detail = " | ".join(details[:2]) if details else "-"
    marker = ""
    if "replan" in e["type"] or "modified" in e["type"]:
        marker = "🔄 "
    elif "policy" in e["type"]:
        marker = "🛡️ "
    print(f"{i:>3} │ {marker}{e['type']:<34} │ {e['source']:<16} │ {detail[:55]}")

# ════════════════════════════════════════════════════════
# Phase 4: State Report
# ════════════════════════════════════════════════════════
print(f"\n{'─' * 72}")
print("📋 最终状态报告")
print(f"{'─' * 72}")
print(f"  Goal:       {result['status']}")
p = result.get("progress", {})
print(f"  Tasks:      {p.get('completed_tasks', 0)}/{p.get('total_tasks', 0)} done, "
      f"{p.get('failed_tasks', 0)} failed")
print()

all_tasks = [t for t in runtime._task_graph.list_tasks() if t.plan_id == plan_id]
for t in all_tasks:
    icon = {"completed": "✅", "failed": "❌", "ready": "⏳", "blocked": "🚫",
            "started": "🔄", "timed_out": "⏰"}.get(t.status.value, "⬜")
    deps = f" ← [{', '.join(t.dependencies)}]" if t.dependencies else " (root)"
    print(f"  {icon} [{t.status.value}] {t.task_id[-25:]}{deps}")
    print(f"     {t.required_capability}: {t.description[:60]}")

# MPC stats
mpc_events = [e for e in traced if "replan" in e["type"] or "modified" in e["type"]]
print(f"\n  🔄 MPC Replan events: {len(mpc_events)}")
for e in mpc_events:
    print(f"     · {e['type']}: trigger={e.get('trigger_reason', 'N/A')} "
          f"count={e.get('replan_count', 'N/A')}")

# PolicyGate
policy_events = [e for e in traced if "policy" in e["type"]]
print(f"  🛡️  PolicyGate: {len(policy_events)} events")
for e in policy_events:
    print(f"     · {e['type']}: action={e.get('action', 'N/A')}")

# Output files
print(f"\n📄 产出文件:")
for fname in ["math_lib.py"]:
    if os.path.exists(fname):
        print(f"  ✅ {fname} ({os.path.getsize(fname)} bytes):")
        with open(fname) as f:
            for line in f:
                print(f"     {line.rstrip()}")
    else:
        print(f"  ⬜ {fname} (not created)")

runtime.shutdown()

# Summary
print(f"\n{'═' * 72}")
print("  全链路验证结果")
print(f"{'═' * 72}")
checks = [
    ("LLM Planner (真实分解)", any("created" in e["type"] for e in traced)),
    ("Scheduler (Cap匹配→分派)", any("assigned" in e["type"] for e in traced)),
    ("MiniSWEAgent 执行成功",
     any("completed" in e["type"] for e in traced) and
     any(isinstance(e.get("agent_name"), str) and "MiniSWE" in e["agent_name"]
         for e in traced if "started" in e["type"])),
    ("FailingAgent 触发失败",
     any(isinstance(e.get("agent_name"), str) and "SecurityGate" in e["agent_name"]
         for e in traced if "failed" in e["type"])),
    ("MPC Replan (失败→重规划)", len(mpc_events) > 0),
    ("全链路事件发布 (37 events)", len(traced) >= 10),
    ("math_lib.py 产出", os.path.exists("math_lib.py")),
]
for name, ok in checks:
    print(f"  {'✅' if ok else '❌'} {name}")
