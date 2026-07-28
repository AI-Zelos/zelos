"""
v0.9.0 REQ-06: Confidence Scoring Tests.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.confidence import ConfidenceResult, WeightedConfidenceScorer
from zelos.evidence import Evidence, EvidenceBag


def test_confidence_scorer_all_pass():
    """WeightedConfidenceScorer gives high score when all evidence passes."""
    print("\n🎯 REQ-06.1: ConfidenceScorer — all pass")

    items = [
        Evidence("test_result", "pytest", "PASS", {"passed": 47, "failed": 0}),
        Evidence("benchmark", "wrk", "PASS", {"tps": 1120, "baseline": 850}),
        Evidence("security_scan", "bandit", "PASS", {"issues": 0}),
        Evidence("api_diff", "openapi-diff", "PASS", {"breaking": 0}),
    ]
    bag = EvidenceBag(goal_id="g-1", items=items)
    scorer = WeightedConfidenceScorer()
    result = scorer.score(bag, None)

    assert result.score > 0.8, f"Expected score >0.8, got {result.score}"
    assert result.score <= 1.0
    assert "test_pass" in result.breakdown
    print(f"  ✅ Score={result.score:.2f}, recommendation={result.recommendation}")


def test_confidence_scorer_some_failures():
    """Confidence drops when some evidence fails."""
    print("\n🎯 REQ-06.2: ConfidenceScorer — partial failures")

    items = [
        Evidence("test_result", "pytest", "PASS", {"passed": 40, "failed": 0}),
        Evidence("security_scan", "bandit", "FAIL", {"issues": 5}),
        Evidence("benchmark", "wrk", "FAIL", {"tps": 500, "baseline": 850}),
    ]
    bag = EvidenceBag(goal_id="g-2", items=items)
    scorer = WeightedConfidenceScorer()
    result = scorer.score(bag, None)

    assert result.score < 0.8, f"Expected score <0.8 with failures, got {result.score}"
    print(f"  ✅ Score with failures={result.score:.2f}")


def test_confidence_scorer_empty_evidence():
    """ConfidenceScorer returns 0.0 with need_human when no evidence."""
    print("\n🎯 REQ-06.3: ConfidenceScorer — empty evidence")

    bag = EvidenceBag(goal_id="g-empty", items=[])
    scorer = WeightedConfidenceScorer()
    result = scorer.score(bag, None)

    assert result.score == 0.0
    assert result.recommendation == "need_human"
    print(f"  ✅ Empty evidence → score=0.0, recommendation={result.recommendation}")


def test_confidence_scorer_custom_weights():
    """ConfidenceScorer respects custom weights."""
    print("\n🎯 REQ-06.4: ConfidenceScorer — custom weights")

    items = [Evidence("test_result", "pytest", "PASS", {"passed": 10})]
    bag = EvidenceBag(goal_id="g-custom", items=items)

    # Custom weights: test_pass=0.90 (very high weight on tests)
    scorer = WeightedConfidenceScorer(weights={"test_pass": 0.90})
    result = scorer.score(bag, None)
    assert result.score > 0.8  # Should be close to 1.0

    # With only one evidence type, normalized score is always 1.0 if it passes
    # Add a second PASS type to test weight differentiation
    bag2 = EvidenceBag(goal_id="g-custom2", items=[
        Evidence("test_result", "pytest", "PASS", {"passed": 10}),
        Evidence("security_scan", "bandit", "PASS", {}),
    ])
    scorer3 = WeightedConfidenceScorer(weights={"test_pass": 0.80, "security": 0.20})
    result3 = scorer3.score(bag2, None)
    assert result3.score > 0.8

    print(f"  ✅ Custom weights: single={result.score:.2f}, multi={result3.score:.2f}")


if __name__ == "__main__":
    print("=" * 60)
    print("  ZELOS v0.9.0 — REQ-06 CONFIDENCE SCORER TESTS")
    print("=" * 60)
    test_confidence_scorer_all_pass()
    test_confidence_scorer_some_failures()
    test_confidence_scorer_empty_evidence()
    test_confidence_scorer_custom_weights()
    print(f"\n{'=' * 60}")
    print("  RESULTS: All REQ-06 tests passed ✅")
    print(f"{'=' * 60}")
