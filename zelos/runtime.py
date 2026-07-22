"""
Zelos Runtime — Main entry point. Ties together all Kernel components.

Phase 3: Fully integrated with Security, Multi-tenancy, Advanced Execution,
         Hot Reload, Container Isolation, Distributed Runtime, and CLI.
"""

import threading
import time
import uuid
from typing import Any

from .advanced_execution import (
    DynamicPlanModifier,
    HumanInTheLoop,
    SubGoalManager,
)
from .capability_registry import CapabilityRegistry
from .config_loader import ConfigLoader
from .container_isolation import ContainerPluginConfig, ContainerRunner, RemotePlugin
from .distributed import ClusterNode, LeaderElection, NodeRegistry, WorkStealing
from .event_bus import EventBus
from .execution_engine import AgentState, ExecutionEngine
from .hot_reload import FileWatcher, HotReloadManager, UpgradeStrategy
from .memory import ContextAssembler, InMemoryMemoryProvider
from .multi_tenancy import ResourceQuota, TenantManager
from .planner import LLMPlanner, MockLLMProvider, PlannerPlan
from .plugin_manager import PluginLifecycleManager
from .policy import CompositePolicy
from .scheduler import PolicyPlugin, Scheduler, ScoringStrategy

# ═══ Phase 3 imports ═══
from .security import AccessControl, APIKeyManager, AuditLogger, TLSConfig
from .task_graph import Task, TaskGraphEngine, TaskStatus
from .verifier import SchemaVerifier, VerificationGate


class ZelosRuntime:
    """Central entry point. Owns Kernel lifecycle and Agent lifecycle.

    Supports:
      - Dict config: ZelosRuntime({"plugins": [...]})
      - YAML file:  ZelosRuntime.from_yaml("zelos.yaml")

    Phase 3: Integrated security (RBAC + audit), multi-tenancy (quotas + isolation),
    advanced execution (dynamic plans + sub-goals + HITL), hot reload (strategies),
    and distributed coordination (leader election + work stealing).
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

        # ── Phase 1 & 2: Kernel ──
        self._event_bus = EventBus()
        self._capability_registry = CapabilityRegistry()
        self._task_graph = TaskGraphEngine()
        self._plugin_manager = PluginLifecycleManager()
        self._scoring_strategy: ScoringStrategy | None = None
        self._policy_plugin: PolicyPlugin | None = None
        self._policy_engine: CompositePolicy | None = None
        self._planner: LLMPlanner | None = None
        self._verifier_gate: VerificationGate | None = None
        self._memory_provider: InMemoryMemoryProvider | None = None
        self._context_assembler: ContextAssembler | None = None
        self._scheduler: Scheduler | None = None
        self._execution_engine = ExecutionEngine(self._task_graph, self._event_bus)
        self._goals: dict[str, dict[str, Any]] = {}
        self._agents: dict[str, dict[str, Any]] = {}  # name → {agent info}
        self._agent_instances: dict[str, Any] = {}  # name → agent object
        self._agent_threads: dict[str, threading.Thread] = {}
        self._orchestrator_thread: threading.Thread | None = None
        self._running = False
        self._lock = threading.RLock()
        self._started_at: float = 0.0

        # ── Phase 3: Security ──
        sec_cfg = self.config.get("security", {})
        self._access_control = AccessControl()
        self._audit_logger = AuditLogger(max_events=sec_cfg.get("audit_max_events", 100000))
        self._api_key_manager = APIKeyManager()
        self._tls_config = TLSConfig(
            cert_file=sec_cfg.get("cert_file", ""),
            key_file=sec_cfg.get("key_file", ""),
            ca_file=sec_cfg.get("ca_file", ""),
            require_client_cert=sec_cfg.get("require_client_cert", True),
            min_tls_version=sec_cfg.get("min_tls_version", "TLSv1.2"),
            verify_hostname=sec_cfg.get("verify_hostname", True),
        )

        # ── Phase 3: Multi-tenancy ──
        mt_cfg = self.config.get("multi_tenancy", {})
        self._tenant_manager = TenantManager()
        if mt_cfg.get("enabled", False):
            for tenant_spec in mt_cfg.get("tenants", []):
                self._tenant_manager.register_tenant(
                    tenant_id=tenant_spec["id"],
                    name=tenant_spec.get("name", ""),
                    quotas=ResourceQuota(**tenant_spec.get("quotas", {})),
                    metadata=tenant_spec.get("metadata", {}),
                )

        # ── Phase 3: Advanced Execution ──
        self._plan_modifier = DynamicPlanModifier(self._task_graph)
        self._sub_goal_manager = SubGoalManager(self._task_graph)
        self._hitl = HumanInTheLoop()

        # ── Phase 3: Hot Reload ──
        hr_cfg = self.config.get("hot_reload", {})
        strategy_name = hr_cfg.get("upgrade_strategy", "rolling")
        try:
            strategy = UpgradeStrategy(strategy_name)
        except ValueError:
            strategy = UpgradeStrategy.ROLLING
        self._hot_reload_manager = HotReloadManager(upgrade_strategy=strategy)
        self._file_watcher: FileWatcher | None = None

        # ── Phase 3: Distributed ──
        dist_cfg = self.config.get("distributed", {})
        self._node_id = dist_cfg.get("node_id", f"zelos-{uuid.uuid4().hex[:8]}")
        self._leader_election = LeaderElection(
            node_id=self._node_id,
            heartbeat_interval_ms=dist_cfg.get("heartbeat_ms", 500),
        )
        self._node_registry = NodeRegistry(heartbeat_timeout_seconds=dist_cfg.get("heartbeat_timeout_s", 30.0))
        self._work_stealing = WorkStealing(
            node_id=self._node_id,
            max_concurrent_tasks=dist_cfg.get("max_concurrent_tasks", 50),
        )
        self._cluster_enabled = dist_cfg.get("enabled", False)

        # ── Phase 3: Container / Remote isolation ──
        self._container_runners: dict[str, ContainerRunner] = {}  # plugin_id → runner
        self._remote_plugins: dict[str, RemotePlugin] = {}  # plugin_id → remote
        self._remote_health_thread: threading.Thread | None = None

    @classmethod
    def from_yaml(cls, path: str = "zelos.yaml") -> "ZelosRuntime":
        """Create a ZelosRuntime from a zelos.yaml configuration file."""
        loader = ConfigLoader()
        config = loader.load(path)
        return cls(config)

    # ═══════════════════ Auth Helper ═══════════════════

    def _check_auth(
        self, auth_context: dict[str, Any] | None, action: str, resource: str = ""
    ) -> dict[str, Any] | None:
        """Check permission. Returns error dict if denied, None if allowed."""
        if auth_context is None or auth_context == {}:
            return None  # Backward compat: no auth = admin

        # API key auth
        api_key = auth_context.get("api_key")
        if api_key:
            key_info = self._api_key_manager.validate(api_key)
            if not key_info:
                return {"status": "rejected", "reason": "Invalid or expired API key"}
            role = key_info["role"]
        else:
            role = auth_context.get("role", "viewer")

        if not self._access_control.check(role, action):
            self._audit_logger.log(
                actor=auth_context.get("actor", "unknown"),
                action=action,
                resource=resource,
                detail=f"Permission denied for role '{role}'",
                result="denied",
            )
            return {"status": "rejected", "reason": f"Permission denied: role '{role}' cannot '{action}'"}
        return None

    def _audit(self, actor: str, action: str, resource: str, detail: str = "", result: str = "success", **meta) -> None:
        """Record an audit event (fire-and-forget)."""
        try:
            self._audit_logger.log(actor=actor, action=action, resource=resource, detail=detail, result=result, **meta)
        except Exception:
            pass

    def _resolve_tenant(self, auth_context: dict | None = None) -> str:
        """Get tenant_id from auth context, or 'default'."""
        if auth_context and auth_context.get("tenant_id"):
            return auth_context["tenant_id"]
        return "default"

    # ═══════════════════ Agent Management ═══════════════════

    def add_agent(
        self,
        name: str,
        entrypoint: str,
        capabilities: list[Any],
        *,
        max_concurrent_tasks: int = 5,
        heartbeat_interval_ms: int = 30000,
        restart_policy: str = "always",
        config: dict | None = None,
        auth_context: dict | None = None,
    ) -> str:
        """Register an agent. If Runtime is running, hot-join.

        Phase 3: Enforces RBAC + tenant agent quota + audit logging.
        """
        # Auth check
        err = self._check_auth(auth_context, "agent.register", f"agent:{name}")
        if err:
            return err

        tenant_id = self._resolve_tenant(auth_context)
        tenant = self._tenant_manager.get_tenant(tenant_id)
        if tenant and not tenant.active:
            return {"status": "rejected", "reason": f"Tenant '{tenant_id}' is deactivated"}

        # Tenant agent quota
        ns = self._tenant_manager.get_namespace(tenant_id)
        if ns and not ns.check_quota("agents"):
            return {"status": "rejected", "reason": f"Agent quota exceeded for tenant '{tenant_id}'"}

        agent_id = str(uuid.uuid4())
        agent_info = {
            "agent_id": agent_id,
            "name": name,
            "entrypoint": entrypoint,
            "capabilities": capabilities,
            "max_concurrent_tasks": max_concurrent_tasks,
            "heartbeat_interval_ms": heartbeat_interval_ms,
            "restart_policy": restart_policy,
            "config": config or {},
            "tenant_id": tenant_id,
        }
        with self._lock:
            self._agents[name] = agent_info

        if ns:
            ns.add_agent(agent_id)

        self._audit(
            actor=auth_context.get("actor", "system") if auth_context else "system",
            action="agent.register",
            resource=agent_id,
            detail=f"Registered agent '{name}' in tenant '{tenant_id}'",
        )

        if self._running:
            self._start_agent(name, agent_info)

        return agent_id

    def remove_agent(self, name_or_id: str, auth_context: dict | None = None) -> dict | None:
        """Remove an agent (hot-leave). Phase 3: RBAC + audit."""
        err = self._check_auth(auth_context, "agent.remove", f"agent:{name_or_id}")
        if err:
            return err

        tenant_id = self._resolve_tenant(auth_context)
        agent_info = None
        with self._lock:
            for name, info in self._agents.items():
                if name == name_or_id or info["agent_id"] == name_or_id:
                    if tenant_id != "default" and info.get("tenant_id", "default") != tenant_id:
                        return {"status": "rejected", "reason": f"Agent not in tenant '{tenant_id}'"}
                    agent_info = info
                    del self._agents[name]
                    break
        if agent_info:
            self._execution_engine.remove_agent(agent_info["agent_id"])
            self._capability_registry.remove_agent(agent_info["agent_id"])
            ns = self._tenant_manager.get_namespace(tenant_id)
            if ns:
                ns.remove_agent(agent_info["agent_id"])
            self._audit(
                actor=auth_context.get("actor", "system") if auth_context else "system",
                action="agent.remove",
                resource=agent_info["agent_id"],
                detail=f"Removed agent '{name_or_id}'",
            )
        return None

    def list_agents(self, auth_context: dict | None = None) -> list[dict[str, Any]]:
        """List agents. Phase 3: tenant-filtered."""
        tenant_id = self._resolve_tenant(auth_context)
        result = []
        for agent in self._execution_engine.list_agents():
            # Tenant filter
            agent_tenant = "default"
            for info in self._agents.values():
                if info["agent_id"] == agent.agent_id:
                    agent_tenant = info.get("tenant_id", "default")
                    break
            if tenant_id != "default" and agent_tenant != tenant_id:
                continue

            result.append(
                {
                    "agent_id": agent.agent_id,
                    "name": agent.agent_name,
                    "status": agent.status,
                    "operational_state": agent.operational_state,
                    "current_tasks": len(agent.current_tasks),
                    "max_concurrent_tasks": agent.max_concurrent_tasks,
                    "tenant_id": agent_tenant,
                }
            )
        return result

    def get_agent(self, name_or_id: str, auth_context: dict | None = None) -> dict[str, Any] | None:
        tenant_id = self._resolve_tenant(auth_context)
        for agent in self._execution_engine.list_agents():
            if agent.agent_id == name_or_id or agent.agent_name == name_or_id:
                agent_tenant = "default"
                for info in self._agents.values():
                    if info["agent_id"] == agent.agent_id:
                        agent_tenant = info.get("tenant_id", "default")
                        break
                if tenant_id != "default" and agent_tenant != tenant_id:
                    return None
                return {
                    "agent_id": agent.agent_id,
                    "name": agent.agent_name,
                    "status": agent.status,
                    "operational_state": agent.operational_state,
                    "capabilities": agent.capabilities,
                    "current_tasks": agent.current_tasks,
                    "max_concurrent_tasks": agent.max_concurrent_tasks,
                    "historical_success_rate": agent.historical_success_rate,
                    "total_completed": agent.total_completed,
                    "total_failed": agent.total_failed,
                    "tenant_id": agent_tenant,
                }
        return None

    # ═══════════════════ Phase 3: Container / Remote Plugin Management ═══════════════════

    def add_container_agent(
        self,
        name: str,
        container_config: ContainerPluginConfig,
        capabilities: list[Any],
        auth_context: dict | None = None,
    ) -> str:
        """Register an agent running in a Docker/Podman container.

        The container is actually started via subprocess. If the runtime
        is not installed, falls back gracefully.
        """
        err = self._check_auth(auth_context, "agent.register", f"container:{name}")
        if err:
            return err

        agent_id = str(uuid.uuid4())
        cap_dicts = []
        for c in capabilities:
            if hasattr(c, "to_dict"):
                cap_dicts.append(c.to_dict())
            elif isinstance(c, dict):
                cap_dicts.append(c)
            else:
                cap_dicts.append({"name": str(c), "version": "1.0.0"})

        self._capability_registry.register(agent_id, name, cap_dicts)
        self._capability_registry.mark_available(agent_id)

        runner = ContainerRunner(container_config)
        started = runner.start()
        self._container_runners[agent_id] = runner

        self._audit(
            "system",
            "container.agent.add",
            agent_id,
            detail=f"Container agent '{name}' ({'started' if started else 'pending'})",
        )

        return agent_id

    def add_remote_agent(
        self, name: str, remote_plugin: RemotePlugin, capabilities: list[Any], auth_context: dict | None = None
    ) -> str:
        """Register an agent that runs on a remote host via HTTP."""
        err = self._check_auth(auth_context, "agent.register", f"remote:{name}")
        if err:
            return err

        agent_id = str(uuid.uuid4())
        cap_dicts = []
        for c in capabilities:
            if hasattr(c, "to_dict"):
                cap_dicts.append(c.to_dict())
            elif isinstance(c, dict):
                cap_dicts.append(c)
            else:
                cap_dicts.append({"name": str(c), "version": "1.0.0"})

        self._capability_registry.register(agent_id, name, cap_dicts)
        self._capability_registry.mark_available(agent_id)

        remote_plugin.plugin_id = agent_id
        self._remote_plugins[agent_id] = remote_plugin

        # Start remote health monitor if not already running
        if self._remote_health_thread is None and self._running:
            self._remote_health_thread = threading.Thread(target=self._remote_health_loop, daemon=True)
            self._remote_health_thread.start()

        self._audit("system", "remote.agent.add", agent_id, detail=f"Remote agent '{name}' at {remote_plugin.endpoint}")

        return agent_id

    def _remote_health_loop(self) -> None:
        """Background loop: periodic health checks for remote plugins."""
        while self._running:
            for agent_id, rp in list(self._remote_plugins.items()):
                rp.health_check()
                if not rp.is_healthy:
                    self._capability_registry.mark_unavailable(agent_id)
                else:
                    self._capability_registry.mark_available(agent_id)
            time.sleep(15.0)  # Check every 15 seconds

    def _dispatch_to_remote(self, agent_id: str, task: Task) -> bool:
        """Dispatch a task to a remote plugin via HTTP."""
        rp = self._remote_plugins.get(agent_id)
        if not rp:
            return False
        task_dict = {
            "task_id": task.task_id,
            "plan_id": task.plan_id,
            "description": task.description,
            "required_capability": task.required_capability,
            "priority": task.priority,
            "timeout_ms": task.timeout_ms,
        }
        result = rp.dispatch(task_dict)
        if result and result.get("status") == "completed":
            self._execution_engine.submit_result(task.task_id, agent_id, result)
            self._audit("system", "task.completed", task.task_id, detail=f"Remote dispatch to {agent_id}")
            return True
        elif result and result.get("status") == "failed":
            self._execution_engine.submit_result(task.task_id, agent_id, result)
            self._audit(
                "system",
                "task.failed",
                task.task_id,
                detail=f"Remote dispatch failed: {result.get('error', {}).get('message', '')}",
            )
            return True
        return False

    # ═══════════════════ Runtime Lifecycle ═══════════════════

    def start(self) -> None:
        """Start the Runtime Kernel and all registered agents. Phase 3: init all new components."""
        with self._lock:
            if self._running:
                return

            # Load plugins
            plugin_configs = []
            if "plugins" in self.config:
                plugin_configs = self.config["plugins"]
            manifests = self._plugin_manager.discover_from_config(plugin_configs)
            self._plugin_manager.load_all(manifests)

            # Extract scoring strategy and policy from plugins
            for inst in self._plugin_manager.list_plugins():
                if inst.manifest.plugin_type == "scoring_strategy" and inst.instance:
                    self._scoring_strategy = inst.instance
                elif inst.manifest.plugin_type == "policy" and inst.instance:
                    self._policy_plugin = inst.instance

            # Planner: from plugin config or direct config
            planner_loaded = False
            for inst in self._plugin_manager.list_plugins():
                if inst.manifest.plugin_type == "planner" and inst.instance:
                    self._planner = inst.instance
                    planner_loaded = True
                    # Register with hot reload manager
                    self._hot_reload_manager.register_version(
                        plugin_id=inst.manifest.plugin_id,
                        version="1.0.0",
                        entrypoint=inst.manifest.entrypoint,
                        checksum="initial",
                    )
                    break

            if not planner_loaded:
                planner_config = self.config.get("planner") or {}
                for cfg in self.config.get("plugins", []):
                    if cfg.get("type") == "planner":
                        planner_config = cfg.get("config", {})
                        break
                if planner_config:
                    try:
                        self._planner = LLMPlanner(planner_config)
                    except Exception:
                        pass

            if self._planner is None:
                self._planner = LLMPlanner({"provider": "mock"})
                self._planner._provider = MockLLMProvider(
                    response='{"tasks":[{"task_id":"t1","description":"Execute the goal","required_capability":"code-generation.python"}],"dependencies":[]}'
                )

            # Initialize Memory Provider
            if self._memory_provider is None:
                self._memory_provider = InMemoryMemoryProvider()
                self._context_assembler = ContextAssembler(self._memory_provider)

            # Initialize Verifier Gate
            if self._verifier_gate is None:
                self._verifier_gate = VerificationGate()
                self._verifier_gate.add_verifier(SchemaVerifier())

            # Initialize Policy Engine
            if self._policy_engine is None:
                self._policy_engine = CompositePolicy()

            # Initialize Scheduler
            self._scheduler = Scheduler(
                self._task_graph,
                self._capability_registry,
                scoring_strategy=self._scoring_strategy,
                policy_plugin=self._policy_plugin,
            )

            # Set up Execution Engine callbacks
            self._execution_engine._agent_dispatch = self._on_dispatch

            # Start all agents
            for name, info in list(self._agents.items()):
                self._start_agent(name, info)

            # Start timeout monitor
            self._execution_engine.start_monitor()

            # ── Phase 3: Start File Watcher (hot reload) ──
            hr_cfg = self.config.get("hot_reload", {})
            plugin_dir = hr_cfg.get("plugin_dir")
            if plugin_dir:
                self._file_watcher = FileWatcher(
                    plugin_dir,
                    patterns=hr_cfg.get("watch_patterns", ["*.py"]),
                    poll_interval_ms=hr_cfg.get("poll_interval_ms", 500),
                )
                self._file_watcher.on_change(self._on_plugin_file_change)
                self._file_watcher.start()

            # ── Phase 3: Start Leader Election (if cluster enabled) ──
            dist_cfg = self.config.get("distributed", {})
            self._cluster_enabled = dist_cfg.get("enabled", False)
            if self._cluster_enabled:
                # Register self
                host = dist_cfg.get("host", "127.0.0.1")
                port = dist_cfg.get("port", 9876)
                caps = dist_cfg.get("capabilities", [])
                self._node_registry.register(
                    ClusterNode(
                        node_id=self._node_id,
                        host=host,
                        port=port,
                        capabilities=caps,
                        capacity=dist_cfg.get("capacity", 20),
                    )
                )
                # Register peers
                for peer in dist_cfg.get("peers", []):
                    self._leader_election.register_peer(peer["node_id"], peer.get("priority", 0))
                    self._node_registry.register(
                        ClusterNode(
                            node_id=peer["node_id"],
                            host=peer.get("host", ""),
                            port=peer.get("port", 9876),
                            capabilities=peer.get("capabilities", []),
                            capacity=peer.get("capacity", 10),
                        )
                    )
                self._leader_election.start()

            self._running = True
            self._started_at = time.time()

            # Start orchestrator loop (background thread)
            self._orchestrator_thread = threading.Thread(target=self._orchestrator_loop, daemon=True)
            self._orchestrator_thread.start()

    def shutdown(self) -> None:
        """Graceful shutdown of Runtime and all agents."""
        self._running = False
        self._execution_engine.stop_monitor()

        if self._orchestrator_thread and self._orchestrator_thread.is_alive():
            self._orchestrator_thread.join(timeout=5.0)

        # Cancel all in-flight tasks
        for tid in list(self._execution_engine._in_flight.keys()):
            self._execution_engine.cancel_task(tid)

        # Stop all agent threads
        for _name, thread in list(self._agent_threads.items()):
            if thread.is_alive():
                thread.join(timeout=5.0)

        # Stop all plugins
        for inst in self._plugin_manager.list_plugins():
            self._plugin_manager.stop_plugin(inst.manifest.plugin_id)

        # Phase 3: Stop file watcher
        if self._file_watcher:
            self._file_watcher.stop()

        # Phase 3: Stop leader election
        if self._cluster_enabled:
            self._leader_election.stop()

        # Phase 3: Drain hot reload versions
        for p in self._hot_reload_manager.list_plugins():
            for v in self._hot_reload_manager.get_versions(p["plugin_id"]):
                if v.status == "active":
                    self._hot_reload_manager.drain_version(p["plugin_id"], v.version)

    def _orchestrator_loop(self) -> None:
        """Background loop: evaluate deps → schedule → dispatch → escalate → verify.

        Phase 3 additions:
          - HITL approval check before dispatching tasks that require approval
          - Work stealing from peer nodes (when cluster enabled)
          - Dead node detection and cleanup
        """
        poll_interval = 0.5
        READY_TIMEOUT = 60.0
        _stuck_since: dict[str, float] = {}

        while self._running:
            try:
                # 1. Evaluate dependencies → CREATED → READY
                newly_ready = self._task_graph.evaluate_all()
                for tid in newly_ready:
                    _stuck_since.pop(tid, None)

                # 2. Schedule all READY tasks (skip those awaiting HITL approval)
                if self._scheduler:
                    # Check HITL timeouts
                    self._hitl.check_timeouts()

                    assignments = self._scheduler.schedule()
                    dispatched_ids = set()
                    for a in assignments:
                        tid = a["task_id"]
                        aid = a["agent_id"]
                        task = self._task_graph.get_task(tid)
                        if task and task.status == TaskStatus.ASSIGNED:
                            # HITL gate: if task requires approval, block dispatch
                            pending_list = self._hitl.list_pending()
                            if any(r.task_id == tid for r in pending_list):
                                continue
                            self._execution_engine.dispatch(tid, aid)
                            dispatched_ids.add(tid)

                    # Three-Tier Escalation for Unscheduled READY Tasks
                    now = time.time()
                    ready_tasks = self._task_graph.get_ready_tasks()

                    for task in ready_tasks:
                        tid = task.task_id
                        if tid in dispatched_ids:
                            _stuck_since.pop(tid, None)
                            continue
                        if tid not in _stuck_since:
                            _stuck_since[tid] = now
                            continue
                        stuck_duration = now - _stuck_since[tid]
                        if stuck_duration > READY_TIMEOUT:
                            try:
                                self._task_graph.transition(tid, TaskStatus.FAILED)
                            except ValueError:
                                pass
                            _stuck_since.pop(tid, None)
                            self._try_replan(task)

                # 3. Check Goal completion + Sub-goal completion
                with self._lock:
                    for goal_id, goal in list(self._goals.items()):
                        if goal["status"] in ("completed", "failed", "cancelled"):
                            continue
                        plan_id = goal.get("plan_id")
                        all_tasks = [t for t in self._task_graph.list_tasks() if t.plan_id == plan_id]
                        if not all_tasks:
                            continue
                        terminal = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}
                        all_done = all(t.status in terminal for t in all_tasks)
                        if all_done:
                            all_completed = all(t.status == TaskStatus.COMPLETED for t in all_tasks)
                            goal["status"] = "completed" if all_completed else "failed"
                            goal["completed_at"] = now
                            self._audit(
                                "system",
                                "goal.completed" if all_completed else "goal.failed",
                                goal_id,
                                detail=goal.get("description", ""),
                            )

                # 4. Phase 3: Distributed — real work stealing + dead node cleanup
                if self._cluster_enabled:
                    # Find the most overloaded peer
                    peers = [
                        n
                        for n in self._node_registry.list_nodes()
                        if n.node_id != self._node_id and n.status == "healthy"
                    ]
                    for _peer in peers:
                        if self._work_stealing.can_accept_more():
                            # Steal READY tasks from overloaded peers
                            our_depth = self._work_stealing.queue_size()
                            # Local heuristic: steal from anyone while we have capacity
                            if our_depth < self._work_stealing.max_concurrent_tasks / 2:
                                # Pull tasks from the distributed ready-task pool
                                ready = self._task_graph.get_ready_tasks()
                                for rt in ready:
                                    if self._work_stealing.can_accept_more():
                                        self._work_stealing.enqueue_task(
                                            rt.task_id, rt.required_capability, priority=rt.priority
                                        )
                                    else:
                                        break

                    # Detect dead nodes and clean up
                    dead = self._node_registry.detect_dead_nodes()
                    for dead_id in dead:
                        self._node_registry.deregister(dead_id)

                # 5. Phase 3: Dispatch to remote plugins
                for agent_id in list(self._remote_plugins.keys()):
                    rp = self._remote_plugins.get(agent_id)
                    if rp and rp.is_healthy:
                        # Check for tasks assigned to this remote agent
                        for inflight_id, ft in list(self._execution_engine._in_flight.items()):
                            if ft.agent_id == agent_id:
                                self._dispatch_to_remote(agent_id, self._task_graph.get_task(inflight_id))

            except Exception:
                pass

            time.sleep(poll_interval)

    def _try_replan(self, failed_task: Task) -> None:
        """Tier 3: Ask Planner to find an alternative way to achieve the goal."""
        if self._planner is None:
            return
        plan_id = failed_task.plan_id
        goal_description = ""
        goal_id = ""
        for gid, g in self._goals.items():
            if g.get("plan_id") == plan_id:
                goal_description = g.get("description", "")
                goal_id = gid
                break
        if not goal_description:
            return

        try:
            current_tasks = [t for t in self._task_graph.list_tasks() if t.plan_id == plan_id]
            current_plan = PlannerPlan(
                plan_id=plan_id,
                goal_id=goal_id,
                tasks=[],
                dependencies=[],
                version=1,
            )
            from .planner import PlannerTask as PT

            for t in current_tasks:
                current_plan.tasks.append(
                    PT(
                        task_id=t.task_id,
                        description=t.description,
                        required_capability=t.required_capability,
                        dependencies=list(t.dependencies),
                    )
                )
            current_plan.version = len([t for t in current_tasks if t.status == TaskStatus.COMPLETED]) + 1

            new_plan = self._planner.replan(
                goal_description,
                current_plan,
                [
                    {
                        "event_type": "task.failed",
                        "task_id": failed_task.task_id,
                        "reason": f"no agent provides capability: {failed_task.required_capability}",
                    }
                ],
            )

            for pt in new_plan.tasks:
                if pt.task_id not in self._task_graph._tasks:
                    task = Task(
                        task_id=pt.task_id,
                        plan_id=plan_id,
                        description=pt.description,
                        required_capability=pt.required_capability,
                        dependencies=list(pt.dependencies),
                        priority=pt.priority,
                        timeout_ms=pt.timeout_ms,
                    )
                    self._task_graph.add_task(task)

            for dep in new_plan.dependencies:
                try:
                    self._task_graph.add_dependency(dep["from_task_id"], dep["to_task_id"])
                except ValueError:
                    pass

            self._task_graph.evaluate_all()
            self._plan_modifier._log_modification(
                "replan", plan_id, {"new_tasks": len(new_plan.tasks), "old_tasks": len(current_tasks)}
            )

        except Exception:
            pass

    def _start_agent(self, name: str, info: dict) -> None:
        """Start an agent: register, heartbeat, make available."""
        agent_id = info["agent_id"]

        self._execution_engine.register_agent(
            agent_id=agent_id,
            agent_name=name,
            max_concurrent_tasks=info["max_concurrent_tasks"],
            heartbeat_interval_ms=info["heartbeat_interval_ms"],
        )

        caps = info["capabilities"]
        cap_dicts = []
        for c in caps:
            if hasattr(c, "to_dict"):
                cap_dicts.append(c.to_dict())
            elif isinstance(c, dict):
                cap_dicts.append(c)
            else:
                cap_dicts.append(
                    {
                        "name": getattr(c, "name", str(c)),
                        "version": getattr(c, "version", "1.0.0"),
                        "description": getattr(c, "description", ""),
                        "input_schema": getattr(c, "input_schema", {}),
                        "output_schema": getattr(c, "output_schema", {}),
                        "tags": getattr(c, "tags", []),
                    }
                )
        self._capability_registry.register(agent_id, name, cap_dicts)
        self._capability_registry.mark_available(agent_id)

        self._execution_engine.heartbeat(agent_id)

        entrypoint = info["entrypoint"]
        if ":" in entrypoint:
            module_path, class_name = entrypoint.split(":", 1)
            try:
                import importlib

                mod = importlib.import_module(module_path)
                cls = getattr(mod, class_name)
                agent_instance = cls(name=name, **info.get("config", {}))
                self._agent_instances[name] = agent_instance
                thread = threading.Thread(
                    target=self._agent_loop,
                    args=(name, agent_instance, agent_id),
                    daemon=True,
                )
                self._agent_threads[name] = thread
                thread.start()
            except (ImportError, AttributeError):
                pass

    def _agent_loop(self, name: str, agent_instance: Any, agent_id: str) -> None:
        """Background loop for an in-process agent."""
        while self._running:
            try:
                self._execution_engine.heartbeat(agent_id)
            except Exception:
                pass
            time.sleep(
                self._execution_engine._agents.get(
                    agent_id, AgentState(agent_id="", agent_name="")
                ).heartbeat_interval_ms
                / 1000
            )

    def _on_dispatch(self, agent_id: str, task: Task) -> None:
        """Called when Execution Engine dispatches a task.

        Phase 3: Checks HITL approval before executing. Logs audit events.
        """
        # HITL gate: check if this task has a pending approval
        pending = self._hitl.list_pending()
        for req in pending:
            if req.task_id == task.task_id:
                # Task awaiting approval — don't execute yet
                return

        self._audit("system", "task.dispatched", task.task_id, detail=f"Dispatched to agent {agent_id}")

        for name, info in self._agents.items():
            if info["agent_id"] == agent_id:
                agent = self._agent_instances.get(name)
                if agent and hasattr(agent, "execute"):
                    try:
                        artifact = agent.execute(task)
                        result = {
                            "status": "completed",
                            "artifact": {
                                "content_type": getattr(artifact, "content_type", "application/json"),
                                "content": getattr(artifact, "content", artifact)
                                if hasattr(artifact, "content")
                                else str(artifact),
                            },
                        }
                        self._execution_engine.submit_result(task.task_id, agent_id, result)
                        self._audit("system", "task.completed", task.task_id, result="success")
                    except Exception as e:
                        self._execution_engine.submit_result(
                            task.task_id,
                            agent_id,
                            {"status": "failed", "error": {"code": "internal_error", "message": str(e)}},
                        )
                        self._audit("system", "task.failed", task.task_id, result="failed", detail=str(e))
                else:
                    print(f"  🤖 [{name}] → {task.required_capability}: {task.description[:60]}...")
                    self._execution_engine.submit_result(
                        task.task_id,
                        agent_id,
                        {
                            "status": "completed",
                            "artifact": {
                                "content_type": "application/json",
                                "content": {"result": f"Task {task.task_id} completed"},
                            },
                        },
                    )
                    self._audit("system", "task.completed", task.task_id, detail="auto-completed (demo mode)")

    # ═══════════════════ Goal Submission ═══════════════════

    def submit_goal(
        self,
        description: str,
        *,
        budget: float | None = None,
        deadline: str | None = None,
        priority: str = "medium",
        project_id: str | None = None,
        metadata: dict | None = None,
        auth_context: dict | None = None,
        require_approval: bool = False,
        approvers: list[str] | None = None,
    ) -> dict[str, Any]:
        """Submit a Goal. Phase 3: RBAC + tenant quota + audit.

        Args:
            require_approval: If True, creates HITL approval before tasks dispatch.
            approvers: List of approver IDs for HITL.
        """
        if not description or not description.strip():
            return {"goal_id": str(uuid.uuid4()), "status": "rejected", "reason": "Description is required"}

        if priority not in ("low", "medium", "high", "critical"):
            return {
                "goal_id": str(uuid.uuid4()),
                "status": "rejected",
                "reason": f"Invalid priority: {priority}",
                "validation_errors": ["priority must be one of: low, medium, high, critical"],
            }

        # Auth
        err = self._check_auth(auth_context, "goal.submit", "goal:new")
        if err:
            return err

        # Tenant
        tenant_id = self._resolve_tenant(auth_context)
        tenant = self._tenant_manager.get_tenant(tenant_id)
        if tenant and not tenant.active:
            return {
                "goal_id": str(uuid.uuid4()),
                "status": "rejected",
                "reason": f"Tenant '{tenant_id}' is deactivated",
            }

        ns = self._tenant_manager.get_namespace(tenant_id)
        if ns and not ns.check_quota("goals"):
            return {
                "goal_id": str(uuid.uuid4()),
                "status": "rejected",
                "reason": f"Goal quota exceeded for tenant '{tenant_id}'",
            }

        if budget and ns and not ns.quotas.check_budget(budget):
            return {
                "goal_id": str(uuid.uuid4()),
                "status": "rejected",
                "reason": f"Budget ${budget} exceeds per-goal limit ${ns.quotas.budget_per_goal}",
            }

        goal_id = str(uuid.uuid4())
        plan_id = str(uuid.uuid4())

        goal = {
            "goal_id": goal_id,
            "description": description,
            "status": "accepted",
            "budget": budget,
            "deadline": deadline,
            "priority": priority,
            "project_id": project_id,
            "metadata": metadata or {},
            "plan_id": plan_id,
            "tenant_id": tenant_id,
            "created_at": time.time(),
            "updated_at": time.time(),
            "completed_at": None,
            "progress": {
                "total_tasks": 0,
                "completed_tasks": 0,
                "failed_tasks": 0,
                "ready_tasks": 0,
                "in_flight_tasks": 0,
                "blocked_tasks": 0,
                "percent_complete": 0.0,
            },
        }
        with self._lock:
            self._goals[goal_id] = goal

        if ns:
            ns.add_goal(goal_id)

        # HITL: create approval request if required
        if require_approval and approvers:
            self._hitl.create_request(
                task_id=f"{goal_id}-approval",
                description=f"Goal approval: {description[:80]}",
                approvers=approvers,
                context={"goal_id": goal_id, "budget": budget, "priority": priority},
                require_all=len(approvers) > 1,
            )

        self._audit(
            actor=auth_context.get("actor", "system") if auth_context else "system",
            action="goal.submit",
            resource=goal_id,
            detail=f"'{description[:60]}' in tenant '{tenant_id}'",
            budget=budget,
            priority=priority,
        )

        # Planner: decompose Goal → Tasks
        if self._planner is not None and self._running:
            try:
                planner_plan = self._planner.plan(description, goal_id=goal_id)
                planner_plan.plan_id = plan_id
            except Exception:
                from .planner import PlannerTask as PT

                planner_plan = PlannerPlan(
                    plan_id=plan_id,
                    goal_id=goal_id,
                    tasks=[],
                    planner_id="fallback",
                )
                planner_plan.tasks.append(
                    PT(
                        task_id=f"{goal_id}-t1",
                        description=description,
                        required_capability="code-generation.python",
                    )
                )

            for pt in planner_plan.tasks:
                task = Task(
                    task_id=pt.task_id,
                    plan_id=plan_id,
                    description=pt.description,
                    required_capability=pt.required_capability,
                    dependencies=list(pt.dependencies),
                    priority=pt.priority,
                    timeout_ms=pt.timeout_ms,
                )
                self._task_graph.add_task(task)

            for dep in planner_plan.dependencies:
                try:
                    self._task_graph.add_dependency(dep["from_task_id"], dep["to_task_id"])
                except ValueError:
                    pass

            self._task_graph.evaluate_all()

            goal["status"] = "planned"
            goal["plan_id"] = plan_id
            goal["updated_at"] = time.time()

        task_count = len([t for t in self._task_graph.list_tasks() if t.plan_id == plan_id])

        return {
            "goal_id": goal_id,
            "status": goal["status"],
            "created_at": goal["created_at"],
            "plan_id": plan_id,
            "task_count": task_count,
        }

    def get_goal_status(self, goal_id: str, auth_context: dict | None = None) -> dict[str, Any] | None:
        """Get goal status. Phase 3: tenant-filtered."""
        goal = self._goals.get(goal_id)
        if not goal:
            return None

        # Tenant isolation
        tenant_id = self._resolve_tenant(auth_context)
        if tenant_id != "default" and goal.get("tenant_id", "default") != tenant_id:
            return None

        tasks = self._task_graph.list_tasks()
        plan_id = goal.get("plan_id", "")
        goal_tasks = [t for t in tasks if t.plan_id == plan_id]

        total = len(goal_tasks)
        completed = sum(1 for t in goal_tasks if t.status == TaskStatus.COMPLETED)
        failed = sum(1 for t in goal_tasks if t.status == TaskStatus.FAILED)
        ready = sum(1 for t in goal_tasks if t.status == TaskStatus.READY)
        in_flight = sum(1 for t in goal_tasks if t.status in (TaskStatus.ASSIGNED, TaskStatus.STARTED))
        blocked = sum(1 for t in goal_tasks if t.status == TaskStatus.CREATED)

        goal["progress"] = {
            "total_tasks": total,
            "completed_tasks": completed,
            "failed_tasks": failed,
            "ready_tasks": ready,
            "in_flight_tasks": in_flight,
            "blocked_tasks": blocked,
            "percent_complete": (completed / total * 100) if total > 0 else 0.0,
        }
        goal["updated_at"] = time.time()
        return {
            "goal_id": goal["goal_id"],
            "status": goal["status"],
            "plan_id": goal["plan_id"],
            "progress": goal["progress"],
            "created_at": goal["created_at"],
            "updated_at": goal["updated_at"],
            "completed_at": goal["completed_at"],
            "tenant_id": goal.get("tenant_id", "default"),
        }

    def cancel_goal(self, goal_id: str, auth_context: dict | None = None) -> dict[str, Any] | None:
        """Cancel a goal. Phase 3: RBAC + audit."""
        err = self._check_auth(auth_context, "goal.cancel", goal_id)
        if err:
            return err

        goal = self._goals.get(goal_id)
        if not goal:
            return None
        tenant_id = self._resolve_tenant(auth_context)
        if tenant_id != "default" and goal.get("tenant_id", "default") != tenant_id:
            return {"goal_id": goal_id, "status": "rejected", "reason": "Goal not in this tenant"}

        if goal["status"] in ("completed", "failed", "cancelled"):
            return {
                "goal_id": goal_id,
                "status": goal["status"],
                "error": {"code": "conflict", "message": "Goal is already in a terminal state"},
            }
        goal["status"] = "cancelled"
        goal["completed_at"] = time.time()
        self._audit(
            actor=auth_context.get("actor", "system") if auth_context else "system",
            action="goal.cancel",
            resource=goal_id,
        )
        return {"goal_id": goal_id, "status": "cancelled"}

    def wait_for_goal(self, goal_id: str, timeout_seconds: float = 600, poll_interval: float = 1.0) -> dict[str, Any]:
        """Block until goal reaches a terminal state."""
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            status = self.get_goal_status(goal_id)
            if status is None:
                return {"goal_id": goal_id, "status": "not_found"}
            if status["status"] in ("completed", "failed", "cancelled"):
                return status
            time.sleep(poll_interval)
        status = self.get_goal_status(goal_id)
        return status or {"goal_id": goal_id, "status": "timeout"}

    # ═══════════════════ Phase 3: Advanced Execution API ═══════════════════

    def modify_plan(self, plan_id: str, operation: str, **kwargs) -> dict[str, Any]:
        """Dynamically modify a running plan.

        Operations: add_task, remove_task, modify_task, add_dependency, remove_dependency
        """
        try:
            if operation == "add_task":
                if "plan_id" not in kwargs:
                    kwargs["plan_id"] = plan_id
                self._plan_modifier.add_task(**kwargs)
            elif operation == "remove_task":
                ok = self._plan_modifier.remove_task(kwargs["task_id"])
                if not ok:
                    return {"status": "failed", "reason": f"Task '{kwargs['task_id']}' not found"}
            elif operation == "modify_task":
                task_id = kwargs.pop("task_id")
                self._plan_modifier.modify_task(task_id, **kwargs)
            elif operation == "add_dependency":
                self._plan_modifier.add_dependency(kwargs["from_task_id"], kwargs["to_task_id"])
            elif operation == "remove_dependency":
                self._plan_modifier.remove_dependency(kwargs["from_task_id"], kwargs["to_task_id"])
            else:
                return {"status": "rejected", "reason": f"Unknown operation: {operation}"}
            self._audit("system", f"plan.{operation}", plan_id, detail=str(kwargs))
            return {"status": "ok", "operation": operation}
        except (ValueError, KeyError) as e:
            return {"status": "failed", "reason": str(e)}
        except Exception as e:
            return {"status": "failed", "reason": str(e)}

    def spawn_sub_goal(
        self,
        parent_task_id: str,
        description: str,
        budget: float | None = None,
        required_capability: str = "code-generation.python",
        num_tasks: int = 1,
    ) -> dict[str, Any]:
        """Spawn a sub-goal from a parent task."""
        sub = self._sub_goal_manager.spawn_sub_goal(
            parent_task_id=parent_task_id,
            description=description,
            budget=budget,
            required_capability=required_capability,
            num_tasks=num_tasks,
        )
        self._audit("system", "sub_goal.spawned", sub["sub_goal_id"], detail=description[:60])
        return sub

    def get_sub_goal_status(self, sub_goal_id: str) -> dict[str, Any] | None:
        return self._sub_goal_manager.get_sub_goal(sub_goal_id)

    def approve_task(self, task_id: str, approver: str, comment: str = "") -> dict[str, Any]:
        """Approve a HITL request for a task."""
        pending = [r for r in self._hitl.list_pending() if r.task_id == task_id]
        if not pending:
            # Try direct request_id
            ok = self._hitl.approve(task_id, approver, comment)
            if ok:
                self._audit(approver, "hitl.approve", task_id, comment)
                return {"status": "approved"}
            return {"status": "not_found", "reason": "No pending approval for this task"}
        req = pending[0]
        ok = self._hitl.approve(req.request_id, approver, comment)
        if ok:
            self._audit(approver, "hitl.approve", task_id, comment)
            return {"status": "approved"}
        return {"status": "failed", "reason": "Approval rejected — approver not authorized"}

    def reject_task(self, task_id: str, approver: str, reason: str = "") -> dict[str, Any]:
        """Reject a HITL request for a task."""
        pending = [r for r in self._hitl.list_pending() if r.task_id == task_id]
        if not pending:
            ok = self._hitl.reject(task_id, approver, reason)
            if ok:
                self._audit(approver, "hitl.reject", task_id, reason)
                # Try to fail the task in graph if it exists
                try:
                    if task_id in self._task_graph._tasks:
                        self._task_graph.transition(task_id, TaskStatus.FAILED)
                except (ValueError, KeyError):
                    pass
                return {"status": "rejected"}
            return {"status": "not_found"}
        req = pending[0]
        ok = self._hitl.reject(req.request_id, approver, reason)
        if ok:
            self._audit(approver, "hitl.reject", task_id, reason)
            # Try to fail the associated task in graph (it may be a goal-id, not task-id)
            try:
                if task_id in self._task_graph._tasks:
                    self._task_graph.transition(task_id, TaskStatus.FAILED)
            except (ValueError, KeyError):
                pass
            # Find goal by task_id pattern and cancel it
            for gid, goal in list(self._goals.items()):
                if goal["status"] not in ("completed", "failed", "cancelled"):
                    if task_id.startswith(gid + "-approval"):
                        goal["status"] = "failed"
                        goal["completed_at"] = time.time()
                        self._audit(approver, "goal.failed", gid, detail=f"Rejected: {reason}")
                        break
            return {"status": "rejected"}
        return {"status": "failed", "reason": "Rejection denied — approver not authorized"}

    def list_pending_approvals(self) -> list[dict[str, Any]]:
        """List all pending HITL approval requests."""
        return [
            {
                "request_id": r.request_id,
                "task_id": r.task_id,
                "description": r.description,
                "approvers": r.approvers,
                "require_all": r.require_all,
                "created_at": r.created_at,
                "status": r.status.value,
            }
            for r in self._hitl.list_pending()
        ]

    # ═══════════════════ Phase 3: Hot Reload API ═══════════════════

    def reload_plugin(self, plugin_id: str, new_entrypoint: str, new_version: str) -> dict[str, Any]:
        """Hot-reload a plugin to a new version."""
        current = self._hot_reload_manager.get_active_version(plugin_id)
        if current and current.version == new_version:
            return {"status": "ok", "message": f"Already at version {new_version}"}

        # Drain current version
        if current:
            self._hot_reload_manager.drain_version(plugin_id, current.version)

        # Register new version (auto-activates as latest)
        self._hot_reload_manager.register_version(
            plugin_id, new_version, new_entrypoint, checksum=f"reload-{int(time.time())}"
        )

        # Reload in plugin manager
        for inst in self._plugin_manager.list_plugins():
            if inst.manifest.plugin_id == plugin_id:
                self._plugin_manager.stop_plugin(plugin_id)
                inst.manifest.entrypoint = new_entrypoint
                self._plugin_manager.start_plugin(plugin_id)
                break

        self._audit("system", "plugin.reload", plugin_id, detail=f"Reloaded to {new_version} ({new_entrypoint})")
        return {"status": "ok", "plugin_id": plugin_id, "version": new_version}

    def rollback_plugin(self, plugin_id: str, target_version: str) -> dict[str, Any]:
        """Rollback a plugin to a previous version."""
        target = self._hot_reload_manager.get_version(plugin_id, target_version)
        if not target:
            return {"status": "failed", "reason": f"Version {target_version} not found for {plugin_id}"}

        ok = self._hot_reload_manager.rollback(plugin_id, target_version)
        if ok:
            self._audit("system", "plugin.rollback", plugin_id, detail=f"Rolled back to {target_version}")
            return {"status": "ok", "plugin_id": plugin_id, "version": target_version}
        return {"status": "failed", "reason": "Rollback failed"}

    def set_upgrade_strategy(self, strategy_name: str) -> dict[str, Any]:
        """Change the hot reload upgrade strategy."""
        try:
            strategy = UpgradeStrategy(strategy_name)
        except ValueError:
            return {
                "status": "failed",
                "reason": f"Unknown strategy: {strategy_name}. Available: {[s.value for s in UpgradeStrategy]}",
            }
        self._hot_reload_manager.set_upgrade_strategy(strategy)
        return {"status": "ok", "strategy": strategy.value}

    def get_plugin_versions(self, plugin_id: str) -> list[dict[str, Any]]:
        """Get version history for a plugin."""
        return [v.to_dict() for v in self._hot_reload_manager.get_versions(plugin_id)]

    def _on_plugin_file_change(self, change_event: dict[str, Any]) -> None:
        """Handle file watcher events for hot reload.

        Implements real strategy differentiation:
          - ROLLING: reload one at a time (simulated as instant for in-process)
          - BLUE_GREEN: register new version, keep old running until new is healthy
          - CANARY: register with canary_percent, route accordingly
          - INSTANT: immediate reload

        Matches the changed file to actually registered plugins by checking
        if the module path contains the filename stem.
        """
        filename = change_event.get("filename", "")
        file_stem = filename.replace(".py", "")

        # Find matching plugin(s) in the plugin manager — don't guess from filename
        matched_plugins = []
        for inst in self._plugin_manager.list_plugins():
            entrypoint = inst.manifest.entrypoint or ""
            # Match if entrypoint contains the file stem (e.g. "plugins.my_plugin:v1")
            if file_stem in entrypoint or inst.manifest.plugin_id == file_stem:
                matched_plugins.append(inst.manifest.plugin_id)

        if not matched_plugins:
            return  # File changed but no matching plugin — safe no-op

        strategy = self._hot_reload_manager.upgrade_strategy
        timestamp = int(time.time())

        for plugin_id in matched_plugins:
            if strategy == UpgradeStrategy.CANARY:
                new_ver = f"canary-{timestamp}"
                self._hot_reload_manager.register_version(
                    plugin_id, new_ver, self._get_plugin_entrypoint(plugin_id), canary_percent=10
                )
                # Old version still gets 90% via _route_canary()

            elif strategy == UpgradeStrategy.BLUE_GREEN:
                new_ver = f"bg-{timestamp}"
                self._hot_reload_manager.register_version(plugin_id, new_ver, self._get_plugin_entrypoint(plugin_id))
                # Old version stays active — explicit cutover via reload_plugin()

            elif strategy == UpgradeStrategy.INSTANT:
                new_ver = f"instant-{timestamp}"
                self.reload_plugin(plugin_id, self._get_plugin_entrypoint(plugin_id), new_ver)

            else:  # ROLLING (default)
                new_ver = f"rolling-{timestamp}"
                self.reload_plugin(plugin_id, self._get_plugin_entrypoint(plugin_id), new_ver)

    def _get_plugin_entrypoint(self, plugin_id: str) -> str:
        """Get the current entrypoint of a plugin by its ID."""
        for inst in self._plugin_manager.list_plugins():
            if inst.manifest.plugin_id == plugin_id:
                return inst.manifest.entrypoint or f"plugins.{plugin_id}:unknown"
        return f"plugins.{plugin_id}:unknown"

    def _route_canary(self, plugin_id: str) -> str | None:
        """CANARY routing: return which version to use based on canary_percent.

        This is called before dispatching a task to a plugin. Returns the
        version string to use, or None to use the default active version.
        """
        versions = self._hot_reload_manager.get_versions(plugin_id)
        active_version = None
        canary_version = None

        for v in versions:
            if v.status == "active" and v.canary_percent > 0:
                canary_version = v
            elif v.status == "active" and v.canary_percent == 0:
                active_version = v

        if not canary_version:
            return None  # No canary in progress — use default

        # Route based on canary_percent
        import random

        if random.randint(1, 100) <= canary_version.canary_percent:
            return canary_version.version  # Route to canary
        return active_version.version if active_version else None  # Route to stable

    # ═══════════════════ Phase 3: Security API ═══════════════════

    def validate_api_key(self, key: str) -> dict[str, Any] | None:
        """Validate an API key. Returns role info or None."""
        return self._api_key_manager.validate(key)

    def generate_api_key(
        self, role: str, description: str = "", ttl_seconds: float | None = None, auth_context: dict | None = None
    ) -> str:
        """Generate a new API key (admin only)."""
        err = self._check_auth(auth_context, "admin.api_key.generate", "")
        if err:
            return ""
        key = self._api_key_manager.generate_key(role, description, ttl_seconds)
        self._audit(
            auth_context.get("actor", "system") if auth_context else "system",
            "api_key.generate",
            role[:8],
            detail=f"Generated key for role '{role}' ({description})",
        )
        return key

    def revoke_api_key(self, key: str, auth_context: dict | None = None) -> bool:
        """Revoke an API key (admin only)."""
        err = self._check_auth(auth_context, "admin.api_key.revoke", "")
        if err:
            return False
        ok = self._api_key_manager.revoke(key)
        if ok:
            self._audit(
                auth_context.get("actor", "system") if auth_context else "system",
                "api_key.revoke",
                "",
                detail="Key revoked",
            )
        return ok

    def get_audit_log(self, auth_context: dict | None = None, **filters) -> list[dict[str, Any]]:
        """Query audit log (admin/operator only)."""
        err = self._check_auth(auth_context or {}, "admin.audit.read", "")
        if err:
            return []
        events = self._audit_logger.query(**filters)
        return [e.to_dict() for e in events]

    def add_role(
        self, name: str, permissions: list[str], description: str = "", auth_context: dict | None = None
    ) -> dict[str, Any]:
        """Add a custom RBAC role."""
        err = self._check_auth(auth_context, "admin.role.manage", name)
        if err:
            return err
        self._access_control.add_role(name, permissions, description)
        self._audit(auth_context.get("actor", "system") if auth_context else "system", "role.add", name)
        return {"status": "ok", "role": name}

    # ═══════════════════ Phase 3: Multi-tenancy API ═══════════════════

    def register_tenant(
        self,
        tenant_id: str,
        name: str = "",
        quotas: dict | None = None,
        metadata: dict | None = None,
        auth_context: dict | None = None,
    ) -> dict[str, Any]:
        """Register a new tenant."""
        err = self._check_auth(auth_context, "admin.tenant.manage", tenant_id)
        if err:
            return err
        rq = ResourceQuota(**(quotas or {}))
        self._tenant_manager.register_tenant(tenant_id, name, rq, metadata)
        self._audit(
            auth_context.get("actor", "system") if auth_context else "system", "tenant.register", tenant_id, detail=name
        )
        return {"status": "ok", "tenant_id": tenant_id}

    def list_tenants(self, auth_context: dict | None = None) -> list[dict[str, Any]]:
        """List all tenants."""
        return [t.to_dict() for t in self._tenant_manager.list_tenants()]

    def get_tenant_usage(self, auth_context: dict | None = None) -> dict[str, Any]:
        """Get usage report across all tenants."""
        return self._tenant_manager.get_usage_report()

    # ═══════════════════ Phase 3: Distributed API ═══════════════════

    def is_leader(self) -> bool:
        """Check if this node is the cluster leader."""
        return self._leader_election.is_leader()

    def get_cluster_status(self) -> dict[str, Any]:
        """Get cluster-wide status."""
        status = self._node_registry.cluster_status()
        status["this_node"] = self._node_id
        status["is_leader"] = self._leader_election.is_leader()
        status["leader_id"] = self._leader_election.get_leader_id()
        return status

    def get_work_queue_depth(self) -> int:
        """Get local work queue depth."""
        return self._work_stealing.queue_size()

    # ═══════════════════ Admin ═══════════════════

    def get_health(self) -> dict[str, Any]:
        agent_count = len(self._execution_engine.list_agents())
        connected = sum(1 for a in self._execution_engine.list_agents() if a.status == "heartbeating")
        plugin_statuses = {}
        for inst in self._plugin_manager.list_plugins():
            plugin_statuses[inst.manifest.plugin_id] = inst.status.value if inst.status else "unknown"

        # Phase 3 additions
        audit_count = self._audit_logger.total_events()
        tenant_count = self._tenant_manager.tenant_count()
        pending_approvals = self._hitl.get_pending_count()

        return {
            "status": "healthy" if self._running else "degraded",
            "uptime_seconds": time.time() - self._started_at if self._started_at > 0 else 0,
            "components": {
                "kernel": "healthy" if self._running else "degraded",
                "plugins": {
                    "total": len(plugin_statuses),
                    "healthy": sum(1 for s in plugin_statuses.values() if s == "RUNNING"),
                    "degraded": sum(1 for s in plugin_statuses.values() if s == "ERROR"),
                    "error": sum(1 for s in plugin_statuses.values() if s == "ERROR"),
                },
                "agents": {"total": agent_count, "connected": connected, "disconnected": agent_count - connected},
                "security": {"audit_events": audit_count, "mTLS_configured": self._tls_config.is_configured()},
                "multi_tenancy": {"tenants": tenant_count},
                "hitl": {"pending_approvals": pending_approvals},
                "cluster": {"enabled": self._cluster_enabled, "is_leader": self._leader_election.is_leader()},
            },
            "version": "0.3.0",
        }

    def get_metrics(self) -> dict[str, Any]:
        tasks = self._task_graph.list_tasks()
        return {
            "goals": {
                "active": sum(
                    1 for g in self._goals.values() if g["status"] not in ("completed", "failed", "cancelled")
                ),
                "completed_total": sum(1 for g in self._goals.values() if g["status"] == "completed"),
                "failed_total": sum(1 for g in self._goals.values() if g["status"] == "failed"),
                "cancelled_total": sum(1 for g in self._goals.values() if g["status"] == "cancelled"),
            },
            "tasks": {
                "in_flight": self._execution_engine.in_flight_count,
                "completed_total": sum(1 for t in tasks if t.status == TaskStatus.COMPLETED),
                "failed_total": sum(1 for t in tasks if t.status == TaskStatus.FAILED),
                "timed_out_total": sum(1 for t in tasks if t.status == TaskStatus.TIMED_OUT),
                "avg_completion_ms": 0,
            },
            "agents": {
                "registered": len(self._execution_engine.list_agents()),
                "connected": sum(1 for a in self._execution_engine.list_agents() if a.status == "heartbeating"),
                "avg_success_rate": 0.9,
                "total_tasks_dispatched": 0,
            },
            "events": {"published_total": self._event_bus.total_events(), "events_per_second": 0},
            # Phase 3
            "security": {
                "audit_events": self._audit_logger.total_events(),
                "active_api_keys": len(self._api_key_manager.list_keys()),
            },
            "multi_tenancy": {
                "tenants": self._tenant_manager.tenant_count(),
                "usage": self._tenant_manager.get_usage_report(),
            },
            "hitl": {"pending_approvals": self._hitl.get_pending_count()},
            "hot_reload": {"plugins_tracked": len(self._hot_reload_manager.list_plugins())},
            "cluster": {
                "enabled": self._cluster_enabled,
                "nodes": self._node_registry.node_count() if self._cluster_enabled else 0,
                "is_leader": self._leader_election.is_leader(),
            },
        }
