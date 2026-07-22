"""
Phase 3 Advanced Execution — Dynamic Plan Modification, Sub-Goal Spawning, Human-in-the-Loop.

Production-grade execution features beyond basic task dispatch:
  - DynamicPlanModifier: Modify running plans (add/remove tasks, change capabilities)
  - SubGoalManager: Spawn sub-goals from within task execution
  - HumanInTheLoop: Approval workflows for critical actions
"""
import time
import uuid
import threading
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .task_graph import Task, TaskStatus, TaskGraphEngine


# ═══════════════════ Dynamic Plan Modification ═══════════════════

class DynamicPlanModifier:
    """Modify an Execution Plan while it's running.

    Operations:
      - add_task: Insert a new task into an active plan's DAG
      - remove_task: Remove a not-yet-started task
      - modify_task: Change task capability, priority, timeout
      - add_dependency / remove_dependency: Re-wire the DAG
    """

    def __init__(self, task_graph: TaskGraphEngine):
        self._tg = task_graph
        self._modification_log: List[Dict[str, Any]] = []
        self._lock = threading.RLock()

    def add_task(self, task_id: str, plan_id: str, description: str,
                 required_capability: str, dependencies: Optional[List[str]] = None,
                 priority: str = "medium", timeout_ms: int = 30000,
                 fallback_capability: Optional[str] = None) -> Task:
        """Add a new task to a running plan."""
        task = Task(
            task_id=task_id,
            plan_id=plan_id,
            description=description,
            required_capability=required_capability,
            dependencies=list(dependencies or []),
            priority=priority,
            timeout_ms=timeout_ms,
            fallback_capability=fallback_capability,
        )
        with self._lock:
            self._tg.add_task(task)
            self._tg.evaluate_all()
            self._log_modification("add_task", task_id, {"plan_id": plan_id})
        return task

    def remove_task(self, task_id: str) -> bool:
        """Remove an unstarted task from the plan."""
        task = self._tg.get_task(task_id)
        if not task:
            return False
        if task.status in (TaskStatus.STARTED, TaskStatus.COMPLETED):
            raise ValueError(f"Cannot remove task in '{task.status.value}' state")

        with self._lock:
            self._tg.remove_task(task_id)
            self._log_modification("remove_task", task_id, {})
        return True

    def modify_task(self, task_id: str, **updates) -> Task:
        """Modify task attributes. Rejected for STARTED/COMPLETED tasks."""
        task = self._tg.get_task(task_id)
        if not task:
            raise KeyError(f"Task not found: {task_id}")
        if task.status in (TaskStatus.STARTED, TaskStatus.COMPLETED,
                           TaskStatus.CANCELLED):
            raise ValueError(f"Cannot modify task in '{task.status.value}' state")

        allowed_fields = {
            "description", "required_capability", "priority", "timeout_ms",
            "max_retries", "fallback_capability", "preferred_agent_id",
            "min_success_rate", "max_cost_per_call", "max_latency_ms",
        }

        for key, value in updates.items():
            if key in allowed_fields and hasattr(task, key):
                setattr(task, key, value)

        with self._lock:
            task.updated_at = time.time()
            self._log_modification("modify_task", task_id, updates)

        return task

    def add_dependency(self, from_task_id: str, to_task_id: str) -> None:
        """Add edge: from → to (to depends on from completing)."""
        with self._lock:
            self._tg.add_dependency(from_task_id, to_task_id)
            self._log_modification("add_dependency", to_task_id,
                                   {"depends_on": from_task_id})

    def remove_dependency(self, from_task_id: str, to_task_id: str) -> None:
        """Remove dependency: to no longer depends on from."""
        to_task = self._tg.get_task(to_task_id)
        if not to_task:
            raise KeyError(f"Task not found: {to_task_id}")
        if from_task_id in to_task.dependencies:
            to_task.dependencies.remove(from_task_id)
            # Also clean up dependents map
            if from_task_id in self._tg._dependents_map:
                self._tg._dependents_map[from_task_id].discard(to_task_id)
            if to_task_id in self._tg._dependencies:
                self._tg._dependencies[to_task_id].discard(from_task_id)

            with self._lock:
                self._tg.evaluate_all()
                self._log_modification("remove_dependency", to_task_id,
                                       {"removed_dep": from_task_id})

    def _log_modification(self, operation: str, target_id: str,
                          details: Dict[str, Any]) -> None:
        self._modification_log.append({
            "operation": operation,
            "target_id": target_id,
            "details": details,
            "timestamp": time.time(),
        })

    def get_modification_log(self) -> List[Dict[str, Any]]:
        return list(self._modification_log)


# ═══════════════════ Sub-Goal Spawning ═══════════════════

class SubGoalManager:
    """Manage sub-goals spawned during task execution.

    A task may discover it needs additional work — SubGoalManager
    allows it to spawn a sub-goal without interacting with the Planner.

    The parent task blocks until all sub-goals complete.
    Sub-goal failure propagates to the parent task.
    """

    def __init__(self, task_graph: TaskGraphEngine):
        self._tg = task_graph
        self._sub_goals: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()

    def spawn_sub_goal(self, parent_task_id: str, description: str,
                       budget: Optional[float] = None,
                       priority: str = "medium",
                       required_capability: str = "code-generation.python",
                       num_tasks: int = 1) -> Dict[str, Any]:
        """Spawn a sub-goal from a parent task.

        Creates a mini plan with one or more tasks. Parent task should
        wait for sub-goal completion before finishing.
        """
        sub_goal_id = f"sub-{uuid.uuid4().hex[:8]}"
        plan_id = f"sub-plan-{sub_goal_id}"
        task_ids = []

        for i in range(num_tasks):
            task_id = f"{sub_goal_id}-t{i + 1}"
            task = Task(
                task_id=task_id,
                plan_id=plan_id,
                description=f"[Sub-goal] {description}" + (f" (part {i + 1}/{num_tasks})" if num_tasks > 1 else ""),
                required_capability=required_capability,
                priority=priority,
            )
            if i > 0:
                task.dependencies = [task_ids[i - 1]]

            with self._lock:
                self._tg.add_task(task)
            task_ids.append(task_id)

        with self._lock:
            self._tg.evaluate_all()

        sub_goal = {
            "sub_goal_id": sub_goal_id,
            "parent_task_id": parent_task_id,
            "plan_id": plan_id,
            "description": description,
            "task_ids": task_ids,
            "budget": budget,
            "status": "running",
            "created_at": time.time(),
        }

        with self._lock:
            self._sub_goals[sub_goal_id] = sub_goal

        return sub_goal

    def get_sub_goal(self, sub_goal_id: str) -> Optional[Dict[str, Any]]:
        return self._sub_goals.get(sub_goal_id)

    def mark_sub_goal_failed(self, sub_goal_id: str) -> None:
        """Mark a sub-goal as failed."""
        sg = self._sub_goals.get(sub_goal_id)
        if sg:
            sg["status"] = "failed"
            sg["completed_at"] = time.time()

    def mark_sub_goal_completed(self, sub_goal_id: str) -> None:
        """Mark a sub-goal as completed."""
        sg = self._sub_goals.get(sub_goal_id)
        if sg:
            sg["status"] = "completed"
            sg["completed_at"] = time.time()

    def list_sub_goals(self, parent_task_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all sub-goals, optionally filtered by parent."""
        if parent_task_id:
            return [sg for sg in self._sub_goals.values()
                    if sg["parent_task_id"] == parent_task_id]
        return list(self._sub_goals.values())

    def are_all_completed(self, parent_task_id: str) -> bool:
        """Check if all sub-goals for a parent task are done."""
        children = self.list_sub_goals(parent_task_id)
        if not children:
            return True
        terminal = {"completed", "failed"}
        return all(c["status"] in terminal for c in children)

    def get_sub_goal_count(self) -> int:
        return len(self._sub_goals)


# ═══════════════════ Human-in-the-Loop ═══════════════════

class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CHANGES_REQUESTED = "changes_requested"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


@dataclass
class ApprovalRequest:
    """A request for human approval on a task action."""
    request_id: str
    task_id: str
    description: str
    context: Dict[str, Any] = field(default_factory=dict)
    approvers: List[str] = field(default_factory=list)
    require_all: bool = False
    status: ApprovalStatus = ApprovalStatus.PENDING
    timeout_seconds: float = 3600.0
    created_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None
    resolution_comment: str = ""


class HumanInTheLoop:
    """Human-in-the-loop approval workflow manager.

    Supports:
      - Single and multi-step approvals
      - Timeout-based auto-rejection
      - Approval audit trail
      - Change requests with feedback
    """

    def __init__(self):
        self._requests: Dict[str, ApprovalRequest] = {}
        self._history: Dict[str, List[Dict[str, Any]]] = {}
        self._lock = threading.RLock()

    def create_request(self, task_id: str, description: str,
                       approvers: List[str],
                       context: Optional[Dict] = None,
                       require_all: bool = False,
                       timeout_seconds: float = 3600.0) -> ApprovalRequest:
        """Create a new approval request."""
        req = ApprovalRequest(
            request_id=f"approval-{uuid.uuid4().hex[:12]}",
            task_id=task_id,
            description=description,
            context=context or {},
            approvers=list(approvers),
            require_all=require_all,
            timeout_seconds=timeout_seconds,
        )
        with self._lock:
            self._requests[req.request_id] = req
            self._history[req.request_id] = [{
                "action": "created",
                "timestamp": req.created_at,
                "detail": f"Approval requested from: {', '.join(approvers)}",
            }]
        return req

    def approve(self, request_id: str, approver: str, comment: str = "") -> bool:
        """Approve a request. For multi-approver, all must approve if require_all=True."""
        req = self._requests.get(request_id)
        if not req or req.status != ApprovalStatus.PENDING:
            return False
        if approver not in req.approvers:
            return False

        with self._lock:
            self._history[request_id].append({
                "action": "approved",
                "approver": approver,
                "comment": comment,
                "timestamp": time.time(),
            })

            if req.require_all:
                # Check if all approvers have approved
                approved_set = {
                    h["approver"] for h in self._history[request_id]
                    if h["action"] == "approved"
                }
                if set(req.approvers).issubset(approved_set):
                    req.status = ApprovalStatus.APPROVED
                    req.resolved_at = time.time()
                    req.resolution_comment = comment
            else:
                req.status = ApprovalStatus.APPROVED
                req.resolved_at = time.time()
                req.resolution_comment = comment

        return True

    def reject(self, request_id: str, approver: str, reason: str = "") -> bool:
        """Reject a request."""
        req = self._requests.get(request_id)
        if not req or req.status != ApprovalStatus.PENDING:
            return False
        if approver not in req.approvers:
            return False

        with self._lock:
            req.status = ApprovalStatus.REJECTED
            req.resolved_at = time.time()
            req.resolution_comment = reason
            self._history[request_id].append({
                "action": "rejected",
                "approver": approver,
                "comment": reason,
                "timestamp": time.time(),
            })
        return True

    def request_changes(self, request_id: str, approver: str,
                        feedback: str = "") -> bool:
        """Request changes — task goes back with feedback."""
        req = self._requests.get(request_id)
        if not req or req.status != ApprovalStatus.PENDING:
            return False

        with self._lock:
            req.status = ApprovalStatus.CHANGES_REQUESTED
            req.resolution_comment = feedback
            self._history[request_id].append({
                "action": "changes_requested",
                "approver": approver,
                "comment": feedback,
                "timestamp": time.time(),
            })
        return True

    def cancel_request(self, request_id: str) -> bool:
        """Cancel a pending approval request."""
        req = self._requests.get(request_id)
        if not req or req.status != ApprovalStatus.PENDING:
            return False

        with self._lock:
            req.status = ApprovalStatus.CANCELLED
            req.resolved_at = time.time()
            self._history[request_id].append({
                "action": "cancelled",
                "timestamp": time.time(),
            })
        return True

    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        return self._requests.get(request_id)

    def get_history(self, request_id: str) -> List[Dict[str, Any]]:
        """Get the full audit trail for a request."""
        return self._history.get(request_id, [])

    def list_pending(self) -> List[ApprovalRequest]:
        """List all pending approval requests."""
        return [r for r in self._requests.values()
                if r.status == ApprovalStatus.PENDING]

    def check_timeouts(self) -> List[ApprovalRequest]:
        """Check and auto-reject timed-out requests."""
        now = time.time()
        timed_out = []
        for req in self._requests.values():
            if req.status == ApprovalStatus.PENDING:
                if now - req.created_at > req.timeout_seconds:
                    req.status = ApprovalStatus.TIMED_OUT
                    req.resolved_at = now
                    timed_out.append(req)
        return timed_out

    def get_pending_count(self) -> int:
        return len(self.list_pending())
