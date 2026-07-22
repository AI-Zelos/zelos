"""
Demo 20 — Human-in-the-Loop (HITL) Approval Workflow

Complete lifecycle: create → approve/reject/request-changes → timeout → audit trail.

Covers 6 scenarios:
  1. Single approver (any-one-sufficient)
  2. Multi-approver with require_all=True
  3. Rejection with reason
  4. Change request with feedback loop
  5. Timeout auto-rejection
  6. Immutable audit trail

Run: python3 demo/20_hitl_approval_workflow.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.advanced_execution import HumanInTheLoop


def scenario_1_single_approval():
    print("── Scenario 1: Single Approver ──")
    hitl = HumanInTheLoop()
    req = hitl.create_request("task-deploy", "Deploy payment-api to production", ["alice@org.com"])
    print(f"  Created: {req.request_id} (pending)")
    hitl.approve(req.request_id, "alice@org.com", "LGTM, ship it")
    result = hitl.get_request(req.request_id)
    assert result.status.value == "approved"
    print("  → Approved by alice\n")


def scenario_2_multi_approver():
    print("── Scenario 2: Multi-Approver (require_all=True) ──")
    hitl = HumanInTheLoop()
    req = hitl.create_request(
        "task-rotate-creds", "Rotate root credentials", ["sec-admin@org.com", "cto@org.com"], require_all=True
    )
    print(f"  Created: {req.request_id} (requires BOTH)")
    hitl.approve(req.request_id, "cto@org.com", "Mgmt approved")
    r1 = hitl.get_request(req.request_id)
    print(f"  After cto: {r1.status.value} (still waiting)")
    assert r1.status.value == "pending"
    hitl.approve(req.request_id, "sec-admin@org.com", "Security OK")
    r2 = hitl.get_request(req.request_id)
    assert r2.status.value == "approved"
    print(f"  After sec-admin: {r2.status.value}\n")


def scenario_3_rejection():
    print("── Scenario 3: Rejection with Reason ──")
    hitl = HumanInTheLoop()
    req = hitl.create_request("task-bad-code", "Review AI-generated payment module", ["senior-dev@org.com"])
    hitl.reject(req.request_id, "senior-dev@org.com", "Missing error handling in payment flow")
    r = hitl.get_request(req.request_id)
    assert r.status.value == "rejected"
    print(f"  → Rejected: {r.resolution_comment}\n")


def scenario_4_change_request():
    print("── Scenario 4: Change Request with Feedback ──")
    hitl = HumanInTheLoop()
    req = hitl.create_request("task-ui-widget", "Review React dashboard", ["designer@org.com"])
    hitl.request_changes(
        req.request_id, "designer@org.com", "Color contrast too low (WCAG AA 4.5:1). Add loading skeleton."
    )
    r1 = hitl.get_request(req.request_id)
    assert r1.status.value == "changes_requested"
    print(f"  → Changes requested: {r1.resolution_comment[:60]}...")
    print("  → Agent fixes issues and submits a NEW approval request")
    # After changes, agent creates new request for the revised work
    req2 = hitl.create_request("task-ui-widget-v2", "Review React dashboard (revised)", ["designer@org.com"])
    hitl.approve(req2.request_id, "designer@org.com", "All fixes applied, WCAG compliant, looks great")
    r2 = hitl.get_request(req2.request_id)
    assert r2.status.value == "approved"
    print(f"  → New request approved: {r2.status.value}\n")


def scenario_5_timeout():
    print("── Scenario 5: Timeout Auto-Rejection ──")
    hitl = HumanInTheLoop()
    req = hitl.create_request("task-urgent", "Fix prod outage", ["oncall@org.com"], timeout_seconds=1)
    print("  Created with 1s timeout, waiting...")
    time.sleep(1.5)
    timed_out = hitl.check_timeouts()
    r = hitl.get_request(req.request_id)
    assert r.status.value == "timed_out"
    print(f"  → Auto-rejected ({len(timed_out)} overdue)\n")


def scenario_6_audit_trail():
    print("── Scenario 6: Immutable Audit Trail ──")
    hitl = HumanInTheLoop()
    req = hitl.create_request("task-q3-report", "Auto-generated Q3 financial report", ["cfo@org.com"])
    hitl.approve(req.request_id, "cfo@org.com", "Verified against Q3 ledger — approved")
    history = hitl.get_history(req.request_id)
    for h in history:
        print(f"  [{h['action']:>8}] {h.get('approver', ''):<20} {h.get('comment', '')}")
    assert len(history) == 2
    print("  → 2 actions recorded (created + approved)\n")


if __name__ == "__main__":
    print("=" * 60)
    print("  HITL APPROVAL WORKFLOW — 6 SCENARIOS")
    print("=" * 60 + "\n")
    scenario_1_single_approval()
    scenario_2_multi_approver()
    scenario_3_rejection()
    scenario_4_change_request()
    scenario_5_timeout()
    scenario_6_audit_trail()
    print("=" * 60)
    print("  ✅ ALL 6 HITL SCENARIOS PASSED")
    print("=" * 60)
