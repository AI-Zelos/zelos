"""
Plugin Lifecycle Manager — Discovers, loads, configures, and manages plugin lifecycle.
"""
import time
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from enum import Enum


class PluginStatus(Enum):
    UNLOADED = "UNLOADED"
    LOADED = "LOADED"
    CONFIGURED = "CONFIGURED"
    INITIALIZED = "INITIALIZED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    ERROR = "ERROR"
    PAUSED = "PAUSED"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"


PLUGIN_LOAD_ORDER = ["storage", "memory", "policy", "scoring_strategy", "verifier", "planner", "adapter"]


@dataclass
class PluginManifest:
    plugin_id: str
    plugin_type: str
    version: str
    display_name: str = ""
    description: str = ""
    entrypoint: str = ""
    dependencies: List[str] = field(default_factory=list)
    runtime_api_version: str = "1.0.0"
    config_schema: Dict[str, Any] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)
    restart_policy: str = "always"  # always | never | on_crash
    max_restarts: int = 5


@dataclass
class PluginInstance:
    manifest: PluginManifest
    status: PluginStatus = PluginStatus.UNLOADED
    restarts: int = 0
    instance: Any = None  # The actual plugin object
    load_error: Optional[str] = None


class PluginLifecycleManager:
    """Kernel component — plugin lifecycle management."""

    def __init__(self):
        self._plugins: Dict[str, PluginInstance] = {}  # plugin_id → PluginInstance
        self._plugin_factory: Dict[str, Callable] = {}  # plugin_id → factory function
        self._health_check_interval: float = 10.0
        self._lock = threading.RLock()

    # ── Discovery ──

    def discover_from_config(self, plugin_configs: List[dict]) -> List[PluginManifest]:
        manifests = []
        for cfg in plugin_configs:
            manifest = PluginManifest(
                plugin_id=cfg["id"],
                plugin_type=cfg.get("type", ""),
                version=cfg.get("version", "0.1.0"),
                display_name=cfg.get("display_name", cfg["id"]),
                description=cfg.get("description", ""),
                entrypoint=cfg.get("entrypoint", ""),
                dependencies=cfg.get("dependencies", []),
                runtime_api_version=cfg.get("runtime_api_version", "1.0.0"),
                config_schema=cfg.get("config_schema", {}),
                config=cfg.get("config", {}),
                restart_policy=cfg.get("restart_policy", "always"),
                max_restarts=cfg.get("max_restarts", 5),
            )
            manifests.append(manifest)
        return manifests

    # ── Loading ──

    def load_all(self, manifests: List[PluginManifest]) -> List[PluginInstance]:
        """Load plugins in topological order by type."""
        # Sort by load order
        type_order = {t: i for i, t in enumerate(PLUGIN_LOAD_ORDER)}

        def sort_key(m: PluginManifest):
            return (type_order.get(m.plugin_type, 99), m.plugin_id)

        manifests.sort(key=sort_key)

        # Check for circular dependencies
        self._check_circular_deps(manifests)

        # Topological sort within same type
        sorted_manifests = self._topological_sort(manifests)

        instances = []
        for m in sorted_manifests:
            inst = self._load_one(m)
            instances.append(inst)
        return instances

    def _load_one(self, manifest: PluginManifest) -> PluginInstance:
        inst = PluginInstance(manifest=manifest)
        self._plugins[manifest.plugin_id] = inst

        # Version check
        if not self._version_compatible(manifest.runtime_api_version, "1.0.0"):
            inst.status = PluginStatus.ERROR
            inst.load_error = f"Runtime API version {manifest.runtime_api_version} not compatible"
            return inst

        # Config validation
        if manifest.config_schema:
            if not self._validate_config(manifest.config, manifest.config_schema):
                inst.status = PluginStatus.ERROR
                inst.load_error = "Config validation failed"
                return inst

        # Load
        inst.status = PluginStatus.LOADED
        inst.status = PluginStatus.CONFIGURED
        inst.status = PluginStatus.INITIALIZED
        inst.status = PluginStatus.STARTING

        # Create instance if factory registered
        if manifest.plugin_id in self._plugin_factory:
            try:
                inst.instance = self._plugin_factory[manifest.plugin_id](manifest.config)
            except Exception as e:
                inst.status = PluginStatus.ERROR
                inst.load_error = str(e)
                return inst

        inst.status = PluginStatus.RUNNING
        return inst

    def register_factory(self, plugin_id: str, factory: Callable) -> None:
        """Register a factory function for creating plugin instances."""
        self._plugin_factory[plugin_id] = factory

    # ── Lifecycle ──

    def stop_plugin(self, plugin_id: str) -> None:
        inst = self._plugins.get(plugin_id)
        if inst and inst.status == PluginStatus.RUNNING:
            inst.status = PluginStatus.STOPPING
            inst.status = PluginStatus.STOPPED

    def restart_plugin(self, plugin_id: str) -> bool:
        inst = self._plugins.get(plugin_id)
        if not inst:
            return False
        if inst.restarts >= inst.manifest.max_restarts:
            inst.status = PluginStatus.ERROR
            return False
        inst.restarts += 1
        inst.status = PluginStatus.STARTING
        inst.status = PluginStatus.RUNNING
        return True

    def health_check(self, plugin_id: str) -> bool:
        inst = self._plugins.get(plugin_id)
        if not inst or inst.status != PluginStatus.RUNNING:
            return False
        if inst.instance and hasattr(inst.instance, 'health'):
            try:
                return inst.instance.health()
            except Exception:
                return False
        return True  # No health method → assume healthy

    # ── Query ──

    def get_plugin(self, plugin_id: str) -> Optional[PluginInstance]:
        return self._plugins.get(plugin_id)

    def list_plugins(self, plugin_type: Optional[str] = None) -> List[PluginInstance]:
        result = list(self._plugins.values())
        if plugin_type:
            result = [p for p in result if p.manifest.plugin_type == plugin_type]
        return result

    def get_status(self, plugin_id: str) -> Optional[PluginStatus]:
        inst = self._plugins.get(plugin_id)
        return inst.status if inst else None

    # ── Internal ──

    @staticmethod
    def _version_compatible(required: str, actual: str) -> bool:
        """Check if actual >= required (simple semver prefix check)."""
        try:
            req_parts = required.lstrip(">=").strip().split(".")
            act_parts = actual.split(".")
            return tuple(map(int, act_parts)) >= tuple(map(int, req_parts))
        except Exception:
            return False

    @staticmethod
    def _validate_config(config: dict, schema: dict) -> bool:
        """Basic JSON Schema validation for config."""
        if "properties" not in schema:
            return True
        for key, prop in schema["properties"].items():
            if key in config:
                val = config[key]
                if "type" in prop:
                    expected = prop["type"]
                    if expected == "integer" and not isinstance(val, int):
                        return False
                    if expected == "string" and not isinstance(val, str):
                        return False
                if "minimum" in prop and isinstance(val, (int, float)):
                    if val < prop["minimum"]:
                        return False
                if "maximum" in prop and isinstance(val, (int, float)):
                    if val > prop["maximum"]:
                        return False
        return True

    def _topological_sort(self, manifests: List[PluginManifest]) -> List[PluginManifest]:
        """Topological sort within same type by dependencies."""
        id_to_manifest = {m.plugin_id: m for m in manifests}
        visited = set()
        result = []

        def dfs(m: PluginManifest):
            if m.plugin_id in visited:
                return
            visited.add(m.plugin_id)
            for dep_id in m.dependencies:
                if dep_id in id_to_manifest:
                    dfs(id_to_manifest[dep_id])
            result.append(m)

        for m in manifests:
            if m.plugin_id not in visited:
                dfs(m)
        return result

    def _check_circular_deps(self, manifests: List[PluginManifest]) -> None:
        """Check for circular dependencies."""
        id_to_manifest = {m.plugin_id: m for m in manifests}
        visiting = set()
        done = set()

        def visit(pid):
            if pid in done:
                return
            if pid in visiting:
                raise ValueError(f"Circular dependency detected involving '{pid}'")
            visiting.add(pid)
            m = id_to_manifest.get(pid)
            if m is None:
                return
            for dep_id in m.dependencies:
                if dep_id in id_to_manifest:
                    visit(dep_id)
            visiting.discard(pid)
            done.add(pid)

        for m in manifests:
            visit(m.plugin_id)
