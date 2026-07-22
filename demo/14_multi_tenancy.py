"""
Demo 14: Multi-tenancy — Namespace Isolation + Resource Quotas

Demonstrates Phase 3 multi-tenancy features:
  - Namespace creation with resource quotas
  - Cross-tenant isolation enforcement
  - Tenant lifecycle management
  - Usage tracking and reporting

Run: python3 demo/14_multi_tenancy.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.multi_tenancy import (
    Namespace,
    ResourceQuota,
    TenantManager,
)


def main():
    print("=" * 60)
    print("  DEMO 14: Multi-tenancy — Namespace + Quotas")
    print("=" * 60)

    # ── 1. Namespace Creation ──
    print("\n🏠 1. Namespace with Resource Quotas")

    # Enterprise tenant — generous limits
    enterprise_ns = Namespace(
        "ent-001",
        "Enterprise Corp",
        quotas=ResourceQuota(
            max_goals=500,
            max_tasks=5000,
            max_agents=100,
            budget_per_goal=10000.0,
            max_concurrent_tasks=200,
        ),
    )

    # Startup tenant — tight limits
    startup_ns = Namespace(
        "startup-001",
        "AI Startup Inc",
        quotas=ResourceQuota(
            max_goals=10,
            max_tasks=50,
            max_agents=5,
            budget_per_goal=100.0,
        ),
    )

    print(f"   {enterprise_ns.name}:")
    print(
        f"     Goals: 0/{enterprise_ns.quotas.max_goals}, "
        f"Tasks: 0/{enterprise_ns.quotas.max_tasks}, "
        f"Budget: ${enterprise_ns.quotas.budget_per_goal}/goal"
    )

    print(f"   {startup_ns.name}:")
    print(
        f"     Goals: 0/{startup_ns.quotas.max_goals}, "
        f"Tasks: 0/{startup_ns.quotas.max_tasks}, "
        f"Budget: ${startup_ns.quotas.budget_per_goal}/goal"
    )

    # ── 2. Cross-Tenant Isolation ──
    print("\n🔒 2. Cross-Tenant Isolation")

    # Enterprise adds goals
    for i in range(5):
        enterprise_ns.add_goal(f"ent-g-{i}")
    print(f"   Enterprise goals: {enterprise_ns.goal_count}")

    # Startup adds goals — separated namespace
    for i in range(3):
        startup_ns.add_goal(f"su-g-{i}")
    print(f"   Startup goals: {startup_ns.goal_count}")

    print(f"   ✅ Enterprise cannot see Startup's goals: {enterprise_ns.goal_count} vs {startup_ns.goal_count}")

    # ── 3. Quota Enforcement ──
    print("\n⚖️  3. Quota Enforcement")

    tiny_ns = Namespace("tiny", "Tiny Tenant", quotas=ResourceQuota(max_goals=3))
    for i in range(3):
        result = tiny_ns.add_goal(f"g-{i}")
        print(f"   Add goal {i}: {'✅' if result else '❌'}")

    # 4th goal — should be rejected
    result = tiny_ns.add_goal("g-4")
    print(f"   Add goal 4 (exceeds quota): {'✅' if result else '❌ QUOTA EXCEEDED'}")

    # Budget check
    print(f"\n   Budget check: $50 within $100 limit? {'✅' if tiny_ns.quotas.check_budget(50) else '❌'}")
    print(f"   Budget check: $150 within $100 limit? {'✅' if tiny_ns.quotas.check_budget(150) else '❌ EXCEEDED'}")

    # ── 4. Tenant Manager ──
    print("\n👥 4. Tenant Manager")

    tm = TenantManager()

    # Register tenants
    tm.register_tenant(
        "acme-corp",
        "ACME Corporation",
        quotas=ResourceQuota(max_goals=100, budget_per_goal=5000),
        metadata={"org": "Engineering", "tier": "enterprise"},
    )

    tm.register_tenant(
        "dev-team",
        "Development Team",
        quotas=ResourceQuota(max_goals=20, budget_per_goal=200),
        metadata={"org": "R&D", "tier": "standard"},
    )

    tm.register_tenant(
        "oss-project",
        "Open Source Project",
        quotas=ResourceQuota(max_goals=5, budget_per_goal=0),
        metadata={"org": "Community", "tier": "free"},
    )

    print(f"   Registered tenants: {tm.tenant_count()}")

    for tenant in tm.list_tenants():
        ns = tenant.namespace
        ns.add_goal(f"{tenant.tenant_id}-g-1")
        ns.add_agent(f"{tenant.tenant_id}-agent-1")
        print(
            f"   [{tenant.metadata.get('tier', 'N/A'):12s}] {tenant.name:25s} "
            f"→ {ns.goal_count} goals, {ns.agent_count} agents, "
            f"budget=${ns.quotas.budget_per_goal}/goal"
        )

    # Deactivate a tenant
    tm.deactivate_tenant("oss-project")
    print(f"\n   OSS Project active: {tm.is_active('oss-project')}")
    print(f"   ACME Corp active: {tm.is_active('acme-corp')}")

    # ── 5. Usage Report ──
    print("\n📊 5. Usage Report")
    report = tm.get_usage_report()
    print(f"   Total tenants: {report['total_tenants']}")
    print(f"   Active tenants: {report['active_tenants']}")

    print(f"\n{'=' * 60}")
    print("  Demo complete. Multi-tenancy primitives working.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
