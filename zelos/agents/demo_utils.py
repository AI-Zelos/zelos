"""
Demo utility agents for Zelos full-chain testing.

Provides agent implementations used in demos that exercise specific
Zelos Runtime features (MPC replan, verification, etc.).
"""

from typing import Any

from zelos.task_graph import Task


class FailingAgent:
    """An agent that always fails — used to trigger MPC replan in demos.

    Registered for a specific capability (e.g., code-review.security),
    this agent raises a RuntimeError to trigger task failure, which feeds
    into the MPC _mpc_replan_check → replan rules → _on_replan flow.

    Note: We raise an exception because Zelos Runtime's _on_dispatch only
    triggers submit_result(failed) on exceptions from agent.execute().
    """

    def __init__(self, name: str = "FailingAgent", **config):
        self.name = name
        self.fail_code = config.get("fail_code", "demo_failure")
        self.fail_message = config.get("fail_message", "Deliberate failure for MPC demo")

    def execute(self, task: Task) -> dict[str, Any]:
        raise RuntimeError(f"[{self.fail_code}] {self.fail_message}")
