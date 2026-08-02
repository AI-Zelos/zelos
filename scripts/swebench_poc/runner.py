#!/usr/bin/env python3
"""
PoC Experiment Runner — Unified entry point.

Usage:
  # Step 1: Select instances
  python runner.py select-instances

  # Step 2: Run baseline group
  python runner.py run --group baseline --repo /path/to/repo

  # Step 2: Run +diagnosis group
  python runner.py run --group runtime_diag --repo /path/to/repo

  # Step 2: Run orchestrated group
  python runner.py run --group orchestrated --repo /path/to/repo

  # Step 2: Run all groups
  python runner.py run-all --repo /path/to/repo

  # Step 3: Generate report
  python runner.py report
"""

import json
import os
import subprocess
import sys

INSTANCES_FILE = "logs/poc/selected_instances.json"
RESULTS_DIR = "logs/poc_results"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def cmd_select_instances():
    """Step 1: Select 5 SWE-bench instances."""
    script = os.path.join(SCRIPT_DIR, "select_instances.py")
    subprocess.run([sys.executable, script], check=True)


def cmd_run(group: str, repo_dir: str):
    """Step 2: Run one experiment group."""
    if not os.path.exists(INSTANCES_FILE):
        print(f"ERROR: Instances file not found: {INSTANCES_FILE}")
        print("Run 'python runner.py select-instances' first.")
        sys.exit(1)

    script_map = {
        "baseline": "baseline.py",
        "runtime_diag": "runtime_diag.py",
        "orchestrated": "orchestrated.py",
    }

    if group not in script_map:
        print(f"ERROR: Unknown group '{group}'. "
              f"Options: {list(script_map.keys())}")
        sys.exit(1)

    script = os.path.join(SCRIPT_DIR, script_map[group])
    print(f"\n{'='*60}")
    print(f"Running {group} group...")
    print(f"{'='*60}")

    # Check Claude CLI availability
    try:
        subprocess.run(["claude", "--version"], capture_output=True, timeout=5)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print("WARNING: 'claude' CLI not found. Agent calls will fail.")
        print("Install Claude Code: https://docs.anthropic.com/en/docs/claude-code")

    subprocess.run(
        [sys.executable, script, INSTANCES_FILE, repo_dir],
        check=False,
    )


def cmd_run_all(repo_dir: str):
    """Run all three groups sequentially."""
    # Baseline first (go/no-go check)
    print("\n" + "="*60)
    print("PHASE 1/3: BASELINE (go/no-go after this)")
    print("="*60)
    cmd_run("baseline", repo_dir)

    # Go/no-go check
    with open(INSTANCES_FILE) as f:
        instances = json.load(f)
    total = len(instances)

    baseline_dir = os.path.join(RESULTS_DIR, "baseline")
    passed = 0
    if os.path.isdir(baseline_dir):
        for fname in os.listdir(baseline_dir):
            if fname.endswith(".json"):
                with open(os.path.join(baseline_dir, fname)) as f:
                    r = json.load(f)
                    if r.get("result", {}).get("pass", False):
                        passed += 1

    print(f"\n{'='*60}")
    print(f"GO/NO-GO CHECK: Baseline {passed}/{total} passed")
    print(f"{'='*60}")

    if passed <= 1:
        print("⚠️  Baseline pass rate ≤ 1/{0}. Consider:".format(total))
        print("   1. Choosing easier instances")
        print("   2. Using a stronger Agent")
        print("   Continuing anyway (experimental)...")
    elif passed >= total - 1:
        print(f"⚠️  Baseline pass rate ≥ {total-1}/{total}. Consider:")
        print("   1. Choosing harder instances (ceiling too high)")
        print("   Continuing anyway...")

    # Continue with diagnosis + orchestrated
    print("\n" + "="*60)
    print("PHASE 2/3: +RUNTIME DIAGNOSIS")
    print("="*60)
    cmd_run("runtime_diag", repo_dir)

    print("\n" + "="*60)
    print("PHASE 3/3: +ORCHESTRATION")
    print("="*60)
    cmd_run("orchestrated", repo_dir)

    # Generate report
    print("\n" + "="*60)
    print("GENERATING REPORT")
    print("="*60)
    cmd_report()


def cmd_report():
    """Step 3: Generate comparison report."""
    script = os.path.join(SCRIPT_DIR, "report.py")
    subprocess.run(
        [sys.executable, script, "--results-dir", RESULTS_DIR],
        check=False,
    )


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "select-instances":
        cmd_select_instances()

    elif command == "run":
        if len(sys.argv) < 4 or "--group" not in sys.argv:
            print("Usage: python runner.py run --group <group> --repo <path>")
            sys.exit(1)
        group_idx = sys.argv.index("--group")
        repo_idx = sys.argv.index("--repo")
        group = sys.argv[group_idx + 1]
        repo = sys.argv[repo_idx + 1]
        cmd_run(group, repo)

    elif command == "run-all":
        if "--repo" not in sys.argv:
            print("Usage: python runner.py run-all --repo <path>")
            sys.exit(1)
        repo_idx = sys.argv.index("--repo")
        repo = sys.argv[repo_idx + 1]
        cmd_run_all(repo)

    elif command == "report":
        cmd_report()

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
