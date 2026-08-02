#!/usr/bin/env python3
"""
Step 1: Select 5 SWE-bench Verified instances for PoC experiment.

Criteria (from experiment design doc):
  - Difficulty gradient: 2 simple (1-2 files), 2 medium (3-5 files), 1 hard (5+ files)
  - Deterministic: clear FAIL_TO_PASS tests, no flaky instances
  - Diverse: at least 3 different projects
  - Runnable: Docker image available

Output: logs/poc/selected_instances.json
"""

import json
import os
import sys

# ── Config ──
OUTPUT_DIR = "logs/poc"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "selected_instances.json")
MIN_FAIL_TESTS = 1
MAX_FAIL_TESTS = 10
MAX_FILES_CHANGED = 10

os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_dataset():
    """Load SWE-bench Verified dataset. Tries hf-mirror first for China access."""
    from datasets import load_dataset

    # Try mirror first (no VPN needed in China)
    for endpoint in [
        "https://hf-mirror.com",
        "https://huggingface.co",
    ]:
        try:
            os.environ["HF_ENDPOINT"] = endpoint
            ds = load_dataset("princeton-nlp/SWE-bench_Verified", split="test")
            print(f"✓ Loaded SWE-bench_Verified from {endpoint}: {len(ds)} instances")
            return ds
        except Exception as e:
            print(f"  Failed via {endpoint}: {e}")

    # Fallback: try SWE-bench_Lite (smaller, more widely available)
    try:
        ds = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
        print(f"✓ Fallback to SWE-bench_Lite: {len(ds)} instances")
        return ds
    except Exception as e:
        print(f"✗ Cannot load any SWE-bench dataset: {e}")
        sys.exit(1)


def parse_test_list(value) -> list:
    """Parse FAIL_TO_PASS / PASS_TO_PASS which may be JSON string or list."""
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            # Split by newline if not JSON
            return [t.strip() for t in value.split("\n") if t.strip()]
    return []


def estimate_file_count(test_patch: str) -> int:
    """Estimate number of files to change from test_patch."""
    if not test_patch:
        return 999
    files = set()
    for line in test_patch.split("\n"):
        if line.startswith("+++ b/") or line.startswith("--- a/"):
            f = line[6:].split("\t")[0]
            if f != "/dev/null":
                files.add(f)
    return len(files)


def classify_difficulty(file_count):
    if file_count <= 2:
        return "simple"
    elif file_count <= 5:
        return "medium"
    else:
        return "hard"


def select_instances(dataset, target_count=5):
    candidates = []

    for inst in dataset:
        iid = inst.get("instance_id", "")
        repo = inst.get("repo", "")
        fail_tests = parse_test_list(inst.get("FAIL_TO_PASS", []))
        pass_tests = parse_test_list(inst.get("PASS_TO_PASS", []))
        test_patch = inst.get("test_patch", "")
        problem = inst.get("problem_statement", "")

        if not fail_tests:
            continue
        if len(fail_tests) < MIN_FAIL_TESTS or len(fail_tests) > MAX_FAIL_TESTS:
            continue
        if not test_patch or not problem:
            continue

        file_count = estimate_file_count(test_patch)
        if file_count == 0 or file_count > MAX_FILES_CHANGED:
            continue

        difficulty = classify_difficulty(file_count)
        total_tests = len(fail_tests) + len(pass_tests)

        candidates.append({
            "instance_id": iid,
            "repo": repo,
            "difficulty": difficulty,
            "file_count": file_count,
            "fail_tests": len(fail_tests),
            "pass_tests": len(pass_tests),
            "total_tests": total_tests,
            "problem_length": len(problem),
        })

    print(f"  Filtered {len(candidates)} candidate instances")

    # Group by difficulty and repo
    by_difficulty = {"simple": [], "medium": [], "hard": []}
    for c in candidates:
        by_difficulty[c["difficulty"]].append(c)

    print(f"  Simple: {len(by_difficulty['simple'])}, "
          f"Medium: {len(by_difficulty['medium'])}, "
          f"Hard: {len(by_difficulty['hard'])}")

    # Pick instances with repo diversity
    selected = []
    used_repos = set()

    # Desired: 2 simple, 2 medium, 1 hard
    buckets = [
        ("simple", 2),
        ("medium", 2),
        ("hard", 1),
    ]

    for difficulty, count in buckets:
        pool = sorted(
            by_difficulty[difficulty],
            key=lambda c: (
                c["repo"] in used_repos,  # Penalize same-repo
                -c["total_tests"],        # Prefer more tests
            ),
        )
        for c in pool:
            if len([s for s in selected if s["difficulty"] == difficulty]) >= count:
                break
            selected.append(c)
            used_repos.add(c["repo"])

        # If not enough in this difficulty, grab from other levels
        if len([s for s in selected if s["difficulty"] == difficulty]) < count:
            fill_pool = sorted(
                by_difficulty["hard"] + by_difficulty["medium"],
                key=lambda c: (
                    c["repo"] in used_repos,
                    -c["total_tests"],
                ),
            )
            for c in fill_pool:
                if c["instance_id"] in [s["instance_id"] for s in selected]:
                    continue
                if len([s for s in selected if s["difficulty"] == difficulty]) >= count:
                    break
                c["difficulty"] = difficulty  # Reclassify
                selected.append(c)
                used_repos.add(c["repo"])

    return selected


def main():
    print("Step 1: Selecting SWE-bench instances for PoC...")
    dataset = load_dataset()

    selected = select_instances(dataset, target_count=5)

    print(f"\nSelected {len(selected)} instances:")
    print("-" * 80)
    for i, s in enumerate(selected):
        print(f"  {i+1}. [{s['difficulty']:7s}] {s['instance_id']}")
        print(f"      Repo: {s['repo']}, Files: ~{s['file_count']}, "
              f"Tests: {s['total_tests']} ({s['fail_tests']} fail + {s['pass_tests']} pass)")
    print("-" * 80)

    # Save
    with open(OUTPUT_FILE, "w") as f:
        json.dump(selected, f, indent=2)
    print(f"\nSaved to {OUTPUT_FILE}")

    # Export instance IDs for runner
    ids_file = os.path.join(OUTPUT_DIR, "selected_instance_ids.txt")
    with open(ids_file, "w") as f:
        for s in selected:
            f.write(s["instance_id"] + "\n")
    print(f"Instance IDs saved to {ids_file}")


if __name__ == "__main__":
    main()
