"""
Phase 2 Protocol Adapters — gRPC, MCP, A2A, WebSocket.

Each adapter translates an external protocol → Runtime API.
Adapters contain ZERO business logic. They are stateless, replaceable plugins.

Architecture:
  Protocol Adapter (translate) → Runtime API → Kernel
"""

import threading
import time
from abc import ABC, abstractmethod
from typing import Any

# ═══════════════════ Adapter Base ═══════════════════


class ProtocolAdapter(ABC):
    """Base for all protocol adapters."""

    def __init__(self, runtime=None):
        self.runtime = runtime

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...


# ═══════════════════ gRPC Adapter ═══════════════════


class GRPCAdapter(ProtocolAdapter):
    """
    gRPC Adapter — translates gRPC calls to Runtime API.

    Proto service definition (zelos.proto):

      service Zelos {
        rpc SubmitGoal(SubmitGoalRequest) returns (GoalResponse);
        rpc GetGoalStatus(GetGoalStatusRequest) returns (GoalStatusResponse);
        rpc CancelGoal(CancelGoalRequest) returns (GoalStatusResponse);
        rpc WatchGoal(WatchGoalRequest) returns (stream Event);
        rpc RegisterAgent(RegisterAgentRequest) returns (AgentResponse);
        rpc AgentHeartbeat(HeartbeatRequest) returns (HeartbeatResponse);
        rpc SubmitResult(SubmitResultRequest) returns (SubmitResultResponse);
        rpc GetHealth(Empty) returns (HealthResponse);
        rpc GetMetrics(Empty) returns (MetricsResponse);
      }

    Phase 2: Full service handler implementation. For production,
    use grpcio to create the server with generated stubs.
    """

    def __init__(self, runtime=None, host: str = "0.0.0.0", port: int = 50051):
        super().__init__(runtime)
        self.host = host
        self.port = port
        self._running = False

    def start(self) -> None:
        self._running = True
        # In production: grpc.server with generated ZelosServicer
        # Phase 2 reference: service handlers below

    def stop(self) -> None:
        self._running = False

    # ── Service Handlers ──

    def SubmitGoal(self, request: dict) -> dict:
        """gRPC → Runtime API: SubmitGoal."""
        if not self.runtime:
            return {"goal_id": "", "status": "rejected", "reason": "Runtime not connected"}
        return self.runtime.submit_goal(
            description=request.get("description", ""),
            budget=request.get("budget"),
            deadline=request.get("deadline"),
            priority=request.get("priority", "medium"),
        )

    def GetGoalStatus(self, request: dict) -> dict:
        if not self.runtime:
            return {"goal_id": "", "status": "not_found"}
        return self.runtime.get_goal_status(request["goal_id"]) or {"status": "not_found"}

    def CancelGoal(self, request: dict) -> dict:
        if not self.runtime:
            return {}
        return self.runtime.cancel_goal(request["goal_id"]) or {}

    def RegisterAgent(self, request: dict) -> dict:
        if not self.runtime:
            return {"agent_id": "", "status": "rejected"}
        agent_id = self.runtime.add_agent(
            name=request.get("name", "grpc-agent"),
            entrypoint=request.get("entrypoint", ""),
            capabilities=request.get("capabilities", []),
        )
        return {
            "agent_id": agent_id,
            "status": "registered",
            "heartbeat_interval_ms": 30000,
            "runtime_version": "0.7.0",
        }

    def AgentHeartbeat(self, request: dict) -> dict:
        if not self.runtime:
            return {"status": "re-register"}
        ok = self.runtime._execution_engine.heartbeat(request["agent_id"])
        return {"status": "ok" if ok else "re-register", "pending_tasks": 0}

    def SubmitResult(self, request: dict) -> dict:
        if not self.runtime:
            return {"status": "rejected"}
        ok = self.runtime._execution_engine.submit_result(
            request.get("task_id", ""), request.get("agent_id", ""), request.get("result", {})
        )
        return {"status": "accepted" if ok else "rejected"}

    def GetHealth(self, _=None) -> dict:
        return self.runtime.get_health() if self.runtime else {"status": "unhealthy"}

    def GetMetrics(self, _=None) -> dict:
        return self.runtime.get_metrics() if self.runtime else {}


# ═══════════════════ WebSocket Adapter ═══════════════════


class WebSocketAdapter(ProtocolAdapter):
    """
    WebSocket Adapter — streams Events to connected clients.

    Supports:
      - watch_goal(goal_id): stream all events for a Goal
      - watch_tasks(pattern): stream task.* events
      - health streaming

    Phase 2: Reference implementation using a simple event subscription model.
    """

    def __init__(self, runtime=None):
        super().__init__(runtime)
        self._clients: dict[str, dict] = {}  # client_id → {subscriptions, queue}
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._running = True
        if self.runtime:
            # Subscribe to all major event domains
            for domain in ["goal", "task", "plan", "agent", "artifact", "verification", "plugin"]:
                self.runtime._event_bus.subscribe_pattern(f"{domain}.*", self._on_event)

    def stop(self) -> None:
        self._running = False
        self._clients.clear()

    def register_client(self, client_id: str) -> None:
        self._clients[client_id] = {"subscriptions": [], "queue": []}

    def unregister_client(self, client_id: str) -> None:
        self._clients.pop(client_id, None)

    def watch_goal(self, client_id: str, goal_id: str) -> None:
        if client_id in self._clients:
            self._clients[client_id]["subscriptions"].append(f"goal.{goal_id}")

    def get_events(self, client_id: str) -> list[dict]:
        """Drain event queue for a client."""
        if client_id not in self._clients:
            return []
        queue = self._clients[client_id]["queue"]
        events = list(queue)
        queue.clear()
        return events

    def _on_event(self, event) -> Any:
        """Fan out event to interested clients."""
        for _cid, client in self._clients.items():
            for sub in client["subscriptions"]:
                # Simple match: "goal.g-001" matches events with correlation_id
                parts = sub.split(".", 1)
                if len(parts) == 2 and event.correlation_id == parts[1]:
                    client["queue"].append(event.to_dict())
                elif event.event_type.startswith(sub):
                    client["queue"].append(event.to_dict())
        from zelos.event_bus import HandlerResult

        return HandlerResult.ACK


# ═══════════════════ MCP Adapter ═══════════════════


class MCPAdapter(ProtocolAdapter):
    """
    MCP (Model Context Protocol) Adapter.

    MCP is how Agents access TOOLS during Task execution — NOT how they
    communicate with the Runtime. The Runtime is unaware of MCP internals.

    Phase 2: MCP Server lifecycle management + Tool registry.
    """

    def __init__(self, runtime=None):
        super().__init__(runtime)
        self._tool_registry: dict[str, dict] = {}  # tool_name → {server, schema}

    def start(self) -> None: ...

    def stop(self) -> None: ...

    def register_tool(self, name: str, server_endpoint: str, schema: dict) -> None:
        """Register an MCP tool available to Agents."""
        self._tool_registry[name] = {"endpoint": server_endpoint, "schema": schema}

    def list_tools(self) -> list[dict]:
        """Return all registered MCP tools (MCP tools/list format)."""
        return [
            {
                "name": name,
                "description": info["schema"].get("description", ""),
                "inputSchema": info["schema"].get("input_schema", {}),
            }
            for name, info in self._tool_registry.items()
        ]

    def call_tool(self, name: str, arguments: dict) -> dict:
        """Invoke an MCP tool (MCP tools/call format)."""
        tool = self._tool_registry.get(name)
        if not tool:
            return {"isError": True, "content": [{"type": "text", "text": f"Tool not found: {name}"}]}
        # Phase 2: In production, forward to the tool server
        return {"content": [{"type": "text", "text": f"Tool '{name}' invoked with {arguments}"}]}


# ═══════════════════ A2A Adapter ═══════════════════


class A2AAdapter(ProtocolAdapter):
    """
    A2A (Agent-to-Agent Protocol) Adapter.

    A2A is an EXTERNAL interoperability protocol for:
      - Runtime ↔ Runtime coordination
      - External Agent integration
      - Third-party Agent services

    Key translation: A2A Agent Card ↔ Zelos Capability list
                     A2A Task ↔ Zelos Task
                     A2A Message ↔ Zelos Event

    A2A assumes direct agent-to-agent communication. Zelos PROHIBITS this.
    The A2A Adapter routes ALL A2A messages through the Runtime:
      A2A: Agent A → Agent B
      → Zelos: Agent A → Runtime → Agent B
    """

    def __init__(self, runtime=None):
        super().__init__(runtime)
        self._external_agents: dict[str, dict] = {}

    def start(self) -> None: ...

    def stop(self) -> None: ...

    def generate_agent_card(self, agent_id: str) -> dict:
        """Generate A2A Agent Card from Zelos Agent Capabilities."""
        if not self.runtime:
            return {}
        agent = self.runtime.get_agent(agent_id)
        if not agent:
            return {}
        return {
            "agentId": agent.get("agent_id", ""),
            "name": agent.get("name", ""),
            "description": f"Zelos Agent providing {len(agent.get('capabilities', []))} capabilities",
            "skills": [
                {"name": c["name"], "description": c.get("description", "")} for c in agent.get("capabilities", [])
            ],
            "endpoint": f"zelos://agents/{agent.get('agent_id', '')}",
        }

    def receive_external_task(self, task_data: dict) -> str | None:
        """Receive an A2A Task from an external system → create Zelos Task."""
        if not self.runtime:
            return None
        goal = self.runtime.submit_goal(
            description=task_data.get("description", "External A2A task"),
            priority=task_data.get("priority", "medium"),
        )
        return goal.get("goal_id")

    def register_external_agent(self, agent_card: dict) -> str:
        """Register an external (non-Zelos) Agent via its A2A Card."""
        import uuid

        aid = str(uuid.uuid4())
        self._external_agents[aid] = {
            "card": agent_card,
            "registered_at": time.time(),
        }
        return aid
