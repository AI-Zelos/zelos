"""
Zelos SDK Client — Remote client for communicating with a Zelos Runtime.

Use ZelosClient when your application is separate from the Runtime process.
It wraps the full HTTP API: Goal submission, Agent management, Admin operations.

For in-process use (same Python process as the Runtime), use ZelosRuntime directly.
"""

import json
import time
import urllib.error
import urllib.request
from typing import Any


class ZelosError(Exception):
    """Base exception for Zelos SDK errors."""

    pass


class ConnectionError(ZelosError):
    """Failed to connect to the Runtime."""

    pass


class AuthenticationError(ZelosError):
    """API key invalid or missing."""

    pass


class GoalError(ZelosError):
    """Goal submission or execution failed."""

    pass


class TaskTimeoutError(ZelosError):
    """Task exceeded its timeout."""

    pass


class ZelosClient:
    """HTTP client for a remote Zelos Runtime.

    Usage:
        client = ZelosClient("http://localhost:9876", api_key="zk-client-dev")
        client.health()                       # check Runtime health
        goal = client.submit_goal("Build...") # submit a Goal
        result = client.wait_for_goal(goal["goal_id"])  # wait for completion
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:9876",
        api_key: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries

    # ── HTTP helpers ──

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _request(
        self,
        method: str,
        path: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(url, data=body, headers=self._headers(), method=method)

        last_error = None
        for attempt in range(self.max_retries):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read())
            except urllib.error.HTTPError as e:
                error_body = {}
                try:
                    error_body = json.loads(e.read())
                except Exception:
                    pass
                if e.code == 401:
                    raise AuthenticationError(
                        f"Authentication failed: {error_body.get('error', 'Invalid API key')}"
                    ) from e
                if e.code == 404:
                    return {"error": "not_found", "status_code": 404}
                if e.code == 409:
                    return {"error": "conflict", "status_code": 409, **error_body}
                last_error = ZelosError(f"HTTP {e.code}: {error_body.get('error', str(e))}")
            except urllib.error.URLError as e:
                last_error = ConnectionError(f"Cannot reach Runtime at {url}: {e.reason}")
            except Exception as e:
                last_error = ZelosError(f"Request failed: {e}")

            if attempt < self.max_retries - 1:
                backoff = 2**attempt * 0.5
                time.sleep(backoff)

        raise last_error  # type: ignore[misc]

    # ── Goal API ──

    def submit_goal(
        self,
        description: str,
        *,
        priority: str = "medium",
        budget: float = 0.0,
        deadline_ms: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Submit a Goal to the Runtime. Returns {goal_id, status, ...}."""
        payload: dict[str, Any] = {
            "description": description,
            "priority": priority,
        }
        if budget:
            payload["budget"] = budget
        if deadline_ms:
            payload["deadline_ms"] = deadline_ms
        if metadata:
            payload["metadata"] = metadata
        return self._request("POST", "/api/v1/goals", payload)

    def get_goal_status(self, goal_id: str) -> dict[str, Any]:
        """Get current status and progress of a Goal."""
        return self._request("GET", f"/api/v1/goals/{goal_id}")

    def list_goals(self, status_filter: str | None = None) -> dict[str, Any]:
        """List all Goals, optionally filtered by status."""
        path = "/api/v1/goals"
        if status_filter:
            path += f"?status={status_filter}"
        return self._request("GET", path)

    def cancel_goal(self, goal_id: str) -> dict[str, Any]:
        """Cancel a running Goal."""
        return self._request("DELETE", f"/api/v1/goals/{goal_id}")

    def wait_for_goal(
        self,
        goal_id: str,
        timeout_seconds: float = 600,
        poll_interval: float = 1.0,
    ) -> dict[str, Any]:
        """Block until the Goal reaches a terminal state.

        Returns the final Goal status dict.
        """
        terminal = {"completed", "failed", "cancelled", "rejected"}
        deadline = time.time() + timeout_seconds

        while time.time() < deadline:
            status = self.get_goal_status(goal_id)
            if "error" in status:
                return status
            if status.get("status") in terminal:
                return status
            time.sleep(poll_interval)

        raise GoalError(
            f"Goal {goal_id} did not complete within {timeout_seconds}s. "
            f"Current status: {status.get('status', 'unknown')}"
        )

    # ── Agent API ──

    def register_agent(
        self,
        name: str,
        entrypoint: str,
        capabilities: list[dict[str, Any]],
        *,
        protocol: str = "http",
        endpoint: str = "",
        max_concurrent_tasks: int = 5,
        heartbeat_interval_ms: int = 30000,
    ) -> dict[str, Any]:
        """Register an Agent with the Runtime via HTTP."""
        payload = {
            "name": name,
            "entrypoint": entrypoint,
            "capabilities": capabilities,
            "protocol": protocol,
            "endpoint": endpoint,
            "max_concurrent_tasks": max_concurrent_tasks,
            "heartbeat_interval_ms": heartbeat_interval_ms,
        }
        return self._request("POST", "/api/v1/agents", payload)

    def list_agents(self) -> dict[str, Any]:
        """List all registered Agents."""
        return self._request("GET", "/api/v1/agents")

    def get_agent(self, agent_id: str) -> dict[str, Any]:
        """Get details of a specific Agent."""
        return self._request("GET", f"/api/v1/agents/{agent_id}")

    def agent_heartbeat(self, agent_id: str) -> dict[str, Any]:
        """Send a heartbeat for an Agent."""
        return self._request("POST", f"/api/v1/agents/{agent_id}/heartbeat")

    def submit_result(
        self,
        agent_id: str,
        task_id: str,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        """Submit a Task execution result back to the Runtime."""
        return self._request(
            "POST",
            f"/api/v1/agents/{agent_id}/tasks/{task_id}/result",
            {"result": result},
        )

    # ── Admin API ──

    def health(self) -> dict[str, Any]:
        """Check Runtime health status."""
        return self._request("GET", "/api/v1/health")

    def metrics(self) -> dict[str, Any]:
        """Get Runtime metrics (goals, tasks, agents)."""
        return self._request("GET", "/api/v1/admin/metrics")

    def list_capabilities(self) -> dict[str, Any]:
        """List all registered capabilities."""
        return self._request("GET", "/api/v1/capabilities")
