"""
Diagnosis Engine — Runtime understands test failure logs.

v1.2.0: Extracts structured diagnosis from pytest/unittest output.
Not compression — understanding. Produces actionable conclusions.
"""

import re
from dataclasses import dataclass, field


@dataclass
class FailureDetail:
    """Single test failure with precise location and values."""
    test_name: str = ""
    failure_type: str = "unknown"  # AssertionError, TypeError, ImportError, etc.
    expected: str | None = None
    actual: str | None = None
    location_file: str | None = None
    location_line: int | None = None
    traceback_summary: str = ""


@dataclass
class DiagnosisResult:
    """Structured diagnosis from test execution output."""
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    pass_rate: float = 0.0
    failures: list[FailureDetail] = field(default_factory=list)
    impact_scope: str = "unknown"  # single_module, multi_module, full_explosion
    recommendation: str = ""       # repair, retry, abandon
    raw_summary: str = ""

    def to_dict(self) -> dict:
        return {
            "total_tests": self.total_tests,
            "passed": self.passed, "failed": self.failed, "errors": self.errors,
            "pass_rate": self.pass_rate,
            "failures": [
                {"test_name": f.test_name, "failure_type": f.failure_type,
                 "location": f"{f.location_file}:{f.location_line}" if f.location_file else ""}
                for f in self.failures[:10]  # Top 10 only
            ],
            "impact_scope": self.impact_scope,
            "recommendation": self.recommendation,
        }


class DiagnosisEngine:
    """Parses test execution output into structured diagnosis.

    Input: raw pytest/unittest stdout
    Output: DiagnosisResult with actionable conclusions
    """

    # pytest patterns — match "X passed, Y failed, Z errors"
    _SESSION_RE = re.compile(r'(\d+)\s+passed.*?(?:(\d+)\s+failed)?.*?(?:(\d+)\s+errors?)?')
    _FAILED_RE = re.compile(r'(\S+)\s+FAILED')
    _ERROR_RE = re.compile(r'(\S+)\s+ERROR')
    _ASSERT_RE = re.compile(r'AssertionError:?\s*(.*?)(?:\n|$)', re.DOTALL)
    _EXPECTED_RE = re.compile(r'[Ee]xpected[:\s]+(.+?)(?:\n|,?\s*[Aa]ctual)', re.DOTALL)
    _ACTUAL_RE = re.compile(r'[Aa]ctual[:\s]+(.+?)(?:\n|$)')
    _LOCATION_RE = re.compile(r'File\s+"([^"]+)",\s*line\s+(\d+)')
    _TRACEBACK_RE = re.compile(r'(Traceback \(most recent call last\):.*?)(?=\n\w|\Z)', re.DOTALL)

    def diagnose(self, test_output: str) -> DiagnosisResult:
        """Parse test output into structured diagnosis."""
        if not test_output or not test_output.strip():
            return DiagnosisResult(pass_rate=1.0, recommendation="all_passed",
                                   raw_summary="No test output")

        # Skip leading noise (conda activation, Docker setup logs)
        # Find the actual pytest output start
        session_start = test_output.find("= test session starts =")
        if session_start > 0:
            test_output = test_output[session_start:]

        result = DiagnosisResult(raw_summary=test_output[:500])

        # Parse pytest summary line
        session_match = self._SESSION_RE.search(test_output)
        if session_match:
            result.passed = int(session_match.group(1)) if session_match.group(1) else 0
            result.failed = int(session_match.group(2)) if session_match.group(2) else 0
            result.errors = int(session_match.group(3)) if session_match.group(3) else 0

        # Fallback: count FAILED/ERROR lines if session parse missed them
        failed_lines = len(self._FAILED_RE.findall(test_output))
        error_lines = len(self._ERROR_RE.findall(test_output))
        if result.failed == 0 and failed_lines > 0:
            result.failed = failed_lines
        if result.errors == 0 and error_lines > 0:
            result.errors = error_lines

        result.total_tests = result.passed + result.failed + result.errors
        if result.total_tests == 0:
            result.pass_rate = 1.0
            result.recommendation = "all_passed"
            return result

        result.pass_rate = result.passed / result.total_tests

        # Extract per-failure details
        failed_tests = self._FAILED_RE.findall(test_output)
        error_tests = self._ERROR_RE.findall(test_output)

        for test_name in failed_tests[:20]:
            detail = FailureDetail(test_name=test_name)

            # Find traceback block for this test
            tb_pattern = re.compile(
                r'(FAILED\s+' + re.escape(test_name) + r'.*?)(?=FAILED|ERROR|\Z)', re.DOTALL
            )
            tb_match = tb_pattern.search(test_output)
            if tb_match:
                block = tb_match.group(1)

                # Extract assertion info
                assert_match = self._ASSERT_RE.search(block)
                if assert_match:
                    detail.failure_type = "AssertionError"
                    detail.expected = self._extract_value(self._EXPECTED_RE.search(block))
                    detail.actual = self._extract_value(self._ACTUAL_RE.search(block))

                # Extract location
                loc_match = self._LOCATION_RE.search(block)
                if loc_match:
                    detail.location_file = loc_match.group(1)
                    detail.location_line = int(loc_match.group(2))

                # Check for other error types
                if "TypeError" in block:
                    detail.failure_type = "TypeError"
                elif "ImportError" in block or "ModuleNotFoundError" in block:
                    detail.failure_type = "ImportError"
                elif "AttributeError" in block:
                    detail.failure_type = "AttributeError"
                elif "Timeout" in block:
                    detail.failure_type = "Timeout"

                # Extract traceback summary (last 3 lines)
                tb_lines = [l for l in block.split('\n') if l.strip() and 'File "' in l]
                detail.traceback_summary = '\n'.join(tb_lines[-3:])

            result.failures.append(detail)

        # Determine impact scope
        fail_ratio = result.failed / max(result.total_tests, 1)
        if fail_ratio > 0.5:
            result.impact_scope = "full_explosion"
        elif fail_ratio > 0.2:
            result.impact_scope = "multi_module"
        else:
            result.impact_scope = "single_module"

        # Recommendation
        if result.failed == 0 and result.errors == 0:
            result.recommendation = "all_passed"
        elif result.impact_scope == "full_explosion":
            result.recommendation = "abandon"
        elif all(f.failure_type in ("AssertionError", "TypeError", "AttributeError")
                 for f in result.failures[:5]):
            result.recommendation = "repair"
        else:
            result.recommendation = "retry"

        return result

    @staticmethod
    def _extract_value(match) -> str | None:
        if match:
            return match.group(1).strip()[:200]
        return None
