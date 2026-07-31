#!/usr/bin/env python3
"""
SWE-bench Zelos Runtime Test — v2.

Zelos value: deterministic verification + auto-retry.
NOT: LLM reviewing LLM output.
"""

import json, os, re, subprocess, sys, tempfile, time
from datasets import load_dataset

# ── Load ──
ds = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
INSTANCES = [
    "astropy__astropy-14182", "astropy__astropy-6938", "django__django-10924",
]
instances = {i["instance_id"]: i for i in ds if i["instance_id"] in INSTANCES}

# ── Claude Code call ──
def claude(prompt, timeout=300):
    r = subprocess.run(
        ["claude", "--print", "--output-format", "text", prompt],
        capture_output=True, text=True, timeout=timeout, input="",
    )
    return r.stdout.strip()

# ── Deterministic Verifiers ──
def verify_patch_format(patch):
    """Check if patch is a valid unified diff that can be applied."""
    # Must have diff indicators
    if not re.search(r'^(--- |\+\+\+ |diff --git)', patch, re.MULTILINE):
        return False, "No diff indicators found"
    # Must end with newline
    if not patch.endswith('\n'):
        return False, "Patch doesn't end with newline"
    # Try dry-run apply
    with tempfile.TemporaryDirectory() as d:
        patchfile = os.path.join(d, "test.patch")
        with open(patchfile, "w") as f:
            f.write(patch)
        result = subprocess.run(
            ["patch", "--dry-run", "-p1", "-i", patchfile],
            capture_output=True, text=True, cwd=d,
        )
        if result.returncode != 0:
            # Also try -p0
            result2 = subprocess.run(
                ["patch", "--dry-run", "-p0", "-i", patchfile],
                capture_output=True, text=True, cwd=d,
            )
            if result2.returncode != 0:
                return False, f"patch --dry-run failed (p1/p0): {result.stderr[:100]}"
    return True, "OK"

def verify_no_markdown(patch):
    """Check for markdown fences in patch."""
    for fence in ["```diff", "``` Diff", "```\n", "```"]:
        if fence in patch:
            return False, f"Contains markdown fence: {fence}"
    return True, "OK"

# ── Run with Zelos-style retry ──
MAX_RETRIES = 3
results = []

for i, iid in enumerate(INSTANCES):
    inst = instances[iid]
    print(f"\n[{i+1}/7] {iid} — {inst['repo']}", flush=True)

    prompt = (
        f"Fix this GitHub issue. Output ONLY a unified diff patch. No markdown.\n"
        f"Repository: {inst['repo']}\n"
        f"Issue: {inst['problem_statement'][:2000]}"
    )

    best_patch = None
    retries = 0
    t0 = time.perf_counter()

    for attempt in range(MAX_RETRIES):
        patch = claude(prompt, timeout=300)

        # Verify format
        fmt_ok, fmt_reason = verify_patch_format(patch)
        md_ok, md_reason = verify_no_markdown(patch)

        if fmt_ok and md_ok:
            best_patch = patch
            retries = attempt
            break
        else:
            retries = attempt + 1
            reason = f"fmt={fmt_reason}" if not fmt_ok else f"md={md_reason}"
            print(f"  Attempt {attempt+1}: FAIL ({reason}), retrying...", flush=True)

    elapsed = time.perf_counter() - t0
    if best_patch:
        print(f"  OK: {len(best_patch)} chars, {retries} retries, {elapsed:.0f}s", flush=True)
    else:
        print(f"  GAVE UP after {MAX_RETRIES} attempts, {elapsed:.0f}s", flush=True)

    results.append({
        "instance_id": iid,
        "model_name_or_path": "zelos-runtime",
        "model_patch": best_patch or patch,
        "zelos_retries": retries,
        "zelos_verified": best_patch is not None,
    })

# ── Save ──
os.makedirs("data", exist_ok=True)
with open("data/swebench_zelos_v2.json", "w") as f:
    json.dump(results, f, indent=2)

verified = sum(1 for r in results if r["zelos_verified"])
print(f"\nZelos Runtime: {verified}/{len(results)} verified, "
      f"{sum(r['zelos_retries'] for r in results)} total retries")
print("Saved to data/swebench_zelos_v2.json")
