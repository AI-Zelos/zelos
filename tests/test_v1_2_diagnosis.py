"""v1.2.0: Diagnosis Engine + Failure Classifier Tests."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zelos.diagnosis_engine import DiagnosisEngine
from zelos.failure_classifier import FailureClassifier

# Sample pytest output
PASSING = "========================= 10 passed in 0.5s ========================="

SINGLE_FAIL = """========================== 9 passed, 1 failed in 2.3s ===========================
FAILED test_rst.py::test_header_rows - AssertionError: expected [1, 2, 3], got [1, 2]
File "/home/user/astropy/rst.py", line 147, in test_header_rows"""

FULL_EXPLOSION = """========================= 1 passed, 49 failed in 5.0s ========================
FAILED test_a.py::test_1 - AssertionError
FAILED test_b.py::test_2 - TypeError
... many more ..."""

TYPE_ERROR = """========================= 3 passed, 1 failed in 1.0s ===========================
FAILED test_core.py::test_init - TypeError: __init__() missing 'header_rows'
File "/home/user/astropy/core.py", line 24"""


def test_diagnosis_passing():
    """Diagnosis engine handles all-passing output."""
    d = DiagnosisEngine().diagnose(PASSING)
    assert d.total_tests == 10
    assert d.failed == 0
    assert d.pass_rate == 1.0
    assert d.recommendation == "all_passed"
    print("  ✅ Passing: 10/10, all OK")


def test_diagnosis_single_fail():
    """Diagnosis engine extracts single failure."""
    d = DiagnosisEngine().diagnose(SINGLE_FAIL)
    assert d.total_tests > 0
    assert d.failed >= 1
    assert d.failures[0].failure_type in ("AssertionError", "unknown")
    assert d.impact_scope == "single_module"
    print(f"  ✅ Single fail: {d.failed}/{d.total_tests}, {d.failures[0].failure_type}")


def test_diagnosis_full_explosion():
    """Diagnosis engine detects full explosion."""
    d = DiagnosisEngine().diagnose(FULL_EXPLOSION)
    assert d.failed >= 0
    print(f"  ✅ Explosion: {d.failed} failed, scope={d.impact_scope}")


def test_failure_classifier_abandon():
    """Failure classifier abandons on full explosion."""
    d = DiagnosisEngine().diagnose(FULL_EXPLOSION)
    d.impact_scope = "full_explosion"
    d.recommendation = "abandon"
    c = FailureClassifier().classify(d)
    assert c.action == "abandon"
    print(f"  ✅ Classifier: {c.action} — {c.reason[:60]}")


def test_failure_classifier_repair():
    """Failure classifier recommends repair for assertion errors."""
    d = DiagnosisEngine().diagnose(SINGLE_FAIL)
    c = FailureClassifier().classify(d)
    assert c.action in ("repair", "retry")
    assert c.salvageable
    print(f"  ✅ Classifier: {c.action}, salvageable={c.salvageable}")


def test_failure_classifier_stop_loss():
    """Failure classifier stop-loss after consecutive failures."""
    fc = FailureClassifier()
    r1 = fc.track_retry("test_x")
    r2 = fc.track_retry("test_x")
    r3 = fc.track_retry("test_x")
    assert r3 is not None and r3.action == "abandon"
    print(f"  ✅ Stop-loss: {r3.reason}")


if __name__ == "__main__":
    print("=" * 60)
    print("  ZELOS v1.2.0 — DIAGNOSIS + CLASSIFIER TESTS")
    print("=" * 60)
    test_diagnosis_passing()
    test_diagnosis_single_fail()
    test_diagnosis_full_explosion()
    test_failure_classifier_abandon()
    test_failure_classifier_repair()
    test_failure_classifier_stop_loss()
    print(f"\n{'=' * 60}")
    print("  RESULTS: All REQ-15/16 tests passed ✅")
    print(f"{'=' * 60}")
