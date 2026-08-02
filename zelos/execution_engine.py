"""
Execution Engine — Dispatches Tasks to Agents, monitors lifecycle, enforces timeouts.
"""

import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

from .event_bus import Event, EventBus
from .task_graph import Task, TaskGraphEngine, TaskStatus


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
    required_credentials: list[str] = field(default_factory=list)  # v1.1.0
    historical_success_rate: float = 0.0
    total_completed: int = 0
    total_failed: int = 0


class ExecutionEngine:
    """Kernel component — Task dispatch, lifecycle, timeouts, heartbeat tracking.

    v1.3.0: MPC replan_check hook, incremental verification, diagnosis trigger.
    """

    def __init__(self, task_graph: TaskGraphEngine, event_bus: EventBus):
        self._task_graph = task_graph
        self._event_bus = event_bus
        task_graph._event_bus = event_bus  # v0.9.0: wire lifecycle events
        self._in_flight: dict[str, InFlightTask] = {}  # task_id → InFlightTask
        self._agents: dict[str, AgentState] = {}
        self._agent_dispatch: Callable | None = None  # Callback: (agent_id, task) → bool
        self._agent_cancel: Callable | None = None
        self._lock = threading.RLock()
        self._monitor_thread: threading.Thread | None = None
        self._running = False
        self._task_inputs: dict[str, dict] = {}  # v0.9.0: task input context
        self._task_start_times: dict[str, float] = {}  # v0.9.0: task start timestamps
        self._credential_injector = None  # v1.1.0: set by runtime

        # v1.3.0: MPC Adaptive Loop
        self._replan_callback: Callable | None = None  # Runtime._on_replan
        self._replan_rules: list = []  # ReplanRule instances
        self._current_plan = None  # PlannerPlan reference
        self._replan_count: dict[str, int] = {}  # goal_id → count
        self._max_replans: int = 5
        self._incremental_verifier = None  # SchemaVerifier for per-task check
        self._diagnosis_engine = None  # DiagnosisEngine instance (from feature flag)

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

    def set_task_input_context(self, task_id: str, input_context: dict) -> None:
        """v0.9.0: Set the input context for a task before dispatch."""
        with self._lock:
            self._task_inputs[task_id] = input_context

    def dispatch(self, task_id: str, agent_id: str) -> bool:
        """Dispatch a task to an agent. Returns True if agent accepted."""
        task = self._task_graph.get_task(task_id)
        agent = self._agents.get(agent_id)
        if not task or not agent:
            return False

        with self._lock:
            self._task_graph.transition(task_id, TaskStatus.STARTED, agent_id=agent_id)
            hb_timeout = getattr(task, 'heartbeat_timeout_ms', 0) or agent.heartbeat_interval_ms * 3
            now = time.time()
            in_flight = InFlightTask(
                task_id=task_id,
                agent_id=agent_id,
                agent_name=agent.agent_name,
                started_at=now,
                timeout_at=now + (task.timeout_ms / 1000),
                heartbeat_at=now,
                heartbeat_timeout_ms=hb_timeout,
            )
            self._in_flight[task_id] = in_flight
            self._task_start_times[task_id] = now  # v0.9.0
            agent.current_tasks.append(task_id)
            agent.operational_state = "busy"

        # v1.1.0: Inject credentials before dispatch
        if self._credential_injector and agent.required_credentials:
            try:
                self._credential_injector.inject(task, agent_id, agent.required_credentials)
            except Exception:
                # Credential failure → reject task for retry
                self._in_flight.pop(task_id, None)
                agent.current_tasks.remove(task_id)
                try:
                    self._task_graph.transition(task_id, TaskStatus.FAILED)
                except ValueError:
                    pass
                return False

        # v0.9.0: Publish task.started event with input context
        input_ctx = self._task_inputs.pop(task_id, None)
        self._event_bus.publish(Event(
            event_id=str(uuid.uuid4()),
            event_type="task.started",
            source="execution_engine",
            timestamp=now,
            correlation_id=task.plan_id,
            payload={
                "task_id": task_id,
                "agent_id": agent_id,
                "agent_name": agent.agent_name,
                "required_capability": task.required_capability,
                "input_context": input_ctx or {},
            },
        ))

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

            status = result.get("status")
            duration_ms = (time.time() - self._task_start_times.pop(task_id, time.time())) * 1000
            task = self._task_graph.get_task(task_id)

            if status == "completed":
                try:
                    self._task_graph.transition(task_id, TaskStatus.COMPLETED)
                except ValueError:
                    return False
                if agent:
                    agent.total_completed += 1
                # v0.9.0: Publish task.completed with artifact
                artifact = result.get("artifact", {})
                payload_size = len(str(artifact))
                event_payload = {
                    "task_id": task_id, "agent_id": agent_id,
                    "duration_ms": int(duration_ms),
                }
                if payload_size > 100000:
                    event_payload["content_ref"] = f"storage:task:{task_id}:artifact"
                    event_payload["output_artifact_summary"] = f"Large artifact ({payload_size} bytes)"
                else:
                    event_payload["output_artifact"] = artifact
                self._event_bus.publish(Event(
                    event_id=str(uuid.uuid4()),
                    event_type="task.completed",
                    source="execution_engine",
                    timestamp=time.time(),
                    correlation_id=task.plan_id if task else "",
                    payload=event_payload,
                ))
            else:
                # v0.8.0: Check non_retryable_errors
                error_code = (result.get("error") or {}).get("code", "")
                if task and error_code and task.non_retryable_errors:
                    if error_code in task.non_retryable_errors:
                        try:
                            self._task_graph.transition(task_id, TaskStatus.FATAL_FAILED)
                        except ValueError:
                            self._task_graph.transition(task_id, TaskStatus.FAILED)
                        if agent:
                            agent.total_failed += 1
                        return True
                try:
                    self._task_graph.transition(task_id, TaskStatus.FAILED)
                except ValueError:
                    return False
                if agent:
                    agent.total_failed += 1
                # v0.9.0: Publish task.failed with error
                self._event_bus.publish(Event(
                    event_id=str(uuid.uuid4()),
                    event_type="task.failed",
                    source="execution_engine",
                    timestamp=time.time(),
                    correlation_id=task.plan_id if task else "",
                    payload={
                        "task_id": task_id, "agent_id": agent_id,
                        "error": result.get("error", {}),
                        "duration_ms": int(duration_ms),
                    },
                ))

        # ── v1.3.0: MPC Replan Check (outside lock to avoid deadlock) ──
        self._mpc_replan_check(task_id, result)
        return True

    def _mpc_replan_check(self, task_id: str, result: dict) -> None:
        """v1.3.0: After task result is handled, check if replan is needed."""
        if not self._replan_callback or not self._replan_rules:
            return
        if not self._current_plan:
            return

        # Only trigger replan on failed tasks
        status = result.get("status")
        if status == "completed":
            return

        goal_id = getattr(self._current_plan, 'goal_id', 'unknown')
        count = self._replan_count.get(goal_id, 0)
        if count >= self._max_replans:
            self._event_bus.publish(Event(
                event_id=str(uuid.uuid4()),
                event_type="goal.replan_limit_exceeded",
                source="execution_engine",
                timestamp=time.time(),
                correlation_id=goal_id,
                payload={
                    "goal_id": goal_id,
                    "replan_count": count,
                    "max_replans": self._max_replans,
                    "reason": f"Exceeded max replans ({self._max_replans})",
                },
            ))
            return

        artifact = result.get("artifact", {})
        verdict = self._run_incremental_verify(task_id, artifact)

        from .replan_rules import ReplanContext
        ctx = ReplanContext(
            task_id=task_id,
            artifact=artifact,
            verdict=verdict,
            current_plan=self._current_plan,
        )

        diagnosis = self._run_diagnosis_if_applicable(task_id, result)

        for rule in self._replan_rules:
            if rule.should_replan(ctx):
                new_plan = self._replan_callback(
                    plan_id=self._current_plan.plan_id,
                    trigger=rule.trigger_reason,
                    context={
                        "failed_task_id": task_id,
                        "verdict": verdict,
                        "diagnosis": diagnosis,
                        "completed_tasks": self._get_completed_task_ids(),
                        "failed_task": self._task_graph.get_task(task_id),
                    },
                )
                if new_plan:
                    self._current_plan = new_plan
                    self._replan_count[goal_id] = count + 1
                    self._event_bus.publish(Event(
                        event_id=str(uuid.uuid4()),
                        event_type="execution_plan.modified",
                        source="execution_engine",
                        timestamp=time.time(),
                        correlation_id=new_plan.plan_id,
                        payload={
                            "plan_id": new_plan.plan_id,
                            "trigger_reason": rule.trigger_reason,
                            "failed_task_id": task_id,
                            "replan_count": count + 1,
                        },
                    ))
                break

    # ── v1.3.0: MPC Support Methods ──

    def set_replan_callback(self, callback: Callable) -> None:
        """v1.3.0: Inject Runtime._on_replan as the replan callback."""
        self._replan_callback = callback

    def set_current_plan(self, plan) -> None:
        """v1.3.0: Set the current ExecutionPlan reference."""
        self._current_plan = plan

    def set_diagnosis_engine(self, engine) -> None:
        """v1.3.0: Inject DiagnosisEngine for failure analysis."""
        self._diagnosis_engine = engine

    def _run_incremental_verify(self, task_id: str, artifact: dict | None):
        """v1.3.0: Lightweight per-task verification after completion."""
        verifier = self._incremental_verifier
        if not verifier:
            from .verifier import Verdict
            return Verdict(verdict="passed", score=1.0, verifier_id="incremental")

        if artifact is None or (isinstance(artifact, dict) and not artifact):
            from .verifier import Verdict
            return Verdict(verdict="failed", score=0.0, verifier_id="incremental",
                          summary="Empty artifact")

        task = self._task_graph.get_task(task_id)
        rules = ["non_empty"]
        expected_schema = getattr(task, 'expected_output_schema', None) if task else None
        if expected_schema:
            rules.append("schema")

        from .verifier import VerificationCriteria
        criteria = VerificationCriteria(
            expected_output_schema=expected_schema or {},
            rules=rules,
        )
        return verifier.verify(artifact, criteria)

    def _run_diagnosis_if_applicable(self, task_id: str, result: dict):
        """v1.3.0: Run DiagnosisEngine if test_output is present in result."""
        if not self._diagnosis_engine:
            return None
        test_output = (
            result.get("test_output")
            or (result.get("error") or {}).get("test_output", "")
        )
        if not test_output:
            return None
        return self._diagnosis_engine.diagnose(test_output)

    def _get_completed_task_ids(self) -> list[str]:
        """v1.3.0: Return task_ids of all COMPLETED tasks in current plan."""
        if not self._current_plan:
            return []
        completed = []
        for task in self._task_graph.list_tasks():
            if task.status == TaskStatus.COMPLETED:
                completed.append(task.task_id)
        return completed

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
