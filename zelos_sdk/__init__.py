"""
Zelos Python SDK — Developer interface for building Agents and submitting Goals.

Package structure:
  - zelos_sdk.schema   — Data classes: CapabilityDeclaration, Task, Artifact, etc.
  - zelos_sdk.agent    — BaseAgent class for building custom Agents
  - zelos_sdk.client   — ZelosClient for communicating with a remote Runtime

Quick Start:
    from zelos_sdk import ZelosClient, BaseAgent, CapabilityDeclaration

    # Remote client
    client = ZelosClient("http://localhost:9876", api_key="zk-client-dev")
    client.submit_goal("Build a landing page")

    # Build an Agent
    class MyCoder(BaseAgent):
        def declare_capabilities(self):
            return [CapabilityDeclaration(name="code-generation.python", version="1.0.0")]

        def execute(self, task):
            return {"status": "completed", "artifact": {"content_type": "text/plain", "content": "done"}}
"""

from zelos.runtime import ZelosRuntime

from .agent import BaseAgent, DemoAgent
from .client import (
    AuthenticationError,
    ConnectionError,
    GoalError,
    TaskTimeoutError,
    ZelosClient,
    ZelosError,
)
from .schema import (
    Artifact,
    CapabilityDeclaration,
    GoalResult,
    MemoryContext,
    Task,
    TaskConstraints,
)

__all__ = [
    # Runtime (in-process)
    "ZelosRuntime",
    # Schema
    "CapabilityDeclaration",
    "TaskConstraints",
    "Task",
    "Artifact",
    "MemoryContext",
    "GoalResult",
    # Agent
    "BaseAgent",
    "DemoAgent",
    # Client (remote)
    "ZelosClient",
    "ZelosError",
    "ConnectionError",
    "AuthenticationError",
    "GoalError",
    "TaskTimeoutError",
]
