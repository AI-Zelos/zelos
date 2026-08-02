#!/usr/bin/env python3
"""
+Orchestration — Zelos Full Pipeline (v1.3 MPC infrastructure).

Routes through Zelos Runtime's Event Bus, ExecutionEngine._mpc_replan_check(),
and Runtime._on_replan() instead of a Python for loop.

Flow:
  Zelos Runtime (Stage A + diagnosis + mpc_replan)
    → Task A (Search): ExecutionEngine dispatch → Agent → submit_result
    → Task B (Fix):    ExecutionEngine dispatch → Agent → submit_result
    → External Verify: apply_and_verify_patch()
    → If fail:         submit_result(status="failed") →
                        _mpc_replan_check() → _on_replan() →
                        new Task B' with diagnosis context
    → Repeat until pass or max_replans
"""

import json, os, re, subprocess, sys, time, uuid

from agent_wrapper import (ClaudeCodeAgent, apply_and_verify_patch,
                           checkout_instance_commit)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from zelos.runtime import ZelosRuntime
from zelos.feature_flags import FeatureFlags
from zelos.task_graph import Task, TaskGraphEngine, TaskStatus
from zelos.replan_rules import DEFAULT_REPLAN_RULES
from zelos.planner import PlannerPlan, PlannerTask

MAX_REPLANS = 3
OUTPUT_DIR = "logs/poc_results/orchestrated_zelos"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def _extract_target_file(instance: dict, repo_dir: str) -> str:
    issue = instance.get("problem_statement", "")
    funcs = re.findall(r'(\w+)\.(\w+)\(', issue)
    for _, fn in funcs[:3]:
        if len(fn) > 3:
            try:
                r = subprocess.run(
                    ["grep", "-rl", f"def {fn}", repo_dir],
                    capture_output=True, text=True, timeout=10,
                )
                files = [f for f in r.stdout.strip().split("\n")
                        if f.endswith(".py") and "test" not in f]
                if files:
                    return files[0].replace(repo_dir + "/", "")
            except Exception:
                pass
    return ""


def run_orchestrated_zelos(instance: dict, repo_dir: str) -> dict:
    """
    Run Zelos MPC pipeline for one SWE-bench instance.

    Uses Zelos v1.3 ExecutionEngine._mpc_replan_check() +
    Runtime._on_replan() for the adaptive fix loop.
    """
    iid = instance["instance_id"]
    issue = instance.get("problem_statement", "")
    target_file = _extract_target_file(instance, repo_dir)

    if not checkout_instance_commit(instance, repo_dir):
        print(f"  WARNING: Could not checkout base_commit")

    t_start = time.perf_counter()

    # ── Init Zelos Runtime with MPC ──
    flags = FeatureFlags.stage_a()
    flags.diagnosis_engine = True
    flags.failure_classifier = True

    runtime = ZelosRuntime({"features": flags.__dict__})
    ee = runtime._execution_engine
    tg = runtime._task_graph
    eb = runtime._event_bus

    # Wire MPC
    ee._replan_rules = DEFAULT_REPLAN_RULES
    ee._max_replans = MAX_REPLANS + 1

    # Wire incremental verifier (required for MPC replan rules to trigger)
    from zelos.verifier import SchemaVerifier
    ee._incremental_verifier = SchemaVerifier()

    # Inject diagnosis engine
    from zelos.diagnosis_engine import DiagnosisEngine
    ee.set_diagnosis_engine(DiagnosisEngine())

    # Inject RuleBasedPlanner for deterministic replan_path()
    from zelos.planner import RuleBasedPlanner
    runtime._planner = RuleBasedPlanner()

    # ── Create Plan ──
    plan = PlannerPlan(
        plan_id=f"plan-{uuid.uuid4().hex[:8]}",
        goal_id=f"goal-{uuid.uuid4().hex[:8]}",
        tasks=[
            PlannerTask(task_id="task-search", description="Locate code",
                       required_capability="code-search", dependencies=[]),
            PlannerTask(task_id="task-fix", description="Fix bug",
                       required_capability="code-generation",
                       dependencies=["task-search"]),
        ],
    )

    # Store plan in runtime so _on_replan._get_plan() works
    runtime._goals[plan.plan_id] = {
        "goal_id": plan.goal_id,
        "status": "running",
        "plan": plan,
        "plan_id": plan.plan_id,
        "description": f"Fix {iid}",
    }
    ee._current_plan = plan
    ee._replan_count[plan.goal_id] = 0

    # ── Create Tasks in TaskGraph ──
    t_search = Task(task_id="task-search", plan_id=plan.plan_id,
                    description="Locate relevant files for the issue",
                    required_capability="code-search",
                    dependencies=[], timeout_ms=300000)
    t_fix = Task(task_id="task-fix", plan_id=plan.plan_id,
                 description="Generate a patch to fix the bug",
                 required_capability="code-generation",
                 dependencies=["task-search"], timeout_ms=300000)
    tg.add_task(t_search)
    tg.add_task(t_fix)

    # ── Create Agent ──
    agent = ClaudeCodeAgent(repo_dir)
    # Register agent with ExecutionEngine (bypass add_agent for simplicity)
    ee.register_agent("zelos-agent", "zelos-agent",
                      max_concurrent_tasks=5,
                      heartbeat_interval_ms=30000)
    ee._agent_dispatch = lambda aid, t: None  # We handle execution manually

    # ── Collect MPC events from Event Bus ──
    mpc_events = []
    # Patch EventBus.publish to capture MPC events
    _orig_publish = eb.publish
    def _capture_publish(event):
        if event.event_type in ("execution_plan.modified",
                                "goal.replan_limit_exceeded",
                                "task.failed", "task.completed"):
            mpc_events.append(event)
        _orig_publish(event)
    eb.publish = _capture_publish

    # ═══════════════════════════════════════════
    # Phase 1: Search Task
    # ═══════════════════════════════════════════
    print(f"\n{'='*60}")
    print(f"ZELOS ORCHESTRATED: {iid}")
    print(f"{'='*60}")
    print("  Phase 1: Search Agent (via Zelos dispatch)...")

    # Transition through state machine for dispatch
    tg.transition("task-search", TaskStatus.READY)
    tg.transition("task-search", TaskStatus.ASSIGNED, agent_id="zelos-agent")
    ee.dispatch("task-search", "zelos-agent")

    # Execute search
    search_result = agent.search_location(issue)
    files_found = search_result.get("files", [])
    if not target_file and files_found:
        target_file = files_found[0]
    print(f"    Found: {files_found[:3]}, target={target_file or 'auto'}")

    # Submit search result
    ee.submit_result("task-search", "zelos-agent", {
        "status": "completed",
        "artifact": {"files": files_found, "target": target_file},
    })

    # ═══════════════════════════════════════════
    # Phase 2: Fix Task (with MPC replan)
    # ═══════════════════════════════════════════
    print("  Phase 2: Fix Agent (Zelos MPC loop)...")
    patch = ""
    diagnosis_results = []
    replan_count = 0

    for attempt in range(MAX_REPLANS + 1):
        if attempt > 0:
            # Task was reset by _on_replan → need to re-transition
            # _on_replan creates replacement tasks; find the latest fix task
            fix_tasks = [t for t in tg.list_tasks()
                        if t.required_capability == "code-generation"
                        and t.status in (TaskStatus.CREATED, TaskStatus.READY)]
            if fix_tasks:
                t_fix = fix_tasks[-1]
                tg.transition(t_fix.task_id, TaskStatus.READY)
                tg.transition(t_fix.task_id, TaskStatus.ASSIGNED,
                             agent_id="zelos-agent")
                ee.dispatch(t_fix.task_id, "zelos-agent")
            else:
                # Re-use original task (reset state)
                tg.transition("task-fix", TaskStatus.READY)
                tg.transition("task-fix", TaskStatus.ASSIGNED,
                             agent_id="zelos-agent")
                ee.dispatch("task-fix", "zelos-agent")
        else:
            # First attempt: dispatch the original fix task
            tg.transition("task-fix", TaskStatus.READY)
            tg.transition("task-fix", TaskStatus.ASSIGNED,
                         agent_id="zelos-agent")
            ee.dispatch("task-fix", "zelos-agent")

        # Execute fix
        if attempt == 0:
            result = agent.generate_patch(issue, target_file)
        else:
            result = agent.repair_patch(issue, diag_text, patch)

        patch = result.get("patch", "")
        if not patch or len(patch) < 20:
            print(f"    Attempt {attempt+1}: ✗ Empty patch")
            ee.submit_result(t_fix.task_id, "zelos-agent", {
                "status": "failed",
                "error": {"code": "EMPTY_PATCH", "message": "Empty patch"},
                "artifact": {},
            })
            replan_count += 1
            continue

        tokens = agent._total_input_tokens + agent._total_output_tokens
        print(f"    Attempt {attempt+1}: {len(patch)} chars, tokens={tokens}")

        # External verification
        test_result = apply_and_verify_patch(patch, iid, repo_dir)

        if test_result["all_passed"]:
            print(f"    ✓ OK!")
            ee.submit_result(t_fix.task_id, "zelos-agent", {
                "status": "completed",
                "artifact": {"patch": patch},
            })
            break

        # ── Submit as FAILED → triggers _mpc_replan_check ──
        # Use empty artifact so EmptyArtifactRule triggers the replan
        # (SchemaVerifier would pass any non-empty artifact)
        print(f"    ✗ Failed. Submitting to Zelos MPC...")
        ee.submit_result(t_fix.task_id, "zelos-agent", {
            "status": "failed",
            "error": {
                "code": "VERIFY_FAILED",
                "message": test_result.get("raw_output", "")[:500],
                "test_output": test_result.get("raw_output", ""),
            },
            "artifact": {},  # Empty → triggers EmptyArtifactRule → replan
        })
        replan_count += 1

        # Collect diagnosis from the event flow
        # (DiagnosisEngine ran inside _mpc_replan_check)
        diag_text = test_result.get("raw_output", "")[:500]

        # Check if _on_replan was triggered (it should have been)
        plan_events = [e for e in mpc_events
                      if e.event_type == "execution_plan.modified"]
        print(f"      MPC events: {len(plan_events)} plan modified")

        if not plan_events:
            print(f"      ⚠ MPC did NOT trigger replan — falling back")
            break

    elapsed = time.perf_counter() - t_start
    final = apply_and_verify_patch(patch, iid, repo_dir)

    # ── Collect results ──
    decision_reach_rate = (
        replan_count / (MAX_REPLANS + 1) if (MAX_REPLANS + 1) > 0 else 0
    )
    plan_modified_count = len([e for e in mpc_events
                               if e.event_type == "execution_plan.modified"])

    data = {
        "instance_id": iid, "group": "orchestrated_zelos",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "result": {"pass": final["all_passed"], "patch": patch[:5000],
                    "total_time_seconds": round(elapsed, 1)},
        "metrics": {
            "replan_count": replan_count,
            "mpc_plan_modified_events": plan_modified_count,
            "total_mpc_events": len(mpc_events),
            "agent_tokens_estimate": agent.total_tokens_estimate,
            "total_tokens_estimate": agent.total_tokens_estimate,
            "decision_reach_rate": round(decision_reach_rate, 2),
            "files_found": files_found,
            "target_file": target_file,
        },
    }

    out_file = os.path.join(OUTPUT_DIR, f"{iid.replace('/', '_')}.json")
    with open(out_file, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Saved: {out_file}")

    runtime.shutdown()
    return data


def main():
    if len(sys.argv) < 3:
        print("Usage: python orchestrated_zelos.py <instances.json> <repo_dir>")
        sys.exit(1)
    with open(sys.argv[1]) as f:
        instances = json.load(f)
    for inst in instances:
        try:
            run_orchestrated_zelos(inst, sys.argv[2])
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
