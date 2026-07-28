"""
v0.9.0 REQ-05: Evidence Collection Framework Tests.
"""
import os, sys, time, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.evidence import Evidence, EvidenceBag, EvidenceSummary


def test_evidence_dataclass():
    """Evidence dataclass creation and serialization."""
    print("\n📊 REQ-05.1: Evidence dataclass")

    ev = Evidence(
        type="test_result", tool="pytest", result="PASS",
        data={"passed": 47, "failed": 0, "skipped": 2},
        summary="All tests passed (47/47)"
    )
    d = ev.to_dict()
    restored = Evidence.from_dict(d)
    assert restored.type == "test_result"
    assert restored.tool == "pytest"
    assert restored.result == "PASS"
    assert restored.data["passed"] == 47
    print("  ✅ Evidence round-trip OK")


def test_evidence_bag_aggregation():
    """EvidenceBag aggregates evidence by type."""
    print("\n📊 REQ-05.2: EvidenceBag aggregation")

    items = [
        Evidence("test_result", "pytest", "PASS", {"passed": 10, "failed": 0}),
        Evidence("test_result", "jest", "PASS", {"passed": 5, "failed": 0}),
        Evidence("security_scan", "bandit", "PASS", {"issues": 0}),
        Evidence("benchmark", "wrk", "PASS", {"tps": 1120}),
        Evidence("test_result", "cypress", "FAIL", {"passed": 3, "failed": 1}),
    ]

    bag = EvidenceBag(goal_id="g-1", items=items)
    assert bag.all_pass is False  # one FAIL
    assert len(bag.failed_items) == 1
    assert bag.failed_items[0].type == "test_result"
    assert "test_result" in bag.summary
    assert bag.summary["test_result"].total == 3
    assert bag.summary["test_result"].passed == 2
    assert bag.summary["test_result"].failed == 1
    print(f"  ✅ EvidenceBag: all_pass={bag.all_pass}, failed={len(bag.failed_items)}")


def test_evidence_bag_all_pass():
    """EvidenceBag.all_pass when everything passes."""
    print("\n📊 REQ-05.3: EvidenceBag — all_pass")

    items = [
        Evidence("test_result", "pytest", "PASS", {"passed": 10}),
        Evidence("security_scan", "bandit", "PASS", {}),
    ]
    bag = EvidenceBag(goal_id="g-2", items=items)
    assert bag.all_pass is True
    assert bag.failed_items == []
    print("  ✅ All evidence PASS → all_pass=True")


def test_evidence_bag_empty():
    """EvidenceBag with no items."""
    print("\n📊 REQ-05.4: EvidenceBag — empty")

    bag = EvidenceBag(goal_id="g-3", items=[])
    assert bag.all_pass is True  # empty = no failures
    print("  ✅ Empty EvidenceBag handled")


def test_evidence_large_batch_aggregation():
    """EvidenceBag with large batch auto-aggregates."""
    print("\n📊 REQ-05.5: EvidenceBag — large batch")

    items = [Evidence("test_result", "pytest", "PASS", {"passed": i}) for i in range(100)]
    bag = EvidenceBag(goal_id="g-big", items=items)
    assert len(bag.items) == 100
    assert bag.summary["test_result"].total == 100
    print(f"  ✅ 100 evidence items aggregated in {bag.summary['test_result'].total} total")


if __name__ == "__main__":
    print("=" * 60)
    print("  ZELOS v0.9.0 — REQ-05 EVIDENCE COLLECTION TESTS")
    print("=" * 60)
    test_evidence_dataclass()
    test_evidence_bag_aggregation()
    test_evidence_bag_all_pass()
    test_evidence_bag_empty()
    test_evidence_large_batch_aggregation()
    print(f"\n{'=' * 60}")
    print("  RESULTS: All REQ-05 tests passed ✅")
    print(f"{'=' * 60}")
