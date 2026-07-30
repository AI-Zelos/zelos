#!/usr/bin/env python3
"""
SWE-bench Pilot — 10 instances, single-Agent baseline.

Prerequisites:
    pip install swebench datasets
    docker pull swebench/sweb.eval.x86_64.<instance>:latest  # auto-pulled by harness

Usage:
    python3 scripts/swebench_pilot.py
"""

import json
import os
import subprocess
import sys
import time
import uuid

# ── Load SWE-bench Lite ──
from datasets import load_dataset

print("Loading SWE-bench Lite (300 instances)...")
ds = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
instances = list(ds)[:10]  # pilot: first 10
print(f"Loaded {len(instances)} instances for pilot\n")


def ask_claude_code(instance):
    """Ask Claude Code to fix an issue. Returns (patch, success)."""
    repo = instance["repo"]
    base_commit = instance["base_commit"]
    problem = instance["problem_statement"]
    hint = instance.get("hints_text", "")

    prompt = f"""You are fixing a GitHub issue.

Repository: {repo}
Base commit: {base_commit}

Issue:
{problem}

{f'Hint: {hint}' if hint else ''}

Output ONLY a unified diff patch. No explanations, no markdown fences."""

    # Call Claude Code via CLI
    try:
        result = subprocess.run(
            ["claude", "--print", prompt],
            capture_output=True, text=True, timeout=300,
        )
        return result.stdout.strip(), result.returncode == 0
    except FileNotFoundError:
        print("  Claude Code CLI not found. Install: npm install -g @anthropic-ai/claude-code")
        return "", False
    except subprocess.TimeoutExpired:
        print("  Timeout (300s)")
        return "", False


def run_single(instance, idx):
    """Run one SWE-bench instance."""
    instance_id = instance["instance_id"]
    print(f"[{idx+1}/10] {instance_id} — {instance['repo']}")

    t0 = time.perf_counter()
    patch, ok = ask_claude_code(instance)
    elapsed = time.perf_counter() - t0

    if ok and patch:
        print(f"  OK: {len(patch)} chars patch, {elapsed:.0f}s")
    else:
        print(f"  FAIL: Claude Code error or timeout")

    return {
        "instance_id": instance_id,
        "model_name_or_path": "claude-code-pilot",
        "model_patch": patch,
        "elapsed_s": elapsed,
        "success": ok,
    }


# ── Run ──
results = []
for i, inst in enumerate(instances):
    results.append(run_single(inst, i))

# ── Save ──
out_file = f"data/swebench_pilot_{uuid.uuid4().hex[:8]}.json"
os.makedirs("data", exist_ok=True)

# SWE-bench format: {instance_id: patch_dict, ...}
predictions = {}
for r in results:
    predictions[r["instance_id"]] = {
        "model_name_or_path": r["model_name_or_path"],
        "model_patch": r["model_patch"],
    }

with open(out_file, "w") as f:
    json.dump(predictions, f, indent=2)

print(f"\nSaved {len(results)} predictions to {out_file}")
print(f"Submit: swebench run_eval --predictions_path {out_file} --dataset princeton-nlp/SWE-bench_Lite --split test")
