#!/usr/bin/env python3
"""
Baseline Experiment — Single Agent, self-contained repair loop.

Group A (baseline):
  1 Agent → generate patch → run tests → if fail: full log → retry → repeat
  Agent reads FULL pytest output and decides how to fix.
  No Zelos Runtime intervention.
"""

import json
import os
import subprocess
import sys
import time

from agent_wrapper import ClaudeCodeAgent

# ── Config ──
MAX_RETRIES = 3
TIMEOUT = 300
OUTPUT_DIR = "logs/poc_results/baseline"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def run_tests_in_docker(instance_id: str, patch: str,
                        repo_dir: str) -> dict:
    """
    Run SWE-bench tests in Docker.

    Returns: {"all_passed": bool, "raw_output": str, "exit_code": int}
    """
    # Default: run pytest directly in the repo (not Docker)
    # Docker mode can be added with SWE-bench eval harness
    if not os.path.isdir(repo_dir):
        return {"all_passed": False, "raw_output": "repo dir not found",
                "exit_code": -1}

    # Apply patch
    patch_file = f"/tmp/zelos_poc_{instance_id.replace('/', '_')}.patch"
    with open(patch_file, "w") as f:
        f.write(patch)

    try:
        r = subprocess.run(
            ["git", "apply", "--check", patch_file],
            capture_output=True, text=True, timeout=30, cwd=repo_dir,
        )
        if r.returncode != 0:
            return {"all_passed": False,
                    "raw_output": f"Patch does not apply cleanly:\n{r.stderr[:2000]}",
                    "exit_code": r.returncode}

        subprocess.run(["git", "apply", patch_file],
                       capture_output=True, cwd=repo_dir, timeout=10)
    except subprocess.TimeoutExpired:
        return {"all_passed": False, "raw_output": "Patch application timeout",
                "exit_code": -1}
    finally:
        if os.path.exists(patch_file):
            os.remove(patch_file)

    # Run pytest
    try:
        r = subprocess.run(
            ["python", "-m", "pytest", "-x", "-q", "--tb=short"],
            capture_output=True, text=True, timeout=120, cwd=repo_dir,
        )
        output = r.stdout + "\n" + r.stderr
        all_passed = r.returncode == 0
        # Revert patch
        subprocess.run(["git", "checkout", "--", "."],
                       capture_output=True, cwd=repo_dir, timeout=10)
        return {"all_passed": all_passed, "raw_output": output,
                "exit_code": r.returncode}
    except subprocess.TimeoutExpired:
        subprocess.run(["git", "checkout", "--", "."],
                       capture_output=True, cwd=repo_dir, timeout=10)
        return {"all_passed": False, "raw_output": "Test execution timeout",
                "exit_code": -1}


def run_baseline(instance: dict, repo_dir: str) -> dict:
    """
    Run baseline experiment for one instance.

    Flow:
      1. Agent generates patch
      2. Run tests
      3. If fail: feed full test output to Agent → retry (up to MAX_RETRIES)
      4. Return final result
    """
    iid = instance["instance_id"]
    issue = instance.get("problem_statement", "")
    agent = ClaudeCodeAgent(repo_dir)

    print(f"\n{'='*60}")
    print(f"BASELINE: {iid}")
    print(f"{'='*60}")

    t_start = time.perf_counter()
    patch = ""
    retry_count = 0
    test_outputs = []

    for attempt in range(MAX_RETRIES + 1):
        if attempt == 0:
            print(f"  Attempt {attempt+1}: generating patch...")
            result = agent.generate_patch(issue)
        else:
            print(f"  Attempt {attempt+1}: repairing with full test log...")
            # Give Agent the FULL pytest output (baseline behavior)
            last_output = test_outputs[-1] if test_outputs else ""
            result = agent.repair_patch_full_log(issue, last_output, patch)

        patch = result.get("patch", "")
        if not patch or len(patch) < 20:
            print(f"  ✗ Empty/short patch ({len(patch)} chars), skipping")
            continue

        print(f"  Patch: {len(patch)} chars, {result['elapsed_s']:.0f}s")

        # Run tests
        test_result = run_tests_in_docker(iid, patch, repo_dir)
        test_outputs.append(test_result["raw_output"])

        if test_result["all_passed"]:
            print(f"  ✓ ALL TESTS PASSED!")
            break
        else:
            retry_count += 1
            print(f"  ✗ Tests failed (attempt {attempt+1}/{MAX_RETRIES+1})")

    elapsed = time.perf_counter() - t_start
    final_result = run_tests_in_docker(iid, patch, repo_dir)

    data = {
        "instance_id": iid,
        "group": "baseline",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "result": {
            "pass": final_result["all_passed"],
            "patch": patch[:5000],
            "total_time_seconds": round(elapsed, 1),
        },
        "metrics": {
            "retry_count": retry_count,
            "total_tokens_estimate": agent.total_tokens_estimate,
            "agent_calls": agent._call_count,
        },
    }

    # Save
    out_file = os.path.join(OUTPUT_DIR, f"{iid.replace('/', '_')}.json")
    with open(out_file, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Saved: {out_file}")

    return data


def main():
    if len(sys.argv) < 3:
        print("Usage: python baseline.py <instances.json> <repo_dir>")
        print("  instances.json: output from select_instances.py")
        print("  repo_dir: path to cloned repository")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        instances = json.load(f)

    repo_dir = sys.argv[2]
    results = []

    for inst in instances:
        result = run_baseline(inst, repo_dir)
        results.append(result)

    # Summary
    passed = sum(1 for r in results if r["result"]["pass"])
    print(f"\n{'='*60}")
    print(f"BASELINE SUMMARY: {passed}/{len(results)} passed")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
