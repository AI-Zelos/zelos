# Python SDK

> The Python SDK is the primary developer interface for building Agents and submitting Goals to a Zelos Runtime. It wraps the Runtime API and provides a minimal, stable base class for Agent development.

---

## Document Status

| Status  | Author                     | Date       |
|---------|----------------------------|------------|
| New     | Zelos Architecture Team    | 2026-07-19 |

---

## 1. Overview

The Python SDK is the primary developer interface. It provides one central entry point — `ZelosRuntime` — that manages the entire Runtime lifecycle and all Agents, plus a minimal `Agent` base class for building agent implementations.

```python
# The entire developer experience boils down to this:
from zelos_sdk import ZelosRuntime

runtime = ZelosRuntime()
runtime.add_agent("MyCoder", entrypoint="...", capabilities=[...])
runtime.add_agent("MyReviewer", entrypoint="...", capabilities=[...])
runtime.start()
goal = runtime.submit_goal("Build a website")
result = runtime.wait_for_goal(goal.goal_id)
runtime.shutdown()
```

### 1.1 SDK Responsibilities

| Concern | SDK | Developer |
|---------|-----|-----------|
| Runtime Kernel lifecycle (start/shutdown) | ✅ | — |
| Agent lifecycle (spawn/heartbeat/restart/shutdown) | ✅ | — |
| Agent registration and capability indexing | ✅ | — |
| Hot-join / hot-leave agent management | ✅ | — |
| Goal submission and status tracking | ✅ | — |
| HTTP connection lifecycle | ✅ | — |
| Task deserialization | ✅ | — |
| Artifact construction helpers | ✅ | — |
| Task execution logic | — | ✅ (developer override) |
| Model selection / prompting | — | ✅ (developer override) |

### 1.2 Guiding Principles

1. **One entry point.** `ZelosRuntime` is the only class developers instantiate. Not three agents calling `run()` independently.
2. **Optional, not required.** The Agent protocol is implementable over raw HTTP. The SDK is a convenience.
3. **Minimal surface.** `ZelosRuntime` for orchestration (add/remove/start/shutdown/submit). `Agent` base class for execution (execute).
4. **Transport-agnostic internally.** The SDK uses the Runtime API data structures, not HTTP directly.
5. **No opinion about LLMs.** The SDK never references Claude, GPT, or any model.

---

## 2. ZelosRuntime (Central Entry Point)

`ZelosRuntime` is the only class developers instantiate. It owns the Runtime Kernel lifecycle and all Agent lifecycle. You don't start agents individually — you add them to the Runtime, and the Runtime manages them.

### 2.1 Interface

```python
class ZelosRuntime:
    """
    Central entry point for Zelos. Owns the Runtime Kernel and all Agents.

    Usage:
        runtime = ZelosRuntime()
        runtime.add_agent("Coder", entrypoint="...", capabilities=[...])
        runtime.add_agent("Reviewer", entrypoint="...", capabilities=[...])
        runtime.start()
        goal = runtime.submit_goal("Build a website")
        result = runtime.wait_for_goal(goal.goal_id)
        runtime.shutdown()
    """

    def __init__(
        self,
        *,
        config_path: str | None = None,     # Path to zelos.yaml
        host: str = "127.0.0.1",            # API bind address
        port: int = 9876,                   # API bind port
        api_keys: list[dict] | None = None, # [{"key": "...", "role": "admin"}, ...]
    ): ...

    # ── Agent Management ──

    def add_agent(
        self,
        name: str,
        entrypoint: str,                    # "module.path:ClassName"
        capabilities: list[CapabilityDeclaration],
        *,
        max_concurrent_tasks: int = 5,
        heartbeat_interval_ms: int = 30000,
        restart_policy: str = "always",     # "always" | "on_crash" | "never"
        config: dict | None = None,         # Agent-specific config
    ) -> str:
        """
        Register an agent with the Runtime.

        If called before start(): agent is queued and launched during start().
        If called after start(): agent is launched immediately (hot-join).

        Returns the agent_id.
        """

    def remove_agent(self, name_or_id: str) -> None:
        """
        Remove an agent from the Runtime (hot-leave).

        - In-flight tasks on this agent are cancelled and rescheduled.
        - Capabilities are removed from the Registry immediately.
        - Agent process is stopped gracefully.
        """

    def list_agents(self) -> list[AgentSummary]:
        """List all registered agents and their status."""
        ...

    def get_agent(self, name_or_id: str) -> AgentDetail:
        """Get detailed agent information."""
        ...

    # ── Runtime Lifecycle ──

    def start(self) -> None:
        """
        Start the Runtime Kernel and all registered agents.

        1. Start Kernel (Event Bus, Capability Registry, Scheduler, etc.)
        2. Load plugins from zelos.yaml
        3. Launch all registered agents
        4. Agents register, start heartbeating, become eligible for dispatch
        5. Runtime enters RUNNING state
        """

    def shutdown(self) -> None:
        """
        Graceful shutdown of the Runtime and all agents.

        1. Stop accepting new Goals
        2. Cancel in-flight tasks (or wait, per policy)
        3. Send shutdown signal to all agents
        4. Stop all plugins
        5. Stop Kernel
        """

    # ── Goal Submission ──

    def submit_goal(
        self,
        description: str,
        *,
        budget: float | None = None,
        deadline: str | None = None,        # ISO 8601
        priority: str = "medium",           # "low" | "medium" | "high" | "critical"
        project_id: str | None = None,
        metadata: dict | None = None,
    ) -> GoalResponse:
        """Submit a Goal to the Runtime. Returns immediately with goal_id."""
        ...

    def get_goal_status(self, goal_id: str) -> GoalStatusResponse: ...

    def list_goals(
        self, *, status: str | None = None, limit: int = 100
    ) -> list[GoalStatusResponse]: ...

    def cancel_goal(self, goal_id: str) -> GoalStatusResponse: ...

    def wait_for_goal(
        self,
        goal_id: str,
        *,
        timeout_seconds: float | None = None,
        poll_interval: float = 1.0,
    ) -> GoalStatusResponse:
        """Block until the Goal reaches a terminal state or timeout expires."""
        ...

    # ── Observability ──

    def get_health(self) -> HealthResponse: ...
    def get_metrics(self) -> MetricsResponse: ...
```

### 2.2 Minimal Example

```python
from zelos_sdk import ZelosRuntime
from zelos_sdk.schema import CapabilityDeclaration

runtime = ZelosRuntime()

runtime.add_agent(
    name="MyCoder",
    entrypoint="my_agents.coder:CodingAgent",
    capabilities=[
        CapabilityDeclaration(
            name="code-generation.python", version="1.0.0",
            description="Generates Python code",
            input_schema={...}, output_schema={...}
        ),
    ],
)

runtime.start()                              # Everything up

goal = runtime.submit_goal("Write a REST API")
result = runtime.wait_for_goal(goal.goal_id)

runtime.shutdown()                           # Everything down
```

### 2.3 Hot-Join / Hot-Leave Example

```python
runtime = ZelosRuntime()
runtime.add_agent("Coder", entrypoint="...", capabilities=[...])
runtime.start()

# Submit a long-running goal
goal = runtime.submit_goal("Analyze 10,000 customer reviews")

# Mid-execution: realize we need a data analyst agent
runtime.add_agent(
    name="DataAnalyst",
    entrypoint="my_agents.analyst:SQLAgent",
    capabilities=[
        CapabilityDeclaration(
            name="data-query.sql", version="1.0.0",
            description="Executes SQL queries",
            input_schema={...}, output_schema={...}
        ),
    ],
)
# DataAnalyst is now registered, heartbeating, and eligible for Task dispatch.
# If the Planner needs SQL queries, this agent is immediately available.

# Later: the Coder agent becomes unresponsive
runtime.remove_agent("Coder")
# In-flight tasks on Coder are cancelled, rescheduled to other agents.
# Capability Registry removes Coder's capabilities instantly.

runtime.shutdown()
```

### 2.4 What ZelosRuntime Replaces

| Old Pattern (Anti-Pattern) | New Pattern |
|----------------------------|-------------|
| `agent1.run()` / `agent2.run()` / `agent3.run()` — three separate processes | `runtime.add_agent(...)` × 3, then `runtime.start()` — one entry point |
| Each agent manages its own connection | Runtime manages all agent connections |
| No unified shutdown — each agent must be killed separately | `runtime.shutdown()` — everything stops |
| Adding an agent mid-run requires manual registration | `runtime.add_agent()` — hot-join, instantly available |
| Removing an agent leaves orphaned tasks | `runtime.remove_agent()` — tasks reassigned, capabilities removed |

---

## 3. Package Structure

```
zelos_sdk/
├── __init__.py
├── runtime.py            # ZelosRuntime (central entry point)
├── agent.py              # Agent base class
├── client.py             # ZelosClient (standalone Goal submission, admin)
├── schema/
│   ├── __init__.py
│   ├── task.py           # Task, TaskConstraints dataclasses
│   ├── artifact.py       # Artifact dataclass
│   ├── capability.py     # CapabilityDeclaration
│   └── event.py          # Event dataclass
├── transport/
│   ├── __init__.py
│   ├── http.py           # HTTP transport to Runtime
│   └── base.py           # Transport interface
├── errors.py             # SDK exceptions
└── testing.py            # In-memory Runtime stub for testing
```

---

## 4. Agent Base Class

### 3.1 The Contract

```python
from zelos_sdk.schema.task import Task
from zelos_sdk.schema.artifact import Artifact
from zelos_sdk.schema.capability import CapabilityDeclaration

class Agent:
    """
    Base class for all Zelos Agents.

    Developers override exactly two methods:
      - declare_capabilities() → list[CapabilityDeclaration]
      - execute(task: Task) → Artifact

    Everything else — registration, heartbeat, reconnection, serialization —
    is handled by the SDK.
    """

    # --- Developer MUST override ---

    def declare_capabilities(self) -> list[CapabilityDeclaration]:
        """
        Return the Capabilities this Agent provides.
        Called once at registration time.

        Example:
            return [
                CapabilityDeclaration(
                    name="code-generation",
                    version="1.0.0",
                    description="Generates Python code from specifications",
                    input_schema={...},
                    output_schema={...},
                )
            ]
        """
        raise NotImplementedError

    def execute(self, task: Task) -> Artifact:
        """
        Execute a Task and return an Artifact.

        This is the only method that contains the Agent's core logic.
        The developer chooses the model, prompt, tools, and logic here.
        The SDK handles everything else.

        Args:
            task: Fully assembled Task from the Runtime, containing
                  description, input, context, constraints, timeout_ms.

        Returns:
            An Artifact with the execution result.

        Raises:
            TaskFailedError: If execution fails. The SDK translates this
                             to a SubmitResult with status="failed".
        """
        raise NotImplementedError

    # --- Developer MAY override ---

    def on_registered(self, agent_id: str) -> None:
        """Called after successful registration. Hook for initialization."""
        pass

    def on_shutdown(self) -> None:
        """Called before disconnecting. Hook for cleanup."""
        pass

    def validate_task(self, task: Task) -> bool:
        """
        Called before execute(). Return False to reject the task.
        Default: accepts all tasks.

        Rejections cause the Scheduler to re-assign the Task to another
        Agent and count against this Agent's historical success rate.
        """
        return True
```

### 3.2 Lifecycle (Handled by SDK)

```
  Agent.run() called
       │
       ▼
  ┌─────────────┐
  │ REGISTER    │  POST /api/v1/agents
  │             │  Sends name, capabilities, protocol_version
  │             │  Receives agent_id, heartbeat_interval_ms
  └──────┬──────┘
         │ on_registered(agent_id)
         ▼
  ┌─────────────┐
  │ HEARTBEAT   │  Loop: POST /api/v1/agents/{id}/heartbeat
  │   LOOP      │  Interval: heartbeat_interval_ms
  │             │  Runs in background thread
  └──────┬──────┘
         │ Runtime dispatches Task → execute()
         ▼
  ┌─────────────┐
  │ EXECUTE     │  Developer's execute(task) runs
  │             │  Returns Artifact or raises TaskFailedError
  │             │  SDK calls SubmitResult(task_id, agent_id, result)
  └──────┬──────┘
         │ Loop: wait for next Task, send heartbeat
         │
         │ On KeyboardInterrupt or shutdown signal:
         ▼
  ┌─────────────┐
  │ SHUTDOWN    │  POST /api/v1/agents/{id}/shutdown
  │             │  on_shutdown() hook
  └─────────────┘
```

### 3.3 Minimal Agent Example

```python
from zelos_sdk.agent import Agent
from zelos_sdk.schema.task import Task
from zelos_sdk.schema.artifact import Artifact
from zelos_sdk.schema.capability import CapabilityDeclaration

class MyCodingAgent(Agent):
    def declare_capabilities(self):
        return [
            CapabilityDeclaration(
                name="code-generation",
                version="1.0.0",
                description="Generates Python code",
                input_schema={
                    "type": "object",
                    "properties": {
                        "spec": {"type": "string"}
                    },
                    "required": ["spec"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "code": {"type": "string"},
                        "language": {"type": "string"}
                    }
                }
            )
        ]

    def execute(self, task: Task) -> Artifact:
        spec = task.input.content["spec"] if task.input else task.description
        code = self._call_my_model(spec)  # Your LLM call here
        return Artifact(
            content_type="application/json",
            content={"code": code, "language": "python"}
        )

    def _call_my_model(self, spec: str) -> str:
        # The SDK has no opinion about which model you use.
        # Use any model, any library, any prompt.
        ...

if __name__ == "__main__":
    agent = MyCodingAgent(
        name="ClaudeCode",
        runtime_url="http://localhost:9876",
        api_key="zk-agent-xxxx",
    )
    agent.run()  # Blocks until shutdown
```

---

## 5. ZelosClient (Standalone Goal Submission)

### 4.1 Client Interface

```python
class ZelosClient:
    """
    Client for submitting Goals and querying the Runtime.

    Used by applications that want to submit work to Zelos,
    not by Agent implementations.
    """

    def __init__(self, runtime_url: str, api_key: str): ...

    # --- Goal API ---

    def submit_goal(
        self,
        description: str,
        *,
        budget: float | None = None,
        deadline: datetime | None = None,
        priority: str = "medium",
        project_id: str | None = None,
        metadata: dict | None = None,
    ) -> GoalResponse:
        """
        Submit a Goal to the Runtime.

        Returns immediately with goal_id and status="accepted".
        The Goal is processed asynchronously by the Runtime.
        """

    def get_goal_status(self, goal_id: str) -> GoalStatusResponse: ...
    def list_goals(self, *, status: str | None = None, limit: int = 100) -> list[GoalStatusResponse]: ...
    def cancel_goal(self, goal_id: str) -> GoalStatusResponse: ...

    def wait_for_goal(
        self,
        goal_id: str,
        *,
        timeout_seconds: float | None = None,
        poll_interval: float = 1.0,
    ) -> GoalStatusResponse:
        """
        Block until the Goal reaches a terminal state
        (completed, failed, cancelled) or timeout expires.
        """

    # --- Admin API ---

    def list_agents(self) -> list[AgentSummary]: ...
    def get_agent(self, agent_id: str) -> AgentDetail: ...
    def list_capabilities(self) -> list[CapabilitySummary]: ...
    def get_capability(self, name: str, version: str | None = None) -> CapabilityDetail: ...
    def get_health(self) -> HealthResponse: ...
    def get_metrics(self) -> MetricsResponse: ...
```

### 4.2 Client Usage Example

```python
from zelos_sdk.client import ZelosClient

client = ZelosClient(
    runtime_url="http://localhost:9876",
    api_key="zk-client-xxxx",
)

# Submit a Goal
goal = client.submit_goal(
    description="Build an e-commerce website with React frontend and FastAPI backend",
    budget=100.0,
    deadline=datetime(2026, 8, 1),
    priority="high",
)
print(f"Goal submitted: {goal.goal_id}")

# Wait for completion
result = client.wait_for_goal(goal.goal_id, timeout_seconds=600)
print(f"Goal {goal.goal_id}: {result.status}")
print(f"Progress: {result.progress.percent_complete:.0%}")
```

---

## 6. Data Classes (Schema Bindings)

### 5.1 Task

```python
@dataclass
class TaskConstraints:
    timeout_ms: int
    max_retries: int = 3
    backoff_base_ms: int = 1000
    max_cost_per_call: float | None = None
    priority: str = "medium"
    fallback_capability: str | None = None
    preferred_agent_id: str | None = None
    excluded_agent_ids: list[str] = field(default_factory=list)

@dataclass
class MemoryContext:
    session: dict
    project: dict
    user: dict
    knowledge: dict

@dataclass
class Task:
    task_id: str
    description: str
    input: "Artifact | None"
    expected_output_schema: dict
    timeout_ms: int
    context: dict
    constraints: TaskConstraints
```

### 5.2 Artifact

```python
@dataclass
class Artifact:
    content_type: str              # MIME type: "application/json", "text/plain", ...
    content: dict | str            # The actual artifact data
    metadata: dict | None = None   # Optional metadata (tags, source, etc.)

    # For large artifacts (>1MB), use a content reference:
    # content_ref: str | None = None  # URI to external artifact storage

    @classmethod
    def from_text(cls, text: str) -> "Artifact":
        return cls(content_type="text/plain", content=text)

    @classmethod
    def from_json(cls, data: dict) -> "Artifact":
        return cls(content_type="application/json", content=data)

    @classmethod
    def from_file(cls, path: str, content_type: str) -> "Artifact":
        with open(path, "rb") as f:
            # In Phase 1, small files inline; large files use content_ref
            ...
```

### 5.3 CapabilityDeclaration

```python
@dataclass
class CapabilityDeclaration:
    name: str                      # e.g., "code-generation"
    version: str                   # Semantic version, e.g., "1.0.0"
    description: str
    input_schema: dict             # JSON Schema
    output_schema: dict            # JSON Schema
    tags: list[str] = field(default_factory=list)
    qos: dict | None = None        # Optional QoS claims
```

---

## 7. Transport Layer

### 6.1 Transport Interface

```python
class Transport(ABC):
    """Abstract transport for Runtime API communication."""

    @abstractmethod
    def register(self, request: dict) -> dict: ...
    @abstractmethod
    def heartbeat(self, agent_id: str) -> dict: ...
    @abstractmethod
    def submit_result(self, task_id: str, agent_id: str, result: dict) -> dict: ...
    @abstractmethod
    def submit_goal(self, request: dict) -> dict: ...
    @abstractmethod
    def get_goal_status(self, goal_id: str) -> dict: ...
    @abstractmethod
    def shutdown(self, agent_id: str) -> None: ...
```

### 6.2 HTTP Transport (Phase 1)

```python
class HTTPTransport(Transport):
    """
    Phase 1 transport. Communicates with the Runtime over HTTP/1.1 REST.

    Endpoints:
      POST   /api/v1/agents                        → Register
      POST   /api/v1/agents/{id}/heartbeat         → Heartbeat
      POST   /api/v1/agents/{id}/tasks/{tid}/result → SubmitResult
      POST   /api/v1/goals                         → SubmitGoal
      GET    /api/v1/goals/{id}                    → GetGoalStatus
      DELETE /api/v1/goals/{id}                    → CancelGoal
    """

    def __init__(self, base_url: str, api_key: str):
        self._base_url = base_url
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })

    # Implements all Transport methods with HTTP calls.
    # Handles retry on 5xx, connection errors with exponential backoff.
```

### 6.3 Connection Resiliency

The SDK transport layer handles transient failures transparently:

| Failure | SDK Behavior |
|---------|-------------|
| Connection refused | Retry with exponential backoff (1s → 2s → 4s → ... max 60s) |
| HTTP 5xx | Retry up to 3 times with jitter |
| HTTP 401 (unauthorized) | Fail immediately — bad API key |
| HTTP 429 (rate limited) | Wait for Retry-After header, then retry |
| Heartbeat timeout | Mark connection unhealthy, attempt re-registration |
| SubmitResult failure | Retry up to 5 times (Artifact must be delivered) |

---

## 8. Testing Support

### 7.1 In-Memory Runtime Stub

```python
class InMemoryRuntime:
    """
    A lightweight in-memory Runtime stub for testing Agents.

    Does NOT implement full Kernel semantics — only the Agent API
    surface needed to test Agent registration, execute(), and
    Artifact submission in isolation.
    """

    def __init__(self): ...
    def start(self) -> str: ...        # Returns runtime_url
    def stop(self) -> None: ...
    def dispatch_task(self, agent_id: str, task: Task) -> None: ...
    def get_submitted_results(self, task_id: str) -> list[Artifact]: ...
```

### 7.2 Agent Test Example

```python
from zelos_sdk.testing import InMemoryRuntime

def test_my_agent():
    runtime = InMemoryRuntime()
    url = runtime.start()

    agent = MyCodingAgent(name="TestAgent", runtime_url=url)
    thread = threading.Thread(target=agent.run, daemon=True)
    thread.start()

    # Simulate the Runtime dispatching a Task
    task = Task(
        task_id="task-001",
        description="Write a hello world function",
        input=None,
        expected_output_schema={...},
        timeout_ms=30000,
        context={},
        constraints=TaskConstraints(timeout_ms=30000),
    )
    runtime.dispatch_task(agent.agent_id, task)

    # Wait and verify
    time.sleep(1)
    results = runtime.get_submitted_results("task-001")
    assert len(results) == 1
    assert results[0].content["language"] == "python"
```

---

## 9. Exception Model

```python
class ZelosSDKError(Exception):
    """Base exception for all SDK errors."""

class ConnectionError(ZelosSDKError):
    """Cannot reach the Runtime."""

class AuthenticationError(ZelosSDKError):
    """API key rejected (401)."""

class RegistrationError(ZelosSDKError):
    """Registration rejected by Runtime (schema mismatch, version conflict)."""

class TaskFailedError(ZelosSDKError):
    """
    Raised by developer's execute() to signal Task failure.
    Translated to SubmitResult with status="failed".
    """

class TaskTimeoutError(ZelosSDKError):
    """Task exceeded timeout_ms. SDK enforces this client-side as a safety net."""

class ShutdownSignal(ZelosSDKError):
    """Internal signal to stop the agent loop. Not exposed to developers."""
```

---

## 10. Phase 1 Scope Boundaries

| Feature | Phase 1 | Future |
|---------|---------|--------|
| ZelosRuntime (central entry point) | ✅ | — |
| add_agent / remove_agent (hot-join / hot-leave) | ✅ | — |
| Runtime lifecycle (start / shutdown) | ✅ | — |
| Goal submission via Runtime | ✅ | — |
| Agent base class | ✅ | — |
| Standalone ZelosClient (remote Runtime) | ✅ | — |
| HTTP transport | ✅ | — |
| Heartbeat loop (Runtime-managed) | ✅ | — |
| Agent auto-restart on crash | ✅ | — |
| gRPC transport | — | Phase 2 |
| Async Agent (asyncio) | — | Phase 2 |
| Streaming progress | — | Phase 2 |
| In-memory test Runtime stub | ✅ | — |
| MCP tool integration helpers | — | Phase 2 |
| CLI: `zelos agent run` | — | Phase 2 |
| SDK packaging (PyPI) | — | Phase 2 |

---

## 11. References

- [Runtime API](./runtime-api.md) — The API the SDK wraps
- [RFC-0002: Agent Registration Protocol](../rfc/rfc-0002-agent-registration-protocol.md)
- [Protocol Layer](./protocol-layer.md) — HTTP transport mapping
- [Architecture Invariants](../architecture/invariants.md) — Invariants 5, 6, 9, 13, 14
- [Domain Model](./domain-model.md) — Task, Artifact, Capability entity definitions
