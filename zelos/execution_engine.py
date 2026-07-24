"""
Execution Engine — Dispatches Tasks to Agents, monitors lifecycle, enforces timeouts.
"""

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from .event_bus import EventBus
from .task_graph import TaskGraphEngine, TaskStatus


@dataclass
class InFlightTask:
    task_id: str
    agent_id: str
    agent_name: str
    started_at: float
    timeout_at: float
    heartbeat_at: float = 0.0  # v0.8.0: last heartbeat timestamp
    heartbeat_timeout_ms: int = 30000  # v0.8.0: heartbeat timeout in ms


@dataclass
class AgentState:
    agent_id: str
    agent_name: str
    status: str = "registered"  # registered → connected → heartbeating → disconnected → shutdown
    operational_state: str = "idle"
    last_heartbeat_at: float = 0.0
    heartbeat_interval_ms: int = 30000
    endpoint: str | None = None
    max_concurrent_tasks: int = 5
    current_tasks: list[str] = field(default_factory=list)
    capabilities: list[dict] = field(default_factory=list)
    historical_success_rate: float = 0.0
    total_completed: int = 0
    total_failed: int = 0


class ExecutionEngine:
    """Kernel component — Task dispatch, lifecycle, timeouts, heartbeat tracking."""

    def __init__(self, task_graph: TaskGraphEngine, event_bus: EventBus):
        self._task_graph = task_graph
        self._event_bus = event_bus
        self._in_flight: dict[str, InFlightTask] = {}  # task_id → InFlightTask
        self._agents: dict[str, AgentState] = {}
        self._agent_dispatch: Callable | None = None  # Callback: (agent_id, task) → bool
        self._agent_cancel: Callable | None = None
        self._lock = threading.RLock()
        self._monitor_thread: threading.Thread | None = None
        self._running = False

    # ── Agent Management ──

    def register_agent(self, agent_id: str, agent_name: str, **kwargs) -> AgentState:
        state = AgentState(agent_id=agent_id, agent_name=agent_name, **kwargs)
        with self._lock:
            self._agents[agent_id] = state
        state.status = "connected"
        return state

    def heartbeat(self, agent_id: str) -> bool:
        with self._lock:
            agent = self._agents.get(agent_id)
            if not agent:
                return False
            agent.last_heartbeat_at = time.time()
            if agent.status == "connected":
                agent.status = "heartbeating"
            elif agent.status == "disconnected":
                agent.status = "heartbeating"
            # Update operational state
            agent.operational_state = "busy" if agent.current_tasks else "idle"
            return True

    def remove_agent(self, agent_id: str) -> None:
        with self._lock:
            self._agents.pop(agent_id, None)
            # Cancel all in-flight tasks for this agent
            for tid in list(self._in_flight.keys()):
                if self._in_flight[tid].agent_id == agent_id:
                    self.cancel_task(tid)

    def get_agent(self, agent_id: str) -> AgentState | None:
        return self._agents.get(agent_id)

    def list_agents(self) -> list[AgentState]:
        return list(self._agents.values())

    # ── Dispatch ──

    def dispatch(self, task_id: str, agent_id: str) -> bool:
        """Dispatch a task to an agent. Returns True if agent accepted."""
        task = self._task_graph.get_task(task_id)
        agent = self._agents.get(agent_id)
        if not task or not agent:
            return False

        with self._lock:
            self._task_graph.transition(task_id, TaskStatus.STARTED, agent_id=agent_id)
            hb_timeout = getattr(task, 'heartbeat_timeout_ms', 0) or agent.heartbeat_interval_ms * 3
            in_flight = InFlightTask(
                task_id=task_id,
                agent_id=agent_id,
                agent_name=agent.agent_name,
                started_at=time.time(),
                timeout_at=time.time() + (task.timeout_ms / 1000),
                heartbeat_at=time.time(),  # v0.8.0
                heartbeat_timeout_ms=hb_timeout,  # v0.8.0
            )
            self._in_flight[task_id] = in_flight
            agent.current_tasks.append(task_id)
            agent.operational_state = "busy"

        # Call the agent dispatch callback (in-process: direct function call)
        if self._agent_dispatch:
            self._agent_dispatch(agent_id, task)

        return True

    def reject_task(self, task_id: str) -> None:
        """Agent rejected the task → re-schedule."""
        with self._lock:
            self._in_flight.pop(task_id, None)
            try:
                self._task_graph.transition(task_id, TaskStatus.READY)
            except ValueError:
                pass

    # ── Result Handling ──

    def submit_result(self, task_id: str, agent_id: str, result: dict) -> bool:
        """
        Agent returns task result. result = {status: "completed"|"failed", artifact?: ..., error?: ...}

        v0.8.0: If error code matches task.non_retryable_errors, transition to FATAL_FAILED.
        """
        with self._lock:
            inflight = self._in_flight.pop(task_id, None)
            if not inflight:
                return False

            agent = self._agents.get(agent_id)
            if agent and task_id in agent.current_tasks:
                agent.current_tasks.remove(task_id)
                if not agent.current_tasks:
                    agent.operational_state = "idle"

            if result.get("status") == "completed":
                try:
                    self._task_graph.transition(task_id, TaskStatus.COMPLETED)
                except ValueError:
                    return False
                if agent:
                    agent.total_completed += 1
            else:
                # v0.8.0: Check non_retryable_errors
                task = self._task_graph.get_task(task_id)
                error_code = (result.get("error") or {}).get("code", "")
                if task and error_code and task.non_retryable_errors:
                    if error_code in task.non_retryable_errors:
                        try:
                            self._task_graph.transition(task_id, TaskStatus.FATAL_FAILED)
                        except ValueError:
                            # Fallback: if FATAL_FAILED transition not valid, use FAILED
                            self._task_graph.transition(task_id, TaskStatus.FAILED)
                        if agent:
                            agent.total_failed += 1
                        return True
                # Normal failure
                try:
                    self._task_graph.transition(task_id, TaskStatus.FAILED)
                except ValueError:
                    return False
                if agent:
                    agent.total_failed += 1
            return True

    # ── Cancellation ──

    def cancel_task(self, task_id: str) -> bool:
        with self._lock:
            inflight = self._in_flight.pop(task_id, None)
            if inflight:
                agent = self._agents.get(inflight.agent_id)
                if agent and task_id in agent.current_tasks:
                    agent.current_tasks.remove(task_id)
                try:
                    self._task_graph.transition(task_id, TaskStatus.CANCELLED)
                except ValueError:
                    pass
                if self._agent_cancel:
                    self._agent_cancel(inflight.agent_id, task_id)
                return True
        return False

    # ── v0.8.0: Heartbeat ──

    def submit_heartbeat(self, task_id: str, agent_id: str = "") -> bool:
        """v0.8.0: Update heartbeat timestamp for an in-flight task."""
        with self._lock:
            ft = self._in_flight.get(task_id)
            if not ft:
                return False
            if agent_id and ft.agent_id != agent_id:
                return False
            ft.heartbeat_at = time.time()
            return True

    def _check_heartbeat_timeouts(self) -> list[str]:
        """v0.8.0: Check for heartbeat timeouts, transition tasks to FAILED.
        Returns list of task_ids that timed out due to heartbeat.
        """
        now = time.time()
        timed_out = []
        with self._lock:
            for tid, ft in list(self._in_flight.items()):
                if ft.heartbeat_timeout_ms > 0:
                    timeout_at = ft.heartbeat_at + (ft.heartbeat_timeout_ms / 1000)
                    if now >= timeout_at:
                        try:
                            self._task_graph.transition(tid, TaskStatus.FAILED)
                        except ValueError:
                            pass
                        self._in_flight.pop(tid, None)
                        agent = self._agents.get(ft.agent_id)
                        if agent and tid in agent.current_tasks:
                            agent.current_tasks.remove(tid)
                        timed_out.append(tid)
        return timed_out

    # ── Timeout Monitor ──

    def start_monitor(self) -> None:
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def stop_monitor(self) -> None:
        self._running = False

    def _monitor_loop(self) -> None:
        while self._running:
            now = time.time()
            with self._lock:
                timed_out = [tid for tid, ft in self._in_flight.items() if now >= ft.timeout_at]
            for tid in timed_out:
                try:
                    self._task_graph.transition(tid, TaskStatus.TIMED_OUT)
                except ValueError:
                    pass
                self._in_flight.pop(tid, None)

            # v0.8.0: Heartbeat timeout check
            self._check_heartbeat_timeouts()

            # Agent heartbeat check
            with self._lock:
                for agent in list(self._agents.values()):
                    if agent.status == "heartbeating":
                        elapsed = now - agent.last_heartbeat_at
                        if elapsed > agent.heartbeat_interval_ms * 3 / 1000:
                            agent.status = "disconnected"
            time.sleep(1.0)

    @property
    def in_flight_count(self) -> int:
        return len(self._in_flight)

    @property
    def in_flight_task_ids(self) -> list[str]:
        return list(self._in_flight.keys())
