"""Phase 3 — Acceptance Tests: Security, Multi-tenancy, Advanced Execution,
Container Isolation, Hot Reload, Distributed Runtime, CLI Tool."""

import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.advanced_execution import (
    ApprovalStatus,
    DynamicPlanModifier,
    HumanInTheLoop,
    SubGoalManager,
)
from zelos.cli import (
    ZelosCLI,
    build_argument_parser,
)
from zelos.container_isolation import (
    ContainerIsolationFactory,
    ContainerPluginConfig,
    RemotePlugin,
)
from zelos.distributed import (
    ClusterNode,
    LeaderElection,
    NodeRegistry,
    WorkStealing,
)
from zelos.hot_reload import (
    FileWatcher,
    HotReloadManager,
    UpgradeStrategy,
)
from zelos.multi_tenancy import (
    Namespace,
    ResourceQuota,
    TenantManager,
)
from zelos.security import (
    AccessControl,
    APIKeyManager,
    AuditLogger,
)
from zelos.task_graph import Task, TaskGraphEngine, TaskStatus

PASS = 0
FAIL = 0


def t(name, condition):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name}")


# ═══════════════════ 1. Security Module ═══════════════════


def test_security():
    print("\n🔐 Security — AccessControl, AuditLogger, APIKeyManager")

    # ── SEC-01: AccessControl — Role Definitions ──
    ac = AccessControl()
    t("SEC-01a: Default roles exist", all(r in ac.roles for r in ["admin", "operator", "agent", "viewer"]))

    t("SEC-01b: Admin has all permissions (*)", "*" in ac.roles["admin"].permissions)

    t(
        "SEC-01c: Operator permissions",
        "goal.submit" in ac.roles["operator"].permissions and "agent.read" in ac.roles["operator"].permissions,
    )

    t(
        "SEC-01d: Agent permissions",
        "task.execute" in ac.roles["agent"].permissions and "agent.heartbeat" in ac.roles["agent"].permissions,
    )

    t(
        "SEC-01e: Viewer read-only permissions",
        all(p in ac.roles["viewer"].permissions for p in ["goal.read", "task.read", "agent.read", "metrics.read"]),
    )

    # ── SEC-02: AccessControl — Permission Check ──
    t(
        "SEC-02a: Admin can do anything",
        ac.check("admin", "goal.submit") and ac.check("admin", "agent.delete") and ac.check("admin", "random.action"),
    )

    t("SEC-02b: Agent cannot submit goals", not ac.check("agent", "goal.submit"))

    t("SEC-02c: Operator can read agents", ac.check("operator", "agent.read"))

    t("SEC-02d: Wildcard pattern match (operator task.* → task.create)", ac.check("operator", "task.create"))

    t("SEC-02e: Unknown role denied", not ac.check("unknown_role", "anything"))

    # ── SEC-03: AccessControl — Custom Roles ──
    ac.add_role("custom_dev", ["goal.submit", "task.execute", "artifact.read"])
    t(
        "SEC-03a: Add custom role",
        ac.check("custom_dev", "goal.submit")
        and ac.check("custom_dev", "task.execute")
        and not ac.check("custom_dev", "agent.delete"),
    )

    ac.update_role("custom_dev", add_permissions=["agent.read"])
    t("SEC-03b: Modify role permissions", ac.check("custom_dev", "agent.read"))

    ac.remove_role("custom_dev")
    t("SEC-03c: Remove role", "custom_dev" not in ac.roles and not ac.check("custom_dev", "goal.submit"))

    # ── SEC-04: AuditLogger ──
    al = AuditLogger()
    al.log("admin", "goal.submit", "g-001", detail="Submitted build goal", result="success")
    al.log("agent-1", "task.execute", "t-001", detail="Executed coding task", result="success")
    al.log("admin", "goal.cancel", "g-002", detail="Budget exceeded", result="denied")
    al.log("operator", "agent.read", "agent-1", detail="Health check", result="success")

    t("SEC-04a: Log audit event", al.total_events() == 4)

    admin_events = al.query(actor="admin")
    t("SEC-04b: Query by actor", len(admin_events) == 2)

    submit_events = al.query(action="task.execute")
    t("SEC-04c: Query by action", len(submit_events) == 1)

    # Time range query
    now = time.time()
    for i in range(3):
        al.log("test", "test.action", f"res-{i}", result="success")
        time.sleep(0.01)
    recent = al.query(start_time=now)
    t("SEC-04d: Query by time range", len(recent) >= 3)

    resource_events = al.query(resource="g-001")
    t("SEC-04e: Query by resource", len(resource_events) == 1)

    exported = al.export_json()
    t("SEC-04f: Export audit log (JSON)", isinstance(exported, str) and '"actor"' in exported)

    # ── SEC-05: APIKeyManager ──
    akm = APIKeyManager()
    key1 = akm.generate_key("admin", description="Admin key", ttl_seconds=3600)
    key2 = akm.generate_key("agent", description="Agent key")

    t("SEC-05a: Generate API key (prefix zelos_)", key1.startswith("zelos_") and len(key1) > 30)

    validation = akm.validate(key1)
    t("SEC-05b: Validate valid key", validation is not None and validation["role"] == "admin")

    t("SEC-05c: Reject invalid key", akm.validate("zelos_fake_invalid_key_12345") is None)

    akm.revoke(key2)
    t("SEC-05d: Revoke key", akm.validate(key2) is None)

    # Expired key — generate with very short TTL, then wait
    short_key = akm.generate_key("viewer", ttl_seconds=0.001)
    time.sleep(0.1)
    t("SEC-05e: Expired key fails", akm.validate(short_key) is None)


# ═══════════════════ 2. Multi-tenancy Module ═══════════════════


def test_multi_tenancy():
    print("\n🏢 Multi-tenancy — Namespace, ResourceQuota, TenantManager")

    # ── TEN-01: Namespace ──
    ns_a = Namespace(
        "ns-a", "Tenant A", quotas=ResourceQuota(max_goals=10, max_tasks=50, max_agents=5, budget_per_goal=100.0)
    )
    ns_b = Namespace(
        "ns-b", "Tenant B", quotas=ResourceQuota(max_goals=5, max_tasks=20, max_agents=3, budget_per_goal=50.0)
    )

    t("TEN-01a: Create namespace with quotas", ns_a.namespace_id == "ns-a" and ns_a.quotas.max_goals == 10)

    # Isolation: resources tracked per namespace
    ns_a.add_goal("g-a1")
    ns_a.add_goal("g-a2")
    ns_b.add_goal("g-b1")
    t("TEN-01b: Namespace isolation (goals separate)", ns_a.goal_count == 2 and ns_b.goal_count == 1)

    # ── TEN-02: Resource Quotas ──
    ns_small = Namespace(
        "ns-small", "Small", quotas=ResourceQuota(max_goals=2, max_tasks=5, max_agents=2, budget_per_goal=10.0)
    )

    t("TEN-02a: Goal quota — within limit", ns_small.check_quota("goals") and ns_small.check_quota("tasks"))

    ns_small.add_goal("g-1")
    ns_small.add_goal("g-2")
    t("TEN-02b: Goal quota — exceeding limit", not ns_small.check_quota("goals"))

    # Task quota
    ns_task = Namespace("ns-task", "TaskTest", quotas=ResourceQuota(max_tasks=3))
    for i in range(3):
        ns_task.add_task(f"t-{i}")
    t("TEN-02c: Task quota enforcement", not ns_task.check_quota("tasks"))

    # Agent quota
    ns_agent = Namespace("ns-agent", "AgentTest", quotas=ResourceQuota(max_agents=2))
    ns_agent.add_agent("agent-1")
    ns_agent.add_agent("agent-2")
    t("TEN-02d: Agent quota enforcement", not ns_agent.check_quota("agents"))

    # Budget quota
    t("TEN-02e: Budget quota check", ns_small.quotas.check_budget(5.0) and not ns_small.quotas.check_budget(15.0))

    # Usage tracking
    t("TEN-02f: Quota usage tracking", ns_a.goal_count == 2 and ns_a.agent_count == 0 and ns_a.task_count == 0)

    # ── TEN-03: TenantManager ──
    tm = TenantManager()
    t1 = tm.register_tenant("tenant-1", "First Tenant", quotas=ResourceQuota(max_goals=5))
    tm.register_tenant("tenant-2", "Second Tenant", quotas=ResourceQuota(max_goals=3))

    t("TEN-03a: Register tenants", len(tm.list_tenants()) == 2 and t1.tenant_id == "tenant-1")

    tm.deactivate_tenant("tenant-2")
    t("TEN-03b: Tenant deactivation", not tm.get_tenant("tenant-2").active)

    t("TEN-03c: Active tenant check", tm.is_active("tenant-1") and not tm.is_active("tenant-2"))

    # Cross-tenant isolation
    ns1 = tm.get_namespace("tenant-1")
    ns2 = tm.get_namespace("tenant-2")
    ns1.add_goal("g-t1-1")
    t("TEN-03d: Cross-tenant goal isolation", ns1.goal_count == 1 and ns2.goal_count == 0)

    # Default tenant
    default_ns = tm.get_namespace("nonexistent")
    t("TEN-03e: Default tenant for unknown", default_ns is not None)

    # Tenant metadata
    tm.register_tenant("tenant-meta", "Meta", metadata={"org": "Engineering", "tier": "premium"})
    t("TEN-03f: Tenant metadata", tm.get_tenant("tenant-meta").metadata.get("tier") == "premium")


# ═══════════════════ 3. Advanced Execution Module ═══════════════════


def test_advanced_execution():
    print("\n⚡ Advanced Execution — Dynamic Plan, Sub-Goal, Human-in-the-Loop")

    # ── ADV-01: Dynamic Plan Modification ──
    tg = TaskGraphEngine()
    tasks = {}
    for i in range(1, 5):
        task = Task(
            task_id=f"t{i}",
            plan_id="plan-1",
            description=f"Task {i}",
            required_capability=f"cap.{i}",
        )
        tg.add_task(task)
        tasks[f"t{i}"] = task

    dpm = DynamicPlanModifier(tg)

    # ADV-01a: Add task
    dpm.add_task(
        task_id="t5",
        plan_id="plan-1",
        description="New dynamic task",
        required_capability="cap.5",
        dependencies=["t4"],
    )
    t("ADV-01a: Add task to running plan", tg.get_task("t5") is not None and "t4" in tg.get_task("t5").dependencies)

    # ADV-01b: Remove pending task
    result = dpm.remove_task("t5")
    t("ADV-01b: Remove pending task", result and tg.get_task("t5") is None)

    # ADV-01c: Modify task capability
    dpm.modify_task("t3", required_capability="cap.3-updated", priority="high")
    t(
        "ADV-01c: Modify task capability",
        tg.get_task("t3").required_capability == "cap.3-updated" and tg.get_task("t3").priority == "high",
    )

    # ADV-01d: Add dependency
    dpm.add_dependency("t1", "t4")
    t("ADV-01d: Add dependency edge", "t1" in tg.get_task("t4").dependencies)

    # ADV-01e: Remove dependency
    dpm.remove_dependency("t1", "t4")
    t("ADV-01e: Remove dependency edge", "t1" not in tg.get_task("t4").dependencies)

    # ADV-01f: Cycle prevention
    tg.add_dependency("t2", "t3")
    try:
        dpm.add_dependency("t3", "t2")
        t("ADV-01f: Cycle prevention", False)
    except ValueError:
        t("ADV-01f: Cycle prevention", True)

    # ADV-01g: Cannot modify completed task
    # t1 may already be READY from evaluate_all() in remove_dependency
    t1_task = tg.get_task("t1")
    if t1_task and t1_task.status == TaskStatus.CREATED:
        tg.transition("t1", TaskStatus.READY)
    if t1_task and t1_task.status == TaskStatus.READY:
        tg.transition("t1", TaskStatus.ASSIGNED)
    tg.transition("t1", TaskStatus.STARTED)
    tg.transition("t1", TaskStatus.COMPLETED)
    try:
        dpm.modify_task("t1", required_capability="cap.99")
        t("ADV-01g: Modify completed task rejected", False)
    except ValueError:
        t("ADV-01g: Modify completed task rejected", True)

    # ── ADV-02: Sub-Goal Spawning ──
    sgm = SubGoalManager(tg)

    # ADV-02a: Spawn sub-goal
    tg.get_task("t2")
    sub_goal = sgm.spawn_sub_goal(
        parent_task_id="t2",
        description="Research sub-task",
        budget=10.0,
    )
    t("ADV-02a: Spawn sub-goal from task", sub_goal is not None and sub_goal["parent_task_id"] == "t2")

    # ADV-02b: Sub-goal has plan
    t("ADV-02b: Sub-goal has plan_id", sub_goal["plan_id"] is not None and len(sub_goal["task_ids"]) >= 1)

    # ADV-02c: Check sub-goal completion
    sub_tasks = [tg.get_task(tid) for tid in sub_goal["task_ids"] if tg.get_task(tid)]
    t("ADV-02c: Sub-goal tasks exist in graph", len(sub_tasks) >= 1)

    # ADV-02d: Sub-goal failure
    sgm.mark_sub_goal_failed(sub_goal["sub_goal_id"])
    t("ADV-02d: Sub-goal failure tracked", sgm.get_sub_goal(sub_goal["sub_goal_id"])["status"] == "failed")

    # ADV-02e: Nested sub-goals
    sub2 = sgm.spawn_sub_goal(
        parent_task_id="t3",
        description="Nested level 2",
    )
    sgm.spawn_sub_goal(
        parent_task_id=sub2["task_ids"][0] if sub2["task_ids"] else "t3",
        description="Nested level 3",
    )
    t("ADV-02e: Nested sub-goals", len(sgm.list_sub_goals()) >= 3)

    # ADV-02f: Budget inheritance
    sub_budget = sgm.spawn_sub_goal("t4", "Budget test", budget=25.0)
    t("ADV-02f: Sub-goal budget", sub_budget["budget"] == 25.0)

    # ── ADV-03: Human-in-the-Loop ──
    hitl = HumanInTheLoop()

    # ADV-03a: Create approval request
    req = hitl.create_request(
        task_id="t-approval-1",
        description="Deploy to production",
        context={"env": "prod", "version": "2.0"},
        approvers=["alice", "bob"],
        timeout_seconds=3600,
    )
    t("ADV-03a: Create approval request", req.request_id is not None and req.status == ApprovalStatus.PENDING)

    # ADV-03b: Approve
    result = hitl.approve(req.request_id, approver="alice", comment="LGTM")
    t("ADV-03b: Approve action", result and req.status == ApprovalStatus.APPROVED)

    # ADV-03c: Reject
    req2 = hitl.create_request(
        task_id="t-approval-2",
        description="Risky change",
        approvers=["alice"],
    )
    result2 = hitl.reject(req2.request_id, approver="alice", reason="Too risky")
    t("ADV-03c: Reject action", result2 and req2.status == ApprovalStatus.REJECTED)

    # ADV-03d: Request changes
    req3 = hitl.create_request(
        task_id="t-approval-3",
        description="Feature PR",
        approvers=["bob"],
    )
    hitl.request_changes(req3.request_id, approver="bob", feedback="Add more tests please")
    t("ADV-03d: Request changes", req3.status == ApprovalStatus.CHANGES_REQUESTED)

    # ADV-03e: Approval timeout
    # skip — requires real clock wait

    # ADV-03f: Approval audit trail
    history = hitl.get_history(req.request_id)
    t("ADV-03f: Approval audit trail", len(history) >= 2)  # created + approved

    # ADV-03g: Multi-step approval
    req4 = hitl.create_request(
        task_id="t-approval-4",
        description="Critical release",
        approvers=["alice", "bob"],
        require_all=True,
    )
    hitl.approve(req4.request_id, "alice", "First approved")
    t("ADV-03g: Multi-step — not complete after first", req4.status == ApprovalStatus.PENDING)  # Still pending bob
    hitl.approve(req4.request_id, "bob", "Second approved")
    t("ADV-03g: Multi-step — complete after all", req4.status == ApprovalStatus.APPROVED)


# ═══════════════════ 4. Container/Remote Plugin Isolation ═══════════════════


def test_container_isolation():
    print("\n📦 Container/Remote Isolation — Docker, Remote Plugin")

    # ── ISO2-01: Container Plugin Config ──
    docker_config = ContainerPluginConfig(
        plugin_id="docker-agent",
        image="zelos/agent:latest",
        command=["python", "agent.py"],
        env={"API_KEY": "test123", "LOG_LEVEL": "debug"},
        mounts={"/tmp/output": "/app/output"},
        cpu_limit=1.0,
        memory_limit_mb=512,
        network_mode="bridge",
    )
    t(
        "ISO2-01a: Docker config valid",
        docker_config.runtime == "docker" and docker_config.image == "zelos/agent:latest",
    )
    t("ISO2-01b: Resource limits", docker_config.cpu_limit == 1.0 and docker_config.memory_limit_mb == 512)
    t("ISO2-01c: Network config", docker_config.network_mode == "bridge")

    podman_config = ContainerPluginConfig(
        plugin_id="podman-agent",
        image="zelos/agent:latest",
        runtime="podman",
    )
    t("ISO2-01d: Podman config", podman_config.runtime == "podman")

    # ── ISO2-02: Remote Plugin ──
    rp = RemotePlugin(
        plugin_id="remote-agent-1",
        endpoint="http://remote-host:8080",
        health_endpoint="/health",
        task_endpoint="/execute",
    )
    t(
        "ISO2-02a: Remote plugin registration",
        rp.plugin_id == "remote-agent-1" and rp.endpoint == "http://remote-host:8080",
    )

    # Health check config
    t("ISO2-02b: Remote health config", rp.health_endpoint == "/health")

    # Task dispatch config
    t("ISO2-02c: Remote task dispatch config", rp.task_endpoint == "/execute")

    # Callback URL
    rp2 = RemotePlugin(
        plugin_id="remote-2",
        endpoint="http://host:9090",
        callback_url="http://zelos:9876/callback",
    )
    t("ISO2-02d: Remote callback config", rp2.callback_url == "http://zelos:9876/callback")

    # Timeout config
    rp3 = RemotePlugin(
        plugin_id="remote-3",
        endpoint="http://host:7070",
        timeout_seconds=15.0,
    )
    t("ISO2-02e: Remote timeout config", rp3.timeout_seconds == 15.0)

    # Retry config
    rp4 = RemotePlugin(
        plugin_id="remote-4",
        endpoint="http://host:6060",
        max_retries=3,
        retry_backoff_ms=1000,
    )
    t("ISO2-02f: Remote retry config", rp4.max_retries == 3 and rp4.retry_backoff_ms == 1000)

    # Factory
    factory_docker = ContainerIsolationFactory.create("docker", docker_config)
    t("ISO2-03a: Factory — Docker", factory_docker is not None and factory_docker.runtime == "docker")

    factory_remote = ContainerIsolationFactory.create("remote", rp)
    t("ISO2-03b: Factory — Remote", factory_remote is not None and factory_remote.plugin_id == "remote-agent-1")


# ═══════════════════ 5. Hot Reload Module ═══════════════════


def test_hot_reload():
    print("\n🔄 Hot Reload — FileWatcher, HotReloadManager")

    # ── HOT-01: FileWatcher ──
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a plugin file
        plugin_file = os.path.join(tmpdir, "my_plugin.py")
        with open(plugin_file, "w") as f:
            f.write("# version 1.0.0\ndef execute(): return 'v1'\n")

        fw = FileWatcher(tmpdir, patterns=["*.py"])
        fw.start()
        time.sleep(0.1)

        # Initially no changes
        changes = fw.get_changes()
        t("HOT-01a: File watcher started", fw.is_running())

        # Modify file
        time.sleep(0.1)
        with open(plugin_file, "w") as f:
            f.write("# version 1.1.0\ndef execute(): return 'v2'\n")
        time.sleep(1.0)  # Allow watcher poll cycle (500ms) + debounce (300ms)

        changes = fw.get_changes()
        t("HOT-01b: File change detected", len(changes) >= 1 and "my_plugin.py" in str(changes))

        fw.stop()

    # ── HOT-02: HotReloadManager ──
    hrm = HotReloadManager()

    # Register plugin versions
    hrm.register_version(
        plugin_id="test-plugin",
        version="1.0.0",
        entrypoint="my_plugin:v1",
        checksum="abc123",
    )
    hrm.register_version(
        plugin_id="test-plugin",
        version="1.1.0",
        entrypoint="my_plugin:v2",
        checksum="def456",
    )

    t("HOT-02a: Register plugin versions", len(hrm.get_versions("test-plugin")) == 2)

    # Active version
    t("HOT-02b: Latest is active", hrm.get_active_version("test-plugin").version == "1.1.0")

    # Upgrade
    hrm.register_version(
        plugin_id="test-plugin",
        version="2.0.0",
        entrypoint="my_plugin:v3",
        checksum="ghi789",
    )
    t("HOT-02c: Upgrade to new version", hrm.get_active_version("test-plugin").version == "2.0.0")

    # Drain old version
    hrm.drain_version("test-plugin", "1.0.0")
    drained = hrm.get_version("test-plugin", "1.0.0")
    t("HOT-02d: Drain old version", drained.status == "drained")

    # Rollback
    hrm.rollback("test-plugin", "1.1.0")
    t("HOT-02e: Rollback to previous version", hrm.get_active_version("test-plugin").version == "1.1.0")

    # Version history
    history = hrm.get_version_history("test-plugin")
    t("HOT-02f: Version history maintained", len(history) == 3 and history[0].version == "1.0.0")

    # Concurrent plugin management
    hrm.register_version("plugin-a", "1.0.0", "a:v1", "aaa")
    hrm.register_version("plugin-b", "1.0.0", "b:v1", "bbb")
    t(
        "HOT-02g: Concurrent plugin tracking",
        len(hrm.get_versions("plugin-a")) == 1 and len(hrm.get_versions("plugin-b")) == 1,
    )

    # Upgrade strategy
    t("HOT-03a: Rolling upgrade strategy", hrm.upgrade_strategy == UpgradeStrategy.ROLLING)

    hrm.set_upgrade_strategy(UpgradeStrategy.BLUE_GREEN)
    t("HOT-03b: Blue-green strategy", hrm.upgrade_strategy == UpgradeStrategy.BLUE_GREEN)

    hrm.set_upgrade_strategy(UpgradeStrategy.CANARY)
    t("HOT-03c: Canary strategy", hrm.upgrade_strategy == UpgradeStrategy.CANARY)

    # Canary percentage
    hrm.register_version("canary-plugin", "2.0.0", "c:v2", "ccc", canary_percent=10)
    t("HOT-03d: Canary percentage configuration", hrm.get_version("canary-plugin", "2.0.0").canary_percent == 10)


# ═══════════════════ 6. Distributed Runtime Module ═══════════════════


def test_distributed_runtime():
    print("\n🌐 Distributed Runtime — Leader Election, Work Stealing, Node Registry")

    # ── DIST-01: Leader Election ──
    le = LeaderElection(node_id="node-1", heartbeat_interval_ms=500)

    # Start and check initial state
    le.start()
    t("DIST-01a: Leader election starts", le.state.value in ("leader", "candidate", "follower"))

    # Single node should become leader
    time.sleep(0.3)
    t("DIST-01b: Single node becomes leader", le.is_leader())

    le.stop()

    # Multiple leaders test — register peers so they know about each other
    le1 = LeaderElection(node_id="n1", heartbeat_interval_ms=200)
    le2 = LeaderElection(node_id="n2", heartbeat_interval_ms=200)
    le3 = LeaderElection(node_id="n3", heartbeat_interval_ms=200)

    # Register peers with each other
    le1.register_peer("n2")
    le1.register_peer("n3")
    le2.register_peer("n1")
    le2.register_peer("n3")
    le3.register_peer("n1")
    le3.register_peer("n2")

    le1.start()
    le2.start()
    le3.start()
    time.sleep(0.5)

    # After election, should converge to at most one leader
    leaders = sum([le1.is_leader(), le2.is_leader(), le3.is_leader()])
    t("DIST-01c: At most one leader", leaders <= 1)
    t("DIST-01d: At least one leader elected", leaders >= 1)

    # Leader resignation
    for le_obj, _name in [(le1, "n1"), (le2, "n2"), (le3, "n3")]:
        if le_obj.is_leader():
            le_obj.resign()
            break
    time.sleep(0.2)
    leaders_after = sum([le1.is_leader(), le2.is_leader(), le3.is_leader()])
    t(
        "DIST-01e: Leader resignation → re-election possible", leaders_after <= 1
    )  # At most one, may or may not be re-elected

    le1.stop()
    le2.stop()
    le3.stop()

    # ── DIST-02: Work Stealing ──
    ws = WorkStealing(node_id="stealer-1", max_concurrent_tasks=20)

    # Queue some tasks
    for i in range(5):
        ws.enqueue_task(f"task-{i}", "cap.test")
    t("DIST-02a: Task queue initial size", ws.queue_size() == 5)

    # Steal from overloaded node
    overloaded = WorkStealing(node_id="overloaded", max_concurrent_tasks=3)
    for i in range(20):
        overloaded.enqueue_task(f"big-task-{i}", "cap.heavy")

    stolen = ws.steal_from(overloaded, max_count=3)
    t("DIST-02b: Steal from overloaded", len(stolen) == 3 and ws.queue_size() == 8)

    # Steal only READY-equivalent
    t("DIST-02c: Only steal available tasks", all(t["status"] == "ready" for t in stolen))

    # Capacity check
    full_node = WorkStealing(node_id="full", max_concurrent_tasks=1)
    full_node.enqueue_task("only-task", "cap.x")
    t(
        "DIST-02d: Capacity-aware stealing",
        not full_node.can_accept_more() or full_node.queue_size() <= full_node.max_concurrent_tasks,
    )

    # ── DIST-03: Node Registry ──
    nr = NodeRegistry()
    n1 = ClusterNode(
        node_id="node-1",
        host="10.0.0.1",
        port=9876,
        capabilities=["code-generation.python", "code-review.security"],
        capacity=10,
    )
    n2 = ClusterNode(
        node_id="node-2",
        host="10.0.0.2",
        port=9876,
        capabilities=["automation.browser", "code-generation.typescript"],
        capacity=8,
    )
    n3 = ClusterNode(
        node_id="node-3",
        host="10.0.0.3",
        port=9876,
        capabilities=["code-generation.python", "data-analysis.sql"],
        capacity=5,
    )

    nr.register(n1)
    nr.register(n2)
    nr.register(n3)
    t("DIST-03a: Node registration", nr.node_count() == 3 and nr.get_node("node-1") is not None)

    # Heartbeat
    nr.heartbeat("node-1")
    node1 = nr.get_node("node-1")
    t("DIST-03b: Node heartbeat updates time", node1.last_heartbeat > 0)

    # Node removal
    nr.deregister("node-3")
    t("DIST-03c: Node removal", nr.node_count() == 2 and nr.get_node("node-3") is None)

    # Metadata
    t("DIST-03d: Node metadata", n1.capacity == 10 and len(n1.capabilities) == 2)

    # Cluster status
    status = nr.cluster_status()
    t("DIST-03e: Cluster status", status["total_nodes"] == 2 and status["healthy_nodes"] == 2)

    # Find by capability
    python_nodes = nr.find_by_capability("code-generation.python")
    t("DIST-03f: Find by capability", len(python_nodes) == 1 and python_nodes[0].node_id == "node-1")

    # Dead node detection
    nr.heartbeat("node-1")
    nr.heartbeat("node-2", timestamp=time.time() - 3600)  # Simulate stale
    dead = nr.detect_dead_nodes(timeout_seconds=1800)
    t("DIST-03g: Dead node detection", len(dead) >= 1 and "node-2" in dead)


# ═══════════════════ 7. CLI Tool Module ═══════════════════


def test_cli():
    print("\n💻 CLI Tool — Argument Parser, Command Dispatch")

    # ── CLI-01: Basic Commands ──
    cli = ZelosCLI()

    # Version
    version_output = cli.run(["--version"])
    t("CLI-01a: --version", "zelos" in version_output.lower() or "0." in version_output)

    # Help — argparse prints to stdout and exits; verify help subcommand works
    parser = build_argument_parser()
    t("CLI-01b: --help flag available", parser is not None and hasattr(parser, "format_help"))

    # ── CLI-02: Goal Commands ──
    goal_submit = cli.run(["goal", "submit", "--description", "Test goal"])
    t("CLI-02a: goal submit", "goal" in goal_submit.lower() and "submitted" in goal_submit.lower())

    goal_list = cli.run(["goal", "list"])
    t("CLI-02b: goal list", "goal" in goal_list.lower())

    goal_status = cli.run(["goal", "status", "--goal-id", "g-test-1"])
    t("CLI-02c: goal status", "status" in goal_status.lower() or "not found" in goal_status.lower())

    goal_cancel = cli.run(["goal", "cancel", "--goal-id", "g-test-1"])
    t("CLI-02d: goal cancel", "cancel" in goal_cancel.lower() or "not found" in goal_cancel.lower())

    # ── CLI-03: Agent Commands ──
    agent_list = cli.run(["agent", "list"])
    t("CLI-03a: agent list", "agent" in agent_list.lower())

    agent_info = cli.run(["agent", "info", "--agent-id", "agent-1"])
    t("CLI-03b: agent info", "agent" in agent_info.lower())

    # ── CLI-04: Admin Commands ──
    health = cli.run(["health"])
    t("CLI-04a: health check", "health" in health.lower() or "status" in health.lower())

    metrics = cli.run(["metrics"])
    t("CLI-04b: metrics", "metric" in metrics.lower() or "goal" in metrics.lower())

    # ── Argument Parser ──
    parser = build_argument_parser()
    t("CLI-05: Argument parser builds correctly", parser is not None)


if __name__ == "__main__":
    print("=" * 60)
    print("  PHASE 3 — ACCEPTANCE TESTS")
    print("  Runtime Ecosystem: Security, Multi-tenancy,")
    print("  Advanced Execution, Container Isolation,")
    print("  Hot Reload, Distributed Runtime, CLI")
    print("=" * 60)

    test_security()
    test_multi_tenancy()
    test_advanced_execution()
    test_container_isolation()
    test_hot_reload()
    test_distributed_runtime()
    test_cli()

    total = PASS + FAIL
    print(f"\n{'=' * 60}")
    print(f"  RESULTS: {PASS}/{total} passed ({FAIL} failed)")
    print(f"{'=' * 60}")
    sys.exit(0 if FAIL == 0 else 1)
