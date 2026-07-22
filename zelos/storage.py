"""
Pluggable Storage Backends — Event persistence + State storage.

Phase 2: InMemory, Redis, PostgreSQL, MySQL backends.
All share a common interface: connect / disconnect / append / read / state / snapshot.
"""

import json
import threading
import time
from abc import ABC, abstractmethod

# ═══════════════════ Common Interface ═══════════════════


class StorageBackend(ABC):
    """Abstract storage backend for events and state."""

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
    def append(self, stream: str, events: list[dict]) -> int: ...

    @abstractmethod
    def read(self, stream: str, from_position: int, count: int) -> list[dict]: ...

    @abstractmethod
    def set_state(self, key: str, value: dict) -> None: ...

    @abstractmethod
    def get_state(self, key: str) -> dict | None: ...

    @abstractmethod
    def delete_state(self, key: str) -> None: ...

    def create_snapshot(self, key: str, events_position: int, state: dict) -> None:
        self.set_state(
            f"snapshot:{key}", {"events_position": events_position, "state": state, "timestamp": time.time()}
        )

    def get_snapshot(self, key: str) -> dict | None:
        return self.get_state(f"snapshot:{key}")

    @property
    def is_connected(self) -> bool:
        return self._connected


# ═══════════════════ InMemory ═══════════════════


class InMemoryStorageBackend(StorageBackend):
    """Phase 1 compatible — stores everything in memory."""

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self._streams: dict[str, list[dict]] = {}
        self._state: dict[str, dict] = {}
        self._lock = threading.Lock()

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def health(self) -> bool:
        return self._connected

    def append(self, stream: str, events: list[dict]) -> int:
        with self._lock:
            if stream not in self._streams:
                self._streams[stream] = []
            self._streams[stream].extend(events)
            return len(self._streams[stream])

    def read(self, stream: str, from_position: int, count: int) -> list[dict]:
        with self._lock:
            events = self._streams.get(stream, [])
            return events[from_position : from_position + count]

    def set_state(self, key: str, value: dict) -> None:
        with self._lock:
            self._state[key] = value

    def get_state(self, key: str) -> dict | None:
        return self._state.get(key)

    def delete_state(self, key: str) -> None:
        self._state.pop(key, None)


# ═══════════════════ Redis ═══════════════════


class RedisStorageBackend(StorageBackend):
    """Redis-backed storage. Events stored as lists, state as hash.

    Config:
      url: redis://localhost:6379/0
      prefix: "zelos" (key namespace)
    """

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self._url = (config or {}).get("url", "redis://localhost:6379/0")
        self._prefix = (config or {}).get("prefix", "zelos")
        self._client = None

    def connect(self) -> bool:
        try:
            import redis

            self._client = redis.Redis.from_url(self._url, decode_responses=True)
            self._client.ping()
            self._connected = True
            return True
        except Exception:
            self._connected = False
            return False

    def disconnect(self) -> None:
        if self._client:
            self._client.close()
        self._connected = False

    def health(self) -> bool:
        if not self._client:
            return False
        try:
            self._client.ping()
            return True
        except Exception:
            return False

    def _stream_key(self, stream: str) -> str:
        return f"{self._prefix}:stream:{stream}"

    def _state_key(self, key: str) -> str:
        return f"{self._prefix}:state:{key}"

    def append(self, stream: str, events: list[dict]) -> int:
        if not self._client:
            return -1
        pipe = self._client.pipeline()
        for e in events:
            pipe.rpush(self._stream_key(stream), json.dumps(e))
        pipe.execute()
        return self._client.llen(self._stream_key(stream))

    def read(self, stream: str, from_position: int, count: int) -> list[dict]:
        if not self._client:
            return []
        raw = self._client.lrange(self._stream_key(stream), from_position, from_position + count - 1)
        return [json.loads(r) for r in raw]

    def set_state(self, key: str, value: dict) -> None:
        if self._client:
            self._client.set(self._state_key(key), json.dumps(value))

    def get_state(self, key: str) -> dict | None:
        if not self._client:
            return None
        raw = self._client.get(self._state_key(key))
        return json.loads(raw) if raw else None

    def delete_state(self, key: str) -> None:
        if self._client:
            self._client.delete(self._state_key(key))


# ═══════════════════ PostgreSQL ═══════════════════


class PostgreSQLStorageBackend(StorageBackend):
    """PostgreSQL-backed storage. Events table + state table.

    Config:
      url: postgresql://user:pass@localhost:5432/zelos
    """

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self._url = (config or {}).get("url", "postgresql://localhost:5432/zelos")
        self._conn = None

    def connect(self) -> bool:
        try:
            import psycopg2

            self._conn = psycopg2.connect(self._url)
            self._conn.autocommit = True
            self._create_tables()
            self._connected = True
            return True
        except Exception:
            self._connected = False
            return False

    def disconnect(self) -> None:
        if self._conn:
            self._conn.close()
        self._connected = False

    def health(self) -> bool:
        if not self._conn:
            return False
        try:
            cur = self._conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
            return True
        except Exception:
            return False

    def _create_tables(self) -> None:
        cur = self._conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS zelos_events (
                id SERIAL PRIMARY KEY,
                stream VARCHAR(255) NOT NULL,
                position INTEGER NOT NULL,
                event_data JSONB NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_zelos_events_stream_pos
                ON zelos_events(stream, position);
            CREATE TABLE IF NOT EXISTS zelos_state (
                key VARCHAR(255) PRIMARY KEY,
                value JSONB NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW()
            );
        """)
        cur.close()

    def append(self, stream: str, events: list[dict]) -> int:
        if not self._conn:
            return -1
        cur = self._conn.cursor()
        # Get current max position
        cur.execute("SELECT COALESCE(MAX(position), -1) FROM zelos_events WHERE stream = %s", (stream,))
        pos = cur.fetchone()[0]
        for e in events:
            pos += 1
            cur.execute(
                "INSERT INTO zelos_events (stream, position, event_data) VALUES (%s, %s, %s)",
                (stream, pos, json.dumps(e)),
            )
        cur.close()
        return pos + 1

    def read(self, stream: str, from_position: int, count: int) -> list[dict]:
        if not self._conn:
            return []
        cur = self._conn.cursor()
        cur.execute(
            "SELECT event_data FROM zelos_events WHERE stream = %s AND position >= %s ORDER BY position LIMIT %s",
            (stream, from_position, count),
        )
        rows = cur.fetchall()
        cur.close()
        return [r[0] for r in rows]

    def set_state(self, key: str, value: dict) -> None:
        if not self._conn:
            return
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO zelos_state (key, value, updated_at) VALUES (%s, %s, NOW()) "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()",
            (key, json.dumps(value)),
        )
        cur.close()

    def get_state(self, key: str) -> dict | None:
        if not self._conn:
            return None
        cur = self._conn.cursor()
        cur.execute("SELECT value FROM zelos_state WHERE key = %s", (key,))
        row = cur.fetchone()
        cur.close()
        return row[0] if row else None

    def delete_state(self, key: str) -> None:
        if not self._conn:
            return
        cur = self._conn.cursor()
        cur.execute("DELETE FROM zelos_state WHERE key = %s", (key,))
        cur.close()


# ═══════════════════ MySQL ═══════════════════


class MySQLStorageBackend(StorageBackend):
    """MySQL-backed storage. Same schema as PostgreSQL.

    Config:
      url: mysql://user:pass@localhost:3306/zelos
    """

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self._url = (config or {}).get("url", "mysql://localhost:3306/zelos")
        self._conn = None

    def connect(self) -> bool:
        try:
            # Parse URL
            from urllib.parse import urlparse

            import mysql.connector

            parsed = urlparse(self._url)
            self._conn = mysql.connector.connect(
                host=parsed.hostname or "localhost",
                port=parsed.port or 3306,
                user=parsed.username or "root",
                password=parsed.password or "",
                database=parsed.path.lstrip("/") or "zelos",
                autocommit=True,
            )
            self._create_tables()
            self._connected = True
            return True
        except Exception:
            self._connected = False
            return False

    def disconnect(self) -> None:
        if self._conn:
            self._conn.close()
        self._connected = False

    def health(self) -> bool:
        if not self._conn:
            return False
        try:
            cur = self._conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
            return True
        except Exception:
            return False

    def _create_tables(self) -> None:
        cur = self._conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS zelos_events (
                id INT AUTO_INCREMENT PRIMARY KEY,
                stream VARCHAR(255) NOT NULL,
                position INT NOT NULL,
                event_data JSON NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_stream_pos (stream, position)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS zelos_state (
                `key` VARCHAR(255) PRIMARY KEY,
                value JSON NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        cur.close()

    def append(self, stream: str, events: list[dict]) -> int:
        if not self._conn:
            return -1
        cur = self._conn.cursor()
        cur.execute("SELECT COALESCE(MAX(position), -1) FROM zelos_events WHERE stream = %s", (stream,))
        pos = cur.fetchone()[0]
        for e in events:
            pos += 1
            cur.execute(
                "INSERT INTO zelos_events (stream, position, event_data) VALUES (%s, %s, %s)",
                (stream, pos, json.dumps(e)),
            )
        cur.close()
        return pos + 1

    def read(self, stream: str, from_position: int, count: int) -> list[dict]:
        if not self._conn:
            return []
        cur = self._conn.cursor()
        cur.execute(
            "SELECT event_data FROM zelos_events WHERE stream = %s AND position >= %s ORDER BY position LIMIT %s",
            (stream, from_position, count),
        )
        rows = cur.fetchall()
        cur.close()
        # JSON type returns str in MySQL connector
        return [json.loads(r[0]) if isinstance(r[0], str) else r[0] for r in rows]

    def set_state(self, key: str, value: dict) -> None:
        if not self._conn:
            return
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO zelos_state (`key`, value) VALUES (%s, %s) ON DUPLICATE KEY UPDATE value = VALUES(value)",
            (key, json.dumps(value)),
        )
        cur.close()

    def get_state(self, key: str) -> dict | None:
        if not self._conn:
            return None
        cur = self._conn.cursor()
        cur.execute("SELECT value FROM zelos_state WHERE `key` = %s", (key,))
        row = cur.fetchone()
        cur.close()
        if row:
            return json.loads(row[0]) if isinstance(row[0], str) else row[0]
        return None

    def delete_state(self, key: str) -> None:
        if not self._conn:
            return
        cur = self._conn.cursor()
        cur.execute("DELETE FROM zelos_state WHERE `key` = %s", (key,))
        cur.close()


# ═══════════════════ Factory ═══════════════════

BACKENDS = {
    "memory": InMemoryStorageBackend,
    "redis": RedisStorageBackend,
    "postgresql": PostgreSQLStorageBackend,
    "postgres": PostgreSQLStorageBackend,
    "pgsql": PostgreSQLStorageBackend,
    "mysql": MySQLStorageBackend,
}


def create_storage_backend(config: dict) -> StorageBackend:
    """Factory: create a storage backend from configuration."""
    backend_type = config.get("type", "memory").lower()
    cls = BACKENDS.get(backend_type)
    if cls is None:
        raise ValueError(f"Unsupported storage backend: '{backend_type}'. Supported: {', '.join(BACKENDS.keys())}")
    return cls(config)
