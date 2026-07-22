"""
Event Bus — In-process pub/sub event system.

Phase 1: In-memory ring buffer, at-least-once delivery, prefix pattern matching.
"""
import uuid
import time
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from enum import Enum


class HandlerResult(Enum):
    ACK = "ack"
    RETRY = "retry"
    SKIP = "skip"


@dataclass
class Event:
    event_id: str
    event_type: str
    source: str
    timestamp: float
    correlation_id: str
    data_version: str = "1.0.0"
    payload: Dict[str, Any] = field(default_factory=dict)
    causation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    _frozen: bool = field(default=False, repr=False)

    def __post_init__(self):
        self._frozen = True

    def __setattr__(self, name, value):
        if getattr(self, "_frozen", False) and name != "_frozen":
            raise ValueError(f"Event is immutable: cannot modify '{name}'")
        super().__setattr__(name, value)

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "source": self.source,
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id,
            "data_version": self.data_version,
            "payload": dict(self.payload),
            "causation_id": self.causation_id,
            "metadata": dict(self.metadata),
        }


MAX_EVENT_SIZE_BYTES = 1_000_000  # 1 MB


class EventBus:
    """In-process Event Bus. Central communication backbone."""

    def __init__(self, max_events: int = 10000):
        self._subscribers: Dict[str, List[Callable]] = {}  # exact type → handlers
        self._pattern_subscribers: List[tuple] = []  # (pattern, handler)
        self._correlation_subscribers: Dict[str, List[Callable]] = {}  # corr_id → handlers
        self._store = InMemoryEventStore(max_events=max_events)
        self._lock = threading.RLock()

    # ── Publish ──

    def publish(self, event: Event) -> None:
        """Publish an event. Silently ignores duplicate event_ids."""
        if event.event_id in self._store._event_ids:
            return

        payload_size = len(str(event.payload))
        if payload_size > MAX_EVENT_SIZE_BYTES:
            raise ValueError(f"Event payload exceeds {MAX_EVENT_SIZE_BYTES} bytes")

        with self._lock:
            self._store.append(event)
            self._deliver(event)

    def _deliver(self, event: Event) -> None:
        """Deliver event to all matching subscribers."""
        # Exact type
        for handler in self._subscribers.get(event.event_type, []):
            self._invoke_handler(handler, event)

        # Pattern
        for pattern, handler in self._pattern_subscribers:
            if self._match_pattern(pattern, event.event_type):
                self._invoke_handler(handler, event)

        # Correlation
        for handler in self._correlation_subscribers.get(event.correlation_id, []):
            self._invoke_handler(handler, event)

    @staticmethod
    def _match_pattern(pattern: str, event_type: str) -> bool:
        """Prefix-only matching: 'task.*' matches 'task.created', 'task.completed', etc."""
        if pattern.endswith(".*"):
            prefix = pattern[:-2]
            return event_type.startswith(prefix + ".")
        return pattern == event_type

    @staticmethod
    def _invoke_handler(handler, event: Event) -> None:
        """Invoke handler; respect Ack/Retry/Skip results."""
        max_retries = 3
        for _ in range(max_retries):
            result = handler(event)
            if result == HandlerResult.ACK:
                return
            elif result == HandlerResult.SKIP:
                return
            elif result == HandlerResult.RETRY:
                continue
            else:
                return  # unknown → treat as ACK

    # ── Subscribe ──

    def subscribe(self, event_type: str, handler: Callable) -> None:
        with self._lock:
            self._subscribers.setdefault(event_type, []).append(handler)

    def subscribe_pattern(self, pattern: str, handler: Callable) -> None:
        with self._lock:
            self._pattern_subscribers.append((pattern, handler))

    def subscribe_correlation(self, correlation_id: str, handler: Callable) -> None:
        with self._lock:
            self._correlation_subscribers.setdefault(correlation_id, []).append(handler)

    # ── Replay ──

    def replay_from(self, from_position: int, handler: Callable) -> int:
        events = self._store.read_from(from_position)
        for event in events:
            handler(event)
        return len(events)

    def replay_correlation(self, correlation_id: str, handler: Callable) -> int:
        count = 0
        for event in self._store._events:
            if event.correlation_id == correlation_id:
                handler(event)
                count += 1
        return count

    # ── Store ──

    @property
    def store(self):
        return self._store

    def total_events(self) -> int:
        return len(self._store._events)


class InMemoryEventStore:
    """Phase 1: In-memory ring buffer event store."""

    def __init__(self, max_events: int = 10000):
        self._events: List[Event] = []
        self._event_ids: set = set()
        self._max_events = max_events
        self._position = 0

    def append(self, event: Event) -> None:
        if event.event_id in self._event_ids:
            return  # Idempotent
        if len(self._events) >= self._max_events:
            removed = self._events.pop(0)
            self._event_ids.discard(removed.event_id)
            self._position += 1
        self._events.append(event)
        self._event_ids.add(event.event_id)

    def read_from(self, from_position: int) -> List[Event]:
        idx = from_position - self._position
        if idx < 0:
            idx = 0
        return list(self._events[idx:])

    def get_by_correlation(self, correlation_id: str) -> List[Event]:
        return [e for e in self._events if e.correlation_id == correlation_id]

    def __len__(self):
        return len(self._events)
