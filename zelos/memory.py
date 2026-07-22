"""
Memory Architecture — 6-layer context storage with pluggable providers.

Layers: session, project, user, knowledge, execution, skill.
Phase 1: In-memory provider with TTL, max entries, and search.
"""
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class MemoryLayer:
    """Labels for the 6 memory layers."""
    SESSION = "session"
    PROJECT = "project"
    USER = "user"
    KNOWLEDGE = "knowledge"
    EXECUTION = "execution"
    SKILL = "skill"

    ALL = [SESSION, PROJECT, USER, KNOWLEDGE, EXECUTION, SKILL]


@dataclass
class MemoryEntry:
    key: str
    value: Any
    layer: str
    created_at: float = 0.0
    updated_at: float = 0.0
    ttl_seconds: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self, now: Optional[float] = None) -> bool:
        if self.ttl_seconds is None:
            return False
        t = now or time.time()
        return t > (self.created_at + self.ttl_seconds)


class MemoryProvider(ABC):
    """Abstract base for memory storage backends."""

    @abstractmethod
    def store(self, layer: str, key: str, value: Any,
              ttl_seconds: Optional[float] = None, metadata: Optional[Dict] = None) -> None:
        ...

    @abstractmethod
    def retrieve(self, layer: str, key: str) -> Optional[Any]:
        ...

    @abstractmethod
    def update(self, layer: str, key: str, value: Any) -> None:
        ...

    @abstractmethod
    def delete(self, layer: str, key: str) -> None:
        ...

    @abstractmethod
    def search(self, layer: str, query: str) -> List[MemoryEntry]:
        ...


class InMemoryMemoryProvider(MemoryProvider):
    """Phase 1: In-memory memory provider with per-layer LRU eviction."""

    def __init__(self, config: Optional[Dict] = None):
        config = config or {}
        self.max_entries_per_layer = config.get("max_entries_per_layer", 5000)
        self.default_ttl = config.get("ttl_seconds")
        # layer → {key: MemoryEntry}, using OrderedDict for LRU
        self._layers: Dict[str, OrderedDict] = {
            layer: OrderedDict() for layer in MemoryLayer.ALL
        }

    def store(self, layer: str, key: str, value: Any,
              ttl_seconds: Optional[float] = None, metadata: Optional[Dict] = None) -> None:
        self._validate_layer(layer)
        entry = MemoryEntry(
            key=key, value=value, layer=layer,
            created_at=time.time(), updated_at=time.time(),
            ttl_seconds=ttl_seconds or self.default_ttl,
            metadata=metadata or {},
        )
        layer_dict = self._layers[layer]
        # LRU eviction: if at max, remove oldest
        if key not in layer_dict and len(layer_dict) >= self.max_entries_per_layer:
            layer_dict.popitem(last=False)  # Remove first (oldest)
        layer_dict[key] = entry
        layer_dict.move_to_end(key)

    def retrieve(self, layer: str, key: str) -> Optional[Any]:
        self._validate_layer(layer)
        entry = self._layers[layer].get(key)
        if entry is None:
            return None
        if entry.is_expired():
            del self._layers[layer][key]
            return None
        self._layers[layer].move_to_end(key)
        return entry.value

    def update(self, layer: str, key: str, value: Any) -> None:
        self._validate_layer(layer)
        entry = self._layers[layer].get(key)
        if entry is None:
            raise KeyError(f"No entry for '{key}' in layer '{layer}'")
        if entry.is_expired():
            del self._layers[layer][key]
            raise KeyError(f"Entry '{key}' in layer '{layer}' has expired")
        entry.value = value
        entry.updated_at = time.time()
        self._layers[layer].move_to_end(key)

    def delete(self, layer: str, key: str) -> None:
        self._validate_layer(layer)
        self._layers[layer].pop(key, None)

    def search(self, layer: str, query: str) -> List[MemoryEntry]:
        self._validate_layer(layer)
        results = []
        for entry in list(self._layers[layer].values()):
            if entry.is_expired():
                del self._layers[layer][entry.key]
                continue
            # Search in key and string representation of value
            if query.lower() in entry.key.lower():
                results.append(entry)
            elif query.lower() in str(entry.value).lower():
                results.append(entry)
        return results

    def _validate_layer(self, layer: str) -> None:
        if layer not in MemoryLayer.ALL:
            raise ValueError(f"Unknown memory layer: '{layer}'. Valid: {MemoryLayer.ALL}")


class ContextAssembler:
    """Assembles MemoryContext for Task dispatch from multiple memory layers."""

    def __init__(self, provider: MemoryProvider):
        self._provider = provider

    def assemble(self, task_id: str, goal_id: str,
                 project_id: Optional[str] = None,
                 user_id: Optional[str] = None) -> Dict[str, Any]:
        """Gather relevant context from all layers for a Task."""
        context = {
            "session": self._get_layer_entries(MemoryLayer.SESSION, goal_id),
            "project": self._get_layer_entries(MemoryLayer.PROJECT, project_id or goal_id),
            "user": self._get_layer_entries(MemoryLayer.USER, user_id or "default"),
            "knowledge": self._get_layer_entries(MemoryLayer.KNOWLEDGE, "global"),
            "execution": self._get_layer_entries(MemoryLayer.EXECUTION, task_id),
        }
        return context

    def _get_layer_entries(self, layer: str, scope: str) -> Dict[str, Any]:
        entries = self._provider.search(layer, scope)
        result = {}
        for e in entries:
            result[e.key] = e.value
        return result
