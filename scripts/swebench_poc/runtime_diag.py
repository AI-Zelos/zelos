#!/usr/bin/env python3
"""
+Runtime Diagnosis Experiment — Single Agent + Zelos Diagnosis Engine.

Group B: Agent generates patch → apply + verify → if fail:
  Diagnosis Engine → structured diagnosis → Agent repairs (NOT full log)
"""

import json
import os
import sys
import time

from agent_wrapper import ClaudeCodeAgent, apply_and_verify_patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from zelos.diagnosis_engine import DiagnosisEngine
from zelos.failure_classifier import FailureClassifier

MAX_RETRIES = 3
OUTPUT_DIR = "logs/poc_results/runtime_diag"
os.makedirs(OUTPUT_DIR, exist_ok=True)

diagnosis_engine = DiagnosisEngine()
classifier = FailureClassifier()


def format_diagnosis_for_agent(diag) -> str:
    """Convert DiagnosisResult to a concise, agent-friendly string."""
    lines = [f"Tests: {diag.passed}P {diag.failed}F {diag.errors}E "
             f"(pass rate: {diag.pass_rate:.0%})",
             f"Impact: {diag.impact_scope}",
             f"Recommendation: {diag.recommendation}", ""]
    for i, f_detail in enumerate(diag.failures[:5]):
        loc = f"{f_detail.location_file}:{f_detail.location_line}" \
            if f_detail.location_file else "unknown"
        lines.append(f"Failure {i+1}: {f_detail.test_name}")
        lines.append(f"  Type: {f_detail.failure_type}")
        lines.append(f"  Location: {loc}")
        if f_detail.expected:
            lines.append(f"  Expected: {f_detail.expected}")
        if f_detail.actual:
            lines.append(f"  Actual: {f_detail.actual}")
    return "\n".join(lines)


def estimate_diagnosis_tokens(diag) -> int:
    return len(format_diagnosis_for_agent(diag)) // 4


def run_runtime_diag(instance: dict, repo_dir: str) -> dict:
    iid = instance["instance_id"]
    issue = instance.get("problem_statement", "")
    agent = ClaudeCodeAgent(repo_dir)

    print(f"\n{'='*60}")
    print(f"+DIAGNOSIS: {iid}")
    print(f"{'='*60}")

    t_start = time.perf_counter()
    patch = ""
    retry_count = 0
    total_diag_tokens = 0

    for attempt in range(MAX_RETRIES + 1):
        if attempt == 0:
            print(f"  Attempt {attempt+1}: generating patch...")
            result = agent.generate_patch(issue)
        else:
            print(f"  Attempt {attempt+1}: repairing with diagnosis...")
            result = agent.repair_patch(issue, last_diagnosis_text, patch)

        patch = result.get("patch", "")
        if not patch or len(patch) < 20:
            print(f"  ✗ Empty/short patch ({len(patch)} chars)")
            retry_count += 1
            continue

        print(f"  Patch: {len(patch)} chars, {result['elapsed_s']:.0f}s")

        test_result = apply_and_verify_patch(patch, iid, repo_dir)
        if test_result["all_passed"]:
            print(f"  ✓ OK!")
            break

        # ── Runtime Diagnosis ──
        retry_count += 1
        diag = diagnosis_engine.diagnose(test_result["raw_output"])
        total_diag_tokens += estimate_diagnosis_tokens(diag)
        print(f"    Diag: {diag.failed}F impact={diag.impact_scope} rec={diag.recommendation}")

        cls = classifier.classify(diag)
        print(f"    Classifier: {cls.action} salvageable={cls.salvageable}")
        last_diagnosis_text = format_diagnosis_for_agent(diag)
        if cls.action == "abandon":
            break

    elapsed = time.perf_counter() - t_start

    data = {
        "instance_id": iid, "group": "runtime_diag",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "result": {"pass": apply_and_verify_patch(patch, iid, repo_dir)["all_passed"],
                    "patch": patch[:5000], "total_time_seconds": round(elapsed, 1)},
        "metrics": {"retry_count": retry_count,
                    "runtime_diag_overhead_tokens": total_diag_tokens,
                    "agent_tokens_estimate": agent.total_tokens_estimate,
                    "total_tokens_estimate": agent.total_tokens_estimate + total_diag_tokens,
                    "agent_calls": agent._call_count},
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
    for inst in instances:
        run_runtime_diag(inst, sys.argv[2])


if __name__ == "__main__":
    main()
