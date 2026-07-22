"""Protocol Adapters — Acceptance Tests: gRPC, WebSocket, MCP, A2A."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.protocol_adapters import GRPCAdapter, WebSocketAdapter, MCPAdapter, A2AAdapter
from zelos.runtime import ZelosRuntime
from zelos.event_bus import Event

PASS = 0; FAIL = 0

def t(name, condition):
    global PASS, FAIL
    if condition:
        PASS += 1; print(f"  ✅ {name}")
    else:
        FAIL += 1; print(f"  ❌ {name}")

def test_protocol_adapters():
    print("\n🌐 Protocol Adapters")

    rt = ZelosRuntime()
    rt.add_agent("TestAgent", "test:Agent", [
        type('C', (), {'name': 'code-generation.python', 'version': '1.0.0', 'description': 'test', 'input_schema': {}, 'output_schema': {}, 'tags': []})
    ])
    rt.start()

    # ── gRPC Adapter ──
    grpc = GRPCAdapter(rt)

    # PROT-01: SubmitGoal via gRPC
    result = grpc.SubmitGoal({"description": "Test gRPC goal", "priority": "high"})
    t("PROT-01: gRPC SubmitGoal", result.get("status") in ("accepted", "planned") and len(result.get("goal_id", "")) > 0)

    # PROT-02: RegisterAgent via gRPC
    agent_result = grpc.RegisterAgent({"name": "GRPCAgent", "capabilities": [
        {"name": "code-generation.python", "version": "1.0.0"}
    ]})
    t("PROT-02: gRPC RegisterAgent", "agent_id" in agent_result and agent_result["status"] == "registered")

    # PROT-02b: GetGoalStatus
    status = grpc.GetGoalStatus({"goal_id": result["goal_id"]})
    t("PROT-02b: gRPC GetGoalStatus", status is not None and "status" in status)

    # Heartbeat
    hb = grpc.AgentHeartbeat({"agent_id": agent_result["agent_id"]})
    t("PROT-02c: gRPC Heartbeat", hb["status"] == "ok")

    # GetHealth / GetMetrics
    health = grpc.GetHealth()
    t("PROT-02d: gRPC GetHealth", "status" in health)
    metrics = grpc.GetMetrics()
    t("PROT-02e: gRPC GetMetrics", "goals" in metrics)

    # ── WebSocket Adapter ──
    ws = WebSocketAdapter(rt)
    ws.start()

    ws.register_client("client-1")
    ws.watch_goal("client-1", result["goal_id"])

    # Publish a goal event
    import uuid, time as _t
    rt._event_bus.publish(Event(
        str(uuid.uuid4()), "goal.planned", "test", _t.time(), result["goal_id"],
        payload={"goal_id": result["goal_id"]}
    ))

    events = ws.get_events("client-1")
    t("PROT-07: WebSocket goal events", len(events) >= 1)
    t("PROT-08: WebSocket event type", any(e.get("event_type") == "goal.planned" for e in events))

    ws.unregister_client("client-1")
    ws.stop()

    # ── MCP Adapter ──
    mcp = MCPAdapter(rt)
    mcp.register_tool("read_file", "http://tool-server:3000", {
        "description": "Read a file from the filesystem",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}},
    })
    mcp.register_tool("web_search", "http://tool-server:3000", {
        "description": "Search the web",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
    })

    tools = mcp.list_tools()
    t("PROT-03: MCP list tools", len(tools) == 2)
    t("PROT-04: MCP call tool", "content" in mcp.call_tool("read_file", {"path": "/tmp/test"}))

    # ── A2A Adapter ──
    a2a = A2AAdapter(rt)

    # PROT-05: Agent Card
    agents = rt.list_agents()
    agent_info = agents[0] if agents else {}
    card = a2a.generate_agent_card(agent_info.get("agent_id", "")) if agent_info else {}
    t("PROT-05: A2A agent card", isinstance(card, dict) and "skills" in card)

    # PROT-06: External task reception
    task_id = a2a.receive_external_task({"description": "External A2A task", "priority": "medium"})
    t("PROT-06: A2A receive task", task_id is not None and len(task_id) > 0)

    # Register external agent
    ext_id = a2a.register_external_agent({"name": "ExternalBot", "skills": [{"name": "image-gen"}]})
    t("PROT-06b: A2A register external agent", len(ext_id) > 0)

    rt.shutdown()


if __name__ == "__main__":
    print("=" * 60)
    print("  PROTOCOL ADAPTERS — ACCEPTANCE TESTS")
    print("=" * 60)
    test_protocol_adapters()
    total = PASS + FAIL
    print(f"\n{'=' * 60}")
    print(f"  RESULTS: {PASS}/{total} passed ({FAIL} failed)")
    print(f"{'=' * 60}")
    sys.exit(0 if FAIL == 0 else 1)
