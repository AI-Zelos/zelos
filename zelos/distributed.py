"""
Phase 3 Distributed Runtime — Multi-node coordination, Leader Election, Work Stealing.

Enables Zelos to run as a cluster:
  - LeaderElection: Bully-algorithm-based leader election with heartbeat
  - WorkStealing: Idle nodes steal tasks from overloaded nodes
  - NodeRegistry: Track cluster membership, health, and capabilities
"""
import time
import uuid
import random
import threading
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


# ═══════════════════ Leader Election ═══════════════════

class LeaderState(Enum):
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"


@dataclass
class ElectionTerm:
    """Tracks the current election term."""
    term_number: int = 0
    voted_for: Optional[str] = None


class LeaderElection:
    """Simple bully-algorithm-based leader election.

    Each node has a unique node_id. The node with the highest
    priority (lexicographically smallest node_id) wins.

    In production, this would use etcd or Raft consensus.
    Phase 3 provides the reference implementation.
    """

    def __init__(self, node_id: str, heartbeat_interval_ms: int = 500,
                 election_timeout_ms: int = 2000, priority: int = 0):
        self.node_id = node_id
        self.heartbeat_interval_ms = heartbeat_interval_ms
        self.election_timeout_ms = election_timeout_ms
        self.priority = priority
        self.state = LeaderState.FOLLOWER
        self._term = ElectionTerm()
        self._leader_id: Optional[str] = None
        self._last_heartbeat: float = 0.0
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        self._peers: Dict[str, Dict[str, Any]] = {}  # node_id → {priority, last_seen}
        self._election_callbacks: List[callable] = []

    def start(self) -> None:
        """Start the election loop."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the election loop."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def is_leader(self) -> bool:
        return self.state == LeaderState.LEADER

    def get_leader_id(self) -> Optional[str]:
        return self._leader_id

    def register_peer(self, node_id: str, priority: int = 0) -> None:
        """Register another node in the cluster."""
        with self._lock:
            self._peers[node_id] = {"priority": priority, "last_seen": time.time()}

    def receive_heartbeat(self, from_node_id: str, term: int) -> None:
        """Receive a heartbeat from the leader."""
        with self._lock:
            if term >= self._term.term_number:
                self._term.term_number = term
                self.state = LeaderState.FOLLOWER
                self._leader_id = from_node_id
                self._last_heartbeat = time.time()
                if from_node_id in self._peers:
                    self._peers[from_node_id]["last_seen"] = time.time()

    def resign(self) -> None:
        """Voluntarily step down as leader."""
        with self._lock:
            if self.state == LeaderState.LEADER:
                self.state = LeaderState.FOLLOWER
                self._leader_id = None

    def on_leader_change(self, callback: callable) -> None:
        """Register a callback for leader change events."""
        self._election_callbacks.append(callback)

    def _loop(self) -> None:
        """Main election loop."""
        while self._running:
            now = time.time()

            if self.state == LeaderState.LEADER:
                # Send heartbeats
                self._last_heartbeat = now
                time.sleep(self.heartbeat_interval_ms / 1000)
                continue

            # Follower or Candidate — check for election timeout
            if now - self._last_heartbeat > self.election_timeout_ms / 1000:
                self._start_election()

            time.sleep(min(self.heartbeat_interval_ms, 200) / 1000)

    def _start_election(self) -> None:
        """Start a new election round."""
        with self._lock:
            self._term.term_number += 1
            self._term.voted_for = self.node_id
            self.state = LeaderState.CANDIDATE

        # Simple bully: highest priority (or lexicographically smallest node_id) wins
        # In single-node mode, always become leader
        if not self._peers:
            with self._lock:
                self.state = LeaderState.LEADER
                self._leader_id = self.node_id
                self._last_heartbeat = time.time()
            self._notify_leader_change(self.node_id)
        else:
            # Check if we have the highest priority among known peers
            all_nodes = list(self._peers.keys()) + [self.node_id]
            all_nodes.sort()  # Lexicographic sort
            winner = all_nodes[0]  # Smallest node_id wins
            if winner == self.node_id:
                with self._lock:
                    self.state = LeaderState.LEADER
                    self._leader_id = self.node_id
                    self._last_heartbeat = time.time()
                self._notify_leader_change(self.node_id)

    def _notify_leader_change(self, new_leader: str) -> None:
        for cb in self._election_callbacks:
            try:
                cb(new_leader)
            except Exception:
                pass


# ═══════════════════ Work Stealing ═══════════════════

class WorkStealing:
    """Work-stealing queue for distributed task scheduling.

    When a node is idle, it can steal READY tasks from overloaded nodes.
    Only steals READY (not in-flight) tasks.
    Respects the stealing node's capacity.
    """

    def __init__(self, node_id: str, max_concurrent_tasks: int = 10):
        self.node_id = node_id
        self.max_concurrent_tasks = max_concurrent_tasks
        self._ready_queue: List[Dict[str, Any]] = []
        self._lock = threading.RLock()

    def enqueue_task(self, task_id: str, capability: str,
                     priority: str = "medium", **metadata) -> None:
        """Add a READY task to the local queue."""
        with self._lock:
            self._ready_queue.append({
                "task_id": task_id,
                "capability": capability,
                "priority": priority,
                "status": "ready",
                "enqueued_at": time.time(),
                "metadata": metadata,
            })

    def dequeue_task(self) -> Optional[Dict[str, Any]]:
        """Get the next task (highest priority first)."""
        with self._lock:
            if not self._ready_queue:
                return None
            # Sort by priority
            order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            self._ready_queue.sort(key=lambda t: order.get(t["priority"], 2))
            return self._ready_queue.pop(0)

    def queue_size(self) -> int:
        with self._lock:
            return len(self._ready_queue)

    def can_accept_more(self) -> bool:
        return self.queue_size() < self.max_concurrent_tasks

    def steal_from(self, other: "WorkStealing", max_count: int = 5) -> List[Dict[str, Any]]:
        """Steal tasks from another node's queue."""
        stolen = []
        with self._lock:
            capacity = self.max_concurrent_tasks - len(self._ready_queue)
            steal_count = min(max_count, capacity)

        if steal_count <= 0:
            return stolen

        with other._lock:
            for _ in range(min(steal_count, len(other._ready_queue))):
                if other._ready_queue:
                    task = other._ready_queue.pop()
                    task["stolen_from"] = other.node_id
                    task["stolen_at"] = time.time()
                    stolen.append(task)

        with self._lock:
            self._ready_queue.extend(stolen)

        return stolen

    def get_load_percent(self) -> float:
        """Current load as percentage of max capacity."""
        return self.queue_size() / max(self.max_concurrent_tasks, 1) * 100


# ═══════════════════ Node Registry ═══════════════════

@dataclass
class ClusterNode:
    """A node in the Zelos cluster."""
    node_id: str
    host: str
    port: int
    capabilities: List[str] = field(default_factory=list)
    capacity: int = 10
    status: str = "unknown"  # unknown, healthy, degraded, dead
    last_heartbeat: float = 0.0
    registered_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "host": self.host,
            "port": self.port,
            "capabilities": self.capabilities,
            "capacity": self.capacity,
            "status": self.status,
            "last_heartbeat": self.last_heartbeat,
            "registered_at": self.registered_at,
            "metadata": self.metadata,
        }


class NodeRegistry:
    """Central registry of all nodes in the cluster.

    Tracks node health via heartbeats. Detects dead nodes.
    Provides capability-based lookup across the cluster.
    """

    def __init__(self, heartbeat_timeout_seconds: float = 30.0):
        self._nodes: Dict[str, ClusterNode] = {}
        self.heartbeat_timeout_seconds = heartbeat_timeout_seconds
        self._lock = threading.RLock()

    def register(self, node: ClusterNode) -> None:
        """Register a node in the cluster."""
        node.last_heartbeat = time.time()
        node.status = "healthy"
        with self._lock:
            self._nodes[node.node_id] = node

    def deregister(self, node_id: str) -> bool:
        """Remove a node from the cluster."""
        with self._lock:
            if node_id in self._nodes:
                del self._nodes[node_id]
                return True
        return False

    def heartbeat(self, node_id: str, timestamp: Optional[float] = None) -> bool:
        """Record a heartbeat from a node."""
        node = self._nodes.get(node_id)
        if not node:
            return False
        node.last_heartbeat = timestamp or time.time()
        node.status = "healthy"
        return True

    def get_node(self, node_id: str) -> Optional[ClusterNode]:
        return self._nodes.get(node_id)

    def node_count(self) -> int:
        return len(self._nodes)

    def list_nodes(self, status: Optional[str] = None) -> List[ClusterNode]:
        """List all nodes, optionally filtered by status."""
        nodes = list(self._nodes.values())
        if status:
            nodes = [n for n in nodes if n.status == status]
        return nodes

    def find_by_capability(self, capability_name: str) -> List[ClusterNode]:
        """Find nodes that provide a specific capability."""
        results = []
        for node in self._nodes.values():
            if capability_name in node.capabilities:
                results.append(node)
        return results

    def detect_dead_nodes(self, timeout_seconds: Optional[float] = None) -> List[str]:
        """Detect nodes that haven't sent heartbeats recently.

        Returns list of dead node IDs.
        """
        timeout = timeout_seconds or self.heartbeat_timeout_seconds
        now = time.time()
        dead = []
        for node in list(self._nodes.values()):
            if now - node.last_heartbeat > timeout:
                node.status = "dead"
                dead.append(node.node_id)
        return dead

    def cluster_status(self) -> Dict[str, Any]:
        """Aggregate cluster health info."""
        nodes = list(self._nodes.values())
        total = len(nodes)
        healthy = sum(1 for n in nodes if n.status == "healthy")
        degraded = sum(1 for n in nodes if n.status == "degraded")
        dead = sum(1 for n in nodes if n.status == "dead")

        all_caps: Set[str] = set()
        for n in nodes:
            all_caps.update(n.capabilities)

        return {
            "total_nodes": total,
            "healthy_nodes": healthy,
            "degraded_nodes": degraded,
            "dead_nodes": dead,
            "total_capacity": sum(n.capacity for n in nodes),
            "cluster_capabilities": sorted(all_caps),
            "leader_id": None,  # Set by Runtime
        }

    def get_node_by_host(self, host: str, port: int) -> Optional[ClusterNode]:
        for node in self._nodes.values():
            if node.host == host and node.port == port:
                return node
        return None
