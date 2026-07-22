"""
Demo 13: Security — Access Control, Audit Logging, API Key Management

Demonstrates Phase 3 security features:
  - RBAC with wildcard permissions
  - Audit logging with multi-field query
  - API key lifecycle management

Run: python3 demo/13_security.py
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.security import AccessControl, AuditLogger, APIKeyManager


def main():
    print("=" * 60)
    print("  DEMO 13: Security — Access Control + Audit + API Keys")
    print("=" * 60)

    # ── 1. Role-Based Access Control ──
    print("\n📋 1. Role-Based Access Control (RBAC)")
    ac = AccessControl()

    print(f"   Default roles: {', '.join(ac.roles.keys())}")

    # Check permissions
    checks = [
        ("admin", "goal.submit"),
        ("admin", "agent.delete"),
        ("operator", "goal.submit"),
        ("operator", "agent.delete"),
        ("agent", "task.execute"),
        ("agent", "goal.submit"),
        ("viewer", "goal.read"),
        ("viewer", "goal.submit"),
    ]
    for role, action in checks:
        result = "✅ ALLOW" if ac.check(role, action) else "❌ DENY"
        print(f"   {role:12s} → {action:20s} : {result}")

    # Custom role
    print("\n   Adding custom role: 'sre'")
    ac.add_role("sre", ["goal.read", "metrics.read", "agent.read", "plugin.configure"])
    print(f"   Custom role permissions: {ac.list_permissions('sre')}")

    # ── 2. Audit Logging ──
    print("\n📝 2. Audit Logging")
    al = AuditLogger()

    # Log some events
    events = [
        ("admin", "goal.submit", "g-001", "Deploy v2.0 to production", "success"),
        ("agent-codex", "task.execute", "t-001", "Generated React component", "success"),
        ("admin", "agent.register", "agent-3", "Registered new security scanner", "success"),
        ("operator", "goal.cancel", "g-002", "Budget exceeded: $150 > $100 limit", "denied"),
        ("agent-codex", "task.execute", "t-003", "Code review failed security scan", "failed"),
    ]
    for actor, action, resource, detail, result in events:
        al.log(actor, action, resource, detail=detail, result=result)

    print(f"   Total audit events: {al.total_events()}")

    # Query examples
    print(f"   Events by 'admin': {len(al.query(actor='admin'))}")
    print(f"   Failed events: {len(al.query(result='failed'))}")
    print(f"   Events on g-001: {len(al.query(resource='g-001'))}")

    # JSON export (first 2 events)
    exported = json.loads(al.export_json())
    for e in exported[:2]:
        print(f"   [{e['actor']}] {e['action']} → {e['resource']}: {e['detail'][:50]}")

    # ── 3. API Key Management ──
    print("\n🔑 3. API Key Management")
    akm = APIKeyManager()

    # Generate keys
    admin_key = akm.generate_key("admin", "Production admin key")
    agent_key = akm.generate_key("agent", "CI/CD agent key", ttl_seconds=3600)
    viewer_key = akm.generate_key("viewer", "Dashboard viewer", ttl_seconds=0.001)

    print(f"   Admin key: {admin_key[:20]}... (full access)")
    print(f"   Agent key: {agent_key[:20]}... (expires in 1h)")
    print(f"   Viewer key: {viewer_key[:20]}... (0.001s TTL)")

    # Validate
    admin_valid = akm.validate(admin_key)
    agent_valid = akm.validate(agent_key)
    time.sleep(0.01)
    viewer_valid = akm.validate(viewer_key)

    print(f"\n   Admin key valid: {admin_valid is not None} → role: {admin_valid['role'] if admin_valid else 'N/A'}")
    print(f"   Agent key valid: {agent_valid is not None} → role: {agent_valid['role'] if agent_valid else 'N/A'}")
    print(f"   Viewer key valid (expired): {viewer_valid is not None}")

    # Revoke
    akm.revoke(agent_key)
    print(f"\n   Agent key after revoke: {akm.validate(agent_key) is not None}")

    # List all keys
    keys = akm.list_keys()
    print(f"\n   Registered keys: {len(keys)}")
    for k in keys:
        print(f"   - {k['key_hash']}: {k['role']} ({'revoked' if k['revoked'] else 'active'})")

    print(f"\n{'=' * 60}")
    print(f"  Demo complete. All security primitives working.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
