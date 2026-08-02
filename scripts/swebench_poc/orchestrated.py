#!/usr/bin/env python3
"""
+Orchestration Experiment — Zelos Runtime MPC with 3-Agent pipeline.

Zelos Runtime manages: Planner → Executor → Incremental Verify → MPC Replan.
Uses v1.3.0 MPC features with RuleBasedPlanner + Diagnosis Engine.
"""

import json, os, re, subprocess, sys, time

from agent_wrapper import (ClaudeCodeAgent, apply_and_verify_patch,
                           checkout_instance_commit)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from zelos.runtime import ZelosRuntime
from zelos.feature_flags import FeatureFlags
from zelos.planner import RuleBasedPlanner
from zelos.replan_rules import DEFAULT_REPLAN_RULES

MAX_REPLANS = 3
OUTPUT_DIR = "logs/poc_results/orchestrated"
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


def run_orchestrated(instance: dict, repo_dir: str) -> dict:
    iid = instance["instance_id"]
    issue = instance.get("problem_statement", "")
    target_file = _extract_target_file(instance, repo_dir)

    if not checkout_instance_commit(instance, repo_dir):
        print(f"  WARNING: Could not checkout base_commit")

    print(f"\n{'='*60}")
    print(f"ORCHESTRATED: {iid}  (target: {target_file or 'auto'})")
    print(f"{'='*60}")

    t_start = time.perf_counter()
    replan_count = 0
    patch = ""

    # ── Init Zelos Runtime ──
    flags = FeatureFlags.stage_a()
    flags.diagnosis_engine = True
    flags.failure_classifier = True

    runtime = ZelosRuntime({"features": flags.__dict__})
    runtime._planner = RuleBasedPlanner()
    ee = runtime._execution_engine
    ee._replan_rules = DEFAULT_REPLAN_RULES
    ee._max_replans = MAX_REPLANS + 1

    from zelos.diagnosis_engine import DiagnosisEngine
    ee.set_diagnosis_engine(DiagnosisEngine())

    agent = ClaudeCodeAgent(repo_dir)

    # ── Phase 1: Search (locate relevant code) ──
    print("  Phase 1: Locating code...")
    search_result = agent.search_location(issue)
    files_found = search_result.get("files", [])
    print(f"    Found: {files_found[:3]}")

    # ── Phase 2: Fix (with MPC loop) ──
    print("  Phase 2: Fix + MPC loop...")
    diagnosis_results = []

    for attempt in range(MAX_REPLANS + 1):
        if attempt == 0:
            result = agent.generate_patch(issue, target_file)
        else:
            result = agent.repair_patch(issue, diag_text, patch)

        patch = result.get("patch", "")
        if not patch or len(patch) < 20:
            print(f"    ✗ Empty/short patch")
            replan_count += 1
            continue

        print(f"    Attempt {attempt+1}: {len(patch)} chars")

        test_result = apply_and_verify_patch(patch, iid, repo_dir)
        if test_result["all_passed"]:
            print(f"    ✓ OK!")
            break

        # ── MPC Replan ──
        replan_count += 1
        print(f"    ✗ Failed. MPC Replan #{replan_count}...")

        de = DiagnosisEngine()
        diag = de.diagnose(test_result.get("raw_output", ""))
        diagnosis_results.append(diag.to_dict())

        from zelos.failure_classifier import FailureClassifier
        fc = FailureClassifier()
        cls = fc.classify(diag)
        print(f"      Diag: {diag.failed}F, Classifier: {cls.action}")
        diag_text = str(diag.to_dict())

        if cls.action == "abandon":
            print(f"      → Abandoning")
            break

    elapsed = time.perf_counter() - t_start
    final = apply_and_verify_patch(patch, iid, repo_dir)

    data = {
        "instance_id": iid, "group": "orchestrated",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "result": {"pass": final["all_passed"], "patch": patch[:5000],
                    "total_time_seconds": round(elapsed, 1)},
        "metrics": {
            "replan_count": replan_count,
            "agent_tokens_estimate": agent.total_tokens_estimate,
            "total_tokens_estimate": agent.total_tokens_estimate,
            "decision_reach_rate": round(
                replan_count / (MAX_REPLANS + 1) if (MAX_REPLANS + 1) > 0 else 0, 2
            ),
            "diagnosis_results": diagnosis_results,
            "files_found": files_found,
        },
    }

    out_file = os.path.join(OUTPUT_DIR, f"{iid.replace('/', '_')}.json")
    with open(out_file, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Saved: {out_file}")
    return data


def main():
    if len(sys.argv) < 3:
        print("Usage: python orchestrated.py <instances.json> <repo_dir>")
        sys.exit(1)
    with open(sys.argv[1]) as f:
        instances = json.load(f)
    for inst in instances:
        run_orchestrated(inst, sys.argv[2])


if __name__ == "__main__":
    main()
