"""
Phase 3 Container/Remote Plugin Isolation — Docker, Podman, Remote execution.

Phase 3: Full container execution via subprocess + remote HTTP dispatch.
  - ContainerPluginConfig: Docker/Podman container spec + command generation
  - ContainerRunner: Actually executes containers via subprocess
  - RemotePlugin: HTTP-based remote plugin execution with retry
  - ContainerIsolationFactory: Create the right isolation mode
"""
import json
import time
import threading
import subprocess
import shutil
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ═══════════════════ Container Plugin Config ═══════════════════

@dataclass
class ContainerPluginConfig:
    """Configuration for running a plugin in a container."""
    plugin_id: str
    image: str
    runtime: str = "docker"
    command: Optional[List[str]] = None
    entrypoint: Optional[str] = None
    env: Dict[str, str] = field(default_factory=dict)
    mounts: Dict[str, str] = field(default_factory=dict)
    ports: Dict[int, int] = field(default_factory=dict)
    cpu_limit: float = 1.0
    memory_limit_mb: int = 512
    network_mode: str = "bridge"
    restart_policy: str = "unless-stopped"
    labels: Dict[str, str] = field(default_factory=dict)

    def to_docker_command(self) -> List[str]:
        """Generate the docker/podman run command."""
        cmd = [self.runtime, "run", "--rm"]
        cmd.extend(["--name", f"zelos-plugin-{self.plugin_id}"])
        cmd.extend(["--cpus", str(self.cpu_limit)])
        cmd.extend(["--memory", f"{self.memory_limit_mb}m"])
        cmd.extend(["--network", self.network_mode])
        cmd.extend(["--restart", self.restart_policy])
        for key, val in self.env.items():
            cmd.extend(["-e", f"{key}={val}"])
        for host_path, container_path in self.mounts.items():
            cmd.extend(["-v", f"{host_path}:{container_path}"])
        for host_port, container_port in self.ports.items():
            cmd.extend(["-p", f"{host_port}:{container_port}"])
        for key, val in self.labels.items():
            cmd.extend(["-l", f"{key}={val}"])
        if self.entrypoint:
            cmd.extend(["--entrypoint", self.entrypoint])
        cmd.append(self.image)
        if self.command:
            cmd.extend(self.command)
        return cmd

    def to_dict(self) -> dict:
        return {
            "plugin_id": self.plugin_id, "image": self.image,
            "runtime": self.runtime, "command": self.command,
            "env": self.env, "mounts": self.mounts,
            "cpu_limit": self.cpu_limit, "memory_limit_mb": self.memory_limit_mb,
            "network_mode": self.network_mode,
        }


# ═══════════════════ Container Runner (Phase 3: actual execution) ═══════════════════

class ContainerRunner:
    """Actually runs and manages container plugins via subprocess.

    Executes real docker/podman commands. Gracefully falls back
    if the runtime is not installed.
    """

    def __init__(self, config: ContainerPluginConfig):
        self.config = config
        self._process: Optional[subprocess.Popen] = None
        self._running = False

    def start(self) -> bool:
        """Start the container via subprocess. Returns True on success."""
        if not self._check_runtime():
            return False
        cmd = self.config.to_docker_command()
        try:
            self._process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self._running = True
            return True
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            return False

    def stop(self, timeout_seconds: float = 10.0) -> None:
        """Stop container gracefully; force-kill on timeout."""
        if not self._process:
            return
        try:
            stop_cmd = [self.config.runtime, "stop",
                        f"zelos-plugin-{self.config.plugin_id}"]
            subprocess.run(stop_cmd, timeout=timeout_seconds, capture_output=True)
        except (subprocess.SubprocessError, FileNotFoundError):
            if self._process:
                self._process.kill()
        finally:
            self._running = False
            self._process = None

    def is_running(self) -> bool:
        if not self._process:
            return False
        return self._process.poll() is None

    def health_check(self) -> bool:
        if not self.is_running():
            return False
        try:
            inspect_cmd = [self.config.runtime, "inspect",
                           f"zelos-plugin-{self.config.plugin_id}"]
            result = subprocess.run(inspect_cmd, capture_output=True,
                                    text=True, timeout=5)
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def _check_runtime(self) -> bool:
        return shutil.which(self.config.runtime) is not None

    def get_logs(self, tail: int = 50) -> str:
        if not self._process:
            return ""
        try:
            logs_cmd = [self.config.runtime, "logs", "--tail", str(tail),
                        f"zelos-plugin-{self.config.plugin_id}"]
            result = subprocess.run(logs_cmd, capture_output=True,
                                    text=True, timeout=5)
            return result.stdout
        except (subprocess.SubprocessError, FileNotFoundError):
            return ""


# ═══════════════════ Remote Plugin ═══════════════════

class RemotePlugin:
    """Plugin that executes on a remote host via HTTP.

    Protocol:
      - Health: GET {endpoint}{health_endpoint}
      - Dispatch: POST {endpoint}{task_endpoint} with task payload
      - Result: POST {callback_url} with result payload

    Supports retry, timeout, and reconnection logic.
    Phase 3: dispatch() called from Runtime orchestrator for remote agents.
    """

    def __init__(self, plugin_id: str, endpoint: str,
                 health_endpoint: str = "/health",
                 task_endpoint: str = "/execute",
                 callback_url: Optional[str] = None,
                 timeout_seconds: float = 30.0,
                 max_retries: int = 3,
                 retry_backoff_ms: int = 1000):
        self.plugin_id = plugin_id
        self.endpoint = endpoint.rstrip("/")
        self.health_endpoint = health_endpoint
        self.task_endpoint = task_endpoint
        self.callback_url = callback_url
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_backoff_ms = retry_backoff_ms
        self._status = "registered"
        self._last_health_check: float = 0.0
        self._healthy = False
        self._lock = threading.RLock()

    @property
    def health_url(self) -> str:
        return f"{self.endpoint}{self.health_endpoint}"

    @property
    def task_url(self) -> str:
        return f"{self.endpoint}{self.task_endpoint}"

    def health_check(self) -> bool:
        """Check if remote plugin is healthy via HTTP GET."""
        import urllib.request
        try:
            req = urllib.request.Request(self.health_url, method="GET")
            urllib.request.urlopen(req, timeout=5)
            with self._lock:
                self._healthy = True
                self._last_health_check = time.time()
            return True
        except Exception:
            with self._lock:
                self._healthy = False
            return False

    def dispatch(self, task: dict) -> Optional[dict]:
        """Dispatch a task to the remote plugin via HTTP POST. Returns result."""
        import urllib.request
        last_error = None
        for attempt in range(self.max_retries):
            try:
                payload = json.dumps(task).encode("utf-8")
                req = urllib.request.Request(
                    self.task_url, data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST")
                resp = urllib.request.urlopen(req, timeout=self.timeout_seconds)
                return json.loads(resp.read().decode("utf-8"))
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_backoff_ms / 1000 * (attempt + 1))
        return {
            "status": "failed",
            "error": {"code": "remote_dispatch_failed",
                      "message": str(last_error), "attempts": self.max_retries}
        }

    @property
    def is_healthy(self) -> bool:
        return self._healthy

    def to_dict(self) -> dict:
        return {
            "plugin_id": self.plugin_id, "endpoint": self.endpoint,
            "status": self._status, "healthy": self._healthy,
            "last_health_check": self._last_health_check,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
        }


# ═══════════════════ Factory ═══════════════════

class ContainerIsolationFactory:
    """Create plugin isolation instances by type."""

    ISOLATION_MODES = {"docker", "podman", "remote", "subprocess", "in-process"}

    @staticmethod
    def create(mode: str, config: Any) -> Any:
        if mode not in ContainerIsolationFactory.ISOLATION_MODES:
            raise ValueError(
                f"Unknown isolation mode: '{mode}'. "
                f"Supported: {', '.join(sorted(ContainerIsolationFactory.ISOLATION_MODES))}")
        if mode == "remote":
            if not isinstance(config, RemotePlugin):
                raise TypeError("Remote mode requires a RemotePlugin instance")
            return config
        elif mode in ("docker", "podman"):
            if isinstance(config, ContainerPluginConfig):
                config.runtime = mode
                return config
            raise TypeError(f"{mode} mode requires a ContainerPluginConfig instance")
        else:
            return config

    @staticmethod
    def list_modes() -> List[str]:
        return sorted(ContainerIsolationFactory.ISOLATION_MODES)
