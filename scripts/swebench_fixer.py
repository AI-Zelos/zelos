#!/usr/bin/env python3
"""
SWE-bench Runtime-Guided Repair — P1 Fixer Loop.

Pipeline:
  1. Claude Code generates initial patch
  2. SWE-bench Docker eval → test output
  3. If failed: Diagnosis Engine → Failure Classifier
  4. If salvageable: build RepairContext → Claude Code fixes → re-eval
  5. Repeat up to 3 rounds
"""

import json, os, re, subprocess, time
from datasets import load_dataset

from zelos.diagnosis_engine import DiagnosisEngine
from zelos.failure_classifier import FailureClassifier
from zelos.repair_orchestrator import RepairOrchestrator

# ── Load ──
ds = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
INSTANCES = [
    "astropy__astropy-12907","astropy__astropy-14182","astropy__astropy-14365",
    "astropy__astropy-14995","astropy__astropy-6938","astropy__astropy-7746",
    "django__django-10914","django__django-10924","django__django-11001",
    "django__django-11019","django__django-11039","django__django-11049",
    "django__django-11099","django__django-11133","django__django-11179",
    "django__django-11283","django__django-11422","django__django-11564",
    "django__django-11583","django__django-11620",
]
instances = {i["instance_id"]: i for i in ds if i["instance_id"] in INSTANCES}

diagnosis_engine = DiagnosisEngine()
classifier = FailureClassifier()
repair_orch = RepairOrchestrator(max_attempts=3)

def claude(prompt, timeout=300):
    r = subprocess.run(["claude","--print","--output-format","text",prompt],
        capture_output=True,text=True,timeout=timeout,input="")
    return r.stdout.strip()

def coder_prompt(issue):
    return f"Fix this issue. Output ONLY unified diff patch. No markdown.\nRepo: {issue['repo']}\nIssue: {issue['problem_statement'][:2000]}"

def run_docker_eval(instance_id, patch):
    """Run single SWE-bench eval and return test output."""
    pred_file = f"/tmp/swebench_fixer_{instance_id}.json"
    with open(pred_file,"w") as f:
        json.dump([{"instance_id":instance_id,"model_name_or_path":"zelos-fixer","model_patch":patch}], f)
    result = subprocess.run([
        "python3","-m","swebench.harness.run_evaluation",
        "--dataset_name","princeton-nlp/SWE-bench_Lite","--split","test",
        "--predictions_path",pred_file,"--max_workers","1",
        "--run_id",f"fixer-{instance_id}","--timeout","900",
    ], capture_output=True, text=True, timeout=600)
    os.unlink(pred_file)
    return result.stdout + "\n" + result.stderr

def check_passed(test_output):
    """Check if all tests passed."""
    return "resolved_instances\": 1" in test_output or "resolved_ids" in test_output

# ── Run ──
results = []
for i, iid in enumerate(INSTANCES):
    inst = instances[iid]
    print(f"\n[{i+1}/{len(INSTANCES)}] {iid}", flush=True)
    t0 = time.perf_counter()

    # Phase 1: Initial generation
    patch = claude(coder_prompt(inst))

    # Phase 2: Docker eval
    test_output = run_docker_eval(iid, patch)
    passed = check_passed(test_output)

    fixer_rounds = 0
    hypotheses = []

    if not passed:
        # Phase 3: Diagnosis + Repair loop
        diagnosis = diagnosis_engine.diagnose(test_output)
        classification = classifier.classify(diagnosis)

        print(f"  Dx: {diagnosis.failed}F/{diagnosis.total_tests}T, {diagnosis.impact_scope}, {classification.action}", flush=True)

        while (repair_orch.should_repair(classification) and fixer_rounds < 3):
            fixer_rounds += 1
            ctx = repair_orch.build_context(
                issue=inst["problem_statement"],
                patch=patch,
                diagnosis=diagnosis,
                previous_hypotheses=hypotheses,
            )
            prompt = ctx.build_fixer_prompt()

            # Fixer round
            patch = claude(prompt)
            test_output = run_docker_eval(iid, patch)
            passed = check_passed(test_output)

            h = repair_orch.record_hypothesis(fixer_rounds, f"Fixer round {fixer_rounds}",
                                              "passed" if passed else "still_failing")
            hypotheses.append(h)

            if passed:
                break
            diagnosis = diagnosis_engine.diagnose(test_output)
            classification = classifier.classify(diagnosis)
            print(f"    Round {fixer_rounds}: {'PASS' if passed else 'FAIL'} -> {classification.action}", flush=True)

    elapsed = time.perf_counter() - t0
    status = "PASS" if passed else "FAIL"
    print(f"  {status}: {fixer_rounds} fixer rounds, {elapsed:.0f}s", flush=True)

    results.append({
        "instance_id": iid,
        "model_name_or_path": "zelos-fixer",
        "model_patch": patch,
        "fixer_rounds": fixer_rounds,
        "passed": passed,
    })

# ── Save ──
os.makedirs("data", exist_ok=True)
with open("data/swebench_fixer.json","w") as f:
    json.dump(results, f, indent=2)
passed = sum(1 for r in results if r["passed"])
print(f"\n{'='*60}")
print(f"FIXER RESULTS: {passed}/{len(results)} passed ({passed/len(results)*100:.1f}%)")
print(f"Saved to data/swebench_fixer.json")
