#!/usr/bin/env python3
"""
Baseline Experiment — Single Agent, self-contained repair loop.

Agent generates patch → apply + syntax check → if fail: full log → retry.
"""

import json
import os
import sys
import time

from agent_wrapper import (ClaudeCodeAgent, apply_and_verify_patch,
                           checkout_instance_commit)

MAX_RETRIES = 3
OUTPUT_DIR = "logs/poc_results/baseline"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def run_baseline(instance: dict, repo_dir: str) -> dict:
    iid = instance["instance_id"]
    issue = instance.get("problem_statement", "")

    # Ensure repo is at the correct commit
    if not checkout_instance_commit(instance, repo_dir):
        print(f"  WARNING: Could not checkout base_commit, repo may be at wrong state")

    agent = ClaudeCodeAgent(repo_dir)

    print(f"\n{'='*60}")
    print(f"BASELINE: {iid}")
    print(f"{'='*60}")

    t_start = time.perf_counter()
    patch = ""
    retry_count = 0

    for attempt in range(MAX_RETRIES + 1):
        if attempt == 0:
            print(f"  Attempt {attempt+1}: generating patch...")
            result = agent.generate_patch(issue)
        else:
            print(f"  Attempt {attempt+1}: repairing with full test log...")
            result = agent.repair_patch_full_log(issue,
                f"Previous attempt failed. Patch application or syntax error.", patch)

        patch = result.get("patch", "")
        if not patch or len(patch) < 20:
            print(f"  ✗ Empty/short patch ({len(patch)} chars)")
            continue

        print(f"  Patch: {len(patch)} chars, {result['elapsed_s']:.0f}s, "
              f"tokens={agent._total_input_tokens + agent._total_output_tokens}")

        test_result = apply_and_verify_patch(patch, iid, repo_dir)
        if test_result["all_passed"]:
            print(f"  ✓ Patch applied OK, syntax OK!")
            break
        else:
            retry_count += 1
            print(f"  ✗ Failed: {test_result['raw_output'][:120]}")

    elapsed = time.perf_counter() - t_start
    final = apply_and_verify_patch(patch, iid, repo_dir)

    data = {
        "instance_id": iid,
        "group": "baseline",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "result": {
            "pass": final["all_passed"],
            "patch": patch[:5000],
            "total_time_seconds": round(elapsed, 1),
        },
        "metrics": {
            "retry_count": retry_count,
            "total_tokens_estimate": agent.total_tokens_estimate,
            "agent_calls": agent._call_count,
        },
    }

    out_file = os.path.join(OUTPUT_DIR, f"{iid.replace('/', '_')}.json")
    with open(out_file, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Saved: {out_file}")
    return data


def main():
    if len(sys.argv) < 3:
        print("Usage: python baseline.py <instances.json> <repo_dir>")
        sys.exit(1)
    with open(sys.argv[1]) as f:
        instances = json.load(f)
    for inst in instances:
        run_baseline(inst, sys.argv[2])


if __name__ == "__main__":
    main()
