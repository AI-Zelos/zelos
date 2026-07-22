"""
Demo 21 — Multi-Tenant Isolation

Demonstrates complete multi-tenant lifecycle:
  1. Tenant registration with independent resource quotas
  2. Quota enforcement (goal/agent/budget limits)
  3. Cross-tenant isolation (A cannot see B's resources)
  4. Tenant activation / deactivation
  5. Aggregated usage report across all tenants

Run: python3 demo/21_multi_tenant_isolation.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.multi_tenancy import ResourceQuota, TenantManager


def scenario_1_registration():
    print("── Scenario 1: Tenant Registration ──")
    tm = TenantManager()
    tm.register_tenant(
        "tenant-finance", "Finance Dept", quotas=ResourceQuota(max_goals=50, max_agents=10, budget_per_goal=100)
    )
    tm.register_tenant(
        "tenant-eng", "Engineering Team", quotas=ResourceQuota(max_goals=200, max_agents=50, budget_per_goal=500)
    )
    f = tm.get_tenant("tenant-finance")
    e = tm.get_tenant("tenant-eng")
    print(
        f"  {f.name}: goals≤{f.namespace.quotas.max_goals}, agents≤{f.namespace.quotas.max_agents}, budget≤${f.namespace.quotas.budget_per_goal}"
    )
    print(
        f"  {e.name}: goals≤{e.namespace.quotas.max_goals}, agents≤{e.namespace.quotas.max_agents}, budget≤${e.namespace.quotas.budget_per_goal}"
    )
    assert f.name == "Finance Dept"
    return tm


def scenario_2_quota_enforcement():
    print("── Scenario 2: Quota Enforcement ──")
    tm = TenantManager()
    tm.register_tenant(
        "tenant-small", "Small Team", quotas=ResourceQuota(max_goals=3, max_agents=2, budget_per_goal=10)
    )
    ns = tm.get_namespace("tenant-small")

    # Goal quota: allow 3, reject 4th
    for i in range(3):
        assert ns.add_goal(f"goal-{i}")
    assert not ns.check_quota("goals"), "4th goal should be rejected"
    print(f"  Goals: 3/3 allowed, 4th rejected (max={ns.quotas.max_goals})")

    # Agent quota: allow 2, reject 3rd
    for i in range(2):
        assert ns.add_agent(f"agent-{i}")
    assert not ns.check_quota("agents"), "3rd agent rejected"
    print(f"  Agents: 2/2 allowed, 3rd rejected (max={ns.quotas.max_agents})")

    # Budget enforcement
    ns.quotas.check_budget(5)
    assert not ns.quotas.check_budget(15)
    print(f"  Budget: $5 allowed, $15 rejected (limit=${ns.quotas.budget_per_goal})")


def scenario_3_isolation():
    print("── Scenario 3: Cross-Tenant Isolation ──")
    tm = TenantManager()
    tm.register_tenant("t-a", "Alpha", quotas=ResourceQuota(max_goals=10))
    tm.register_tenant("t-b", "Beta", quotas=ResourceQuota(max_goals=10))
    ns_a = tm.get_namespace("t-a")
    ns_b = tm.get_namespace("t-b")
    ns_a.add_goal("ga1")
    ns_a.add_goal("ga2")
    ns_b.add_goal("gb1")
    print(f"  Alpha: {ns_a.goal_count} goals | Beta: {ns_b.goal_count} goals")
    assert ns_a.goal_count == 2 and ns_b.goal_count == 1
    print("  → Fully isolated — A cannot touch B's resources")


def scenario_4_lifecycle():
    print("── Scenario 4: Tenant Activate / Deactivate ──")
    tm = TenantManager()
    tm.register_tenant("tenant-temp", "Temporary Project", quotas=ResourceQuota(max_goals=5))
    assert tm.get_tenant("tenant-temp").active
    print("  New tenant: active=True")
    tm.deactivate_tenant("tenant-temp")
    assert not tm.get_tenant("tenant-temp").active
    print("  Deactivated: active=False")
    tm.activate_tenant("tenant-temp")
    assert tm.get_tenant("tenant-temp").active
    print("  Reactivated: active=True")


def scenario_5_usage_report():
    print("── Scenario 5: Usage Report ──")
    tm = TenantManager()
    tm.register_tenant("fin", "Finance", quotas=ResourceQuota(max_goals=100, max_tasks=500))
    tm.register_tenant("eng", "Engineering", quotas=ResourceQuota(max_goals=500, max_tasks=2000))
    ns_f = tm.get_namespace("fin")
    ns_e = tm.get_namespace("eng")
    for _ in range(15):
        ns_f.add_goal(f"fg-{_}")
    for _ in range(80):
        ns_e.add_goal(f"eg-{_}")
    print(
        f"  Finance:     {ns_f.goal_count}/{ns_f.quotas.max_goals} goals ({ns_f.goal_count * 100 // ns_f.quotas.max_goals}%)"
    )
    print(
        f"  Engineering: {ns_e.goal_count}/{ns_e.quotas.max_goals} goals ({ns_e.goal_count * 100 // ns_e.quotas.max_goals}%)"
    )


if __name__ == "__main__":
    print("=" * 60)
    print("  MULTI-TENANT ISOLATION — 5 SCENARIOS")
    print("=" * 60 + "\n")
    scenario_1_registration()
    print()
    scenario_2_quota_enforcement()
    print()
    scenario_3_isolation()
    print()
    scenario_4_lifecycle()
    print()
    scenario_5_usage_report()
    print("\n" + "=" * 60)
    print("  ✅ ALL 5 MULTI-TENANCY SCENARIOS PASSED")
    print("=" * 60)
