"""
Pluggable Coordination Backends — Distributed leader election and service discovery.

Phase 7: InMemory (default), etcd, and abstract base for future backends (Consul, ZooKeeper).

All backends implement the CoordinationBackend interface:
  - register_node / deregister_node
  - elect_leader (campaign)
  - get_leader / watch_leader
  - heartbeat (lease renewal)
"""
import json
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class CoordinationNode:
    """A node registered in the coordination backend."""
    node_id: str
    host: str = ""
    port: int = 0
    capabilities: list[str] = None
    is_leader: bool = False
    last_heartbeat: float = 0.0

    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = []


class CoordinationBackend(ABC):
    """Abstract coordination backend for leader election and service discovery."""

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self._connected = False

    @abstractmethod
    def connect(self) -> bool: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def health(self) -> bool: ...

    @abstractmethod
    def register_node(self, node: CoordinationNode) -> bool:
        """Register this node in the cluster."""
        ...

    @abstractmethod
    def deregister_node(self, node_id: str) -> bool: ...

    @abstractmethod
    def elect_leader(self, node_id: str, ttl_seconds: float = 30.0) -> bool:
        """Campaign for leadership. Returns True if elected."""
        ...

    @abstractmethod
    def get_leader(self) -> str | None:
        """Get current leader node_id, or None."""
        ...

    @abstractmethod
    def watch_leader(self, callback: Callable[[str | None], None]) -> None:
        """Watch for leader changes. callback(new_leader_id or None)."""
        ...

    @abstractmethod
    def heartbeat(self, node_id: str) -> bool:
        """Renew leader lease. Returns False if lease expired."""
        ...

    @abstractmethod
    def list_nodes(self) -> list[CoordinationNode]: ...

    @property
    def is_connected(self) -> bool:
        return self._connected


# ═══════════════════ InMemory Backend ═══════════════════


class InMemoryCoordinationBackend(CoordinationBackend):
    """Phase 7 default: In-memory coordination for single-node deployments."""

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self._nodes: dict[str, CoordinationNode] = {}
        self._leader_id: str | None = None
        self._leader_ttl: float = 0.0
        self._leader_elected_at: float = 0.0
        self._watchers: list[Callable] = []
        self._lock = threading.RLock()
        self._monitor_thread: threading.Thread | None = None

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False
        if self._monitor_thread:
            self._monitor_thread = None

    def health(self) -> bool:
        return self._connected

    def register_node(self, node: CoordinationNode) -> bool:
        with self._lock:
            self._nodes[node.node_id] = node
        return True

    def deregister_node(self, node_id: str) -> bool:
        with self._lock:
            if node_id in self._nodes:
                del self._nodes[node_id]
            if self._leader_id == node_id:
                self._leader_id = None
        return True

    def elect_leader(self, node_id: str, ttl_seconds: float = 30.0) -> bool:
        with self._lock:
            if node_id not in self._nodes:
                return False
            # Lexicographically smallest node_id wins (Bully algorithm)
            candidates = sorted(self._nodes.keys())
            if candidates and candidates[0] == node_id:
                self._leader_id = node_id
                self._leader_ttl = ttl_seconds
                self._leader_elected_at = time.time()
                for w in self._watchers:
                    try:
                        w(node_id)
                    except Exception:
                        pass
                return True
        return False

    def get_leader(self) -> str | None:
        with self._lock:
            if self._leader_id and time.time() - self._leader_elected_at > self._leader_ttl:
                self._leader_id = None
            return self._leader_id

    def watch_leader(self, callback: Callable[[str | None], None]) -> None:
        with self._lock:
            self._watchers.append(callback)

    def heartbeat(self, node_id: str) -> bool:
        with self._lock:
            if node_id == self._leader_id:
                self._leader_elected_at = time.time()
                node = self._nodes.get(node_id)
                if node:
                    node.last_heartbeat = time.time()
                return True
        return False

    def list_nodes(self) -> list[CoordinationNode]:
        with self._lock:
            return list(self._nodes.values())


# ═══════════════════ etcd Backend ═══════════════════


class EtcdCoordinationBackend(CoordinationBackend):
    """etcd v3 coordination backend.

    Uses etcd's lease + transaction for leader election (campaign pattern).
    Config:
      endpoints: "localhost:2379" (or comma-separated list)
      prefix: "/zelos/" (key prefix for all Zelos keys)
    """

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        cfg = config or {}
        self._endpoints = cfg.get("endpoints", "localhost:2379")
        self._prefix = cfg.get("prefix", "/zelos/")
        self._client = None
        self._lease_id = None

    def connect(self) -> bool:
        try:
            import etcd3
            host, port = self._endpoints.split(":") if ":" in self._endpoints else (self._endpoints, "2379")
            self._client = etcd3.client(host=host, port=int(port))
            self._connected = True
            return True
        except ImportError:
            return False  # etcd3 not installed
        except Exception:
            self._connected = False
            return False

    def disconnect(self) -> None:
        if self._lease_id and self._client:
            try:
                self._client.revoke_lease(self._lease_id)
            except Exception:
                pass
        self._connected = False
        self._client = None

    def health(self) -> bool:
        if not self._client or not self._connected:
            return False
        try:
            self._client.status()
            return True
        except Exception:
            return False

    def _key(self, name: str) -> str:
        return f"{self._prefix}{name}"

    def register_node(self, node: CoordinationNode) -> bool:
        if not self._client:
            return False
        try:
            data = json.dumps({
                "node_id": node.node_id, "host": node.host, "port": node.port,
                "capabilities": node.capabilities, "last_heartbeat": time.time(),
            })
            self._client.put(self._key(f"nodes/{node.node_id}"), data)
            return True
        except Exception:
            return False

    def deregister_node(self, node_id: str) -> bool:
        if not self._client:
            return False
        try:
            self._client.delete(self._key(f"nodes/{node_id}"))
            return True
        except Exception:
            return False

    def elect_leader(self, node_id: str, ttl_seconds: float = 30.0) -> bool:
        if not self._client:
            return False
        try:
            # Create a lease if not already held
            if not self._lease_id:
                lease = self._client.lease(int(ttl_seconds))
                self._lease_id = lease.id

            # Campaign: try to create the leader key with our lease (transaction)
            leader_key = self._key("leader")
            success, _ = self._client.transaction(
                compare=[self._client.transactions.version(leader_key) == 0],
                success=[self._client.transactions.put(leader_key, node_id, lease=self._lease_id)],
                failure=[],
            )
            return success
        except Exception:
            return False

    def get_leader(self) -> str | None:
        if not self._client:
            return None
        try:
            value, _ = self._client.get(self._key("leader"))
            return value.decode() if value else None
        except Exception:
            return None

    def watch_leader(self, callback: Callable[[str | None], None]) -> None:
        if not self._client:
            return
        def _watch():
            try:
                events, cancel = self._client.watch(self._key("leader"))
                for event in events:
                    new_leader = event.value.decode() if event.value else None
                    callback(new_leader)
            except Exception:
                pass
        t = threading.Thread(target=_watch, daemon=True)
        t.start()

    def heartbeat(self, node_id: str) -> bool:
        if not self._client or not self._lease_id:
            return False
        try:
            self._client.refresh_lease(self._lease_id)
            return True
        except Exception:
            return False

    def list_nodes(self) -> list[CoordinationNode]:
        if not self._client:
            return []
        nodes = []
        try:
            for value, _ in self._client.get_prefix(self._key("nodes/")):
                data = json.loads(value.decode())
                nodes.append(CoordinationNode(**{k: v for k, v in data.items() if k in CoordinationNode.__dataclass_fields__}))
        except Exception:
            pass
        return nodes


# ═══════════════════ Factory ═══════════════════

BACKENDS = {
    "memory": InMemoryCoordinationBackend,
    "etcd": EtcdCoordinationBackend,
}


def create_coordination_backend(config: dict | None = None) -> CoordinationBackend:
    """Create a coordination backend from config."""
    cfg = config or {}
    backend_type = cfg.get("type", "memory")
    if backend_type not in BACKENDS:
        raise ValueError(f"Unknown coordination backend: '{backend_type}'. Supported: {', '.join(BACKENDS.keys())}")
    return BACKENDS[backend_type](cfg)
