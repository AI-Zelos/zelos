"""
Execution Trace — Complete execution timeline for a Goal.

v0.9.0: Provides get_goal_trace() API returning a structured timeline
of every Task lifecycle event with optional input/output loading.
Supports pagination for large Goals.
"""

from dataclasses import dataclass, field


@dataclass
class TraceEvent:
    """A single event in a Task's execution timeline."""

    event_type: str       # task.created / task.started / task.completed / task.failed / task.retry_scheduled
    timestamp: float
    payload: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "payload": dict(self.payload),
        }


@dataclass
class TaskTrace:
    """Complete execution trace for a single Task within a Goal."""

    task_id: str
    description: str = ""
    required_capability: str = ""
    agent_id: str | None = None
    agent_name: str | None = None
    status: str = "created"
    attempt: int = 0
    timeline: list[TraceEvent] = field(default_factory=list)
    input_context: dict | None = None        # lazy-loaded
    output_artifact: dict | None = None      # lazy-loaded
    error: dict | None = None

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "required_capability": self.required_capability,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "status": self.status,
            "attempt": self.attempt,
            "timeline": [t.to_dict() for t in self.timeline],
            "input_context": self.input_context,
            "output_artifact": self.output_artifact,
            "error": self.error,
        }


@dataclass
class ExecutionTrace:
    """Complete execution trace for a Goal — all Task traces merged.

    Supports pagination via limit/offset.
    """

    goal_id: str
    goal_description: str = ""
    status: str = "unknown"
    total_duration_ms: float = 0.0
    tasks: list[TaskTrace] = field(default_factory=list)
    total_tasks: int = 0    # Total before pagination

    def to_dict(self) -> dict:
        return {
            "goal_id": self.goal_id,
            "goal_description": self.goal_description,
            "status": self.status,
            "total_duration_ms": self.total_duration_ms,
            "tasks": [t.to_dict() for t in self.tasks],
            "total_tasks": self.total_tasks,
        }

    def paginate(self, limit: int = 50, offset: int = 0) -> "ExecutionTrace":
        """Return a paginated view of this trace."""
        sliced = ExecutionTrace(
            goal_id=self.goal_id,
            goal_description=self.goal_description,
            status=self.status,
            total_duration_ms=self.total_duration_ms,
            tasks=self.tasks[offset:offset + limit],
            total_tasks=len(self.tasks),
        )
        return sliced
