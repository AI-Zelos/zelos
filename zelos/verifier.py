"""
Verifier — Quality gate for Artifacts before they flow to downstream Tasks.

Phase 1: Schema validation. Extensible for security, style, fact-checking in Phase 2+.
"""
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Verdict:
    verdict: str  # "passed" | "failed" | "needs_review"
    score: float  # 0.0 - 1.0
    verifier_id: str
    verifier_version: str = "0.1.0"
    issues: List[Dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    checked_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "score": self.score,
            "verifier_id": self.verifier_id,
            "verifier_version": self.verifier_version,
            "issues": self.issues,
            "summary": self.summary,
            "checked_at": self.checked_at or time.time(),
        }


@dataclass
class VerificationCriteria:
    expected_output_schema: Optional[Dict[str, Any]] = None
    rules: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    options: Dict[str, Any] = field(default_factory=dict)


class Verifier(ABC):
    """Base class for all Verifier plugins."""

    def __init__(self, verifier_id: str = "base-verifier", config: Optional[Dict] = None):
        self.verifier_id = verifier_id
        self.config = config or {}

    @abstractmethod
    def verify(self, artifact_content: Any, criteria: VerificationCriteria) -> Verdict:
        ...

    def health(self) -> bool:
        return True


class SchemaVerifier(Verifier):
    """Validates artifact content against a JSON Schema."""

    def __init__(self, config: Optional[Dict] = None):
        super().__init__(verifier_id="schema-verifier", config=config)
        self.strict_mode = (config or {}).get("strict_mode", True)

    def verify(self, artifact_content: Any, criteria: VerificationCriteria) -> Verdict:
        schema = criteria.expected_output_schema
        issues = []

        if schema is None:
            return Verdict(
                verdict="passed", score=1.0,
                verifier_id=self.verifier_id,
                summary="No schema to validate against",
            )

        # Handle content_ref — skip schema validation for external refs
        if isinstance(artifact_content, dict) and "content_ref" in artifact_content:
            return Verdict(
                verdict="passed", score=1.0,
                verifier_id=self.verifier_id,
                summary="Artifact uses content_ref — schema validation deferred",
            )

        # Validate type
        schema_type = schema.get("type", "")
        if schema_type and not self._check_type(artifact_content, schema_type):
            issues.append({
                "severity": "error",
                "message": f"Expected type '{schema_type}', got '{type(artifact_content).__name__}'",
                "rule_id": "type-check",
            })
            return Verdict(
                verdict="failed", score=0.0,
                verifier_id=self.verifier_id,
                issues=issues,
                summary=f"Type mismatch: expected {schema_type}",
            )

        # Validate required fields (object type)
        if schema_type == "object" and isinstance(artifact_content, dict):
            required = schema.get("required", [])
            for field in required:
                if field not in artifact_content:
                    issues.append({
                        "severity": "error",
                        "message": f"Missing required field: '{field}'",
                        "rule_id": "required-check",
                    })

        # Validate properties (object type)
        if schema_type == "object" and isinstance(artifact_content, dict):
            properties = schema.get("properties", {})
            for prop_name, prop_schema in properties.items():
                if prop_name in artifact_content:
                    prop_type = prop_schema.get("type", "")
                    prop_val = artifact_content[prop_name]
                    if prop_type and not self._check_type(prop_val, prop_type):
                        issues.append({
                            "severity": "error",
                            "message": f"Field '{prop_name}': expected '{prop_type}', got '{type(prop_val).__name__}'",
                            "rule_id": "property-type-check",
                        })

        if issues:
            return Verdict(
                verdict="failed", score=0.0,
                verifier_id=self.verifier_id,
                issues=issues,
                summary=f"{len(issues)} validation error(s)",
            )

        return Verdict(
            verdict="passed", score=1.0,
            verifier_id=self.verifier_id,
            summary="Schema validation passed",
        )

    @staticmethod
    def _check_type(value: Any, expected: str) -> bool:
        if expected == "string":
            return isinstance(value, str)
        elif expected == "number":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        elif expected == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        elif expected == "boolean":
            return isinstance(value, bool)
        elif expected == "object":
            return isinstance(value, dict)
        elif expected == "array":
            return isinstance(value, list)
        elif expected == "null":
            return value is None
        return True  # Unknown type → pass


class VerificationGate:
    """Manages verification pipeline: run verifiers sequentially, stop on first failure."""

    def __init__(self):
        self._verifiers: List[Verifier] = []

    def add_verifier(self, verifier: Verifier) -> None:
        self._verifiers.append(verifier)

    def verify(self, artifact_content: Any, criteria: VerificationCriteria) -> Verdict:
        """
        Run all verifiers. Returns first failed verdict, or passed if all pass.
        If no verifiers, artifact is accepted directly.
        """
        if not self._verifiers:
            return Verdict(
                verdict="passed", score=1.0,
                verifier_id="gate",
                summary="No verifiers configured — accepted",
            )

        for verifier in self._verifiers:
            verdict = verifier.verify(artifact_content, criteria)
            if verdict.verdict == "failed":
                return verdict
            if verdict.verdict == "needs_review":
                return verdict

        return Verdict(
            verdict="passed", score=1.0,
            verifier_id="gate",
            summary="All verifiers passed",
        )
