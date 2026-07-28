"""
Verifier Chain — Auto-orchestrated verification pipeline.

v1.0.0: Builds a chain of Verifiers from ChangeProposal.verification_criteria,
executes them in sequence, and escalates on low confidence.
"""

from dataclasses import dataclass, field

from .change_proposal import VerificationCriteria
from .evidence import Evidence, EvidenceBag
from .verifier import SchemaVerifier, Verdict, Verifier


@dataclass
class ChainResult:
    """Result of a VerifierChain execution."""
    all_passed: bool = True
    verdicts: list[Verdict] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    failed_at: str = ""  # Which verifier failed

    def to_dict(self) -> dict:
        return {
            "all_passed": self.all_passed,
            "verdicts": [{"verdict": v.verdict, "reason": v.reason} for v in self.verdicts],
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

    def register(self, name: str, verifier: Verifier) -> None:
        """Register a verifier for auto-selection."""
        self._available_verifiers[name] = verifier

    def build_chain(self, criteria: VerificationCriteria) -> list[Verifier]:
        """Build a verifier chain from CP verification criteria."""
        chain = []
        # Always include schema verifier
        if "schema" in self._available_verifiers:
            chain.append(self._available_verifiers["schema"])

        # Add required verifiers from CP
        for v_name in criteria.required_verifiers:
            if v_name in self._available_verifiers and v_name != "schema":
                chain.append(self._available_verifiers[v_name])

        # Add security verifier if required
        if criteria.security_scan_required and "security" in self._available_verifiers:
            if "security" not in criteria.required_verifiers:
                chain.append(self._available_verifiers["security"])

        return chain

    def execute(self, artifact_content, criteria: VerificationCriteria) -> ChainResult:
        """Execute the verifier chain on an artifact.

        Any FAIL → chain stops. All PASS → all_passed=True.
        """
        chain = self.build_chain(criteria)
        result = ChainResult()

        for verifier in chain:
            try:
                verdict = verifier.verify(artifact_content, criteria)
            except Exception as e:
                verdict = Verdict(verdict="FAIL", reason=f"Verifier error: {e}")

            result.verdicts.append(verdict)

            # Convert verdict to evidence
            result.evidence.append(Evidence(
                type="verification",
                tool=verifier.__class__.__name__,
                result=verdict.verdict,
                data={"reason": verdict.reason},
                summary=f"{verifier.__class__.__name__}: {verdict.verdict}",
            ))

            if verdict.verdict == "FAIL":
                result.all_passed = False
                result.failed_at = verifier.__class__.__name__
                break

        return result

    def escalate(self, artifact_content, criteria: VerificationCriteria,
                 confidence: float) -> ChainResult:
        """Run verification. If confidence is low, add more verifiers."""
        result = self.execute(artifact_content, criteria)

        # Escalation: low confidence → add extra verification
        if confidence < 0.70 and result.all_passed:
            extra_names = [n for n in self._available_verifiers
                          if n not in criteria.required_verifiers and n != "schema"]
            for name in extra_names[:2]:  # Add up to 2 extra verifiers
                v = self._available_verifiers[name]
                verdict = v.verify(artifact_content, criteria)
                result.verdicts.append(verdict)
                result.evidence.append(Evidence(
                    type="verification", tool=name, result=verdict.verdict,
                    data={"reason": verdict.reason, "escalated": True},
                    summary=f"[ESCALATED] {name}: {verdict.verdict}",
                ))
                if verdict.verdict == "FAIL":
                    result.all_passed = False
                    result.failed_at = name
                    break

        return result
