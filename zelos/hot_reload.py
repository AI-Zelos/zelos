"""
Phase 3 Hot Reload — Plugin upgrade without Runtime restart.

Supports:
  - FileWatcher: Watch plugin directories for changes
  - HotReloadManager: Version management, rolling/blue-green/canary upgrades
  - PluginVersion tracking with history

Upgrade strategies:
  - ROLLING: One instance at a time (default)
  - BLUE_GREEN: Spin up new version, then cut over
  - CANARY: Route x% of traffic to new version
"""

import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ═══════════════════ Upgrade Strategy ═══════════════════


class UpgradeStrategy(Enum):
    ROLLING = "rolling"
    BLUE_GREEN = "blue_green"
    CANARY = "canary"
    INSTANT = "instant"


# ═══════════════════ Plugin Version ═══════════════════


@dataclass
class PluginVersion:
    """A specific version of a plugin."""

    plugin_id: str
    version: str
    entrypoint: str
    checksum: str
    status: str = "active"  # active, draining, drained, rolled_back
    canary_percent: int = 0
    created_at: float = field(default_factory=time.time)
    activated_at: float | None = None
    drained_at: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "plugin_id": self.plugin_id,
            "version": self.version,
            "entrypoint": self.entrypoint,
            "checksum": self.checksum,
            "status": self.status,
            "canary_percent": self.canary_percent,
            "created_at": self.created_at,
            "activated_at": self.activated_at,
            "drained_at": self.drained_at,
        }


# ═══════════════════ File Watcher ═══════════════════


class FileWatcher:
    """Watch a directory for file changes using polling.

    Detects: created, modified, deleted files.
    Supports debouncing — multiple rapid changes → single event.
    """

    def __init__(
        self, watch_dir: str, patterns: list[str] | None = None, poll_interval_ms: int = 500, debounce_ms: int = 300
    ):
        self.watch_dir = os.path.abspath(watch_dir)
        self.patterns = patterns or ["*.py"]
        self.poll_interval_ms = poll_interval_ms
        self.debounce_ms = debounce_ms
        self._running = False
        self._thread: threading.Thread | None = None
        self._file_states: dict[str, float] = {}  # filename → last modified
        self._changes: list[dict[str, Any]] = []
        self._lock = threading.RLock()
        self._callbacks: list[Callable] = []

    def start(self) -> None:
        """Start watching the directory."""
        if self._running:
            return
        self._running = True
        # Initialize file states
        self._scan_directory()
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop watching."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def is_running(self) -> bool:
        return self._running

    def on_change(self, callback: Callable) -> None:
        """Register a callback: callback(event_dict) when file changes."""
        self._callbacks.append(callback)

    def get_changes(self) -> list[dict[str, Any]]:
        """Get and clear pending changes."""
        with self._lock:
            changes = list(self._changes)
            self._changes.clear()
        return changes

    def _scan_directory(self) -> None:
        """Scan directory and record file states."""
        if not os.path.isdir(self.watch_dir):
            return
        try:
            for entry in os.listdir(self.watch_dir):
                filepath = os.path.join(self.watch_dir, entry)
                if os.path.isfile(filepath) and self._matches_pattern(entry):
                    self._file_states[entry] = os.path.getmtime(filepath)
        except OSError:
            pass

    def _matches_pattern(self, filename: str) -> bool:
        """Check if filename matches any watch pattern."""
        import fnmatch

        return any(fnmatch.fnmatch(filename, p) for p in self.patterns)

    def _watch_loop(self) -> None:
        """Polling loop."""
        last_event_time: dict[str, float] = {}
        while self._running:
            try:
                if not os.path.isdir(self.watch_dir):
                    time.sleep(self.poll_interval_ms / 1000)
                    continue

                current_files: set[str] = set()
                for entry in os.listdir(self.watch_dir):
                    filepath = os.path.join(self.watch_dir, entry)
                    if os.path.isfile(filepath) and self._matches_pattern(entry):
                        current_files.add(entry)
                        mtime = os.path.getmtime(filepath)

                        if entry not in self._file_states:
                            # New file
                            self._record_change("created", entry, filepath)
                            self._file_states[entry] = mtime
                        elif mtime > self._file_states[entry]:
                            # Modified
                            now = time.time()
                            last = last_event_time.get(entry, 0)
                            if now - last > self.debounce_ms / 1000:
                                self._record_change("modified", entry, filepath)
                                last_event_time[entry] = now
                            self._file_states[entry] = mtime

                # Detect deleted files
                for filename in list(self._file_states.keys()):
                    if filename not in current_files:
                        self._record_change("deleted", filename, os.path.join(self.watch_dir, filename))
                        del self._file_states[filename]

            except OSError:
                pass

            time.sleep(self.poll_interval_ms / 1000)

    def _record_change(self, event_type: str, filename: str, filepath: str) -> None:
        change = {
            "type": event_type,
            "filename": filename,
            "filepath": filepath,
            "timestamp": time.time(),
        }
        with self._lock:
            self._changes.append(change)
        for cb in self._callbacks:
            try:
                cb(change)
            except Exception:
                pass


# ═══════════════════ Hot Reload Manager ═══════════════════


class HotReloadManager:
    """Manages plugin version lifecycle and hot upgrades.

    Each plugin can have multiple registered versions. The manager:
      - Tracks which version is active
      - Supports drain → upgrade → activate flow
      - Maintains version history for rollback
      - Supports canary deployment with traffic splitting
    """

    def __init__(self, upgrade_strategy: UpgradeStrategy = UpgradeStrategy.ROLLING):
        self._versions: dict[str, dict[str, PluginVersion]] = {}  # plugin_id → {version → PluginVersion}
        self._active: dict[str, str] = {}  # plugin_id → active_version
        self.upgrade_strategy = upgrade_strategy
        self._upgrade_history: list[dict[str, Any]] = []
        self._lock = threading.RLock()

    def register_version(
        self, plugin_id: str, version: str, entrypoint: str, checksum: str = "", canary_percent: int = 0, **metadata
    ) -> PluginVersion:
        """Register a new plugin version. The latest version becomes active."""
        pv = PluginVersion(
            plugin_id=plugin_id,
            version=version,
            entrypoint=entrypoint,
            checksum=checksum,
            canary_percent=canary_percent,
            metadata=metadata,
            activated_at=time.time(),
        )

        with self._lock:
            if plugin_id not in self._versions:
                self._versions[plugin_id] = {}
            self._versions[plugin_id][version] = pv
            self._active[plugin_id] = version

            self._upgrade_history.append(
                {
                    "plugin_id": plugin_id,
                    "version": version,
                    "action": "registered",
                    "timestamp": time.time(),
                }
            )

        return pv

    def get_version(self, plugin_id: str, version: str) -> PluginVersion | None:
        """Get a specific plugin version."""
        versions = self._versions.get(plugin_id, {})
        return versions.get(version)

    def get_active_version(self, plugin_id: str) -> PluginVersion | None:
        """Get the currently active version of a plugin."""
        active_ver = self._active.get(plugin_id)
        if active_ver:
            return self._versions.get(plugin_id, {}).get(active_ver)
        return None

    def get_versions(self, plugin_id: str) -> list[PluginVersion]:
        """List all versions of a plugin (oldest first)."""
        versions = self._versions.get(plugin_id, {})
        return sorted(versions.values(), key=lambda v: v.created_at)

    def get_version_history(self, plugin_id: str) -> list[PluginVersion]:
        """Get full version history (all versions, oldest first)."""
        return self.get_versions(plugin_id)

    def drain_version(self, plugin_id: str, version: str) -> bool:
        """Mark a version as draining — stop routing new tasks to it."""
        pv = self.get_version(plugin_id, version)
        if not pv:
            return False
        pv.status = "drained"
        pv.drained_at = time.time()

        self._upgrade_history.append(
            {
                "plugin_id": plugin_id,
                "version": version,
                "action": "drained",
                "timestamp": time.time(),
            }
        )
        return True

    def activate_version(self, plugin_id: str, version: str) -> bool:
        """Manually activate a specific version."""
        pv = self.get_version(plugin_id, version)
        if not pv:
            return False
        pv.status = "active"
        pv.activated_at = time.time()

        with self._lock:
            self._active[plugin_id] = version

        self._upgrade_history.append(
            {
                "plugin_id": plugin_id,
                "version": version,
                "action": "activated",
                "timestamp": time.time(),
            }
        )
        return True

    def rollback(self, plugin_id: str, target_version: str) -> bool:
        """Rollback to a previous version."""
        pv = self.get_version(plugin_id, target_version)
        if not pv:
            return False

        current = self.get_active_version(plugin_id)
        if current:
            current.status = "rolled_back"

        return self.activate_version(plugin_id, target_version)

    def set_upgrade_strategy(self, strategy: UpgradeStrategy) -> None:
        self.upgrade_strategy = strategy

    def get_upgrade_history(self) -> list[dict[str, Any]]:
        return list(self._upgrade_history)

    def list_plugins(self) -> list[dict[str, Any]]:
        """List all plugins with their active versions."""
        result = []
        for plugin_id in self._versions:
            active = self.get_active_version(plugin_id)
            all_versions = self.get_versions(plugin_id)
            result.append(
                {
                    "plugin_id": plugin_id,
                    "active_version": active.version if active else None,
                    "version_count": len(all_versions),
                    "strategy": self.upgrade_strategy.value,
                }
            )
        return result
