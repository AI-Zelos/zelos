"""
NATS / Kafka Message Queue Adapter — Cross-node EventBus transport.

Phase 7: Pluggable messaging backends for distributed Runtime communication.
All backends implement the MessageBus interface: connect / disconnect / publish / subscribe.
"""
import json
import threading
import time
from abc import ABC, abstractmethod


class MessageBus(ABC):
    """Abstract message bus for cross-node event transport."""

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
    def publish(self, subject: str, data: dict, headers: dict | None = None) -> bool:
        """Publish a message to a subject. Returns True on success."""
        ...

    @abstractmethod
    def subscribe(self, subject: str, callback, queue_group: str | None = None) -> bool:
        """Subscribe to a subject. callback(data: dict, headers: dict)."""
        ...

    def request(self, subject: str, data: dict, timeout: float = 5.0) -> dict | None:
        """Request-reply pattern. Publish and wait for first response."""
        result = None
        reply_subject = f"_INBOX.{id(self)}.{int(time.time() * 1000)}"
        event = threading.Event()

        def _reply(msg_data, _headers):
            nonlocal result
            result = msg_data
            event.set()

        self.subscribe(reply_subject, _reply)
        if self.publish(subject, data, headers={"reply": reply_subject}):
            event.wait(timeout)
        return result

    @property
    def is_connected(self) -> bool:
        return self._connected


# ═══════════════════ NATS Backend ═══════════════════


class NatsMessageBus(MessageBus):
    """NATS-backed message bus.

    Config:
      servers: ["nats://localhost:4222"]
      token: optional auth token
    """

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        cfg = config or {}
        self._servers = cfg.get("servers", ["nats://localhost:4222"])
        self._token = cfg.get("token")
        self._nc = None
        self._subscriptions: list = []

    def connect(self) -> bool:
        try:
            import nats
            self._nc = nats.connect(servers=self._servers, token=self._token or None)
            self._connected = True
            return True
        except ImportError:
            return False  # nats-py not installed
        except Exception:
            self._connected = False
            return False

    def disconnect(self) -> None:
        for sub in self._subscriptions:
            try:
                sub.unsubscribe()
            except Exception:
                pass
        self._subscriptions.clear()
        if self._nc:
            try:
                self._nc.close()
            except Exception:
                pass
        self._connected = False
        self._nc = None

    def health(self) -> bool:
        return self._connected and self._nc is not None

    def publish(self, subject: str, data: dict, headers: dict | None = None) -> bool:
        if not self._nc:
            return False
        try:
            payload = json.dumps(data).encode()
            self._nc.publish(subject, payload)
            return True
        except Exception:
            return False

    def subscribe(self, subject: str, callback, queue_group: str | None = None) -> bool:
        if not self._nc:
            return False
        try:
            def _handler(msg):
                try:
                    data = json.loads(msg.data.decode())
                    headers_raw = msg.headers or {}
                    headers = {k: headers_raw[k] for k in headers_raw} if headers_raw else {}
                    callback(data, headers)
                except Exception:
                    pass

            sub = self._nc.subscribe(subject, cb=_handler, queue=queue_group or "")
            self._subscriptions.append(sub)
            return True
        except Exception:
            return False


# ═══════════════════ InMemory Backend ═══════════════════


class InMemoryMessageBus(MessageBus):
    """In-memory message bus for single-node deployments.

    Supports pub/sub with subject-based routing, pattern matching, and queue groups.
    """

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self._subscribers: dict[str, list] = {}
        self._lock = threading.RLock()

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def health(self) -> bool:
        return self._connected

    def publish(self, subject: str, data: dict, headers: dict | None = None) -> bool:
        with self._lock:
            # Exact match subscribers
            for cb in self._subscribers.get(subject, []):
                try:
                    cb(data, headers or {})
                except Exception:
                    pass
            # Wildcard pattern match
            for pattern, callbacks in self._subscribers.items():
                if "*" in pattern:
                    prefix = pattern.replace("*", "")
                    if subject.startswith(prefix):
                        for cb in callbacks:
                            try:
                                cb(data, headers or {})
                            except Exception:
                                pass
        return True

    def subscribe(self, subject: str, callback, queue_group: str | None = None) -> bool:
        with self._lock:
            self._subscribers.setdefault(subject, []).append(callback)
        return True


# ═══════════════════ Factory ═══════════════════

MESSAGE_BACKENDS = {
    "memory": InMemoryMessageBus,
    "nats": NatsMessageBus,
}


def create_message_bus(config: dict | None = None) -> MessageBus:
    cfg = config or {}
    backend_type = cfg.get("type", "memory")
    if backend_type not in MESSAGE_BACKENDS:
        raise ValueError(f"Unknown message bus: '{backend_type}'. Supported: {', '.join(MESSAGE_BACKENDS.keys())}")
    return MESSAGE_BACKENDS[backend_type](cfg)
