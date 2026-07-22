"""
Zelos SDK Agent — Base class for building Agents on Zelos.

Every Agent on Zelos must subclass BaseAgent and override:
  - declare_capabilities() → list of CapabilityDeclaration
  - execute(task_payload) → dict with status + artifact/error

The Runtime owns everything else — planning, scheduling, retry, memory, verification.
The Agent only: Receives Task → Executes → Returns Artifact → Exits.
"""

import threading
import time
from abc import ABC, abstractmethod
from typing import Any

from .schema import CapabilityDeclaration, Task


class BaseAgent(ABC):
    """Abstract base for all Zelos Agents.

    Subclass this and override:
      - declare_capabilities()
      - execute(task_payload)

    The Runtime calls:
      - register()   — during agent registration
      - execute()    — for each dispatched Task
      - heartbeat()  — periodically (handled automatically)
      - shutdown()   — during Runtime shutdown
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.agent_id: str | None = None
        self.runtime_endpoint: str | None = None
        self._running = False
        self._heartbeat_thread: threading.Thread | None = None

    # ── Override these ──

    @abstractmethod
    def declare_capabilities(self) -> list[CapabilityDeclaration]:
        """Return the capabilities this Agent provides.

        Example:
            return [
                CapabilityDeclaration(
                    name="code-generation.python",
                    version="1.0.0",
                    description="Generates Python code",
                    tags=["python", "code-generation"],
                )
            ]
        """
        ...

    @abstractmethod
    def execute(self, task: Task) -> dict[str, Any]:
        """Execute a Task and return the result.

        Args:
            task: Task payload including description, input, memory_context.

        Returns:
            dict with:
              - status: "completed" | "failed"
              - artifact: {content_type, content} (on success)
              - error: {code, message} (on failure)
        """
        ...

    # ── Optional hooks ──

    def validate_task(self, task: Task) -> bool:
        """Hook: reject Tasks this Agent should not handle.

        Return False to reject — the Scheduler will reschedule to another Agent.
        """
        return True

    def on_registered(self, agent_id: str):
        """Called after successful registration with the Runtime."""
        self.agent_id = agent_id

    def on_shutdown(self):  # noqa: B027
        """Called before the Agent is shut down. Clean up resources here."""
        pass

    # ── Lifecycle helpers (used by Runtime) ──

    def start_heartbeat(self, interval_ms: int = 30000):
        """Start automatic heartbeat loop."""
        self._running = True
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            args=(interval_ms / 1000.0,),
            daemon=True,
        )
        self._heartbeat_thread.start()

    def stop_heartbeat(self):
        """Stop the heartbeat loop."""
        self._running = False
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=5)

    def _heartbeat_loop(self, interval_s: float):
        while self._running:
            time.sleep(interval_s)
            if self._running:
                self.heartbeat()

    def heartbeat(self) -> dict[str, str]:
        """Send a heartbeat. Override to call the Runtime API."""
        return {"status": "ok"}


class DemoAgent(BaseAgent):
    """Simple demo Agent — echoes the task description back as an artifact."""

    def declare_capabilities(self) -> list[CapabilityDeclaration]:
        return [
            CapabilityDeclaration(
                name="code-generation.python",
                version="1.0.0",
                description="Generates Python code from task descriptions",
                tags=["python", "demo"],
            )
        ]

    def execute(self, task: Task) -> dict[str, Any]:
        return {
            "status": "completed",
            "artifact": {
                "content_type": "application/json",
                "content": {
                    "code": f"# Generated for: {task.description}\ndef hello():\n    return 'Hello from Zelos!'",
                    "language": "python",
                },
            },
        }
