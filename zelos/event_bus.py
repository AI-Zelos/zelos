"""
Event Bus — In-process pub/sub event system.

Phase 1: In-memory ring buffer, at-least-once delivery, prefix pattern matching.
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


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
    payload: dict[str, Any] = field(default_factory=dict)
    causation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    sequence_id: int = -1  # v0.8.0: monotonic sequence id, -1 = unassigned

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
            "sequence_id": self.sequence_id,
        }


MAX_EVENT_SIZE_BYTES = 1_000_000  # 1 MB


class EventBus:
    """In-process Event Bus. Central communication backbone."""

    def __init__(self, max_events: int = 10000):
        self._subscribers: dict[str, list[Callable]] = {}  # exact type → handlers
        self._pattern_subscribers: list[tuple] = []  # (pattern, handler)
        self._correlation_subscribers: dict[str, list[Callable]] = {}  # corr_id → handlers
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
    """Phase 1: In-memory ring buffer event store.

    v0.8.0: Auto-assigns monotonic sequence_id on append.
    Supports replay_from(sequence_id) for event sourcing.
    """

    def __init__(self, max_events: int = 10000):
        self._events: list[Event] = []
        self._event_ids: set = set()
        self._max_events = max_events
        self._position = 0
        self._next_sequence_id: int = 0  # v0.8.0: monotonic counter

    def append(self, event: Event) -> None:
        if event.event_id in self._event_ids:
            return  # Idempotent
        # v0.8.0: Auto-assign monotonic sequence_id
        if event.sequence_id < 0:
            # Need to bypass frozen check to set sequence_id
            object.__setattr__(event, "_frozen", False)
            event.sequence_id = self._next_sequence_id
            object.__setattr__(event, "_frozen", True)
        self._next_sequence_id = max(self._next_sequence_id, event.sequence_id + 1)
        if len(self._events) >= self._max_events:
            removed = self._events.pop(0)
            self._event_ids.discard(removed.event_id)
            self._position += 1
        self._events.append(event)
        self._event_ids.add(event.event_id)

    def read_from(self, from_position: int) -> list[Event]:
        idx = from_position - self._position
        if idx < 0:
            idx = 0
        return list(self._events[idx:])

    def replay_from(self, sequence_id: int) -> list[Event]:
        """v0.8.0: Return events with sequence_id >= given value."""
        return [e for e in self._events if e.sequence_id >= sequence_id]

    def get_by_correlation(self, correlation_id: str) -> list[Event]:
        return [e for e in self._events if e.correlation_id == correlation_id]

    def __len__(self):
        return len(self._events)


class PersistentEventStore:
    """Phase 2: Event store backed by a pluggable StorageBackend for durability.

    Wraps an InMemoryEventStore for fast reads and syncs writes to the backend.
    On init, replays persisted events into memory for crash recovery.

    v0.8.0: Supports sequence_id in recovery and replay_from.
    """

    def __init__(self, storage_backend, max_events: int = 10000):
        self._backend = storage_backend
        self._memory = InMemoryEventStore(max_events=max_events)
        self._stream = "zelos-events"

    def append(self, event: Event) -> None:
        self._memory.append(event)
        try:
            self._backend.append(self._stream, [event.to_dict()])
        except Exception:
            pass  # Best-effort durability; memory is authoritative

    def read_from(self, from_position: int) -> list[Event]:
        return self._memory.read_from(from_position)

    def replay_from(self, sequence_id: int) -> list[Event]:
        """v0.8.0: Return events with sequence_id >= given value."""
        return self._memory.replay_from(sequence_id)

    def recover(self) -> int:
        """Replay persisted events into memory after restart. Returns count recovered."""
        try:
            raw = self._backend.read(self._stream, 0, 100000)
            for r in raw:
                event = Event(
                    event_id=r["event_id"],
                    event_type=r["event_type"],
                    source=r.get("source", ""),
                    timestamp=r.get("timestamp", 0),
                    correlation_id=r.get("correlation_id", ""),
                    data_version=r.get("data_version", "1.0.0"),
                    payload=r.get("payload", {}),
                    causation_id=r.get("causation_id"),
                    metadata=r.get("metadata", {}),
                    sequence_id=r.get("sequence_id", -1),
                )
                self._memory.append(event)
            return len(raw)
        except Exception:
            return 0

    def get_by_correlation(self, correlation_id: str) -> list[Event]:
        return self._memory.get_by_correlation(correlation_id)

    def __len__(self):
        return len(self._memory)
