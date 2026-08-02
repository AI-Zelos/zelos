#!/usr/bin/env python3
"""Run 3 groups for 4 instances (skip sympy)."""
import json, sys, time
sys.path.insert(0, 'scripts/swebench_poc')
from baseline import run_baseline
from runtime_diag import run_runtime_diag
from orchestrated import run_orchestrated

with open('logs/poc/selected_instances_full.json') as f:
    instances = [i for i in json.load(f) if 'sympy' not in i['instance_id']]

repo_map = {'xarray': '/tmp/xarray_repo', 'django': '/tmp/django_repo'}
results = []

for phase, runner, name in [
    (1, run_baseline, "BASELINE"),
    (2, run_runtime_diag, "+DIAGNOSIS"),
    (3, run_orchestrated, "+ORCHESTRATION"),
]:
    print(f"\n{'='*60}")
    print(f"PHASE {phase}: {name} ({len(instances)} instances)")
    print(f"{'='*60}")
    for inst in instances:
        repo_key = inst['repo'].split('/')[1]
        repo_dir = repo_map[repo_key]
        t0 = time.perf_counter()
        result = runner(inst, repo_dir)
        e = time.perf_counter() - t0
        m = result['metrics']
        print(f"  {inst['instance_id']}: Pass={result['result']['pass']} | {e:.0f}s | Retries={m.get('retry_count',m.get('replan_count','?'))} | Tokens={m.get('total_tokens_estimate',0):,}")
        results.append(result)

print(f"\n{'='*60}")
print("ALL DONE")
for r in results:
    print(f"  [{r['group']:15s}] {r['instance_id']}: {'PASS' if r['result']['pass'] else 'FAIL'}")
print(f"{'='*60}")
