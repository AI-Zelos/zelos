"""
Phase 2 Plugin Isolation — Sub-process mode.

Supports running plugins in separate processes with JSON stdin/stdout communication.
"""

import json
import subprocess
import sys
import threading


class SubProcessPlugin:
    """Manages a plugin running in a sub-process with JSON-line protocol."""

    def __init__(self, command: list, plugin_id: str, timeout: float = 30.0):
        self.command = command
        self.plugin_id = plugin_id
        self.timeout = timeout
        self._process: subprocess.Popen | None = None
        self._running = False
        self._lock = threading.Lock()

    def start(self) -> bool:
        try:
            self._process = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            self._running = True
            return True
        except Exception:
            return False

    def stop(self) -> None:
        with self._lock:
            self._running = False
            if self._process:
                try:
                    self._send_msg({"type": "shutdown"})
                    self._process.wait(timeout=5)
                except Exception:
                    self._process.kill()
                self._process = None

    def is_running(self) -> bool:
        if not self._process:
            return False
        return self._process.poll() is None

    def send(self, msg: dict) -> dict | None:
        """Send a JSON message and wait for response."""
        if not self._process or not self.is_running():
            return None
        try:
            self._send_msg(msg)
            return self._recv_msg()
        except Exception:
            return None

    def health_check(self) -> bool:
        resp = self.send({"type": "health_check"})
        return resp is not None and resp.get("status") == "healthy"

    def _send_msg(self, msg: dict) -> None:
        if self._process and self._process.stdin:
            self._process.stdin.write(json.dumps(msg) + "\n")
            self._process.stdin.flush()

    def _recv_msg(self) -> dict | None:
        if self._process and self._process.stdout:
            line = self._process.stdout.readline()
            if line:
                return json.loads(line.strip())
        return None


class SubProcessPluginRunner:
    """
    Template for a sub-process plugin.

    Use this in your plugin's __main__ to handle stdin/stdout JSON protocol:

        if __name__ == "__main__":
            SubProcessPluginRunner.run(lambda msg: handle_message(msg))
    """

    @staticmethod
    def run(handler):
        """Main loop for sub-process plugins."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
                msg_type = msg.get("type", "")

                if msg_type == "shutdown":
                    SubProcessPluginRunner._respond({"type": "shutdown_ack"})
                    break
                elif msg_type == "health_check":
                    SubProcessPluginRunner._respond({"type": "health", "status": "healthy"})
                else:
                    result = handler(msg)
                    SubProcessPluginRunner._respond(result)
            except json.JSONDecodeError:
                SubProcessPluginRunner._respond({"type": "error", "message": "Invalid JSON"})
            except Exception as e:
                SubProcessPluginRunner._respond({"type": "error", "message": str(e)})

    @staticmethod
    def _respond(msg: dict) -> None:
        sys.stdout.write(json.dumps(msg) + "\n")
        sys.stdout.flush()
