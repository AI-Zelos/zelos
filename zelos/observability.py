"""
Phase 2 Observability — Structured Logging, Metrics, Tracing.

OpenTelemetry-compatible format. Prometheus export for metrics.
"""

import json
import math
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Optional

# ═══════════════════ Structured Logging ═══════════════════


class StructuredLogger:
    """JSON-formatted structured logger with level filtering."""

    LEVELS = {"debug": 10, "info": 20, "warn": 30, "error": 40}

    def __init__(self, level: str = "info", format: str = "json"):
        self.level = level
        self.format = format
        self._min_level = self.LEVELS.get(level, 20)
        self._handlers: list[Callable] = []

    def add_handler(self, handler: Callable[[dict], None]) -> None:
        self._handlers.append(handler)

    def _log(self, level: str, message: str, **context) -> str | None:
        if self.LEVELS.get(level, 0) < self._min_level:
            return None

        entry = {
            "timestamp": time.time(),
            "level": level,
            "message": message,
            "context": context,
        }

        if self.format == "json":
            line = json.dumps(entry)
        else:
            line = f"[{level.upper()}] {message} {json.dumps(context) if context else ''}"

        for h in self._handlers:
            h(entry)

        return line

    def debug(self, message: str, **ctx) -> str | None:
        return self._log("debug", message, **ctx)

    def info(self, message: str, **ctx) -> str | None:
        return self._log("info", message, **ctx)

    def warn(self, message: str, **ctx) -> str | None:
        return self._log("warn", message, **ctx)

    def error(self, message: str, **ctx) -> str | None:
        return self._log("error", message, **ctx)


# ═══════════════════ Metrics ═══════════════════


class Counter:
    """Monotonically increasing counter."""

    def __init__(self, name: str, help: str = "", labels: dict | None = None):
        self.name = name
        self.help = help
        self._value: float = 0
        self._labels = labels or {}

    def inc(self, amount: float = 1) -> None:
        self._value += amount

    @property
    def value(self) -> float:
        return self._value


class Gauge:
    """Value that can go up and down."""

    def __init__(self, name: str, help: str = "", labels: dict | None = None):
        self.name = name
        self.help = help
        self._value: float = 0
        self._labels = labels or {}

    def set(self, value: float) -> None:
        self._value = value

    def inc(self, amount: float = 1) -> None:
        self._value += amount

    def dec(self, amount: float = 1) -> None:
        self._value -= amount

    @property
    def value(self) -> float:
        return self._value


class Histogram:
    """Distribution of values with percentile calculation."""

    def __init__(self, name: str, help: str = "", buckets: list[float] | None = None):
        self.name = name
        self.help = help
        self.buckets = buckets or [0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        self._values: list[float] = []
        self._lock = threading.Lock()

    def observe(self, value: float) -> None:
        with self._lock:
            self._values.append(value)

    def percentile(self, p: float) -> float:
        with self._lock:
            if not self._values:
                return 0.0
            sorted_vals = sorted(self._values)
            idx = int(math.ceil(p / 100.0 * len(sorted_vals))) - 1
            return sorted_vals[max(0, idx)]

    @property
    def count(self) -> int:
        return len(self._values)

    @property
    def sum(self) -> float:
        return sum(self._values)


class MetricsCollector:
    """Central metrics registry with Prometheus export support."""

    def __init__(self):
        self._counters: dict[str, Counter] = {}
        self._gauges: dict[str, Gauge] = {}
        self._histograms: dict[str, Histogram] = {}
        self._lock = threading.Lock()

    def counter(self, name: str, help: str = "") -> Counter:
        with self._lock:
            if name not in self._counters:
                self._counters[name] = Counter(name, help)
            return self._counters[name]

    def gauge(self, name: str, help: str = "") -> Gauge:
        with self._lock:
            if name not in self._gauges:
                self._gauges[name] = Gauge(name, help)
            return self._gauges[name]

    def histogram(self, name: str, help: str = "") -> Histogram:
        with self._lock:
            if name not in self._histograms:
                self._histograms[name] = Histogram(name, help)
            return self._histograms[name]

    def export_prometheus(self) -> str:
        """Export all metrics in Prometheus text format."""
        lines = []
        for c in self._counters.values():
            lbl_str = ",".join(f'{k}="{v}"' for k, v in c._labels.items())
            name = f"{c.name}{{{lbl_str}}}" if lbl_str else c.name
            lines.append(f"# HELP {c.name} {c.help}")
            lines.append(f"# TYPE {c.name} counter")
            lines.append(f"{name} {c.value}")
        for g in self._gauges.values():
            lbl_str = ",".join(f'{k}="{v}"' for k, v in g._labels.items())
            name = f"{g.name}{{{lbl_str}}}" if lbl_str else g.name
            lines.append(f"# HELP {g.name} {g.help}")
            lines.append(f"# TYPE {g.name} gauge")
            lines.append(f"{name} {g.value}")
        for h in self._histograms.values():
            lines.append(f"# HELP {h.name} {h.help}")
            lines.append(f"# TYPE {h.name} histogram")
            lines.append(f"{h.name}_count {h.count}")
            lines.append(f"{h.name}_sum {h.sum:.3f}")
        return "\n".join(lines) + "\n"

    def get_all(self) -> dict:
        return {
            "counters": {n: c.value for n, c in self._counters.items()},
            "gauges": {n: g.value for n, g in self._gauges.items()},
            "histograms": {
                n: {"count": h.count, "p50": h.percentile(50), "p95": h.percentile(95), "p99": h.percentile(99)}
                for n, h in self._histograms.items()
            },
        }


# ═══════════════════ Tracing ═══════════════════


@dataclass
class SpanEvent:
    name: str
    timestamp: float = 0.0
    attributes: dict[str, Any] = field(default_factory=dict)


class Span:
    def __init__(self, name: str, parent: Optional["Span"] = None):
        self.name = name
        self.span_id = str(hash(f"{name}{time.time()}"))[-16:]
        self.parent_id = parent.span_id if parent else None
        self.start_time = time.time()
        self.end_time: float | None = None
        self.events: list[SpanEvent] = []
        self.attributes: dict[str, Any] = {}

    def add_event(self, name: str, **attributes) -> None:
        self.events.append(SpanEvent(name, time.time(), attributes))

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def end(self) -> None:
        self.end_time = time.time()

    @property
    def duration_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0


class Tracer:
    """Simple tracer with span hierarchy."""

    def __init__(self):
        self._spans: list[Span] = []
        self._current: Span | None = None
        self._stack: list[Span] = []

    def start_span(self, name: str) -> Span:
        parent = self._stack[-1] if self._stack else None
        span = Span(name, parent)
        self._spans.append(span)
        self._stack.append(span)
        self._current = span
        return span

    def end_span(self) -> Span | None:
        if self._stack:
            span = self._stack.pop()
            span.end()
            self._current = self._stack[-1] if self._stack else None
            return span
        return None

    def get_spans(self) -> list[Span]:
        return list(self._spans)
