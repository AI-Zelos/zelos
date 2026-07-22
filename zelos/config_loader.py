"""
zelos.yaml Configuration Loader

Reads and validates zelos.yaml, providing defaults for all settings.
"""
import os
import json
from typing import Any, Dict, List, Optional

VALID_PLUGIN_TYPES = {"storage", "memory", "policy", "scoring_strategy", "verifier", "planner", "adapter"}
VALID_AUTH_ROLES = {"admin", "agent", "client"}
DEFAULT_CONFIG = {
    "runtime": {
        "instance_id": "zelos-default",
        "api": {"host": "127.0.0.1", "port": 9876},
        "auth": {"method": "api_key", "keys": []},
        "limits": {"max_goals": 100, "max_tasks_per_goal": 50, "global_max_tasks": 500},
        "logging": {"level": "info", "format": "json"},
    },
    "plugins": [],
}


class ConfigLoader:
    """Loads and validates zelos.yaml configuration."""

    def __init__(self):
        self._config: Dict[str, Any] = {}

    def load(self, path: str) -> Dict[str, Any]:
        """Load configuration from a YAML file."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Configuration file not found: {path}")

        with open(path, "r") as f:
            content = f.read()

        data = self._parse_yaml(content)
        self._config = self._apply_defaults(data)
        self._validate(self._config)
        return self._config

    def load_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Load configuration from a dict (for programmatic use)."""
        self._config = self._apply_defaults(data)
        self._validate(self._config)
        return self._config

    @property
    def config(self) -> Dict[str, Any]:
        return dict(self._config)

    # ── YAML Parser (Phase 1: supports YAML subset — no external dependency) ──

    def _parse_yaml(self, content: str) -> Dict[str, Any]:
        """Parse a YAML-like config. Phase 1: also supports JSON."""
        # Try JSON first (useful for testing)
        content = content.strip()
        if content.startswith("{"):
            return json.loads(content)

        # Try YAML (simple subset: key: value, nested via indentation)
        try:
            import yaml
            return yaml.safe_load(content)
        except ImportError:
            pass

        # Fallback: basic YAML parser for simple configs
        return self._parse_simple_yaml(content)

    def _parse_simple_yaml(self, content: str) -> Dict[str, Any]:
        """Minimal YAML parser supporting nested dicts, lists, scalars."""
        lines = content.split("\n")
        result = {}
        stack = [(result, -1)]  # (dict, indent)

        for line in lines:
            stripped = line.rstrip()
            if not stripped or stripped.strip().startswith("#"):
                continue

            indent = len(line) - len(line.lstrip())
            key_part = stripped.split("#")[0].strip()

            if ":" not in key_part:
                continue

            # Pop stack to correct indent level
            while stack and stack[-1][1] >= indent:
                stack.pop()

            key, _, value = key_part.partition(":")
            key = key.strip().strip('"').strip("'")
            value = value.strip()

            current_dict = stack[-1][0]

            if value == "" or value == "{}":
                # Nested dict — expect indented children
                new_dict = {}
                current_dict[key] = new_dict
                stack.append((new_dict, indent))
            elif value.startswith("[") and value.endswith("]"):
                # List
                items = value[1:-1].split(",")
                current_dict[key] = [i.strip().strip('"').strip("'") for i in items if i.strip()]
            elif value in ("true", "True", "yes"):
                current_dict[key] = True
            elif value in ("false", "False", "no"):
                current_dict[key] = False
            elif value == "null" or value == "~":
                current_dict[key] = None
            else:
                # Scalar
                stripped_val = value.strip('"').strip("'")
                try:
                    if "." in stripped_val:
                        current_dict[key] = float(stripped_val)
                    else:
                        current_dict[key] = int(stripped_val)
                except ValueError:
                    current_dict[key] = stripped_val

        return result

    # ── Defaults ──

    def _apply_defaults(self, data: Dict) -> Dict:
        """Deep-merge user config with defaults."""
        result = json.loads(json.dumps(DEFAULT_CONFIG))  # Deep copy

        if "runtime" in data:
            rt = data["runtime"]
            if "api" in rt:
                result["runtime"]["api"].update(rt["api"])
            if "auth" in rt:
                result["runtime"]["auth"].update(rt["auth"])
            if "limits" in rt:
                result["runtime"]["limits"].update(rt["limits"])
            if "logging" in rt:
                result["runtime"]["logging"].update(rt["logging"])
            if "instance_id" in rt:
                result["runtime"]["instance_id"] = rt["instance_id"]
        if "plugins" in data:
            result["plugins"] = data["plugins"]

        return result

    # ── Validation ──

    def _validate(self, config: Dict) -> None:
        plugins = config.get("plugins", [])
        for p in plugins:
            if not isinstance(p, dict):
                raise ValueError(f"Plugin entry must be a dict: {p}")

            if "id" not in p:
                raise ValueError(f"Plugin missing required field: id")

            ptype = p.get("type", "")
            if ptype and ptype not in VALID_PLUGIN_TYPES:
                raise ValueError(
                    f"Unknown plugin type '{ptype}' for plugin '{p['id']}'. "
                    f"Valid types: {', '.join(sorted(VALID_PLUGIN_TYPES))}"
                )

        # Validate auth keys
        keys = config.get("runtime", {}).get("auth", {}).get("keys", [])
        for k in keys:
            if not isinstance(k, dict) or "key" not in k:
                raise ValueError(f"Auth key entry must have 'key' field: {k}")
            role = k.get("role", "agent")
            if role not in VALID_AUTH_ROLES:
                raise ValueError(f"Invalid auth role '{role}'. Valid: {', '.join(VALID_AUTH_ROLES)}")


def load_config(path: Optional[str] = None) -> Dict[str, Any]:
    """Convenience: load config from path, or return defaults."""
    loader = ConfigLoader()
    if path and os.path.exists(path):
        return loader.load(path)
    return loader.load_dict({})
