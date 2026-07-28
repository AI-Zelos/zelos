"""
Evidence — Typed evidence output from Agent execution.

v0.9.0: Agents produce typed Evidence alongside Artifacts for confidence scoring.
Supports large-batch aggregation and serialization.
"""

from dataclasses import dataclass, field


@dataclass
class Evidence:
    """A single piece of evidence produced by an Agent during Task execution.

    Fields:
        type: Evidence category — test_result, benchmark, security_scan, api_diff, canary, custom
        tool: Tool that produced this evidence (pytest, wrk, bandit, etc.)
        result: PASS, FAIL, WARN, or SKIP
        data: Detailed metrics (passed/failed counts, TPS numbers, etc.)
        summary: Human-readable one-line summary
        timestamp: When this evidence was collected
    """

    type: str
    tool: str = "unknown"
    result: str = "PASS"
    data: dict = field(default_factory=dict)
    summary: str = ""
    timestamp: float = 0.0

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "tool": self.tool,
            "result": self.result,
            "data": dict(self.data),
            "summary": self.summary,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Evidence":
        return cls(
            type=d.get("type", "custom"),
            tool=d.get("tool", "unknown"),
            result=d.get("result", "PASS"),
            data=dict(d.get("data", {})),
            summary=d.get("summary", ""),
            timestamp=float(d.get("timestamp", 0.0)),
        )


@dataclass
class EvidenceSummary:
    """Aggregated summary for one evidence type."""
    type: str
    total: int = 0
    passed: int = 0
    failed: int = 0
    warned: int = 0
    skipped: int = 0

    def to_dict(self) -> dict:
        return {
            "type": self.type, "total": self.total,
            "passed": self.passed, "failed": self.failed,
            "warned": self.warned, "skipped": self.skipped,
        }


@dataclass
class EvidenceBag:
    """Collected evidence from all Tasks in a Goal execution.

    Auto-aggregates by type and provides pass/fail summary.
    Handles large evidence batches efficiently.
    """

    goal_id: str
    items: list[Evidence] = field(default_factory=list)

    def __post_init__(self):
        self._compute_summary()

    def _compute_summary(self):
        self.summary: dict[str, EvidenceSummary] = {}
        for item in self.items:
            if item.type not in self.summary:
                self.summary[item.type] = EvidenceSummary(type=item.type)
            s = self.summary[item.type]
            s.total += 1
            if item.result == "PASS":
                s.passed += 1
            elif item.result == "FAIL":
                s.failed += 1
            elif item.result == "WARN":
                s.warned += 1
            elif item.result == "SKIP":
                s.skipped += 1

    @property
    def all_pass(self) -> bool:
        """True if no evidence has result=FAIL."""
        if not self.items:
            return True
        return all(item.result != "FAIL" for item in self.items)

    @property
    def failed_items(self) -> list[Evidence]:
        """All evidence items with result=FAIL."""
        return [item for item in self.items if item.result == "FAIL"]

    def add(self, evidence: Evidence) -> None:
        """Add an evidence item and update summary incrementally."""
        self.items.append(evidence)
        if evidence.type not in self.summary:
            self.summary[evidence.type] = EvidenceSummary(type=evidence.type)
        s = self.summary[evidence.type]
        s.total += 1
        if evidence.result == "PASS":
            s.passed += 1
        elif evidence.result == "FAIL":
            s.failed += 1
        elif evidence.result == "WARN":
            s.warned += 1
        elif evidence.result == "SKIP":
            s.skipped += 1

    def to_dict(self) -> dict:
        return {
            "goal_id": self.goal_id,
            "items": [item.to_dict() for item in self.items],
            "summary": {k: v.to_dict() for k, v in self.summary.items()},
            "all_pass": self.all_pass,
            "failed_count": len(self.failed_items),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EvidenceBag":
        bag = cls(
            goal_id=d.get("goal_id", ""),
            items=[Evidence.from_dict(i) for i in d.get("items", [])],
        )
        return bag
