#!/usr/bin/env python3
"""
+Runtime Diagnosis Experiment — Single Agent + Zelos Diagnosis Engine.

Baseline Agent, but test failures are parsed by Diagnosis Engine into
structured output instead of feeding raw logs to the Agent.
"""

import json, os, re, subprocess, sys, time

from agent_wrapper import (ClaudeCodeAgent, apply_and_verify_patch,
                           checkout_instance_commit)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
try:
    from zelos.diagnosis_engine import DiagnosisEngine
    from zelos.failure_classifier import FailureClassifier
    HAS_ZELOS = True
except ImportError:
    HAS_ZELOS = False

MAX_RETRIES = 3
OUTPUT_DIR = "logs/poc_results/runtime_diag"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def _extract_target_file(instance: dict, repo_dir: str) -> str:
    """Find source file by grepping for function names in issue."""
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


def run_runtime_diag(instance: dict, repo_dir: str) -> dict:
    iid = instance["instance_id"]
    issue = instance.get("problem_statement", "")
    target_file = _extract_target_file(instance, repo_dir)

    if not checkout_instance_commit(instance, repo_dir):
        print(f"  WARNING: Could not checkout base_commit")

    agent = ClaudeCodeAgent(repo_dir)
    de = DiagnosisEngine() if HAS_ZELOS else None
    fc = FailureClassifier() if HAS_ZELOS else None

    print(f"\n{'='*60}")
    print(f"+DIAGNOSIS: {iid}  (target: {target_file or 'auto'})")
    print(f"{'='*60}")

    t_start = time.perf_counter()
    patch = ""
    retry_count = 0
    total_diag_tokens = 0

    for attempt in range(MAX_RETRIES + 1):
        if attempt == 0:
            print(f"  Attempt {attempt+1}: generating patch...")
            result = agent.generate_patch(issue, target_file)
        else:
            print(f"  Attempt {attempt+1}: repairing with diagnosis...")
            result = agent.repair_patch(issue, last_diag_text, patch)

        patch = result.get("patch", "")
        if not patch or len(patch) < 20:
            print(f"  ✗ Empty/short patch")
            retry_count += 1
            continue

        elapsed = result.get("elapsed_s", 0)
        tokens = agent._total_input_tokens + agent._total_output_tokens
        print(f"  Patch: {len(patch)} chars, {elapsed:.0f}s, tokens={tokens}")

        test_result = apply_and_verify_patch(patch, iid, repo_dir)
        if test_result["all_passed"]:
            print(f"  ✓ OK!")
            break

        retry_count += 1
        raw = test_result.get("raw_output", "")

        # ── Runtime Diagnosis ──
        if de and raw:
            diag = de.diagnose(raw)
            total_diag_tokens += len(str(diag.to_dict())) // 4
            print(f"    Diag: {diag.failed}F impact={diag.impact_scope}")
            last_diag_text = str(diag.to_dict())
            if fc:
                cls = fc.classify(diag)
                print(f"    Classifier: {cls.action} salvageable={cls.salvageable}")
                if cls.action == "abandon":
                    break
        else:
            last_diag_text = raw[:500]  # Fallback: raw error as diagnosis

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
