"""
Policy Engine — Domain-specific rules for filtering, rate-limiting, and cost control.

Phase 1: CostLimit, RateLimit, Allowlist, and Composite policies.
"""
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Any, Dict, List, Optional


class Policy(ABC):
    """Base class for all Policy plugins."""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

    @abstractmethod
    def evaluate(self, context: Dict[str, Any]) -> str:
        """Returns 'allow', 'reject', 'delay', or 'retry'."""
        ...


class CostLimitPolicy(Policy):
    """Reject if cumulative cost + task cost exceeds budget."""

    def __init__(self, config: Optional[Dict] = None):
        super().__init__(config)
        self.max_cost = config.get("max_cost_per_goal", 100.0) if config else 100.0
        self._cumulative: Dict[str, float] = defaultdict(float)

    def evaluate(self, context: Dict[str, Any]) -> str:
        goal_id = context.get("goal_id", "default")
        task_cost = context.get("task_cost", 0.0)
        budget = context.get("max_budget", self.max_cost)

        total = self._cumulative[goal_id] + task_cost
        if total > budget:
            return "reject"
        return "allow"

    def record_cost(self, goal_id: str, cost: float) -> None:
        self._cumulative[goal_id] += cost

    def reset(self, goal_id: str) -> None:
        self._cumulative.pop(goal_id, None)


class RateLimitPolicy(Policy):
    """Reject if task count exceeds rate limit per time window."""

    def __init__(self, config: Optional[Dict] = None):
        super().__init__(config)
        self.max_per_window = config.get("max_tasks_per_minute", 60) if config else 60
        self.window_seconds = config.get("window_seconds", 60) if config else 60
        self._timestamps: List[float] = []

    def evaluate(self, context: Dict[str, Any]) -> str:
        now = time.time()
        cutoff = now - self.window_seconds
        self._timestamps = [t for t in self._timestamps if t > cutoff]
        self._timestamps.append(now)

        if len(self._timestamps) > self.max_per_window:
            return "reject"
        return "allow"

    def reset(self) -> None:
        self._timestamps.clear()


class AllowlistPolicy(Policy):
    """Allow only agents in the allowlist."""

    def __init__(self, config: Optional[Dict] = None):
        super().__init__(config)
        self.allowlist: List[str] = config.get("allowlist_agents", []) if config else []

    def evaluate(self, context: Dict[str, Any]) -> str:
        agent_id = context.get("agent_id", "")
        if self.allowlist and agent_id not in self.allowlist:
            return "reject"
        return "allow"


class CompositePolicy(Policy):
    """Run multiple policies in sequence. Short-circuits on first rejection."""

    def __init__(self, policies: Optional[List[Policy]] = None, config: Optional[Dict] = None):
        super().__init__(config)
        self._policies: List[Policy] = policies or []

    def add(self, policy: Policy) -> None:
        self._policies.append(policy)

    def evaluate(self, context: Dict[str, Any]) -> str:
        for p in self._policies:
            result = p.evaluate(context)
            if result != "allow":
                return result
        return "allow"
