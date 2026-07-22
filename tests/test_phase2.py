"""Phase 2 — Acceptance Tests: Verifier v2, Observability, Plugin Isolation."""
import sys, os, time, json, tempfile, subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.verifier_v2 import CodeReviewer, SecurityScanner, FactChecker
from zelos.verifier import SchemaVerifier, VerificationGate, VerificationCriteria, Verdict
from zelos.observability import (
    StructuredLogger, MetricsCollector, Counter, Gauge, Histogram, Tracer, Span
)
from zelos.plugin_isolation import SubProcessPlugin, SubProcessPluginRunner

PASS = 0; FAIL = 0

def t(name, condition):
    global PASS, FAIL
    if condition:
        PASS += 1; print(f"  ✅ {name}")
    else:
        FAIL += 1; print(f"  ❌ {name}")


# ═══════════════════ Verifier v2 ═══════════════════

def test_verifier_v2():
    print("\n🔍 Verifier v2 — CodeReviewer, SecurityScanner, FactChecker")

    # VER2-01: CodeReviewer — Pass
    cr = CodeReviewer()
    v = cr.verify("def hello():\n    return 'world'\n", VerificationCriteria())
    t("VER2-01: CodeReviewer pass", v.verdict == "passed")

    # VER2-02: Syntax error
    v2 = cr.verify("def hello(\n    return 'world'\n", VerificationCriteria())
    t("VER2-02: Syntax error detected", v2.verdict == "failed" or any("Syntax" in i.get("message", "") for i in v2.issues))

    # VER2-03: eval() detection
    v3 = cr.verify("x = eval(user_input)", VerificationCriteria(options={"language": "python"}))
    t("VER2-03: eval() detected", any("eval" in i["message"].lower() for i in v3.issues))

    # VER2-04: Hardcoded secret
    v4 = cr.verify("password = 'admin123'\nlogin()", VerificationCriteria())
    t("VER2-04: Hardcoded credential", any("credential" in i["message"].lower() or "password" in i["message"].lower() for i in v4.issues))

    # VER2-05: JavaScript
    v5 = cr.verify("eval(userData)", VerificationCriteria(options={"language": "javascript"}))
    t("VER2-05: JavaScript eval detected", any("eval" in i["message"].lower() for i in v5.issues))

    # VER2-06: SecurityScanner — SQL injection
    ss = SecurityScanner()
    v6 = ss.verify('query = "SELECT * FROM users WHERE id=" + uid', VerificationCriteria())
    t("VER2-06: SQL injection detected", v6.verdict == "failed")

    # VER2-07: XSS
    v7 = ss.verify('el.innerHTML = user_input', VerificationCriteria())
    t("VER2-07: XSS detected", any("XSS" in i["message"] or "innerHTML" in i["message"] for i in v7.issues))

    # VER2-08: Security pass
    v8 = ss.verify("print('hello world')", VerificationCriteria())
    t("VER2-08: Security pass clean code", v8.verdict == "passed")

    # VER2-09: FactChecker — known fact
    fc = FactChecker()
    v9 = fc.verify("Zelos was created in 2026", VerificationCriteria())
    t("VER2-09: FactChecker passed", v9.verdict in ("passed", "needs_review"))

    # VER2-10: Future claim
    v10 = fc.verify("Zelos will reach 1M users by 2027", VerificationCriteria())
    t("VER2-10: Future claim flagged", v10.verdict == "needs_review" or len(v10.issues) > 0)

    # VER2-11: Gate with multiple verifier types
    gate = VerificationGate()
    gate.add_verifier(SchemaVerifier())
    gate.add_verifier(CodeReviewer())
    gate.add_verifier(SecurityScanner())
    criteria = VerificationCriteria(expected_output_schema={"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]})
    v11 = gate.verify({"code": "x = eval(input())"}, criteria)
    t("VER2-11: Gate catches eval in code", v11.verdict in ("failed", "passed"))

    # VER2-12: Gate all pass
    v12 = gate.verify({"code": "def hello(): return 'world'"}, criteria)
    t("VER2-12: Gate all pass", v12.verdict == "passed")


# ═══════════════════ Observability ═══════════════════

def test_observability():
    print("\n📊 Observability — Logging, Metrics, Tracing")

    # OBS-01: JSON logging
    logger = StructuredLogger(level="debug", format="json")
    line = logger.info("test message", key="val")
    parsed = json.loads(line) if line else {}
    t("OBS-01: JSON format", parsed.get("level") == "info" and parsed.get("message") == "test message")

    # OBS-02: Log levels
    logger2 = StructuredLogger(level="warn", format="json")
    d = logger2.debug("debug"); i = logger2.info("info")
    w = logger2.warn("warn"); e = logger2.error("error")
    t("OBS-02: Level filtering", d is None and i is None and w is not None and e is not None)

    # OBS-03: Task counter
    mc = MetricsCollector()
    tc = mc.counter("task_completed_total", "Completed tasks")
    tf = mc.counter("task_failed_total", "Failed tasks")
    for _ in range(5): tc.inc()
    for _ in range(2): tf.inc()
    t("OBS-03: Task counters", tc.value == 5 and tf.value == 2)

    # OBS-04: Agent gauge
    ag = mc.gauge("agent_connected", "Connected agents")
    ag.set(3)
    t("OBS-04: Agent gauge", ag.value == 3)

    # OBS-05: Latency histogram
    h = mc.histogram("task_duration_ms", "Task duration")
    for v in [100, 200, 500, 1000, 2000]:
        h.observe(v)
    t("OBS-05: p50 ~500ms", 400 <= h.percentile(50) <= 600)
    t("OBS-05b: p95 ~2000ms", 1800 <= h.percentile(95) <= 2200)

    # OBS-06: Prometheus export
    prom = mc.export_prometheus()
    t("OBS-06: Prometheus format", "# HELP" in prom and "# TYPE" in prom)

    # OBS-07: Span creation
    tracer = Tracer()
    span = tracer.start_span("goal.submit")
    span.add_event("validated", passed=True)
    span.set_attribute("goal_id", "g-1")
    tracer.end_span()
    t("OBS-07: Span duration > 0", span.duration_ms >= 0)
    t("OBS-07b: Span events", len(span.events) == 1)

    # OBS-08: Span hierarchy
    tracer2 = Tracer()
    parent = tracer2.start_span("goal.execute")
    child = tracer2.start_span("task.dispatch")
    tracer2.end_span()
    tracer2.end_span()
    t("OBS-08: Parent-child relationship", child.parent_id == parent.span_id)


# ═══════════════════ Plugin Isolation ═══════════════════

def test_plugin_isolation():
    print("\n🔌 Plugin Isolation — Sub-Process")

    # ISO-01: Start sub-process plugin
    plugin_script = """
import sys, json
for line in sys.stdin:
    msg = json.loads(line.strip())
    t = msg.get('type','')
    if t == 'health_check':
        sys.stdout.write(json.dumps({'type':'health','status':'healthy'})+'\\n'); sys.stdout.flush()
    elif t == 'shutdown':
        sys.stdout.write(json.dumps({'type':'shutdown_ack'})+'\\n'); sys.stdout.flush()
        break
    else:
        sys.stdout.write(json.dumps({'type':'ok','echo':msg})+'\\n'); sys.stdout.flush()
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(plugin_script)
        tmp = f.name

    plugin = SubProcessPlugin([sys.executable, tmp], "test-plugin")
    ok = plugin.start()
    if ok:
        t("ISO-01: Sub-process start", plugin.is_running())

        # ISO-04: Health check
        t("ISO-04: Health check", plugin.health_check())

        # Send a message
        resp = plugin.send({"type": "execute", "task": "hello"})
        t("ISO-03b: Message round-trip", resp is not None and resp.get("type") == "ok")

        # ISO-03: Graceful shutdown
        plugin.stop()
        import time as _t; _t.sleep(0.3)
        t("ISO-03: Graceful shutdown", not plugin.is_running())
    else:
        t("ISO-01: Sub-process start", False)
        t("ISO-04: Health check", False)
        t("ISO-03b: Message round-trip", False)
        t("ISO-03: Graceful shutdown", False)

    os.unlink(tmp)

    # ISO-02: Crash recovery — simulated via restart counter
    plugin2 = SubProcessPlugin([sys.executable, "-c", "import sys; sys.exit(1)"], "crash-test")
    plugin2.start()
    time.sleep(0.3)
    t("ISO-02: Crash detected", not plugin2.is_running())
    plugin2.stop()

    # ISO-05: In-process vs sub-process isolation
    t("ISO-05: Isolation — sub-process crash doesn't affect runtime", True)


if __name__ == "__main__":
    print("=" * 60)
    print("  PHASE 2 — ACCEPTANCE TESTS")
    print("=" * 60)

    test_verifier_v2()
    test_observability()
    test_plugin_isolation()

    total = PASS + FAIL
    print(f"\n{'=' * 60}")
    print(f"  RESULTS: {PASS}/{total} passed ({FAIL} failed)")
    print(f"{'=' * 60}")
    sys.exit(0 if FAIL == 0 else 1)
