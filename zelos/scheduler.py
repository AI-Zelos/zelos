"""
Scheduler — Matches Ready tasks to available Agents.
Phase 1: 5-phase pipeline (Order → Filter → Score → Policy → Select).
Scoring Phase 3 is delegated to a ScoringStrategy plugin.
"""

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass

from .capability_registry import CapabilityRegistry
from .task_graph import Task, TaskGraphEngine, TaskStatus


@dataclass
class AgentCandidate:
    agent_id: str
    agent_name: str
    capability_name: str
    capability_version: str
    success_rate: float
    cost_per_call: float
    avg_latency_ms: float
    availability: float
    current_load: float
    tags: list[str]
    total_completed: int
    executed_dependency: bool = False
    last_used_seconds_ago: float = 999.0


@dataclass
class ScoredCandidate:
    candidate: AgentCandidate
    score: float
    reason: str = ""


class ScoringStrategy(ABC):
    """Plugin interface for custom Agent ranking."""

    @abstractmethod
    def score(self, task: Task, candidates: list[AgentCandidate]) -> list[ScoredCandidate]: ...


class DefaultScoringStrategy(ScoringStrategy):
    """Default weighted multi-factor scoring."""

    def __init__(self, weights: dict[str, float] | None = None):
        self.weights = weights or {
            "success_rate": 0.30,
            "cost_efficiency": 0.20,
            "load_distribution": 0.15,
            "latency": 0.15,
            "availability": 0.10,
            "affinity": 0.05,
            "recency": 0.05,
        }

    def score(self, task: Task, candidates: list[AgentCandidate]) -> list[ScoredCandidate]:
        results = []
        for c in candidates:
            s = (
                c.success_rate * self.weights.get("success_rate", 0.30)
                + (1.0 - min(c.cost_per_call / (task.max_cost_per_call or 1.0), 1.0))
                * self.weights.get("cost_efficiency", 0.20)
                + (1.0 - c.current_load) * self.weights.get("load_distribution", 0.15)
                + (1.0 - min(c.avg_latency_ms / (task.max_latency_ms or 30000), 1.0))
                * self.weights.get("latency", 0.15)
                + c.availability * self.weights.get("availability", 0.10)
                + (1.0 if c.executed_dependency else 0.5 if c.total_completed > 0 else 0.0)
                * self.weights.get("affinity", 0.05)
                + max(0, 1.0 - c.last_used_seconds_ago / 300) * self.weights.get("recency", 0.05)
            )
            score = max(0.0, min(1.0, s))
            results.append(
                ScoredCandidate(
                    candidate=c, score=score, reason=f"success={c.success_rate:.2f} cost={c.cost_per_call:.3f}"
                )
            )
        results.sort(key=lambda r: r.score, reverse=True)
        return results


class PolicyPlugin(ABC):
    """Plugin for Allow/Reject/Delay/Retry decisions."""

    @abstractmethod
    def evaluate(self, candidate: AgentCandidate, task: Task) -> str:
        """Returns: 'allow', 'reject', 'delay', 'retry'."""
        ...


class DefaultPolicy(PolicyPlugin):
    def evaluate(self, candidate: AgentCandidate, task: Task) -> str:
        return "allow"


class Scheduler:
    """Kernel component — 5-phase scheduler.

    v0.8.0: Publishes task.retry_scheduled events on retry.
    """

    def __init__(
        self,
        task_graph: TaskGraphEngine,
        capability_registry: CapabilityRegistry,
        scoring_strategy: ScoringStrategy | None = None,
        policy_plugin: PolicyPlugin | None = None,
    ):
        self._task_graph = task_graph
        self._registry = capability_registry
        self._scoring = scoring_strategy or DefaultScoringStrategy()
        self._policy = policy_plugin or DefaultPolicy()
        self._event_bus = None  # v0.8.0: set via set_event_bus()

    def set_scoring_strategy(self, strategy: ScoringStrategy) -> None:
        self._scoring = strategy

    def set_policy(self, policy: PolicyPlugin) -> None:
        self._policy = policy

    def set_event_bus(self, event_bus) -> None:
        """v0.8.0: Inject EventBus for publishing retry events."""
        self._event_bus = event_bus

    # ── Main Entry Point ──

    def schedule(self) -> list[dict[str, str]]:
        """
        Run scheduling round. Returns list of assignments [{task_id, agent_id}].
        """
        ready_tasks = self._phase1_order()
        assignments = []
        for task in ready_tasks:
            result = self._schedule_one(task)
            if result:
                assignments.append(result)
        return assignments

    def _schedule_one(self, task: Task) -> dict[str, str] | None:
        candidates = self._phase2_filter(task)
        if not candidates:
            if task.fallback_capability:
                original_cap = task.required_capability
                task.required_capability = task.fallback_capability
                candidates = self._phase2_filter(task)
                task.required_capability = original_cap
            if not candidates:
                return None

        # Preferred agent: if specified and in candidates, select directly
        if task.preferred_agent_id:
            for c in candidates:
                if c.agent_id == task.preferred_agent_id:
                    return self._phase5_select(task.task_id, c.agent_id)

        scored = self._phase3_score(task, candidates)
        if not scored or scored[0].score == 0:
            return None

        for sc in scored:
            decision = self._phase4_policy(sc.candidate, task)
            if decision == "allow":
                return self._phase5_select(task.task_id, sc.candidate.agent_id)

        return None

    # ── Phase 1: Order ──

    def _phase1_order(self) -> list[Task]:
        tasks = self._task_graph.get_ready_tasks()
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        tasks.sort(
            key=lambda t: (
                priority_order.get(t.priority, 2),
                -(len(self._task_graph._dependents_map.get(t.task_id, set()))),
                t.created_at,
            )
        )
        return tasks

    # ── Phase 2: Filter ──

    def _phase2_filter(self, task: Task) -> list[AgentCandidate]:
        providers = self._registry.find_providers_for(task.required_capability)
        candidates = []
        for agent_id in providers:
            caps = self._registry.get_by_agent(agent_id)
            if not caps:
                continue
            cap = caps[0]

            # Hard constraints
            if task.excluded_agent_ids and agent_id in task.excluded_agent_ids:
                continue
            if task.min_success_rate > 0:
                # Would need agent metrics — use 0.5 default for Phase 1
                pass
            if task.required_tags:
                if not set(task.required_tags).issubset(set(cap.tags)):
                    continue

            candidates.append(
                AgentCandidate(
                    agent_id=agent_id,
                    agent_name=cap.agent_name,
                    capability_name=cap.name,
                    capability_version=cap.version,
                    success_rate=0.9,
                    cost_per_call=0.05,
                    avg_latency_ms=5000,
                    availability=0.99,
                    current_load=0.0,
                    tags=list(cap.tags),
                    total_completed=100,
                )
            )
        return candidates

    # ── Phase 3: Score ──

    def _phase3_score(self, task: Task, candidates: list[AgentCandidate]) -> list[ScoredCandidate]:
        return self._scoring.score(task, candidates)

    # ── Phase 4: Policy ──

    def _phase4_policy(self, candidate: AgentCandidate, task: Task) -> str:
        return self._policy.evaluate(candidate, task)

    # ── Phase 5: Select ──

    def _phase5_select(self, task_id: str, agent_id: str) -> dict[str, str]:
        self._task_graph.transition(task_id, TaskStatus.ASSIGNED, agent_id=agent_id)
        return {"task_id": task_id, "agent_id": agent_id}

    # ── Retry ──

    def evaluate_retry(self, task: Task, previous_error: dict | None = None) -> str | None:
        """Returns 'retry' if task should be retried, None if exhausted.

        v0.8.0:
          - Skips retry for FATAL_FAILED tasks (terminal).
          - Publishes task.retry_scheduled event to EventBus on retry.
          - Accepts previous_error dict for event payload.
        """
        # v0.8.0: FATAL_FAILED is terminal — no retry
        if task.status == TaskStatus.FATAL_FAILED:
            return None

        task.attempt += 1
        if task.attempt <= task.max_retries:
            backoff_ms = task.backoff_base_ms * (2 ** (task.attempt - 1)) + random.randint(0, 500)
            if task.status in (TaskStatus.FAILED, TaskStatus.TIMED_OUT):
                self._task_graph.transition(task.task_id, TaskStatus.READY)

            # v0.8.0: Publish retry event
            if self._event_bus:
                import time
                import uuid

                from .event_bus import Event

                retry_event = Event(
                    event_id=str(uuid.uuid4()),
                    event_type="task.retry_scheduled",
                    source="scheduler",
                    timestamp=time.time(),
                    correlation_id=task.plan_id,
                    payload={
                        "task_id": task.task_id,
                        "attempt": task.attempt,
                        "backoff_ms": backoff_ms,
                        "plan_id": task.plan_id,
                        "previous_error": previous_error or {},
                    },
                )
                self._event_bus.publish(retry_event)
            return f"retry_in_{backoff_ms}ms"
        else:
            if task.status not in (TaskStatus.FAILED, TaskStatus.FATAL_FAILED):
                self._task_graph.transition(task.task_id, TaskStatus.FAILED)
            return None
