"""Phase 1 Remaining — Acceptance Tests: Config Loader, Verifier, Policy, Memory."""

import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.config_loader import ConfigLoader, load_config
from zelos.memory import ContextAssembler, InMemoryMemoryProvider, MemoryLayer
from zelos.policy import AllowlistPolicy, CompositePolicy, CostLimitPolicy, RateLimitPolicy
from zelos.verifier import SchemaVerifier, Verdict, VerificationCriteria, VerificationGate, Verifier

PASS = 0
FAIL = 0


def check(name, condition):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name}")


def assert_raises(exc_type, fn, *a, **kw):
    try:
        fn(*a, **kw)
        return False
    except exc_type:
        return True
    except Exception:
        return False


# ═══════════════════ Config Loader ═══════════════════


def test_config_loader():
    print("\n📄 Config Loader")

    # CFG-01: Load valid YAML
    yaml_content = """
runtime:
  instance_id: test-instance
  api:
    port: 9999
plugins:
  - id: my-planner
    type: planner
    entrypoint: test.planner
    config:
      model: gpt-4o
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        tmp = f.name
    loader = ConfigLoader()
    config = loader.load(tmp)
    os.unlink(tmp)
    check("CFG-01: Load valid YAML", config["runtime"]["api"]["port"] == 9999)
    check("CFG-01b: Plugins loaded", len(config["plugins"]) == 1)

    # CFG-02: File not found
    ok = assert_raises(FileNotFoundError, ConfigLoader().load, "/nonexistent/path.yaml")
    check("CFG-02: File not found", ok)

    # CFG-03: Invalid plugin type
    ok2 = assert_raises(
        ValueError, ConfigLoader().load_dict, {"plugins": [{"id": "bad", "type": "invalid-type", "entrypoint": "x"}]}
    )
    check("CFG-03: Invalid plugin type rejected", ok2)

    # CFG-04: Missing id
    ok3 = assert_raises(ValueError, ConfigLoader().load_dict, {"plugins": [{"type": "planner"}]})
    check("CFG-04: Missing id rejected", ok3)

    # CFG-05: Runtime defaults
    config2 = ConfigLoader().load_dict({})
    check("CFG-05: Default port", config2["runtime"]["api"]["port"] == 9876)
    check("CFG-05b: Default host", config2["runtime"]["api"]["host"] == "127.0.0.1")

    # CFG-06: Auth keys
    config3 = ConfigLoader().load_dict(
        {
            "runtime": {
                "auth": {
                    "keys": [
                        {"key": "sk-admin", "role": "admin"},
                        {"key": "sk-agent", "role": "agent"},
                    ]
                }
            }
        }
    )
    keys = config3["runtime"]["auth"]["keys"]
    check("CFG-06: Auth key role", keys[0]["role"] == "admin" and keys[1]["role"] == "agent")

    # load_config convenience
    cfg = load_config(None)
    check("CFG-06b: load_config defaults", cfg["runtime"]["instance_id"] == "zelos-default")


# ═══════════════════ Verifier ═══════════════════


def test_verifier():
    print("\n🔍 Verifier")

    sv = SchemaVerifier()

    # VER-01: Schema pass
    criteria = VerificationCriteria(
        expected_output_schema={
            "type": "object",
            "properties": {"code": {"type": "string"}, "language": {"type": "string"}},
            "required": ["code", "language"],
        }
    )
    artifact = {"code": "print('hello')", "language": "python"}
    v = sv.verify(artifact, criteria)
    check("VER-01: Schema pass", v.verdict == "passed" and v.score == 1.0)

    # VER-02: Type mismatch
    v2 = sv.verify("not an object", criteria)
    check("VER-02: Type mismatch", v2.verdict == "failed")

    # VER-03: Missing required field
    v3 = sv.verify({"code": "x"}, criteria)  # missing "language"
    check("VER-03: Missing required", v3.verdict == "failed" and any("language" in i["message"] for i in v3.issues))

    # VER-04: No verifier → accept
    gate = VerificationGate()
    v4 = gate.verify({"data": "any"}, VerificationCriteria())
    check("VER-04: No verifier → accepted", v4.verdict == "passed")

    # VER-05: Multiple verifiers — sequential, first fails
    class FailingVerifier(Verifier):
        def verify(self, content, criteria):
            return Verdict(
                "failed", 0.0, self.verifier_id, issues=[{"severity": "error", "message": "fail"}], summary="fail"
            )

    gate2 = VerificationGate()
    gate2.add_verifier(FailingVerifier("bad-verifier"))
    gate2.add_verifier(sv)
    v5 = gate2.verify({"code": "x"}, criteria)
    check("VER-05: First fails → reject", v5.verdict == "failed" and v5.verifier_id == "bad-verifier")

    # VER-06: Verdict structure
    v6 = sv.verify(artifact, criteria)
    check(
        "VER-06: Verdict structure",
        all(k in v6.to_dict() for k in ["verdict", "score", "verifier_id", "issues", "summary", "checked_at"]),
    )

    # VER-07: content_ref
    v7 = sv.verify({"content_ref": "s3://bucket/artifact"}, criteria)
    check("VER-07: content_ref handled", v7.verdict == "passed")

    # Additional: SchemaVerifier fields
    check("VER-01b: issues empty on pass", len(v.issues) == 0)
    check("VER-02b: issues on fail", len(v2.issues) > 0)


# ═══════════════════ Policy ═══════════════════


def test_policy():
    print("\n📏 Policy Engine")

    # POL-01: Cost limit — under budget
    cp = CostLimitPolicy({"max_cost_per_goal": 100.0})
    result = cp.evaluate({"goal_id": "g1", "task_cost": 5.0})
    check("POL-01: Cost under budget → allow", result == "allow")

    # POL-02: Cost limit — over budget
    cp.record_cost("g1", 70.0)
    result2 = cp.evaluate({"goal_id": "g1", "task_cost": 50.0})
    check("POL-02: Cost over budget → reject", result2 == "reject")

    # POL-03: Rate limit — within limit
    rp = RateLimitPolicy({"max_tasks_per_minute": 60})
    for _ in range(30):
        rp.evaluate({})
    result3 = rp.evaluate({})
    check("POL-03: Rate within limit → allow", result3 == "allow")

    # POL-04: Rate limit — exceeded
    rp2 = RateLimitPolicy({"max_tasks_per_minute": 5})
    for _ in range(6):
        rp2.evaluate({})
    result4 = rp2.evaluate({})
    check("POL-04: Rate exceeded → reject", result4 == "reject")

    # POL-05: Allowlist — agent in list
    ap = AllowlistPolicy({"allowlist_agents": ["agt-1", "agt-2"]})
    check("POL-05: Agent in list → allow", ap.evaluate({"agent_id": "agt-2"}) == "allow")

    # POL-06: Allowlist — agent NOT in list
    check("POL-06: Agent not in list → reject", ap.evaluate({"agent_id": "agt-3"}) == "reject")

    # POL-07: Composite — all pass
    comp = CompositePolicy(
        [
            CostLimitPolicy({"max_cost_per_goal": 100}),
            AllowlistPolicy({"allowlist_agents": ["agt-1"]}),
        ]
    )
    check(
        "POL-07: Composite all pass", comp.evaluate({"goal_id": "g2", "task_cost": 5, "agent_id": "agt-1"}) == "allow"
    )

    # POL-08: Composite — first fails (cost)
    cp2 = CostLimitPolicy({"max_cost_per_goal": 100})
    cp2.record_cost("g3", 95.0)
    comp2 = CompositePolicy([cp2, AllowlistPolicy({"allowlist_agents": ["agt-1"]})])
    check(
        "POL-08: Composite first fails → reject",
        comp2.evaluate({"goal_id": "g3", "task_cost": 20, "agent_id": "agt-1"}) == "reject",
    )


# ═══════════════════ Memory ═══════════════════


def test_memory():
    print("\n🧠 Memory")

    mem = InMemoryMemoryProvider()

    # MEM-01: Store and retrieve
    mem.store("session", "key1", "value1")
    check("MEM-01: Store/retrieve", mem.retrieve("session", "key1") == "value1")

    # MEM-02: Separate layers
    mem.store("session", "k", "session_val")
    mem.store("project", "k", "project_val")
    check("MEM-02: Layer isolation", mem.retrieve("session", "k") != mem.retrieve("project", "k"))

    # MEM-03: Six layers
    for layer in MemoryLayer.ALL:
        mem.store(layer, "test", f"val-{layer}")
    for layer in MemoryLayer.ALL:
        r = mem.retrieve(layer, "test")
        check(f"MEM-03: {layer} layer works", r == f"val-{layer}")

    # MEM-04: Update
    mem.store("session", "upd", "v1")
    mem.update("session", "upd", "v2")
    check("MEM-04: Update", mem.retrieve("session", "upd") == "v2")

    # MEM-05: Update non-existent
    ok = assert_raises(KeyError, mem.update, "session", "nonexistent", "val")
    check("MEM-05: Update non-existent → error", ok)

    # MEM-06: Delete
    mem.store("session", "del-me", "val")
    mem.delete("session", "del-me")
    check("MEM-06: Delete", mem.retrieve("session", "del-me") is None)

    # MEM-07: Search
    mem.store("session", "task-code", {"desc": "write code"})
    mem.store("session", "task-review", {"desc": "review code"})
    results = mem.search("session", "code")
    check("MEM-07: Search finds matches", len(results) >= 2)

    # MEM-08: TTL expiry
    mem.store("session", "ttl-key", "ephemeral", ttl_seconds=0.1)
    time.sleep(0.2)
    check("MEM-08: TTL expiry", mem.retrieve("session", "ttl-key") is None)

    # MEM-09: Context assembly
    assembler = ContextAssembler(mem)
    ctx = assembler.assemble("task-1", "goal-1")
    check("MEM-09: Context session key", "session" in ctx)
    check("MEM-09b: Context project key", "project" in ctx)
    check("MEM-09c: Context user key", "user" in ctx)
    check("MEM-09d: Context knowledge key", "knowledge" in ctx)

    # MEM-10: Max entries per layer
    mem2 = InMemoryMemoryProvider({"max_entries_per_layer": 3})
    for i in range(5):
        mem2.store("session", f"k{i}", f"v{i}")
    # Should have only last 3 (k2, k3, k4) — oldest 2 evicted
    check("MEM-10: Max entries", mem2.retrieve("session", "k0") is None and mem2.retrieve("session", "k4") == "v4")

    # Invalid layer
    ok2 = assert_raises(ValueError, mem.store, "invalid_layer", "k", "v")
    check("MEM-10b: Invalid layer rejected", ok2)


if __name__ == "__main__":
    print("=" * 60)
    print("  PHASE 1 REMAINING — ACCEPTANCE TESTS")
    print("=" * 60)

    test_config_loader()
    test_verifier()
    test_policy()
    test_memory()

    total = PASS + FAIL
    print(f"\n{'=' * 60}")
    print(f"  RESULTS: {PASS}/{total} passed ({FAIL} failed)")
    print(f"{'=' * 60}")
    sys.exit(0 if FAIL == 0 else 1)
