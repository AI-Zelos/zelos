"""
Capability Registry — Index of all registered Capabilities and their Agent providers.
"""
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum


class CapabilityStatus(Enum):
    REGISTERED = "registered"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DEPRECATED = "deprecated"
    REMOVED = "removed"


@dataclass
class CapabilityEntry:
    name: str
    version: str
    description: str = ""
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    status: str = "registered"
    agent_id: str = ""
    agent_name: str = ""
    registered_at: float = 0.0
    max_concurrent_tasks: int = 5


class CapabilityRegistry:
    """Kernel component — indexes all registered Capabilities."""

    def __init__(self):
        self._capabilities: Dict[str, CapabilityEntry] = {}  # key = f"{name}@{version}@{agent_id}"
        self._by_agent: Dict[str, List[str]] = {}  # agent_id → [cap_keys]

    # ── Registration ──

    def register(
        self,
        agent_id: str,
        agent_name: str,
        capabilities: List[Dict[str, Any]],
    ) -> List[str]:
        """Register capabilities for an agent. Returns list of cap keys."""
        keys = []
        for cap in capabilities:
            key = f"{cap['name']}@{cap['version']}@{agent_id}"
            entry = CapabilityEntry(
                name=cap["name"],
                version=cap.get("version", "1.0.0"),
                description=cap.get("description", ""),
                input_schema=cap.get("input_schema", {}),
                output_schema=cap.get("output_schema", {}),
                tags=cap.get("tags", []),
                status="registered",
                agent_id=agent_id,
                agent_name=agent_name,
                registered_at=__import__("time").time(),
                max_concurrent_tasks=cap.get("max_concurrent_tasks", 5),
            )
            self._capabilities[key] = entry
            self._by_agent.setdefault(agent_id, []).append(key)
            keys.append(key)
        return keys

    def mark_available(self, agent_id: str) -> None:
        for key in self._by_agent.get(agent_id, []):
            if key in self._capabilities and self._capabilities[key].status != "removed":
                self._capabilities[key].status = "available"

    def mark_unavailable(self, agent_id: str) -> None:
        for key in self._by_agent.get(agent_id, []):
            if key in self._capabilities and self._capabilities[key].status not in ("removed",):
                self._capabilities[key].status = "unavailable"

    def deprecate(self, agent_id: str, name: str, version: str) -> None:
        key = f"{name}@{version}@{agent_id}"
        if key in self._capabilities:
            self._capabilities[key].status = "deprecated"

    def remove_agent(self, agent_id: str) -> None:
        """Remove all capabilities for an agent."""
        for key in self._by_agent.get(agent_id, []):
            self._capabilities.pop(key, None)
        self._by_agent.pop(agent_id, None)

    # ── Query ──

    def find_by_name(self, name: str, version_req: Optional[str] = None) -> List[CapabilityEntry]:
        results = []
        for entry in self._capabilities.values():
            if entry.name == name and entry.status != "removed":
                if version_req is None or self._version_matches(entry.version, version_req):
                    results.append(entry)
        return results

    def find_by_prefix(self, prefix: str) -> List[CapabilityEntry]:
        return [e for e in self._capabilities.values()
                if e.name.startswith(prefix) and e.status != "removed"]

    def find_by_tag(self, tags: List[str]) -> List[CapabilityEntry]:
        """AND logic: all required tags must be present."""
        tag_set = set(tags)
        return [e for e in self._capabilities.values()
                if e.status != "removed" and tag_set.issubset(set(e.tags))]

    def find_providers_for(self, name: str, version_req: Optional[str] = None) -> List[str]:
        """Returns list of agent_ids providing this capability."""
        entries = self.find_by_name(name, version_req)
        return list(set(e.agent_id for e in entries if e.status == "available"))

    def get_by_agent(self, agent_id: str) -> List[CapabilityEntry]:
        return [self._capabilities[k] for k in self._by_agent.get(agent_id, [])
                if k in self._capabilities]

    def list_all(self) -> List[CapabilityEntry]:
        return [e for e in self._capabilities.values() if e.status != "removed"]

    def get_stats(self) -> dict:
        by_status = {}
        for e in self._capabilities.values():
            by_status[e.status] = by_status.get(e.status, 0) + 1
        return {"total": len(self._capabilities), "by_status": by_status}

    @staticmethod
    def _version_matches(version: str, requirement: str) -> bool:
        """Simple version check. requirement format: '>=1.0, <2.0' or exact '1.0.0'."""
        try:
            v = tuple(map(int, version.split(".")))
            if "," in requirement:
                parts = [p.strip() for p in requirement.split(",")]
                for p in parts:
                    if p.startswith(">="):
                        min_v = tuple(map(int, p[2:].strip().split(".")))
                        if v < min_v:
                            return False
                    elif p.startswith("<"):
                        max_v = tuple(map(int, p[1:].strip().split(".")))
                        if v >= max_v:
                            return False
                return True
            if requirement.startswith(">="):
                return v >= tuple(map(int, requirement[2:].strip().split(".")))
            return version == requirement
        except Exception:
            return version == requirement
