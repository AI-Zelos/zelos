"""
v0.9.0 REQ-07: Execution Report Tests.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.runtime import ZelosRuntime
from zelos.evidence import Evidence


def make_cap():
    return type("Cap", (), {"name": "code", "version": "1.0", "description": "",
                             "input_schema": {}, "output_schema": {}, "tags": []})()


def test_get_execution_report():
    """get_execution_report() returns complete ExecutionReport."""
    print("\n📋 REQ-07.1: get_execution_report")

    rt = ZelosRuntime()
    rt.add_agent("ReportAgent", "test:Agent", [make_cap()])
    rt.start()

    result = rt.submit_goal("Report test goal")
    goal_id = result["goal_id"]
    rt.wait_for_goal(goal_id, timeout_seconds=10)

    report = rt.get_execution_report(goal_id)
    assert report is not None
    assert report.goal_id == goal_id
    assert report.status in ("completed", "accepted", "planned", "failed")
    assert report.trace is not None
    assert report.trace.goal_id == goal_id
    assert report.evidence_bag is not None
    assert report.confidence is not None
    print(f"  ✅ ExecutionReport: status={report.status}, "
          f"confidence={report.confidence.score:.2f}, "
          f"risk={report.risk_level}")


def test_execution_report_to_dict():
    """ExecutionReport serialization round-trip."""
    print("\n📋 REQ-07.2: ExecutionReport serialization")

    rt = ZelosRuntime()
    rt.add_agent("SerReportAgent", "test:Agent", [make_cap()])
    rt.start()

    result = rt.submit_goal("Serialization test")
    goal_id = result["goal_id"]
    rt.wait_for_goal(goal_id, timeout_seconds=10)

    report = rt.get_execution_report(goal_id)
    d = report.to_dict()
    assert d["goal_id"] == goal_id
    assert d["status"] in ("completed", "accepted", "planned", "failed")
    assert "trace" in d
    assert "evidence_bag" in d
    assert "confidence" in d
    rt.shutdown()
    print("  ✅ ExecutionReport.to_dict() OK")


def test_execution_report_json_serializable():
    """ExecutionReport is JSON serializable."""
    print("\n📋 REQ-07.3: ExecutionReport JSON serializable")

    import json
    rt = ZelosRuntime()
    rt.add_agent("JsonAgent", "test:Agent", [make_cap()])
    rt.start()

    result = rt.submit_goal("JSON test")
    goal_id = result["goal_id"]
    rt.wait_for_goal(goal_id, timeout_seconds=10)

    report = rt.get_execution_report(goal_id)
    json_str = json.dumps(report.to_dict(), default=str)
    assert len(json_str) > 0
    parsed = json.loads(json_str)
    assert parsed["goal_id"] == goal_id
    rt.shutdown()
    print(f"  ✅ JSON serializable ({len(json_str)} bytes)")


if __name__ == "__main__":
    print("=" * 60)
    print("  ZELOS v0.9.0 — REQ-07 EXECUTION REPORT TESTS")
    print("=" * 60)
    test_get_execution_report()
    test_execution_report_to_dict()
    test_execution_report_json_serializable()
    print(f"\n{'=' * 60}")
    print("  RESULTS: All REQ-07 tests passed ✅")
    print(f"{'=' * 60}")
