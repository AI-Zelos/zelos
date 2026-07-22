"""
Zelos SDK Schema — Data classes for Capability, Task, Artifact declarations.

These are the developer-facing types used when building Agents and submitting Goals.
All match the JSON Schemas in docs/schema/.
"""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class CapabilityDeclaration:
    """Declare a capability when registering an Agent.

    Matches docs/schema/capability.json.
    """

    name: str
    version: str = "1.0.0"
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    qos: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    required_resources: dict[str, Any] = field(default_factory=dict)
    capacity: int = 1

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        return {k: v for k, v in result.items() if v or k in ("name", "version")}


@dataclass
class TaskConstraints:
    """Optional constraints on a Task dispatched by the Scheduler.

    Used within Task declarations.
    """

    preferred_agent_id: str | None = None
    excluded_agent_ids: list[str] = field(default_factory=list)
    required_tags: list[str] = field(default_factory=list)
    min_success_rate: float | None = None
    timeout_ms: int = 300000
    max_retries: int = 2


@dataclass
class Task:
    """A single unit of work within an Execution Plan.

    Matches docs/schema/task.json.
    """

    task_id: str
    plan_id: str
    description: str
    required_capability: str
    input: dict[str, Any] = field(default_factory=dict)
    expected_output_schema: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    constraints: TaskConstraints = field(default_factory=TaskConstraints)
    fallback_capability: str | None = None
    priority: str = "medium"


@dataclass
class Artifact:
    """Result produced by an Agent after executing a Task.

    Matches docs/schema/artifact.json.
    """

    artifact_id: str
    task_id: str
    agent_id: str
    content_type: str = "application/json"
    content: Any = None
    content_ref: str | None = None
    size_bytes: int = 0
    verification_status: str = "pending"
    execution_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryContext:
    """Context assembled by the Runtime from 6-layer Memory before Task dispatch."""

    session: dict[str, Any] = field(default_factory=dict)
    project: dict[str, Any] = field(default_factory=dict)
    user: dict[str, Any] = field(default_factory=dict)
    knowledge: dict[str, Any] = field(default_factory=dict)
    execution: dict[str, Any] = field(default_factory=dict)
    skill: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GoalResult:
    """Result returned when waiting for a Goal to complete."""

    goal_id: str
    status: str
    progress: dict[str, Any] = field(default_factory=dict)
    artifacts: list[Artifact] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
