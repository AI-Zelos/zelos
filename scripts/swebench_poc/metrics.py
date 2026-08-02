#!/usr/bin/env python3
"""
Metrics collection and calculation for PoC experiment results.

Reads individual experiment JSON files and computes:
  - Per-group pass rates
  - Token consumption (total + breakdown)
  - Retry/replan counts
  - Decision reach rate (orchestrated only)
  - Diagnosis accuracy (orchestrated only)
"""

import json
import os


def load_results(results_dir: str, group: str) -> list[dict]:
    """Load all result JSON files for a group."""
    group_dir = os.path.join(results_dir, group)
    if not os.path.isdir(group_dir):
        return []

    results = []
    for fname in sorted(os.listdir(group_dir)):
        if fname.endswith(".json"):
            with open(os.path.join(group_dir, fname)) as f:
                results.append(json.load(f))
    return results


def compute_group_summary(results: list[dict]) -> dict:
    """Compute summary statistics for one experiment group."""
    n = len(results)
    if n == 0:
        return {"count": 0}

    passed = sum(1 for r in results if r.get("result", {}).get("pass", False))
    total_tokens = sum(
        r.get("metrics", {}).get("total_tokens_estimate", 0) for r in results
    )
    retries = sum(
        r.get("metrics", {}).get("retry_count", 0) for r in results
    )
    avg_time = (
        sum(r.get("result", {}).get("total_time_seconds", 0) for r in results) / n
    )

    return {
        "count": n,
        "passed": passed,
        "pass_rate": f"{passed}/{n} ({passed/n:.0%})",
        "total_tokens_estimate": total_tokens,
        "avg_tokens_per_instance": total_tokens // n if n > 0 else 0,
        "total_retries": retries,
        "avg_retries_per_instance": round(retries / n, 1) if n > 0 else 0,
        "avg_time_seconds": round(avg_time, 0),
    }


def compute_per_instance_comparison(baseline_results: list[dict],
                                    diag_results: list[dict],
                                    orch_results: list[dict]) -> list[dict]:
    """Build per-instance comparison table data."""
    # Index results by instance_id
    baseline_map = {r["instance_id"]: r for r in baseline_results}
    diag_map = {r["instance_id"]: r for r in diag_results}
    orch_map = {r["instance_id"]: r for r in orch_results}

    all_ids = set()
    all_ids.update(baseline_map.keys(), diag_map.keys(), orch_map.keys())

    rows = []
    for iid in sorted(all_ids):
        b = baseline_map.get(iid, {})
        d = diag_map.get(iid, {})
        o = orch_map.get(iid, {})

        rows.append({
            "instance_id": iid,
            "baseline_pass": b.get("result", {}).get("pass", False),
            "diag_pass": d.get("result", {}).get("pass", False),
            "orch_pass": o.get("result", {}).get("pass", False),
            "baseline_tokens": b.get("metrics", {}).get("total_tokens_estimate", 0),
            "diag_tokens": d.get("metrics", {}).get("total_tokens_estimate", 0),
            "orch_tokens": o.get("metrics", {}).get("total_tokens_estimate", 0),
            "baseline_retries": b.get("metrics", {}).get("retry_count", 0),
            "diag_retries": d.get("metrics", {}).get("retry_count", 0),
            "orch_replans": o.get("metrics", {}).get("replan_count", 0),
            "orch_decision_reach_rate": o.get("metrics", {}).get(
                "decision_reach_rate", 0
            ),
        })

    return rows


def compute_orchestrated_details(orch_results: list[dict]) -> dict:
    """Compute orchestrated-specific metrics."""
    total_decisions = sum(
        len(r.get("metrics", {}).get("decisions", [])) for r in orch_results
    )
    total_replans = sum(
        r.get("metrics", {}).get("replan_count", 0) for r in orch_results
    )
    review_verdicts = [
        r.get("metrics", {}).get("review_verdict")
        for r in orch_results
        if r.get("metrics", {}).get("review_verdict") is not None
    ]
    review_pass_rate = (
        sum(1 for v in review_verdicts if v == "pass") / len(review_verdicts)
    ) if review_verdicts else 0

    return {
        "total_mpc_decisions": total_decisions,
        "total_replans": total_replans,
        "instances_with_replan": sum(
            1 for r in orch_results
            if r.get("metrics", {}).get("replan_count", 0) > 0
        ),
        "review_count": len(review_verdicts),
        "review_pass_rate": round(review_pass_rate, 2),
    }
