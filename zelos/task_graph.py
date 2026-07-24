"""
Task Graph Engine — Manages Task state machine and DAG dependency resolution.
"""

from dataclasses import dataclass, field
from enum import Enum


class TaskStatus(Enum):
    CREATED = "created"
    READY = "ready"
    ASSIGNED = "assigned"
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    FATAL_FAILED = "fatal_failed"  # v0.8.0: non-retryable terminal failure


VALID_TRANSITIONS = {
    TaskStatus.CREATED: {TaskStatus.READY, TaskStatus.CANCELLED},
    TaskStatus.READY: {TaskStatus.ASSIGNED, TaskStatus.CANCELLED, TaskStatus.FAILED, TaskStatus.FATAL_FAILED},
    TaskStatus.ASSIGNED: {TaskStatus.STARTED, TaskStatus.READY, TaskStatus.CANCELLED, TaskStatus.FATAL_FAILED},
    TaskStatus.STARTED: {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.TIMED_OUT, TaskStatus.CANCELLED, TaskStatus.FATAL_FAILED},
    TaskStatus.FAILED: {TaskStatus.READY, TaskStatus.FATAL_FAILED},
    TaskStatus.TIMED_OUT: {TaskStatus.READY, TaskStatus.FATAL_FAILED},
    TaskStatus.COMPLETED: set(),  # Terminal
    TaskStatus.CANCELLED: set(),  # Terminal
    TaskStatus.FATAL_FAILED: set(),  # v0.8.0: Terminal — no recovery
}


@dataclass
class Task:
    task_id: str
    plan_id: str
    description: str
    required_capability: str
    status: TaskStatus = TaskStatus.CREATED
    dependencies: list[str] = field(default_factory=list)
    dependents: list[str] = field(default_factory=list)
    attempt: int = 0
    max_retries: int = 3
    backoff_base_ms: int = 1000
    timeout_ms: int = 30000
    assigned_agent_id: str | None = None
    priority: str = "medium"
    fallback_capability: str | None = None
    preferred_agent_id: str | None = None
    excluded_agent_ids: list[str] = field(default_factory=list)
    min_success_rate: float = 0.0
    required_tags: list[str] = field(default_factory=list)
    max_cost_per_call: float | None = None
    max_latency_ms: int | None = None
    non_retryable_errors: list[str] = field(default_factory=list)  # v0.8.0
    created_at: float = 0.0
    updated_at: float = 0.0

    # ═══ v0.8.0: Serialization ═══

    def to_dict(self) -> dict:
        """Serialize Task to a dictionary for persistence."""
        return {
            "task_id": self.task_id,
            "plan_id": self.plan_id,
            "description": self.description,
            "required_capability": self.required_capability,
            "status": self.status.value,
            "dependencies": list(self.dependencies),
            "dependents": list(self.dependents),
            "attempt": self.attempt,
            "max_retries": self.max_retries,
            "backoff_base_ms": self.backoff_base_ms,
            "timeout_ms": self.timeout_ms,
            "assigned_agent_id": self.assigned_agent_id,
            "priority": self.priority,
            "fallback_capability": self.fallback_capability,
            "preferred_agent_id": self.preferred_agent_id,
            "excluded_agent_ids": list(self.excluded_agent_ids),
            "min_success_rate": self.min_success_rate,
            "required_tags": list(self.required_tags),
            "max_cost_per_call": self.max_cost_per_call,
            "max_latency_ms": self.max_latency_ms,
            "non_retryable_errors": list(self.non_retryable_errors),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Task":
        """Deserialize a Task from a dictionary."""
        return cls(
            task_id=d["task_id"],
            plan_id=d["plan_id"],
            description=d["description"],
            required_capability=d["required_capability"],
            status=TaskStatus(d.get("status", "created")),
            dependencies=list(d.get("dependencies", [])),
            dependents=list(d.get("dependents", [])),
            attempt=int(d.get("attempt", 0)),
            max_retries=int(d.get("max_retries", 3)),
            backoff_base_ms=int(d.get("backoff_base_ms", 1000)),
            timeout_ms=int(d.get("timeout_ms", 30000)),
            assigned_agent_id=d.get("assigned_agent_id"),
            priority=d.get("priority", "medium"),
            fallback_capability=d.get("fallback_capability"),
            preferred_agent_id=d.get("preferred_agent_id"),
            excluded_agent_ids=list(d.get("excluded_agent_ids", [])),
            min_success_rate=float(d.get("min_success_rate", 0.0)),
            required_tags=list(d.get("required_tags", [])),
            max_cost_per_call=d.get("max_cost_per_call"),
            max_latency_ms=d.get("max_latency_ms"),
            non_retryable_errors=list(d.get("non_retryable_errors", [])),
            created_at=float(d.get("created_at", 0.0)),
            updated_at=float(d.get("updated_at", 0.0)),
        )


class TaskGraphEngine:
    """Kernel component — manages Tasks and their dependency DAG."""

    def __init__(self):
        self._tasks: dict[str, Task] = {}
        self._dependencies: dict[str, set[str]] = {}  # task_id → {dependency_ids}
        self._dependents_map: dict[str, set[str]] = {}  # task_id → {dependent_ids}
        self._created_task_ids: set[str] = set()  # v0.7.0: O(1) lookup for created tasks

    # ── Task CRUD ──

    def add_task(self, task: Task) -> None:
        task.created_at = __import__("time").time()
        task.updated_at = task.created_at
        self._tasks[task.task_id] = task
        self._dependencies[task.task_id] = set(task.dependencies)
        self._created_task_ids.add(task.task_id)
        # Register as dependent on each dependency
        for dep_id in task.dependencies:
            self._dependents_map.setdefault(dep_id, set()).add(task.task_id)

    def get_task(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def list_tasks(self) -> list[Task]:
        return list(self._tasks.values())

    # ── State Transitions ──

    def transition(self, task_id: str, to_status: TaskStatus, agent_id: str | None = None) -> Task:
        task = self._get_required(task_id)
        from_status = task.status
        valid = VALID_TRANSITIONS.get(from_status, set())
        if to_status not in valid:
            raise ValueError(f"Invalid transition: {from_status.value} → {to_status.value}")

        task.status = to_status
        task.updated_at = __import__("time").time()
        if agent_id and to_status in (TaskStatus.ASSIGNED, TaskStatus.STARTED):
            task.assigned_agent_id = agent_id
        # v0.7.0: track created set for O(1) evaluate_all
        if from_status == TaskStatus.CREATED and to_status != TaskStatus.CREATED:
            self._created_task_ids.discard(task_id)
        elif to_status == TaskStatus.CREATED:
            self._created_task_ids.add(task_id)
        return task

    def _get_required(self, task_id: str) -> Task:
        if task_id not in self._tasks:
            raise KeyError(f"Task not found: {task_id}")
        return self._tasks[task_id]

    # ── Dependency Resolution ──

    def evaluate_dependencies(self, task_id: str) -> bool:
        """Returns True if task becomes READY."""
        task = self._get_required(task_id)
        if task.status != TaskStatus.CREATED:
            return False

        for dep_id in task.dependencies:
            dep = self._tasks.get(dep_id)
            if dep is None or dep.status != TaskStatus.COMPLETED:
                return False

        self.transition(task_id, TaskStatus.READY)
        return True

    def evaluate_all(self) -> list[str]:
        """Evaluate all CREATED tasks (O(|CREATED|) via _created_task_ids set). Returns task_ids that became READY."""
        ready = []
        for task_id in list(self._created_task_ids):
            t = self._tasks.get(task_id)
            if t and t.status == TaskStatus.CREATED and self.evaluate_dependencies(task_id):
                ready.append(task_id)
        return ready

    def on_task_completed(self, completed_task_id: str) -> list[str]:
        """Notify that a task completed. Evaluate its dependents. Returns newly READY task_ids."""
        ready = []
        for dep_id in self._dependents_map.get(completed_task_id, set()):
            if dep_id in self._tasks and self._tasks[dep_id].status == TaskStatus.CREATED:
                if self.evaluate_dependencies(dep_id):
                    ready.append(dep_id)
        return ready

    def get_ready_tasks(self) -> list[Task]:
        return [t for t in self._tasks.values() if t.status == TaskStatus.READY]

    # ── DAG Validation ──

    def add_dependency(self, from_task_id: str, to_task_id: str) -> None:
        """Add edge: from → to (to depends on from)."""
        # Check acyclicity
        if self._would_create_cycle(from_task_id, to_task_id):
            raise ValueError(f"Adding edge {from_task_id}→{to_task_id} would create a cycle")
        to_task = self._get_required(to_task_id)
        if from_task_id not in to_task.dependencies:
            to_task.dependencies.append(from_task_id)
            self._dependencies.setdefault(to_task_id, set()).add(from_task_id)
            self._dependents_map.setdefault(from_task_id, set()).add(to_task_id)

    def _would_create_cycle(self, from_id: str, to_id: str) -> bool:
        """Check if adding edge from→to creates a cycle (DFS from to_id back to from_id)."""
        if from_id == to_id:
            return True
        visited = set()

        def dfs(current):
            if current == from_id:
                return True
            if current in visited:
                return False
            visited.add(current)
            for dep in self._dependents_map.get(current, set()):
                if dfs(dep):
                    return True
            return False

        return dfs(to_id)

    # ── Dynamic Modification ──

    def add_task_dynamic(self, task: Task) -> None:
        """Add a new task to an existing plan."""
        self.add_task(task)
        # Evaluate immediately
        self.evaluate_dependencies(task.task_id)

    def remove_task(self, task_id: str) -> None:
        """Remove an unstarted task."""
        task = self._get_required(task_id)
        if task.status in (TaskStatus.STARTED, TaskStatus.COMPLETED):
            raise ValueError(f"Cannot remove task in '{task.status.value}' state")
        # Remove dependency edges
        for dep_id in task.dependencies:
            self._dependents_map.get(dep_id, set()).discard(task_id)
        for dep_id in self._dependents_map.get(task_id, set()):
            dep_task = self._tasks.get(dep_id)
            if dep_task:
                dep_task.dependencies = [d for d in dep_task.dependencies if d != task_id]
        self._tasks.pop(task_id, None)
        self._dependencies.pop(task_id, None)
        self._dependents_map.pop(task_id, None)
