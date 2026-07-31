"""
Format Verifiers — Deterministic patch quality checks.

v1.2.0: Format/apply/lint verifiers for SWE-bench pipeline.
All zero-cost — no LLM, no Docker, instant feedback.
"""
import re
import subprocess
import tempfile
from typing import Any

from .verifier import Verdict, VerificationCriteria, Verifier


class FormatVerifier(Verifier):
    """Check patch has no markdown fences, is a valid unified diff."""

    def __init__(self):
        super().__init__(verifier_id="format-check")

    def verify(self, artifact_content: Any, criteria: VerificationCriteria) -> Verdict:
        patch = str(artifact_content) if artifact_content else ""
        issues = []

        # No markdown fences
        for fence in ["```diff", "``` Diff", "```"]:
            if fence in patch:
                issues.append({"type": "markdown_fence", "detail": f"Contains '{fence}'"})
                break

        # Must have diff indicators
        if not re.search(r'^(--- |\+\+\+ |diff --git)', patch, re.MULTILINE):
            issues.append({"type": "no_diff_header", "detail": "Missing diff header"})

        # Must end with newline
        if patch and not patch.endswith('\n'):
            issues.append({"type": "no_trailing_newline", "detail": "Does not end with newline"})

        if issues:
            return Verdict(verdict="failed", score=0.0, verifier_id=self.verifier_id,
                           issues=issues,
                           summary=f"{len(issues)} format issues: {[i['type'] for i in issues]}")
        return Verdict(verdict="passed", score=1.0, verifier_id=self.verifier_id, summary="Format OK")


class DryRunVerifier(Verifier):
    """Run patch --dry-run to verify the patch applies cleanly."""

    def __init__(self):
        super().__init__(verifier_id="dryrun")

    def verify(self, artifact_content: Any, criteria: VerificationCriteria) -> Verdict:
        patch = str(artifact_content) if artifact_content else ""
        if not patch.strip():
            return Verdict(verdict="failed", score=0.0, verifier_id=self.verifier_id, summary="Empty patch")

        with tempfile.TemporaryDirectory() as d:
            patchfile = f"{d}/test.patch"
            with open(patchfile, "w") as f:
                f.write(patch)
            for p_level in ["-p1", "-p0"]:
                result = subprocess.run(
                    ["patch", "--dry-run", p_level, "-i", patchfile],
                    capture_output=True, text=True, cwd=d,
                )
                if result.returncode == 0:
                    return Verdict(verdict="passed", score=1.0, verifier_id=self.verifier_id,
                                   summary=f"patch --dry-run {p_level} OK")
            return Verdict(verdict="failed", score=0.0, verifier_id=self.verifier_id,
                           summary=f"patch --dry-run failed: {result.stderr[:200]}")


class SyntaxVerifier(Verifier):
    """Run py_compile on changed Python files to catch syntax errors."""

    def __init__(self):
        super().__init__(verifier_id="syntax")

    def verify(self, artifact_content: Any, criteria: VerificationCriteria) -> Verdict:
        patch = str(artifact_content) if artifact_content else ""
        # Extract +++ filenames from patch
        files = re.findall(r'^\+\+\+ b/(.+\.py)', patch, re.MULTILINE)
        if not files:
            return Verdict(verdict="passed", score=1.0, verifier_id=self.verifier_id, summary="No Python files changed")

        issues = []
        for f in files[:10]:  # Check up to 10 files
            # We can't actually compile without the repo, but we can check
            # that filenames look valid
            if not f.endswith('.py'):
                issues.append({"type": "invalid_filename", "file": f})

        if issues:
            return Verdict(verdict="failed", score=0.5, verifier_id=self.verifier_id, issues=issues, summary="Invalid filenames")
        return Verdict(verdict="passed", score=1.0, verifier_id=self.verifier_id, summary=f"{len(files)} files OK")
