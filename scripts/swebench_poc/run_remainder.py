#!/usr/bin/env python3
"""Run remaining experiments (skip already-completed)."""
import json, os, sys, time
sys.path.insert(0, 'scripts/swebench_poc')
from runtime_diag import run_runtime_diag
from orchestrated import run_orchestrated

with open('logs/poc/selected_instances_full.json') as f:
    instances = [i for i in json.load(f) if 'sympy' not in i['instance_id']]

repo_map = {'xarray': '/tmp/xarray_repo', 'django': '/tmp/django_repo'}

def already_done(group, iid):
    path = f'logs/poc_results/{group}/{iid.replace("/","_")}.json'
    return os.path.exists(path) and os.path.getsize(path) > 200

results = []

for group, runner, name in [
    ("runtime_diag", run_runtime_diag, "+DIAGNOSIS"),
    ("orchestrated", run_orchestrated, "+ORCHESTRATION"),
]:
    todo = [i for i in instances if not already_done(group, i['instance_id'])]
    if not todo:
        print(f"\n{name}: all done, skipping")
        continue
    print(f"\n{'='*60}")
    print(f"{name}: {len(todo)} remaining")
    print(f"{'='*60}")
    for inst in todo:
        repo_dir = repo_map[inst['repo'].split('/')[1]]
        t0 = time.perf_counter()
        try:
            result = runner(inst, repo_dir)
            e = time.perf_counter() - t0
            m = result['metrics']
            print(f"  {inst['instance_id']}: {'PASS' if result['result']['pass'] else 'FAIL'} | {e:.0f}s | Retries={m.get('retry_count',m.get('replan_count','?'))} | Tokens={m.get('total_tokens_estimate',0):,}")
        except Exception as ex:
            print(f"  {inst['instance_id']}: ERROR - {ex}")
        results.append(result)

print(f"\n{'='*60}")
print("DONE")
for r in results:
    print(f"  [{r['group']:15s}] {r['instance_id']}: {'PASS' if r['result']['pass'] else 'FAIL'}")
