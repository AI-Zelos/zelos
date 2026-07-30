"""
Verifier Chain — Auto-orchestrated verification pipeline.

v1.0.0: Builds a chain of Verifiers from ChangeProposal.verification_criteria,
executes them in sequence, and escalates on low confidence.
"""

from dataclasses import dataclass, field

from .change_proposal import VerificationCriteria as CPVerificationCriteria
from .evidence import Evidence
from .verifier import SchemaVerifier, Verdict, VerificationCriteria, Verifier


@dataclass
class ChainResult:
    """Result of a VerifierChain execution."""
    all_passed: bool = True
    verdicts: list = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    failed_at: str = ""

    def to_dict(self) -> dict:
        return {
            "all_passed": self.all_passed,
            "verdicts": [{"verdict": v.verdict} for v in self.verdicts],
            "failed_at": self.failed_at,
        }


class VerifierChain:
    """Auto-orchestrates verifiers based on CP verification criteria.

    Paper definition: E = Verify(CP, Artifact) — verification is a
    deterministic mapping from CP + Artifact → Evidence.
    """

    def __init__(self):
        self._available_verifiers: dict[str, Verifier] = {
            "schema": SchemaVerifier(),
        }
        # Register additional verifiers if available
        try:
            from .verifier_v2 import CodeReviewer, SecurityScanner
            self._available_verifiers["code_review"] = CodeReviewer()
            self._available_verifiers["security"] = SecurityScanner()
        except ImportError:
            pass  # Graceful — extra verifiers are optional

    def register(self, name: str, verifier: Verifier) -> None:
        """Register a verifier for auto-selection."""
        self._available_verifiers[name] = verifier

    def build_chain(self, cp_criteria: CPVerificationCriteria) -> list[Verifier]:
        """Build a verifier chain from CP verification criteria."""
        chain = []
        if "schema" in self._available_verifiers:
            chain.append(self._available_verifiers["schema"])
        for v_name in cp_criteria.required_verifiers:
            if v_name in self._available_verifiers and v_name != "schema":
                chain.append(self._available_verifiers[v_name])
        return chain

    def execute(self, artifact_content, cp_criteria: CPVerificationCriteria) -> ChainResult:
        """Execute the verifier chain. FAIL stops the chain."""
        chain = self.build_chain(cp_criteria)
        result = ChainResult()

        verifier_criteria = VerificationCriteria(
            expected_output_schema={},
            rules=cp_criteria.required_verifiers,
        )

        for verifier in chain:
            try:
                verdict = verifier.verify(artifact_content, verifier_criteria)
            except Exception as e:
                verdict = Verdict(verdict="failed")

            result.verdicts.append(verdict)
            result.evidence.append(Evidence(
                type="verification",
                tool=verifier.__class__.__name__,
                result="PASS" if verdict.verdict == "passed" else "FAIL",
                data={"verdict": verdict.verdict},
                summary=f"{verifier.__class__.__name__}: {verdict.verdict}",
            ))

            if verdict.verdict == "failed":
                result.all_passed = False
                result.failed_at = verifier.__class__.__name__
                break

        return result

    def escalate(self, artifact_content, cp_criteria: CPVerificationCriteria,
                 confidence: float) -> ChainResult:
        """Run verification. If confidence is low (<0.70), add more verifiers."""
        result = self.execute(artifact_content, cp_criteria)
        if confidence < 0.70 and result.all_passed:
            extra_names = [n for n in self._available_verifiers
                          if n not in cp_criteria.required_verifiers and n != "schema"]
            for name in extra_names[:2]:
                v = self._available_verifiers[name]
                verdict = v.verify(artifact_content, VerificationCriteria(
                    expected_output_schema={}))
                result.verdicts.append(verdict)
                result.evidence.append(Evidence(
                    type="verification", tool=name,
                    result="PASS" if verdict.verdict == "passed" else "FAIL",
                    data={"verdict": verdict.verdict, "escalated": True},
                    summary=f"[ESCALATED] {name}: {verdict.verdict}",
                ))
                if verdict.verdict == "failed":
                    result.all_passed = False
                    result.failed_at = name
                    break
        return result
