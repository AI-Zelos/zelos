"""
Goal State — Data class for Goal persistence and event sourcing.

v0.8.0: GoalState is the canonical representation of a Goal's state.
It can be serialized to/from dict for storage and reconstructed from events.
"""

from dataclasses import dataclass, field

from .task_graph import Task


@dataclass
class GoalState:
    """Canonical state of a Goal for persistence and event sourcing.

    Fields:
        goal_id: Unique goal identifier (UUID)
        status: One of accepted, planned, executing, completed, failed, cancelled
        description: Human-readable goal description
        tasks: All tasks in this goal's plan
        event_position: Last applied event sequence_id (for snapshot+incremental recovery)
        plan_id: Associated execution plan ID
        budget: Budget constraint
        deadline: Deadline string
        priority: low | medium | high | critical
        tenant_id: Owning tenant
        created_at: Unix timestamp of creation
        updated_at: Unix timestamp of last update
        completed_at: Unix timestamp of completion (None if not completed)
    """

    goal_id: str
    status: str = "accepted"
    description: str = ""
    tasks: list[Task] = field(default_factory=list)
    event_position: int = 0
    plan_id: str = ""
    budget: float | None = None
    deadline: str | None = None
    priority: str = "medium"
    tenant_id: str = "default"
    created_at: float = 0.0
    updated_at: float = 0.0
    completed_at: float | None = None

    # ═══ Serialization ═══

    def to_dict(self) -> dict:
        """Serialize GoalState to a dictionary for storage."""
        return {
            "goal_id": self.goal_id,
            "status": self.status,
            "description": self.description,
            "tasks": [t.to_dict() for t in self.tasks],
            "event_position": self.event_position,
            "plan_id": self.plan_id,
            "budget": self.budget,
            "deadline": self.deadline,
            "priority": self.priority,
            "tenant_id": self.tenant_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GoalState":
        """Deserialize a GoalState from a dictionary."""
        tasks = [Task.from_dict(t) for t in d.get("tasks", [])]
        return cls(
            goal_id=d["goal_id"],
            status=d.get("status", "accepted"),
            description=d.get("description", ""),
            tasks=tasks,
            event_position=int(d.get("event_position", 0)),
            plan_id=d.get("plan_id", ""),
            budget=d.get("budget"),
            deadline=d.get("deadline"),
            priority=d.get("priority", "medium"),
            tenant_id=d.get("tenant_id", "default"),
            created_at=float(d.get("created_at", 0.0)),
            updated_at=float(d.get("updated_at", 0.0)),
            completed_at=d.get("completed_at"),
        )

    @classmethod
    def from_goal_dict(cls, goal: dict, tasks: list[Task]) -> "GoalState":
        """Factory: build GoalState from the runtime's goal dict format."""
        return cls(
            goal_id=goal.get("goal_id", ""),
            status=goal.get("status", "accepted"),
            description=goal.get("description", ""),
            tasks=tasks,
            event_position=goal.get("event_position", 0),
            plan_id=goal.get("plan_id", ""),
            budget=goal.get("budget"),
            deadline=goal.get("deadline"),
            priority=goal.get("priority", "medium"),
            tenant_id=goal.get("tenant_id", "default"),
            created_at=float(goal.get("created_at", 0.0)),
            updated_at=float(goal.get("updated_at", 0.0)),
            completed_at=goal.get("completed_at"),
        )

    # ═══ Query helpers ═══

    def is_terminal(self) -> bool:
        """Return True if the goal is in a terminal state."""
        return self.status in ("completed", "failed", "cancelled")

    def get_task(self, task_id: str) -> Task | None:
        """Get a task by ID."""
        for t in self.tasks:
            if t.task_id == task_id:
                return t
        return None
