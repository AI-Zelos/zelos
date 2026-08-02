#!/usr/bin/env python3
"""
+Runtime Diagnosis Experiment — Single Agent + Zelos Diagnosis Engine.

Group B (+Runtime diagnosis):
  1 Agent → generate patch → run tests → if fail:
    Diagnosis Engine parses pytest output → structured diagnosis
    Failure Classifier decides: repair / retry / abandon
    → if repair: structured diagnosis (NOT full log) → Agent → retry

Key difference from baseline: Agent receives structured diagnosis
(file:line, expected vs actual) instead of raw 500-line pytest output.
"""

import json
import os
import subprocess
import sys
import time

from agent_wrapper import ClaudeCodeAgent

# Add zelos to path for Diagnosis Engine import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from zelos.diagnosis_engine import DiagnosisEngine
from zelos.failure_classifier import FailureClassifier

# ── Config ──
MAX_RETRIES = 3
TIMEOUT = 300
OUTPUT_DIR = "logs/poc_results/runtime_diag"
os.makedirs(OUTPUT_DIR, exist_ok=True)

diagnosis_engine = DiagnosisEngine()
classifier = FailureClassifier()


def run_tests_in_docker(instance_id: str, patch: str, repo_dir: str) -> dict:
    """Run pytest in repo dir. Same as baseline."""
    if not os.path.isdir(repo_dir):
        return {"all_passed": False, "raw_output": "repo dir not found", "exit_code": -1}

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
                    "raw_output": f"Patch apply check failed:\n{r.stderr[:2000]}",
                    "exit_code": r.returncode}
        subprocess.run(["git", "apply", patch_file],
                       capture_output=True, cwd=repo_dir, timeout=10)
    except subprocess.TimeoutExpired:
        return {"all_passed": False, "raw_output": "Patch timeout", "exit_code": -1}
    finally:
        if os.path.exists(patch_file):
            os.remove(patch_file)

    try:
        r = subprocess.run(
            ["python", "-m", "pytest", "-x", "-q", "--tb=short"],
            capture_output=True, text=True, timeout=120, cwd=repo_dir,
        )
        output = r.stdout + "\n" + r.stderr
        all_passed = r.returncode == 0
        subprocess.run(["git", "checkout", "--", "."],
                       capture_output=True, cwd=repo_dir, timeout=10)
        return {"all_passed": all_passed, "raw_output": output, "exit_code": r.returncode}
    except subprocess.TimeoutExpired:
        subprocess.run(["git", "checkout", "--", "."],
                       capture_output=True, cwd=repo_dir, timeout=10)
        return {"all_passed": False, "raw_output": "Test timeout", "exit_code": -1}


def format_diagnosis_for_agent(diag) -> str:
    """Convert DiagnosisResult to a concise, agent-friendly string."""
    lines = [f"Test results: {diag.passed} passed, {diag.failed} failed, "
             f"{diag.errors} errors (pass rate: {diag.pass_rate:.0%})"]
    lines.append(f"Impact scope: {diag.impact_scope}")
    lines.append(f"Recommendation: {diag.recommendation}")
    lines.append("")

    for i, f in enumerate(diag.failures[:5]):
        loc = f"{f.location_file}:{f.location_line}" if f.location_file else "unknown"
        lines.append(f"Failure {i+1}: {f.test_name}")
        lines.append(f"  Type: {f.failure_type}")
        lines.append(f"  Location: {loc}")
        if f.expected:
            lines.append(f"  Expected: {f.expected}")
        if f.actual:
            lines.append(f"  Actual: {f.actual}")
        lines.append("")

    return "\n".join(lines)


def estimate_diagnosis_tokens(diag) -> int:
    """Rough token estimate for diagnosis output (chars / 4)."""
    text = format_diagnosis_for_agent(diag)
    return len(text) // 4


def run_runtime_diag(instance: dict, repo_dir: str) -> dict:
    """
    Run +Runtime diagnosis experiment for one instance.

    Flow:
      1. Agent generates patch
      2. Run tests
      3. If fail:
         a. Diagnosis Engine parses output → structured diagnosis
         b. Failure Classifier decides action
         c. If repair: structured diagnosis → Agent (NOT full log)
         d. Repeat up to MAX_RETRIES
    """
    iid = instance["instance_id"]
    issue = instance.get("problem_statement", "")
    agent = ClaudeCodeAgent(repo_dir)

    print(f"\n{'='*60}")
    print(f"+DIAGNOSIS: {iid}")
    print(f"{'='*60}")

    t_start = time.perf_counter()
    patch = ""
    retry_count = 0
    diagnosis_count = 0
    total_diag_tokens = 0
    diagnosis_results = []

    for attempt in range(MAX_RETRIES + 1):
        if attempt == 0:
            print(f"  Attempt {attempt+1}: generating patch...")
            result = agent.generate_patch(issue)
        else:
            print(f"  Attempt {attempt+1}: repairing with structured diagnosis...")
            # Use structured diagnosis, NOT full log
            result = agent.repair_patch(issue, last_diagnosis_text, patch)

        patch = result.get("patch", "")
        if not patch or len(patch) < 20:
            print(f"  ✗ Empty/short patch ({len(patch)} chars)")
            break

        print(f"  Patch: {len(patch)} chars, {result['elapsed_s']:.0f}s")

        # Run tests
        test_result = run_tests_in_docker(iid, patch, repo_dir)

        if test_result["all_passed"]:
            print(f"  ✓ ALL TESTS PASSED!")
            break

        # ── Runtime Diagnosis ──
        retry_count += 1
        print(f"  ✗ Tests failed. Running Diagnosis Engine...")

        diag = diagnosis_engine.diagnose(test_result["raw_output"])
        diagnosis_count += 1
        diag_tokens = estimate_diagnosis_tokens(diag)
        total_diag_tokens += diag_tokens

        print(f"    Diagnosis: {diag.failed} failures, "
              f"impact={diag.impact_scope}, rec={diag.recommendation}, "
              f"~{diag_tokens} tokens")

        diag_text = format_diagnosis_for_agent(diag)
        diagnosis_results.append(diag.to_dict())

        # Failure Classifier
        cls = classifier.classify(diag)
        print(f"    Classifier: action={cls.action}, salvageable={cls.salvageable}")

        last_diagnosis_text = diag_text

        if cls.action == "abandon":
            print(f"    → Abandoning (not salvageable)")
            break
        # repair or retry → continue to next attempt

    elapsed = time.perf_counter() - t_start
    final_result = run_tests_in_docker(iid, patch, repo_dir)

    data = {
        "instance_id": iid,
        "group": "runtime_diag",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "result": {
            "pass": final_result["all_passed"],
            "patch": patch[:5000],
            "total_time_seconds": round(elapsed, 1),
        },
        "metrics": {
            "retry_count": retry_count,
            "diagnosis_count": diagnosis_count,
            "runtime_diag_overhead_tokens": total_diag_tokens,
            "agent_tokens_estimate": agent.total_tokens_estimate,
            "total_tokens_estimate": agent.total_tokens_estimate + total_diag_tokens,
            "agent_calls": agent._call_count,
            "diagnosis_results": diagnosis_results,
        },
    }

    out_file = os.path.join(OUTPUT_DIR, f"{iid.replace('/', '_')}.json")
    with open(out_file, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Saved: {out_file}")

    return data


def main():
    if len(sys.argv) < 3:
        print("Usage: python runtime_diag.py <instances.json> <repo_dir>")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        instances = json.load(f)

    repo_dir = sys.argv[2]
    results = []

    for inst in instances:
        result = run_runtime_diag(inst, repo_dir)
        results.append(result)

    passed = sum(1 for r in results if r["result"]["pass"])
    print(f"\n{'='*60}")
    print(f"+DIAGNOSIS SUMMARY: {passed}/{len(results)} passed")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
