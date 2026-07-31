"""
Arbiter — Selects the best result from parallel agent execution.

v1.2.0: Runs VerifierChain on each agent's output, picks first that passes all checks.
"""
from dataclasses import dataclass, field


@dataclass
class ArbiterResult:
    """Result of arbitration across multiple agent outputs."""
    winner_agent_id: str = ""
    winner_output: dict | None = None
    all_verdicts: dict[str, list] = field(default_factory=dict)  # agent_id → verdicts
    total_checked: int = 0
    passed: int = 0

    @property
    def has_winner(self) -> bool:
        return self.winner_agent_id != ""

    def to_dict(self) -> dict:
        return {
            "winner_agent_id": self.winner_agent_id,
            "total_checked": self.total_checked,
            "passed": self.passed,
        }


class Arbiter:
    """Evaluates multiple agent outputs through a VerifierChain, picks the winner.

    Strategy: first-to-pass-all — the first agent whose output passes every
    verifier in the chain wins. Ties go to the agent that finished first.
    """

    def __init__(self, verifier_chain=None):
        self._chain = verifier_chain

    def set_chain(self, chain):
        self._chain = chain

    def judge(self, outputs: dict[str, dict], cp_criteria=None) -> ArbiterResult:
        """Judge multiple agent outputs. Returns ArbiterResult with winner.

        Runs ALL registered verifiers in the chain against each output.
        First agent whose output passes ALL verifiers wins.
        """
        result = ArbiterResult(total_checked=len(outputs))

        if not self._chain:
            for agent_id in outputs:
                result.winner_agent_id = agent_id
                result.winner_output = outputs[agent_id]
                result.passed = 1
                return result

        # Build the full chain: all registered verifiers, not just cp_criteria ones
        all_verifier_names = list(self._chain._available_verifiers.keys())

        for agent_id, output in outputs.items():
            if not output:
                continue
            all_passed = True
            verdicts = []
            for vname in all_verifier_names:
                verifier = self._chain._available_verifiers.get(vname)
                if not verifier:
                    continue
                try:
                    from .verifier import VerificationCriteria
                    # Wrap plain text in a dict for SchemaVerifier compatibility
                    artifact = output if isinstance(output, dict) else {"patch": str(output)}
                    verdict = verifier.verify(artifact, VerificationCriteria())
                    verdicts.append(verdict)
                    if verdict.verdict == "failed":
                        all_passed = False
                        break
                except Exception:
                    all_passed = False
                    break

            result.all_verdicts[agent_id] = verdicts
            if all_passed:
                result.winner_agent_id = agent_id
                result.winner_output = output
                result.passed = 1
                return result

        return result
