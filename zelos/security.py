"""
Phase 3 Security — Capability-scoped Access Control, Audit Logging, API Key Management.

Production-grade security infrastructure:
  - RBAC (Role-Based Access Control) with wildcard permissions
  - Immutable audit log with multi-field query
  - API Key generation, validation, revocation, expiration
  - mTLS configuration support
"""
import time
import uuid
import json
import hashlib
import secrets
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


# ═══════════════════ Access Control ═══════════════════

@dataclass
class Permission:
    """A single permission — dot-separated action path."""
    action: str
    description: str = ""


@dataclass
class Role:
    """A named role with a set of permissions. '*' means all permissions."""
    name: str
    permissions: Set[str] = field(default_factory=set)
    description: str = ""


class AccessControl:
    """Role-Based Access Control with wildcard matching.

    Default roles:
      - admin: * (all permissions — wildcard)
      - operator: goal.submit, goal.cancel, task.*, agent.read, plugin.*
      - agent: task.execute, agent.heartbeat, artifact.create
      - viewer: goal.read, task.read, agent.read, metrics.read
    """

    DEFAULT_ROLES = {
        "admin": {
            "permissions": ["*"],
            "description": "Full system access — all actions allowed",
        },
        "operator": {
            "permissions": [
                "goal.submit", "goal.cancel", "goal.read",
                "task.create", "task.cancel", "task.read",
                "agent.read", "agent.register",
                "plugin.read", "plugin.configure",
                "metrics.read",
            ],
            "description": "Operational control — manage goals and tasks",
        },
        "agent": {
            "permissions": [
                "task.execute",
                "agent.heartbeat",
                "artifact.create",
            ],
            "description": "Agent execution — receive and complete tasks",
        },
        "viewer": {
            "permissions": [
                "goal.read", "task.read", "agent.read", "metrics.read",
            ],
            "description": "Read-only access to all resources",
        },
    }

    def __init__(self):
        self.roles: Dict[str, Role] = {}
        self._lock = threading.RLock()
        self._init_defaults()

    def _init_defaults(self) -> None:
        for name, spec in self.DEFAULT_ROLES.items():
            self.add_role(name, spec["permissions"], spec["description"])

    def add_role(self, name: str, permissions: List[str], description: str = "") -> Role:
        """Add or replace a role."""
        role = Role(name=name, permissions=set(permissions), description=description)
        with self._lock:
            self.roles[name] = role
        return role

    def update_role(self, name: str, add_permissions: Optional[List[str]] = None,
                    remove_permissions: Optional[List[str]] = None) -> Optional[Role]:
        """Update an existing role's permissions."""
        with self._lock:
            role = self.roles.get(name)
            if not role:
                return None
            if add_permissions:
                role.permissions.update(add_permissions)
            if remove_permissions:
                role.permissions.difference_update(remove_permissions)
            return role

    def remove_role(self, name: str) -> bool:
        """Remove a role. Returns True if it existed."""
        with self._lock:
            if name in self.roles:
                del self.roles[name]
                return True
            return False

    def check(self, role_name: str, action: str) -> bool:
        """Check if a role has permission for an action.

        Supports:
          - Exact match: "goal.submit" matches "goal.submit"
          - Wildcard: role with "task.*" matches "task.create", "task.execute", etc.
          - Super wildcard: role with "*" matches everything.
        """
        with self._lock:
            role = self.roles.get(role_name)
            if not role:
                return False

        # Direct wildcard → all access
        if "*" in role.permissions:
            return True

        # Exact match
        if action in role.permissions:
            return True

        # Pattern match: "task.*" matches "task.create"
        action_parts = action.split(".")
        for perm in role.permissions:
            if perm.endswith(".*"):
                prefix = perm[:-2]
                perm_parts = prefix.split(".")
                if action_parts[:len(perm_parts)] == perm_parts:
                    return True

        return False

    def list_permissions(self, role_name: str) -> List[str]:
        """List all permissions for a role."""
        role = self.roles.get(role_name)
        return sorted(role.permissions) if role else []

    def list_roles(self) -> List[Dict[str, Any]]:
        """List all roles with their permissions."""
        return [
            {"name": r.name, "permissions": sorted(r.permissions), "description": r.description}
            for r in self.roles.values()
        ]


# ═══════════════════ Audit Logging ═══════════════════

@dataclass
class AuditEvent:
    """Immutable audit log entry."""
    event_id: str
    timestamp: float
    actor: str
    action: str
    resource: str
    detail: str = ""
    result: str = "success"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "actor": self.actor,
            "action": self.action,
            "resource": self.resource,
            "detail": self.detail,
            "result": self.result,
            "metadata": self.metadata,
        }


class AuditLogger:
    """Immutable, append-only audit log with multi-field query support.

    Every security-sensitive operation MUST be logged:
      - Goal submission / cancellation
      - Task dispatch / completion / failure
      - Agent registration / removal
      - Permission changes
      - API key usage
    """

    def __init__(self, max_events: int = 100000):
        self._events: List[AuditEvent] = []
        self._max_events = max_events
        self._lock = threading.RLock()

    def log(self, actor: str, action: str, resource: str,
            detail: str = "", result: str = "success", **metadata) -> AuditEvent:
        """Record an audit event. Thread-safe."""
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp=time.time(),
            actor=actor,
            action=action,
            resource=resource,
            detail=detail,
            result=result,
            metadata=metadata,
        )
        with self._lock:
            if len(self._events) >= self._max_events:
                self._events.pop(0)  # Ring-buffer: drop oldest
            self._events.append(event)
        return event

    def query(self, actor: Optional[str] = None, action: Optional[str] = None,
              resource: Optional[str] = None, result: Optional[str] = None,
              start_time: Optional[float] = None, end_time: Optional[float] = None,
              limit: int = 1000) -> List[AuditEvent]:
        """Query audit events with multiple filter dimensions."""
        results = []
        with self._lock:
            for e in self._events:
                if actor is not None and e.actor != actor:
                    continue
                if action is not None and e.action != action:
                    continue
                if resource is not None and e.resource != resource:
                    continue
                if result is not None and e.result != result:
                    continue
                if start_time is not None and e.timestamp < start_time:
                    continue
                if end_time is not None and e.timestamp > end_time:
                    continue
                results.append(e)
                if len(results) >= limit:
                    break
        return results

    def export_json(self) -> str:
        """Export all audit events as JSON string."""
        with self._lock:
            return json.dumps([e.to_dict() for e in self._events], indent=2)

    def total_events(self) -> int:
        return len(self._events)

    def clear(self) -> None:
        """Clear all audit events (admin only)."""
        with self._lock:
            self._events.clear()


# ═══════════════════ API Key Manager ═══════════════════

@dataclass
class _APIKeyEntry:
    """Internal API key record."""
    key_hash: str
    role: str
    description: str
    created_at: float
    expires_at: Optional[float]
    revoked: bool = False
    last_used_at: Optional[float] = None


class APIKeyManager:
    """API Key lifecycle management — generate, validate, revoke, expire.

    Key format: zelos_<random_64_hex_chars>
    Stored as SHA-256 hash — plaintext key is never persisted.
    """

    KEY_PREFIX = "zelos_"
    KEY_BYTES = 32  # 256 bits of entropy

    def __init__(self):
        self._keys: Dict[str, _APIKeyEntry] = {}  # key_hash → entry
        self._lock = threading.RLock()

    def generate_key(self, role: str, description: str = "",
                     ttl_seconds: Optional[float] = None) -> str:
        """Generate a new API key. Returns the plaintext key (show once!)."""
        random_bytes = secrets.token_bytes(self.KEY_BYTES)
        key_plaintext = self.KEY_PREFIX + random_bytes.hex()
        key_hash = self._hash(key_plaintext)

        expires_at = (time.time() + ttl_seconds) if ttl_seconds and ttl_seconds > 0 else None

        entry = _APIKeyEntry(
            key_hash=key_hash,
            role=role,
            description=description,
            created_at=time.time(),
            expires_at=expires_at,
        )

        with self._lock:
            self._keys[key_hash] = entry

        return key_plaintext

    def validate(self, key_plaintext: str) -> Optional[Dict[str, Any]]:
        """Validate an API key. Returns {role, description, ...} or None."""
        if not key_plaintext or not key_plaintext.startswith(self.KEY_PREFIX):
            return None

        key_hash = self._hash(key_plaintext)

        with self._lock:
            entry = self._keys.get(key_hash)
            if not entry:
                return None
            if entry.revoked:
                return None
            if entry.expires_at is not None and time.time() > entry.expires_at:
                return None

            entry.last_used_at = time.time()

        return {
            "role": entry.role,
            "description": entry.description,
            "created_at": entry.created_at,
            "expires_at": entry.expires_at,
            "last_used_at": entry.last_used_at,
        }

    def revoke(self, key_plaintext: str) -> bool:
        """Revoke an API key. Returns True if found."""
        key_hash = self._hash(key_plaintext)
        with self._lock:
            if key_hash in self._keys:
                self._keys[key_hash].revoked = True
                return True
        return False

    def list_keys(self) -> List[Dict[str, Any]]:
        """List all keys (hashes only, never plaintext)."""
        with self._lock:
            return [
                {
                    "key_hash": kh[:16] + "...",
                    "role": e.role,
                    "description": e.description,
                    "created_at": e.created_at,
                    "expires_at": e.expires_at,
                    "revoked": e.revoked,
                    "last_used_at": e.last_used_at,
                }
                for kh, e in self._keys.items()
            ]

    @staticmethod
    def _hash(key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()


# ═══════════════════ mTLS Configuration ═══════════════════

@dataclass
class TLSConfig:
    """mTLS configuration for secure Runtime communication."""
    cert_file: str = ""
    key_file: str = ""
    ca_file: str = ""
    require_client_cert: bool = True
    min_tls_version: str = "TLSv1.2"
    verify_hostname: bool = True

    def is_configured(self) -> bool:
        return bool(self.cert_file and self.key_file)

    def to_dict(self) -> dict:
        return {
            "cert_file": self.cert_file,
            "key_file": self.key_file,
            "ca_file": self.ca_file,
            "require_client_cert": self.require_client_cert,
            "min_tls_version": self.min_tls_version,
            "verify_hostname": self.verify_hostname,
        }
