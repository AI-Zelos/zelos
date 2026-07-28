"""
Zelos Governance Demo — Complete Trustworthy Change Workflow
=============================================================

This 10-minute demo shows the full Zelos governance pipeline:
  1. Submit a Goal with structured Intent
  2. Planner decomposes into Tasks with Architecture Delta
  3. Agents execute, each returning Evidence
  4. Runtime collects Evidence → scores Confidence
  5. Policy Gate decides: auto-approve, auto-reject, or need human
  6. Execution Report generated — ready for human sign-off

Run: python3 demo/21_governance_demo.py
"""

import time
from zelos.runtime import ZelosRuntime
from zelos.execution_report import IntentSpec
from zelos.evidence import Evidence
from zelos.confidence import WeightedConfidenceScorer
from zelos.policy_gate import EvidenceBasedPolicyGate


def main():
    print("=" * 65)
    print("  ZELOS GOVERNANCE DEMO — Trustworthy Change Workflow")
    print("=" * 65)

    # ═══ Step 1: Start Runtime ═══
    print("\n🚀 Step 1: Starting Zelos Runtime...")
    rt = ZelosRuntime()

    # Register a demo agent
    rt.add_agent(
        "DemoCoder",
        "test:Agent",
        [type("Cap", (), {
            "name": "code-generation.python", "version": "1.0",
            "description": "", "input_schema": {}, "output_schema": {}, "tags": [],
        })()],
    )
    rt.start()
    print("   Runtime started. Agent registered.")

    # ═══ Step 2: Submit Goal with Intent ═══
    print("\n📝 Step 2: Submitting Goal with structured Intent...")
    intent = IntentSpec(
        description="Implement OAuth2 login with Google and GitHub",
        success_criteria=[
            "Users can sign in with Google OAuth",
            "Users can sign in with GitHub OAuth",
            "Auth tokens expire after 24 hours",
            "Existing password login still works"
        ],
        constraints=[
            "Do not modify password hashing logic",
            "Use standard OAuth2.0 libraries",
            "No client_secret in frontend code"
        ],
        scope="single_module",
    )

    result = rt.submit_goal("OAuth2 login", intent=intent, priority="high")
    goal_id = result["goal_id"]
    print(f"   Goal submitted: {goal_id[:8]}...")
    print(f"   Status: {result['status']}")

    # ═══ Step 3: Add Evidence (simulating Agent outputs) ═══
    print("\n📊 Step 3: Agents executing, collecting Evidence...")
    time.sleep(0.5)

    rt.add_evidence(goal_id, Evidence(
        type="test_result", tool="pytest", result="PASS",
        data={"passed": 47, "failed": 0, "coverage_pct": 89},
        summary="47/47 tests passed, 89% coverage"
    ))
    rt.add_evidence(goal_id, Evidence(
        type="security_scan", tool="bandit", result="PASS",
        data={"issues": 0, "severity_high": 0, "severity_medium": 0},
        summary="No security vulnerabilities found"
    ))
    rt.add_evidence(goal_id, Evidence(
        type="benchmark", tool="wrk", result="PASS",
        data={"metric": "tps", "baseline": 850, "actual": 1120, "p99_ms": 45},
        summary="TPS +31.8% (850 → 1120), p99=45ms"
    ))
    rt.add_evidence(goal_id, Evidence(
        type="api_diff", tool="openapi-diff", result="PASS",
        data={"breaking_changes": 0, "new_endpoints": 1, "modified_endpoints": 0},
        summary="API backward compatible: +1 new endpoint"
    ))
    print("   4 evidence items collected: test_result, security_scan, benchmark, api_diff")

    # ═══ Step 4: Wait for completion ═══
    print("\n⏳ Step 4: Waiting for goal completion...")
    rt.wait_for_goal(goal_id, timeout_seconds=5)

    # ═══ Step 5: Get Execution Report ═══
    print("\n📋 Step 5: Generating Execution Report...")
    report = rt.get_execution_report(goal_id)

    print(f"""
   ┌─────────────────────────────────────────────────┐
   │           EXECUTION REPORT                       │
   ├─────────────────────────────────────────────────┤
   │ Goal:      {report.goal_id[:20]}...
   │ Status:    {report.status}
   │""")

    if report.intent:
        print(f"   │ Intent:    {report.intent.description[:50]}...")
        print(f"   │ Criteria:  {len(report.intent.success_criteria)} success criteria")

    if report.architecture_delta:
        print(f"   │ Arch Risk: {report.architecture_delta.risk_level}")

    print(f"   │ Tasks:     {len(report.trace.tasks) if report.trace else 0}")
    print(f"   │ Duration:  {report.total_duration_ms:.0f}ms")

    bag = report.evidence_bag
    print(f"   │ Evidence:  {len(bag.items)} items, all_pass={bag.all_pass}")
    for ev_type, summary in bag.summary.items():
        print(f"   │   {ev_type}: {summary.passed}/{summary.total} passed")

    c = report.confidence
    print(f"   │ Confidence: {c.score:.0%} → {c.recommendation}")
    for k, v in c.breakdown.items():
        print(f"   │   {k}: {v:.2f}")

    print(f"   │ Risk:      {report.risk_level}")
    if report.rollback_plan:
        print(f"   │ Rollback:  {report.rollback_plan.strategy} "
              f"(~{report.rollback_plan.estimated_downtime_s}s)")
    print(f"   └─────────────────────────────────────────────────┘")

    # ═══ Step 6: Policy Gate Decision ═══
    print("\n🚦 Step 6: Policy Gate decision...")
    decision = rt.auto_decide(goal_id)
    print(f"   Decision: {decision['action']}")
    print(f"   Reason:   {decision['reason']}")
    if decision.get("required_approvers"):
        print(f"   Approvers needed: {decision['required_approvers']}")

    # ═══ Step 7: Summary ═══
    print(f"""
   ╔═══════════════════════════════════════════════════╗
   ║  {'✅ CHANGE APPROVED' if decision['action'] == 'auto_approve' else '🤔 NEEDS HUMAN REVIEW'}                          ║
   ╠═══════════════════════════════════════════════════╣
   ║  What happened:                                   ║
   ║  1. Intent specified with 4 success criteria      ║
   ║  2. Agents executed, returned 4 evidence items    ║
   ║  3. All evidence PASSED                           ║
   ║  4. Confidence scored at {c.score:.0%}                      ║
   ║  5. Policy Gate: {decision['action']:44s} ║
   ║                                                   ║
   ║  No code was manually reviewed.                   ║
   ║  The evidence spoke for itself.                   ║
   ╚═══════════════════════════════════════════════════╝
    """)

    rt.shutdown()
    print("Demo complete. 🎉")


if __name__ == "__main__":
    main()
