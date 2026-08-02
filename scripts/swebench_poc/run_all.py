#!/usr/bin/env python3
"""Run all 3 experiment groups for all 5 instances."""
import json, sys, time
sys.path.insert(0, 'scripts/swebench_poc')
from baseline import run_baseline
from runtime_diag import run_runtime_diag
from orchestrated import run_orchestrated

with open('logs/poc/selected_instances_full.json') as f:
    instances = json.load(f)

repo_map = {
    'xarray': '/tmp/xarray_repo',
    'django': '/tmp/django_repo',
    'sympy': '/tmp/sympy_repo',
}

# Phase 1: Sympy baseline
print("=" * 60)
print("PHASE 1: Sympy baseline")
print("=" * 60)
for inst in instances:
    repo_key = inst['repo'].split('/')[1]
    if repo_key == 'sympy':
        t0 = time.perf_counter()
        result = run_baseline(inst, repo_map[repo_key])
        print(f"  => Pass={result['result']['pass']} | {time.perf_counter()-t0:.0f}s | Retries={result['metrics']['retry_count']}")

# Phase 2: runtime_diag (all 5)
print("\n" + "=" * 60)
print("PHASE 2: +Runtime Diagnosis (all 5)")
print("=" * 60)
for inst in instances:
    repo_key = inst['repo'].split('/')[1]
    repo_dir = repo_map.get(repo_key, '')
    if not repo_dir: continue
    t0 = time.perf_counter()
    result = run_runtime_diag(inst, repo_dir)
    print(f"  => Pass={result['result']['pass']} | {time.perf_counter()-t0:.0f}s | Retries={result['metrics']['retry_count']} | Tokens={result['metrics']['total_tokens_estimate']:,}")

# Phase 3: orchestrated (all 5)
print("\n" + "=" * 60)
print("PHASE 3: +Orchestration (all 5)")
print("=" * 60)
for inst in instances:
    repo_key = inst['repo'].split('/')[1]
    repo_dir = repo_map.get(repo_key, '')
    if not repo_dir: continue
    t0 = time.perf_counter()
    result = run_orchestrated(inst, repo_dir)
    print(f"  => Pass={result['result']['pass']} | {time.perf_counter()-t0:.0f}s | Replans={result['metrics']['replan_count']} | Tokens={result['metrics']['total_tokens_estimate']:,}")

print("\n" + "=" * 60)
print("ALL DONE")
print("=" * 60)
