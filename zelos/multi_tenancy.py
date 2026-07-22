"""
Phase 3 Multi-tenancy — Namespace Isolation, Resource Quotas, Tenant Management.

Produces hard isolation between tenants sharing a single Runtime:
  - Each tenant gets its own Namespace (goals, tasks, agents invisible to others)
  - ResourceQuota caps: goals, tasks, agents, budget per goal
  - TenantManager: register, activate/deactivate, cross-tenant isolation
"""

import threading
import time
from dataclasses import dataclass, field
from typing import Any

# ═══════════════════ Resource Quota ═══════════════════


@dataclass
class ResourceQuota:
    """Resource limits for a namespace or tenant."""

    max_goals: int = 100
    max_tasks: int = 500
    max_agents: int = 50
    budget_per_goal: float = 1000.0
    max_concurrent_tasks: int = 20
    max_storage_mb: int = 1024

    def check_budget(self, cost: float) -> bool:
        """Check if cost is within budget limit."""
        return cost <= self.budget_per_goal

    def to_dict(self) -> dict:
        return {
            "max_goals": self.max_goals,
            "max_tasks": self.max_tasks,
            "max_agents": self.max_agents,
            "budget_per_goal": self.budget_per_goal,
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "max_storage_mb": self.max_storage_mb,
        }


# ═══════════════════ Namespace ═══════════════════


class Namespace:
    """Isolated resource container for a tenant.

    Every namespace tracks its own:
      - Goals (goal IDs only — actual goals stored in Runtime)
      - Tasks (task IDs)
      - Agents (agent IDs)
    """

    def __init__(self, namespace_id: str, name: str = "", quotas: ResourceQuota | None = None):
        self.namespace_id = namespace_id
        self.name = name or namespace_id
        self.quotas = quotas or ResourceQuota()
        self._goals: list[str] = []
        self._tasks: list[str] = []
        self._agents: list[str] = []
        self._created_at = time.time()
        self._lock = threading.RLock()

    # ── Goal tracking ──

    def add_goal(self, goal_id: str) -> bool:
        with self._lock:
            if len(self._goals) >= self.quotas.max_goals:
                return False
            self._goals.append(goal_id)
            return True

    def remove_goal(self, goal_id: str) -> None:
        with self._lock:
            if goal_id in self._goals:
                self._goals.remove(goal_id)

    # ── Task tracking ──

    def add_task(self, task_id: str) -> bool:
        with self._lock:
            if len(self._tasks) >= self.quotas.max_tasks:
                return False
            self._tasks.append(task_id)
            return True

    def remove_task(self, task_id: str) -> None:
        with self._lock:
            if task_id in self._tasks:
                self._tasks.remove(task_id)

    # ── Agent tracking ──

    def add_agent(self, agent_id: str) -> bool:
        with self._lock:
            if len(self._agents) >= self.quotas.max_agents:
                return False
            self._agents.append(agent_id)
            return True

    def remove_agent(self, agent_id: str) -> None:
        with self._lock:
            if agent_id in self._agents:
                self._agents.remove(agent_id)

    # ── Quota Checks ──

    def check_quota(self, resource_type: str) -> bool:
        """Check if adding one more of resource_type is allowed."""
        with self._lock:
            if resource_type == "goals":
                return len(self._goals) < self.quotas.max_goals
            elif resource_type == "tasks":
                return len(self._tasks) < self.quotas.max_tasks
            elif resource_type == "agents":
                return len(self._agents) < self.quotas.max_agents
            elif resource_type == "concurrent_tasks":
                return self.active_task_count() < self.quotas.max_concurrent_tasks
            return True

    def active_task_count(self) -> int:
        return len(self._tasks)

    # ── Counts ──

    @property
    def goal_count(self) -> int:
        with self._lock:
            return len(self._goals)

    @property
    def task_count(self) -> int:
        with self._lock:
            return len(self._tasks)

    @property
    def agent_count(self) -> int:
        with self._lock:
            return len(self._agents)

    def to_dict(self) -> dict:
        return {
            "namespace_id": self.namespace_id,
            "name": self.name,
            "quotas": self.quotas.to_dict(),
            "goal_count": self.goal_count,
            "task_count": self.task_count,
            "agent_count": self.agent_count,
            "created_at": self._created_at,
        }


# ═══════════════════ Tenant ═══════════════════


@dataclass
class Tenant:
    """A tenant represents a team/organization using the Runtime."""

    tenant_id: str
    name: str
    namespace: Namespace
    active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "name": self.name,
            "active": self.active,
            "namespace": self.namespace.to_dict(),
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


# ═══════════════════ Tenant Manager ═══════════════════


class TenantManager:
    """Central tenant registry with cross-tenant isolation enforcement.

    Every tenant gets its own Namespace. Resources in one namespace
    are invisible to other tenants.
    """

    def __init__(self):
        self._tenants: dict[str, Tenant] = {}
        self._default_namespace = Namespace("default", "Default Namespace")
        self._lock = threading.RLock()

    def register_tenant(
        self, tenant_id: str, name: str = "", quotas: ResourceQuota | None = None, metadata: dict | None = None
    ) -> Tenant:
        """Register a new tenant with its own namespace."""
        namespace = Namespace(tenant_id, name, quotas)
        tenant = Tenant(
            tenant_id=tenant_id,
            name=name or tenant_id,
            namespace=namespace,
            metadata=metadata or {},
        )
        with self._lock:
            self._tenants[tenant_id] = tenant
        return tenant

    def get_tenant(self, tenant_id: str) -> Tenant | None:
        return self._tenants.get(tenant_id)

    def get_namespace(self, tenant_id: str) -> Namespace | None:
        """Get a tenant's namespace. Returns default if not found."""
        tenant = self._tenants.get(tenant_id)
        return tenant.namespace if tenant else self._default_namespace

    def deactivate_tenant(self, tenant_id: str) -> bool:
        """Deactivate a tenant — all operations rejected."""
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            return False
        tenant.active = False
        return True

    def activate_tenant(self, tenant_id: str) -> bool:
        """Reactivate a tenant."""
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            return False
        tenant.active = True
        return True

    def is_active(self, tenant_id: str) -> bool:
        tenant = self._tenants.get(tenant_id)
        return tenant.active if tenant else True  # Default tenant always active

    def remove_tenant(self, tenant_id: str) -> bool:
        """Permanently remove a tenant and its namespace."""
        with self._lock:
            if tenant_id in self._tenants:
                del self._tenants[tenant_id]
                return True
        return False

    def list_tenants(self) -> list[Tenant]:
        return list(self._tenants.values())

    def tenant_count(self) -> int:
        return len(self._tenants)

    def get_usage_report(self) -> dict[str, Any]:
        """Aggregate usage across all tenants."""
        tenants_usage = {}
        for tenant_id, tenant in self._tenants.items():
            ns = tenant.namespace
            tenants_usage[tenant_id] = {
                "name": tenant.name,
                "active": tenant.active,
                "goals": ns.goal_count,
                "tasks": ns.task_count,
                "agents": ns.agent_count,
                "quotas": ns.quotas.to_dict(),
            }
        return {
            "total_tenants": len(self._tenants),
            "active_tenants": sum(1 for t in self._tenants.values() if t.active),
            "tenants": tenants_usage,
        }
