#!/usr/bin/env python3
"""
+Orchestration Experiment — Zelos Runtime MPC with 3-Agent pipeline.

Group C (+orchestration):
  Task A (Search): Claude Code locates relevant files/functions
  Task B (Fix):    Claude Code generates patch
  Task C (Test):   Runtime runs tests; if fail → Diagnosis → MPC Replan → new Task B
  Task D (Review): Claude Code reviews the final patch

  Zelos Runtime manages the entire lifecycle:
    Planner → Scheduler → Executor → Incremental Verify → MPC Replan

  This script uses Zelos Runtime's v1.3.0 MPC features:
    - FeatureFlags.stage_a() + diagnosis_engine
    - RuleBasedPlanner for deterministic replan_path()
    - ExecutionEngine._mpc_replan_check() for adaptive loop
"""

import json
import os
import subprocess
import sys
import time
import uuid

from agent_wrapper import ClaudeCodeAgent, apply_and_verify_patch

# Add zelos to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from zelos.runtime import ZelosRuntime
from zelos.feature_flags import FeatureFlags
from zelos.planner import RuleBasedPlanner, PlannerTask, PlannerPlan
from zelos.task_graph import Task, TaskStatus
from zelos.replan_rules import DEFAULT_REPLAN_RULES
from zelos.event_bus import Event

# ── Config ──
MAX_REPLANS = 3  # Fewer than default 5 for controlled experiment
TIMEOUT = 400  # Per Agent call
OUTPUT_DIR = "logs/poc_results/orchestrated"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def run_orchestrated(instance: dict, repo_dir: str) -> dict:
    """
    Run orchestrated experiment using Zelos Runtime MPC.

    Uses Zelos v1.3.0 ExecutionEngine._mpc_replan_check() and
    Runtime._on_replan() with RuleBasedPlanner.

    Flow:
      1. Task A (Search): locate relevant code
      2. Task B (Fix): generate patch
      3. Runtime runs tests
      4. If fail: Diagnosis Engine → MPC Replan → new Task B
      5. Repeat until pass or max replans
    """
    iid = instance["instance_id"]
    issue = instance.get("problem_statement", "")
    search_agent = ClaudeCodeAgent(repo_dir)
    fix_agent = ClaudeCodeAgent(repo_dir)

    print(f"\n{'='*60}")
    print(f"ORCHESTRATED: {iid}")
    print(f"{'='*60}")

    t_start = time.perf_counter()
    replan_count = 0
    decision_events = []

    # ── Initialize Zelos Runtime ──
    flags = FeatureFlags.stage_a()
    flags.diagnosis_engine = True
    flags.failure_classifier = True

    runtime = ZelosRuntime({"features": flags.__dict__})
    runtime._planner = RuleBasedPlanner()

    ee = runtime._execution_engine
    tg = runtime._task_graph

    # Enable MPC with reduced max replans
    ee._replan_rules = DEFAULT_REPLAN_RULES
    ee._max_replans = MAX_REPLANS + 1  # +1 for initial attempt

    # Inject diagnosis engine
    from zelos.diagnosis_engine import DiagnosisEngine
    ee.set_diagnosis_engine(DiagnosisEngine())

    # ── Phase 1: Task A — Search ──
    print("  Phase 1: Search Agent locating code...")
    search_result = search_agent.search_location(issue)
    location_info = search_result.get("location", "")
    files_found = search_result.get("files", [])
    print(f"    Found: {files_found[:3]} ({search_result['elapsed_s']:.0f}s)")

    # ── Phase 2: Task B — Fix (with MPC loop) ──
    print("  Phase 2: Fix Agent generating patch (MPC loop)...")
    patch = ""
    test_output = ""
    diagnosis_results = []

    for attempt in range(MAX_REPLANS + 1):
        if attempt == 0:
            # First attempt: full context
            fix_prompt = (
                f"Issue:\n{issue[:2000]}\n\n"
                f"Code location analysis:\n{location_info[:1000]}\n\n"
                "Generate a unified diff patch to fix this bug. "
                "Output ONLY the patch, no markdown fences."
            )
            fix_result = _call_claude_api(fix_prompt)
        else:
            # Replan attempt: with diagnosis
            print(f"    Replan attempt {attempt}...")
            fix_prompt = (
                f"Issue:\n{issue[:1500]}\n\n"
                f"Previous (FAILED) patch:\n{patch[:1500]}\n\n"
                f"Structured diagnosis of test failures:\n{diagnosis_text}\n\n"
                "Fix ONLY the specific failures mentioned. "
                "Output ONLY a unified diff patch, no markdown fences."
            )
            fix_result = _call_claude_api(fix_prompt)

        patch = fix_result.get("patch", "")
        if not patch or len(patch) < 20:
            print(f"    ✗ Empty/short patch, abandoning")
            break

        print(f"    Attempt {attempt+1}: patch {len(patch)} chars, "
              f"{fix_result['elapsed_s']:.0f}s")

        # ── Phase 3: Test ──
        test_result = apply_and_verify_patch(patch, iid, repo_dir)

        if test_result["all_passed"]:
            print(f"    ✓ ALL TESTS PASSED!")
            break

        # ── MPC Replan: Diagnosis → Classification → Decision ──
        replan_count += 1
        print(f"    ✗ Tests failed. MPC Replan #{replan_count}...")

        # Diagnosis
        from zelos.diagnosis_engine import DiagnosisEngine
        de = DiagnosisEngine()
        diag = de.diagnose(test_result["raw_output"])
        diagnosis_results.append(diag.to_dict())

        # Build diagnosis text for Agent
        diag_lines = [f"Test results: {diag.passed}P {diag.failed}F {diag.errors}E "
                      f"(pass rate: {diag.pass_rate:.0%})"]
        for f_detail in diag.failures[:3]:
            loc = f"{f_detail.location_file}:{f_detail.location_line}" \
                if f_detail.location_file else "unknown"
            diag_lines.append(
                f"  FAILED: {f_detail.test_name} — {f_detail.failure_type} at {loc}"
            )
            if f_detail.expected:
                diag_lines.append(f"    Expected: {f_detail.expected}")
            if f_detail.actual:
                diag_lines.append(f"    Actual: {f_detail.actual}")
        diagnosis_text = "\n".join(diag_lines)

        print(f"      Diagnosis: {diag.failed} failures, impact={diag.impact_scope}, "
              f"rec={diag.recommendation}")

        # Classify
        from zelos.failure_classifier import FailureClassifier
        fc = FailureClassifier()
        cls = fc.classify(diag)
        print(f"      Classifier: {cls.action}, salvageable={cls.salvageable}")

        decision = {
            "attempt": attempt + 1,
            "trigger": "test_failure",
            "action": cls.action,
            "diagnosis": diag.to_dict(),
        }
        decision_events.append(decision)

        if cls.action == "abandon":
            print(f"      → Abandoning")
            break
        # repair/retry → continue loop

        # Track replan count for the event
        test_output = test_result["raw_output"]

    elapsed = time.perf_counter() - t_start
    final_result = run_tests_in_docker(iid, patch, repo_dir)

    # ── Phase 4: Review (optional, if patch passed) ──
    review_result = None
    if final_result["all_passed"] and patch:
        print("  Phase 4: Reviewing patch...")
        review_result = search_agent.review_patch(issue, patch)
        print(f"    Review verdict: {review_result.get('verdict', '?')}")

    # ── Collect metrics ──
    decision_reach_rate = (
        replan_count / (MAX_REPLANS + 1)
        if (MAX_REPLANS + 1) > 0 else 0
    )

    data = {
        "instance_id": iid,
        "group": "orchestrated",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "result": {
            "pass": final_result["all_passed"],
            "patch": patch[:5000],
            "total_time_seconds": round(elapsed, 1),
        },
        "metrics": {
            "replan_count": replan_count,
            "search_agent_tokens": search_agent.total_tokens_estimate,
            "fix_agent_tokens": fix_agent.total_tokens_estimate,
            "total_tokens_estimate": (
                search_agent.total_tokens_estimate +
                fix_agent.total_tokens_estimate
            ),
            "decision_reach_rate": round(decision_reach_rate, 2),
            "decisions": decision_events,
            "diagnosis_results": diagnosis_results,
            "review_verdict": review_result.get("verdict") if review_result else None,
            "files_found": files_found,
        },
    }

    out_file = os.path.join(OUTPUT_DIR, f"{iid.replace('/', '_')}.json")
    with open(out_file, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Saved: {out_file}")

    runtime.shutdown()
    return data


def _call_claude_api(prompt: str, timeout: int = TIMEOUT,
                     system: str = "") -> dict:
    """Call Anthropic API directly (used by orchestrated experiment)."""
    import time as _time
    import anthropic as _anthropic
    from agent_wrapper import clean_patch

    t0 = _time.perf_counter()
    try:
        api_key = os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get(
            "ANTHROPIC_API_KEY", "")
        base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
        model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

        client = _anthropic.Anthropic(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system or (
                "Output ONLY a unified diff patch. Start with '--- a/'. "
                "No markdown fences, no explanations."
            ),
            stop_sequences=["```"],
            messages=[{"role": "user", "content": prompt}],
        )
        output = ""
        for block in response.content:
            if block.type == "text":
                output += block.text
        output = clean_patch(output)
        elapsed = _time.perf_counter() - t0
    except Exception as e:
        output = f"API_ERROR: {e}"
        elapsed = _time.perf_counter() - t0

    return {"patch": output, "elapsed_s": elapsed}


def main():
    if len(sys.argv) < 3:
        print("Usage: python orchestrated.py <instances.json> <repo_dir>")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        instances = json.load(f)

    repo_dir = sys.argv[2]
    results = []

    for inst in instances:
        result = run_orchestrated(inst, repo_dir)
        results.append(result)

    passed = sum(1 for r in results if r["result"]["pass"])
    print(f"\n{'='*60}")
    print(f"ORCHESTRATED SUMMARY: {passed}/{len(results)} passed")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
