#!/usr/bin/env python3
"""
SWE-bench Zelos Multi-Agent Runner.

Pipeline: Planner → Coder → Reviewer
Each step is a Claude Code call. Reviewer fixes malformed patches.
"""

import json, os, subprocess, sys, time
from datasets import load_dataset

# Load the same instances
ds = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
INSTANCES = [
    "astropy__astropy-14182", "astropy__astropy-14995", "astropy__astropy-6938",
    "astropy__astropy-7746", "django__django-10914", "django__django-10924",
    "django__django-11001",
]
instances = {i["instance_id"]: i for i in ds if i["instance_id"] in INSTANCES}

def claude(prompt, timeout=300):
    """Call Claude Code CLI."""
    result = subprocess.run(
        ["claude", "--print", "--output-format", "text", prompt],
        capture_output=True, text=True, timeout=timeout, input="",
    )
    return result.stdout.strip()

def planner(instance):
    """Planner Agent: analyze the issue."""
    prompt = f"""You are a software architect. Analyze this GitHub issue and create a fix plan.

Repository: {instance['repo']}
Issue: {instance['problem_statement'][:2000]}

Output ONLY:
1. Root cause (1 sentence)
2. Files to modify (list)
3. Fix approach (2-3 sentences)"""
    return claude(prompt, timeout=120)

def coder(instance, plan):
    """Coder Agent: generate the patch."""
    prompt = f"""You are a senior developer. Write a unified diff patch to fix this issue.

Repository: {instance['repo']}

Fix plan from architect:
{plan}

Issue: {instance['problem_statement'][:1500]}

Output ONLY the unified diff patch. No markdown fences, no explanations. Just the diff."""
    return claude(prompt, timeout=180)

def reviewer(patch):
    """Reviewer Agent: fix patch format."""
    prompt = f"""Clean this patch. Remove markdown fences (```diff, ```), remove
any non-diff text, ensure it's a valid unified diff.

Input:
{patch[:5000]}

Output ONLY the cleaned unified diff. No markdown fences."""
    cleaned = claude(prompt, timeout=120)
    # Strip any remaining fences
    for fence in ["```diff", "``` Diff", "```diff\n", "```\n", "```"]:
        cleaned = cleaned.replace(fence, "")
    return cleaned.strip()

# ── Run ──
results = {}
for i, iid in enumerate(INSTANCES):
    inst = instances[iid]
    print(f"\n[{i+1}/7] {iid} — {inst['repo']}", flush=True)

    t0 = time.perf_counter()

    # Phase 1: Plan
    print("  Planner...", end=" ", flush=True)
    plan = planner(inst)
    print(f"{len(plan)} chars", flush=True)

    # Phase 2: Code
    print("  Coder...", end=" ", flush=True)
    patch = coder(inst, plan)
    print(f"{len(patch)} chars", flush=True)

    # Phase 3: Review
    print("  Reviewer...", end=" ", flush=True)
    cleaned = reviewer(patch)
    print(f"{len(cleaned)} chars", flush=True)

    elapsed = time.perf_counter() - t0
    print(f"  Total: {elapsed:.0f}s", flush=True)

    results[iid] = {
        "model_name_or_path": "zelos-multi-agent",
        "model_patch": cleaned,
        "elapsed_s": elapsed,
    }

# Save
os.makedirs("data", exist_ok=True)
out = "data/swebench_zelos.json"
with open(out, "w") as f:
    json.dump(list(results.values()), f, indent=2)
print(f"\nSaved to {out}")
