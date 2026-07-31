"""
Patch Ranker — Multi-factor candidate scoring.

v1.2.0: Ranks patch candidates beyond binary pass/fail.
Factors: file count, LOC, test changes, cross-package, API deletions.
"""

import re
from dataclasses import dataclass, field


@dataclass
class RankedPatch:
    """A patch with its rank score and factor breakdown."""
    agent_id: str = ""
    patch: str = ""
    score: float = 0.0
    factors: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"agent_id": self.agent_id, "score": round(self.score, 1),
                "factors": {k: round(v, 1) for k, v in self.factors.items()}}


class PatchRanker:
    """Scores patch candidates on engineering quality heuristics.

    Weights are tunable. Default configuration favors:
    - Small, focused changes
    - Changes that include tests
    - Changes within the issue's mentioned modules
    """

    def __init__(self, weights: dict[str, float] | None = None):
        self.weights = weights or {
            "file_count": 0.25,
            "loc": 0.20,
            "has_tests": 0.15,
            "cross_package": 0.15,
            "in_mentioned_module": 0.15,
            "no_api_deletion": 0.10,
        }

    def rank(self, candidates: list[dict]) -> list[RankedPatch]:
        """Score and rank multiple patch candidates. Returns sorted (best first)."""
        ranked = []
        for c in candidates:
            patch = c.get("patch", c.get("model_patch", ""))
            agent_id = c.get("agent_id", c.get("model_name_or_path", "unknown"))
            score, factors = self._score(patch)
            ranked.append(RankedPatch(agent_id=agent_id, patch=patch, score=score, factors=factors))
        return sorted(ranked, key=lambda r: r.score, reverse=True)

    def _score(self, patch: str) -> tuple[float, dict]:
        """Compute multi-factor score for a patch."""
        if not patch:
            return 0.0, {}

        # Extract metrics
        files = re.findall(r'^\+\+\+ b/(.+)$', patch, re.MULTILINE)
        file_count = len(files)
        lines = len(patch.split('\n'))
        has_tests = any('test' in f.lower() for f in files)
        packages = set(f.split('/')[0] for f in files if '/' in f)
        cross_package = len(packages) > 1
        deleted_lines = len(re.findall(r'^-\s', patch, re.MULTILINE))
        has_api_deletion = bool(re.findall(r'^-\s*(def |class |async def )', patch, re.MULTILINE))

        # Score each factor (0-1)
        f_file = self._score_file_count(file_count)
        f_loc = self._score_loc(lines)
        f_test = 1.0 if has_tests else 0.0
        f_cross = 0.0 if cross_package else 1.0
        f_module = 0.5  # Can't check without issue context, default moderate
        f_api = 0.0 if has_api_deletion else 1.0

        factors = {
            "file_count": f_file, "loc": f_loc, "has_tests": f_test,
            "cross_package": f_cross, "in_mentioned_module": f_module,
            "no_api_deletion": f_api,
        }

        score = sum(self.weights[k] * factors[k] for k in self.weights)
        return min(100, max(0, score * 100)), factors

    @staticmethod
    def _score_file_count(n: int) -> float:
        if n <= 2: return 1.0
        if n <= 5: return 0.7
        if n <= 10: return 0.4
        return 0.1

    @staticmethod
    def _score_loc(n: int) -> float:
        if n <= 50: return 1.0
        if n <= 200: return 0.7
        if n <= 500: return 0.4
        return 0.1
