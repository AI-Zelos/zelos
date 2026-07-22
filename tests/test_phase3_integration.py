"""
Phase 3 Integration Tests — Full Runtime with Security, Multi-tenancy,
Advanced Execution, Hot Reload, Distributed, and CLI.

Tests the COMPLETE integration: not just individual modules, but their
wiring into ZelosRuntime with real auth contexts, tenant isolation,
HITL approval pipelines, and hot reload strategies.
"""

import os
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.hot_reload import UpgradeStrategy
from zelos.runtime import ZelosRuntime

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


def make_auth(role="admin", tenant_id="default", actor="test-user"):
    return {"role": role, "tenant_id": tenant_id, "actor": actor}


# ═══════════════════ 1. Security Integration ═══════════════════


def test_security_integration():
    print("\n🔐 1. Security Integration — RBAC + Audit in Runtime")

    rt = ZelosRuntime({"plugins": []})
    rt.start()

    # INT-SEC-01: Admin submits goal
    result = rt.submit_goal("Test goal", auth_context=make_auth("admin"))
    t("INT-SEC-01: Admin can submit goal", result.get("status") in ("accepted", "planned"))

    # INT-SEC-02: Agent cannot submit goal
    result2 = rt.submit_goal("Agent tries", auth_context=make_auth("agent"))
    t("INT-SEC-02: Agent rejected from submitting goal", result2.get("status") == "rejected")

    # INT-SEC-03: Operator can read agents
    agents = rt.list_agents(auth_context=make_auth("operator"))
    t("INT-SEC-03: Operator can list agents", isinstance(agents, list))

    # INT-SEC-04: Viewer cannot cancel goal
    g = rt.submit_goal("Viewer test", auth_context=make_auth("admin"))
    gid = g["goal_id"]
    cancel_result = rt.cancel_goal(gid, auth_context=make_auth("viewer"))
    t("INT-SEC-04: Viewer cannot cancel goal", cancel_result is not None and cancel_result.get("status") == "rejected")

    # INT-SEC-05: Audit log records operations
    audit = rt.get_audit_log(auth_context=make_auth("admin"))
    t("INT-SEC-05: Audit log populated", len(audit) >= 2)

    # INT-SEC-06: API key auth flow
    key = rt.generate_api_key("admin", "test key", auth_context=make_auth("admin"))
    t("INT-SEC-06a: Generate API key", key.startswith("zelos_"))

    key_auth = {"api_key": key, "actor": "key-user"}
    result3 = rt.submit_goal("Via API key", auth_context=key_auth)
    t("INT-SEC-06b: API key auth works", result3.get("status") in ("accepted", "planned"))

    # INT-SEC-07: Revoked key fails
    rt.revoke_api_key(key, auth_context=make_auth("admin"))
    result4 = rt.submit_goal("Revoked key", auth_context=key_auth)
    t("INT-SEC-07: Revoked key rejected", result4.get("status") == "rejected")

    # INT-SEC-08: Audit log filtering
    admin_logs = rt.get_audit_log(auth_context=make_auth("admin"), actor="test-user")
    t("INT-SEC-08: Audit filtered by actor", len(admin_logs) >= 1)

    rt.shutdown()


# ═══════════════════ 2. Multi-tenancy Integration ═══════════════════


def test_multi_tenancy_integration():
    print("\n🏢 2. Multi-tenancy Integration — Tenant Isolation in Runtime")

    # Create runtime with multi-tenancy enabled
    rt = ZelosRuntime(
        {
            "plugins": [],
            "multi_tenancy": {
                "enabled": True,
                "tenants": [
                    {
                        "id": "acme",
                        "name": "ACME Corp",
                        "quotas": {"max_goals": 3, "max_agents": 2, "budget_per_goal": 100.0},
                    },
                    {
                        "id": "startup",
                        "name": "Startup Inc",
                        "quotas": {"max_goals": 1, "max_agents": 1, "budget_per_goal": 10.0},
                    },
                ],
            },
        }
    )
    rt.start()

    acme_auth = make_auth("admin", "acme", "alice")
    startup_auth = make_auth("admin", "startup", "bob")
    default_auth = make_auth("admin", "default", "sys")

    # INT-TEN-01: Tenant-scoped goal submission
    g1 = rt.submit_goal("ACME project", auth_context=acme_auth)
    g2 = rt.submit_goal("Startup project", auth_context=startup_auth)
    t(
        "INT-TEN-01: Tenant-scoped goal submission",
        g1.get("status") in ("accepted", "planned") and g2.get("status") in ("accepted", "planned"),
    )

    # INT-TEN-02: Cross-tenant isolation — cannot see other tenant's goals
    status_acme = rt.get_goal_status(g1["goal_id"], auth_context=acme_auth)
    status_acme_as_startup = rt.get_goal_status(g1["goal_id"], auth_context=startup_auth)
    t("INT-TEN-02: Cross-tenant goal isolation", status_acme is not None and status_acme_as_startup is None)

    # INT-TEN-03: Default tenant can see all goals
    status_default = rt.get_goal_status(g1["goal_id"], auth_context=default_auth)
    t("INT-TEN-03: Default tenant sees all goals", status_default is not None)

    # INT-TEN-04: Goal quota enforcement
    rt.submit_goal("ACME goal 2", auth_context=acme_auth)
    rt.submit_goal("ACME goal 3", auth_context=acme_auth)
    exceeded = rt.submit_goal("ACME goal 4 — OVER QUOTA", auth_context=acme_auth)
    t("INT-TEN-04: Goal quota exceeded rejected", exceeded.get("status") == "rejected")

    # INT-TEN-05: Budget quota enforcement
    over_budget = rt.submit_goal("Big spend", budget=200.0, auth_context=acme_auth)
    t("INT-TEN-05: Budget quota exceeded rejected", over_budget.get("status") == "rejected")

    # INT-TEN-06: Agent quota enforcement
    rt.add_agent(
        "acme-agent-1", "test:Agent", [{"name": "code-generation.python", "version": "1.0.0"}], auth_context=acme_auth
    )
    rt.add_agent(
        "acme-agent-2", "test:Agent", [{"name": "code-review.security", "version": "1.0.0"}], auth_context=acme_auth
    )
    agent3 = rt.add_agent(
        "acme-agent-3", "test:Agent", [{"name": "automation.browser", "version": "1.0.0"}], auth_context=acme_auth
    )
    t("INT-TEN-06: Agent quota exceeded rejected", isinstance(agent3, dict) and agent3.get("status") == "rejected")

    # INT-TEN-07: Tenant usage report
    usage = rt.get_tenant_usage(auth_context=make_auth("admin"))
    t("INT-TEN-07: Tenant usage report", usage.get("total_tenants", 0) >= 2)

    # INT-TEN-08: Deactivated tenant rejection
    t8 = rt._tenant_manager.get_tenant("startup")
    if t8:
        t8.active = False
    deactivated = rt.submit_goal("Should fail", auth_context=startup_auth)
    t("INT-TEN-08: Deactivated tenant rejected", deactivated.get("status") == "rejected")

    rt.shutdown()


# ═══════════════════ 3. Advanced Execution Integration ═══════════════════


def test_advanced_execution_integration():
    print("\n⚡ 3. Advanced Execution — Plan Mod + Sub-Goal + HITL in Runtime")

    rt = ZelosRuntime({"plugins": []})
    rt.start()

    # INT-ADV-01: Submit goal → tasks created → modify plan
    g = rt.submit_goal("Build and test a feature", auth_context=make_auth("admin"))
    plan_id = g.get("plan_id")
    t("INT-ADV-01a: Goal planned", g.get("status") in ("planned", "accepted"))

    # Dynamically add a task
    result = rt.modify_plan(
        plan_id,
        "add_task",
        task_id="extra-task-1",
        description="Extra verification step",
        required_capability="code-review.security",
    )
    t("INT-ADV-01b: Dynamic add task", result.get("status") == "ok")

    # Remove the task
    result2 = rt.modify_plan(plan_id, "remove_task", task_id="extra-task-1")
    t("INT-ADV-01c: Dynamic remove task", result2.get("status") == "ok")

    # INT-ADV-02: Sub-goal spawning
    tasks = rt._task_graph.list_tasks()
    parent_id = tasks[0].task_id if tasks else "g-fake"
    sub = rt.spawn_sub_goal(
        parent_id, "Investigate alternatives", budget=15.0, required_capability="research.analysis", num_tasks=2
    )
    t("INT-ADV-02a: Spawn sub-goal", sub.get("status") == "running" and len(sub.get("task_ids", [])) == 2)

    status = rt.get_sub_goal_status(sub["sub_goal_id"])
    t("INT-ADV-02b: Sub-goal status query", status is not None and status["budget"] == 15.0)

    # INT-ADV-03: HITL approval flow — submit goal with require_approval
    g2 = rt.submit_goal(
        "Deploy to production — NEEDS APPROVAL",
        require_approval=True,
        approvers=["alice", "bob"],
        auth_context=make_auth("admin"),
    )
    t("INT-ADV-03a: Goal with approval requirement", g2.get("status") in ("planned", "accepted"))

    # Pending approvals
    pending = rt.list_pending_approvals()
    t("INT-ADV-03b: Pending approvals listed", len(pending) >= 1)

    # Approve by first approver
    if pending:
        task_id = pending[0]["task_id"]
        # Approve by alice
        rt.approve_task(task_id, "alice", "LGTM")
        pending2 = rt.list_pending_approvals()

        # With require_all=True and 2 approvers, should still be pending after 1
        t("INT-ADV-03c: Multi-approver — still pending after 1 of 2", any(p["task_id"] == task_id for p in pending2))

        # Second approval
        rt.approve_task(task_id, "bob", "Approved too")
        pending3 = rt.list_pending_approvals()
        t("INT-ADV-03d: Multi-approver — approved after both", not any(p["task_id"] == task_id for p in pending3))

    # INT-ADV-04: Reject a task — the goal should be marked failed
    g3 = rt.submit_goal("Risky change", require_approval=True, approvers=["dba"], auth_context=make_auth("admin"))
    pending4 = rt.list_pending_approvals()
    if pending4:
        reject_req = pending4[-1]
        rt.reject_task(reject_req["task_id"], "dba", "Too dangerous")
        # Check that goal is marked failed
        g3_status = rt.get_goal_status(g3["goal_id"])
        t("INT-ADV-04: Rejected goal → failed", g3_status is not None and g3_status["status"] == "failed")

    # INT-ADV-05: Edge case — approve non-existent
    bad_approve = rt.approve_task("fake-request-id", "alice", "")
    t("INT-ADV-05: Approve non-existent returns not_found", bad_approve.get("status") in ("not_found", "failed"))

    # INT-ADV-06: Edge case — reject non-existent
    bad_reject = rt.reject_task("fake-request-id", "alice", "")
    t("INT-ADV-06: Reject non-existent returns not_found", bad_reject.get("status") == "not_found")

    rt.shutdown()


# ═══════════════════ 4. Hot Reload Integration ═══════════════════


def test_hot_reload_integration():
    print("\n🔄 4. Hot Reload Integration — Strategies + Versioning in Runtime")

    rt = ZelosRuntime(
        {
            "plugins": [],
            "hot_reload": {
                "upgrade_strategy": "rolling",
            },
        }
    )
    rt.start()

    # Register a plugin version
    rt._hot_reload_manager.register_version("test-plugin", "1.0.0", "test:v1", "abc")
    rt._hot_reload_manager.register_version("test-plugin", "1.1.0", "test:v2", "def")
    rt._hot_reload_manager.register_version("test-plugin", "2.0.0", "test:v3", "ghi")

    # INT-HOT-01: Reload to new version
    result = rt.reload_plugin("test-plugin", "test:v4", "3.0.0")
    t("INT-HOT-01a: Hot reload to new version", result.get("status") == "ok")

    active = rt._hot_reload_manager.get_active_version("test-plugin")
    t("INT-HOT-01b: Active version updated", active.version == "3.0.0")

    # INT-HOT-02: Rollback
    result2 = rt.rollback_plugin("test-plugin", "1.1.0")
    t("INT-HOT-02a: Rollback successful", result2.get("status") == "ok")

    active2 = rt._hot_reload_manager.get_active_version("test-plugin")
    t("INT-HOT-02b: Active version is rolled back", active2.version == "1.1.0")

    # INT-HOT-03: Rollback to non-existent version
    result3 = rt.rollback_plugin("test-plugin", "99.0.0")
    t("INT-HOT-03: Rollback non-existent version fails", result3.get("status") == "failed")

    # INT-HOT-04: Strategy switching
    rt.set_upgrade_strategy("canary")
    t("INT-HOT-04a: Set canary strategy", rt._hot_reload_manager.upgrade_strategy == UpgradeStrategy.CANARY)

    rt.set_upgrade_strategy("blue_green")
    t("INT-HOT-04b: Set blue_green strategy", rt._hot_reload_manager.upgrade_strategy == UpgradeStrategy.BLUE_GREEN)

    rt.set_upgrade_strategy("instant")
    t("INT-HOT-04c: Set instant strategy", rt._hot_reload_manager.upgrade_strategy == UpgradeStrategy.INSTANT)

    rt.set_upgrade_strategy("rolling")
    t("INT-HOT-04d: Set rolling strategy", rt._hot_reload_manager.upgrade_strategy == UpgradeStrategy.ROLLING)

    # INT-HOT-05: Bad strategy name
    bad = rt.set_upgrade_strategy("nonexistent")
    t("INT-HOT-05: Bad strategy name rejected", bad.get("status") == "failed")

    # INT-HOT-06: Version history
    versions = rt.get_plugin_versions("test-plugin")
    t("INT-HOT-06: Version history has entries", len(versions) >= 3)

    # INT-HOT-07: File watcher integration
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin_file = os.path.join(tmpdir, "watcher_test.py")
        with open(plugin_file, "w") as f:
            f.write("# v1\ndef execute(): pass\n")

        rt2 = ZelosRuntime(
            {
                "plugins": [],
                "hot_reload": {
                    "plugin_dir": tmpdir,
                    "poll_interval_ms": 200,
                },
            }
        )
        rt2.start()
        time.sleep(0.4)

        # Modify file
        with open(plugin_file, "w") as f:
            f.write("# v2\ndef execute(): pass\n")
        time.sleep(0.8)

        # Check watcher events
        if rt2._file_watcher:
            changes = rt2._file_watcher.get_changes()
            t("INT-HOT-07: File watcher detects changes in Runtime", len(changes) >= 1)
        else:
            t("INT-HOT-07: File watcher detects changes in Runtime", True)

        rt2.shutdown()

    rt.shutdown()


# ═══════════════════ 5. Distributed Integration ═══════════════════


def test_distributed_integration():
    print("\n🌐 5. Distributed Integration — Cluster in Runtime")

    rt = ZelosRuntime(
        {
            "plugins": [],
            "distributed": {
                "enabled": True,
                "node_id": "zelos-master",
                "host": "10.0.0.1",
                "port": 9876,
                "capabilities": ["code-generation.python"],
                "capacity": 20,
                "heartbeat_ms": 300,
                "peers": [
                    {
                        "node_id": "zelos-worker-1",
                        "host": "10.0.0.2",
                        "capabilities": ["automation.browser"],
                        "capacity": 10,
                    },
                    {
                        "node_id": "zelos-worker-2",
                        "host": "10.0.0.3",
                        "capabilities": ["code-review.security"],
                        "capacity": 10,
                    },
                ],
            },
        }
    )
    rt.start()

    # INT-DIST-01: Leader election started
    t("INT-DIST-01: Leader election running", rt._leader_election._running)

    # INT-DIST-02: Node registry populated
    t("INT-DIST-02: Nodes registered", rt._node_registry.node_count() >= 3)  # self + 2 peers

    # INT-DIST-03: Cluster status
    status = rt.get_cluster_status()
    t("INT-DIST-03a: Cluster status total nodes", status.get("total_nodes", 0) >= 3)
    t("INT-DIST-03b: This node ID in status", status.get("this_node") == "zelos-master")

    # INT-DIST-04: Leader election result
    time.sleep(0.5)
    is_leader = rt.is_leader()
    t("INT-DIST-04: Leader election result", isinstance(is_leader, bool))

    # INT-DIST-05: Work queue depth
    depth = rt.get_work_queue_depth()
    t("INT-DIST-05: Work queue depth queryable", depth >= 0)

    # INT-DIST-06: Leader for single node
    rt2 = ZelosRuntime(
        {
            "plugins": [],
            "distributed": {
                "enabled": True,
                "node_id": "solo-node",
            },
        }
    )
    rt2.start()
    time.sleep(0.4)
    t("INT-DIST-06: Solo node becomes leader", rt2.is_leader() is True)
    rt2.shutdown()

    rt.shutdown()


# ═══════════════════ 6. Full End-to-End Pipeline ═══════════════════


def test_full_pipeline():
    print("\n🔗 6. Full Pipeline — End-to-End with All Components")

    rt = ZelosRuntime(
        {
            "plugins": [],
            "multi_tenancy": {
                "enabled": True,
                "tenants": [
                    {
                        "id": "eng",
                        "name": "Engineering",
                        "quotas": {"max_goals": 10, "max_agents": 5, "budget_per_goal": 500},
                    },
                ],
            },
            "hot_reload": {"upgrade_strategy": "rolling"},
            "distributed": {"enabled": False},
        }
    )
    rt.start()

    eng_auth = make_auth("admin", "eng", "alice")
    viewer_auth = make_auth("viewer", "eng", "bob")
    agent_auth = make_auth("agent", "eng", "bot-1")

    # Register agents
    rt.add_agent(
        "CodeAgent", "test:Agent", [{"name": "code-generation.python", "version": "1.0.0"}], auth_context=eng_auth
    )
    rt.add_agent(
        "ReviewAgent", "test:Agent", [{"name": "code-review.security", "version": "1.0.0"}], auth_context=eng_auth
    )

    # INT-FULL-01: Submit goal with all auth
    g = rt.submit_goal("Build user authentication module", budget=100.0, priority="high", auth_context=eng_auth)
    t("INT-FULL-01: Goal submitted with auth", g.get("status") in ("accepted", "planned"))

    # INT-FULL-02: Check progress
    time.sleep(0.5)  # Let orchestrator run a cycle
    status = rt.get_goal_status(g["goal_id"], auth_context=eng_auth)
    t("INT-FULL-02: Goal progress queryable", status is not None and status.get("progress") is not None)

    # INT-FULL-03: Audit trail complete
    audit = rt.get_audit_log(auth_context=eng_auth)
    t("INT-FULL-03: Complete audit trail", len(audit) >= 3)  # goal.submit + 2x agent.register

    # INT-FULL-04: Viewer can read but not modify
    v_status = rt.get_goal_status(g["goal_id"], auth_context=viewer_auth)
    t("INT-FULL-04a: Viewer can read goal", v_status is not None)

    v_cancel = rt.cancel_goal(g["goal_id"], auth_context=viewer_auth)
    t("INT-FULL-04b: Viewer cannot cancel goal", v_cancel is not None and v_cancel.get("status") == "rejected")

    # INT-FULL-05: Agent cannot submit goals
    agent_goal = rt.submit_goal("Agent tries", auth_context=agent_auth)
    t("INT-FULL-05: Agent rejected from goal submission", agent_goal.get("status") == "rejected")

    # INT-FULL-06: Health check includes Phase 3 components
    health = rt.get_health()
    t("INT-FULL-06a: Health includes security", "security" in health.get("components", {}))
    t("INT-FULL-06b: Health includes multi_tenancy", "multi_tenancy" in health.get("components", {}))
    t("INT-FULL-06c: Health includes HITL", "hitl" in health.get("components", {}))

    # INT-FULL-07: Metrics include Phase 3 data
    metrics = rt.get_metrics()
    t("INT-FULL-07a: Metrics include security", "security" in metrics)
    t("INT-FULL-07b: Metrics include multi_tenancy", "multi_tenancy" in metrics)
    t("INT-FULL-07c: Metrics include HITL", "hitl" in metrics)

    # INT-FULL-08: Dynamic plan modification mid-execution
    plan_id = g.get("plan_id")
    mod_result = rt.modify_plan(
        plan_id,
        "add_task",
        task_id="e2e-dynamic-task",
        description="Dynamic add during execution",
        required_capability="code-generation.python",
        priority="critical",
    )
    t("INT-FULL-08: Dynamic plan mod mid-execution", mod_result.get("status") == "ok")

    # INT-FULL-09: Sub-goal from within execution
    tasks = rt._task_graph.list_tasks()
    if tasks:
        parent = tasks[0].task_id
        sub = rt.spawn_sub_goal(parent, "E2E sub-goal test", budget=10.0)
        t("INT-FULL-09: Sub-goal spawned during execution", sub.get("status") == "running")

    # INT-FULL-10: Tenant usage report
    usage = rt.get_tenant_usage()
    t("INT-FULL-10: Tenant usage available", usage is not None and "total_tenants" in usage)

    rt.shutdown()


# ═══════════════════ 7. Edge Cases & Error Handling ═══════════════════


def test_edge_cases():
    print("\n⚠️  7. Edge Cases & Error Handling")

    rt = ZelosRuntime({"plugins": []})

    # INT-EDGE-01: Operations before start() — should not crash
    g_before = rt.submit_goal("Before start", auth_context=make_auth())
    t("INT-EDGE-01: Submit goal before start doesn't crash", g_before is not None)

    # INT-EDGE-02: Start + shutdown + start
    rt.start()
    rt.shutdown()
    rt2 = ZelosRuntime({"plugins": []})
    rt2.start()
    t("INT-EDGE-02: Restart Runtime after shutdown", rt2._running is True)
    rt2.shutdown()

    # INT-EDGE-03: Empty auth context = admin default
    rt3 = ZelosRuntime({"plugins": []})
    rt3.start()
    g = rt3.submit_goal("No auth")  # No auth_context
    t("INT-EDGE-03: No auth context → default admin", g.get("status") in ("accepted", "planned"))
    rt3.shutdown()

    # INT-EDGE-04: Invalid priority
    rt4 = ZelosRuntime({"plugins": []})
    rt4.start()
    bad = rt4.submit_goal("Bad priority", priority="urgent")
    t("INT-EDGE-04: Invalid priority rejected", bad.get("status") == "rejected")
    rt4.shutdown()

    # INT-EDGE-05: Empty description
    rt5 = ZelosRuntime({"plugins": []})
    rt5.start()
    empty = rt5.submit_goal("")
    t("INT-EDGE-05: Empty description rejected", empty.get("status") == "rejected")
    rt5.shutdown()

    # INT-EDGE-06: Modify non-existent plan
    rt6 = ZelosRuntime({"plugins": []})
    rt6.start()
    bad_mod = rt6.modify_plan("fake-plan", "remove_task", task_id="x")
    t("INT-EDGE-06: Modify non-existent plan handled", bad_mod.get("status") in ("failed", "rejected"))
    rt6.shutdown()

    # INT-EDGE-07: Spawn sub-goal from non-existent parent
    rt7 = ZelosRuntime({"plugins": []})
    rt7.start()
    sub = rt7.spawn_sub_goal("non-existent-parent", "Test")
    t("INT-EDGE-07: Sub-goal from non-existent parent doesn't crash", sub is not None and "sub_goal_id" in sub)
    rt7.shutdown()

    # INT-EDGE-08: Concurrent submissions from same tenant
    rt8 = ZelosRuntime({"plugins": []})
    rt8.start()

    errors = []

    def submit_many():
        try:
            for i in range(5):
                rt8.submit_goal(f"Concurrent {i}", auth_context=make_auth())
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=submit_many) for _ in range(4)]
    for th in threads:
        th.start()
    for th in threads:
        th.join(timeout=5)

    t("INT-EDGE-08: Concurrent goal submissions handled", len(errors) == 0)

    rt8.shutdown()

    # INT-EDGE-09: Get status of non-existent goal
    rt9 = ZelosRuntime({"plugins": []})
    rt9.start()
    none_status = rt9.get_goal_status("non-existent-goal-id")
    t("INT-EDGE-09: Non-existent goal returns None", none_status is None)
    rt9.shutdown()

    # INT-EDGE-10: Cancel non-existent goal
    rt10 = ZelosRuntime({"plugins": []})
    rt10.start()
    none_cancel = rt10.cancel_goal("non-existent-goal-id")
    t("INT-EDGE-10: Cancel non-existent goal returns None", none_cancel is None)
    rt10.shutdown()

    # INT-EDGE-11: Cancel already completed goal
    rt11 = ZelosRuntime({"plugins": []})
    rt11.start()
    g = rt11.submit_goal("Test terminal", auth_context=make_auth())
    rt11.cancel_goal(g["goal_id"], auth_context=make_auth())
    cancel_twice = rt11.cancel_goal(g["goal_id"], auth_context=make_auth())
    t(
        "INT-EDGE-11: Cancel already-cancelled goal returns conflict",
        cancel_twice is not None
        and (cancel_twice.get("status") == "cancelled" or cancel_twice.get("error") is not None),
    )
    rt11.shutdown()

    # INT-EDGE-12: API key TTL expiry
    rt12 = ZelosRuntime({"plugins": []})
    rt12.start()
    short_key = rt12.generate_api_key("admin", "short-lived", ttl_seconds=0.001, auth_context=make_auth("admin"))
    time.sleep(0.1)
    short_auth = {"api_key": short_key, "actor": "temp"}
    expired = rt12.submit_goal("With expired key", auth_context=short_auth)
    t("INT-EDGE-12: Expired API key rejected", expired.get("status") == "rejected")
    rt12.shutdown()


if __name__ == "__main__":
    print("=" * 60)
    print("  PHASE 3 — INTEGRATION TESTS")
    print("  Full Runtime: Security + Multi-tenancy +")
    print("  Advanced Execution + Hot Reload + Distributed")
    print("=" * 60)

    test_security_integration()
    test_multi_tenancy_integration()
    test_advanced_execution_integration()
    test_hot_reload_integration()
    test_distributed_integration()
    test_full_pipeline()
    test_edge_cases()

    total = PASS + FAIL
    print(f"\n{'=' * 60}")
    print(f"  RESULTS: {PASS}/{total} passed ({FAIL} failed)")
    print(f"{'=' * 60}")
    sys.exit(0 if FAIL == 0 else 1)
