# Storage Backend — Acceptance Test Specification

## Common Interface (all backends)

### STOR-01: Connect and Disconnect
- Given: Backend configured with valid connection params
- When: connect() → health() → disconnect()
- Then: health() returns True, disconnect() succeeds
- Assert: No exceptions

### STOR-02: Append Events
- Given: Connected backend, 3 events
- When: append("goal-events", [event1, event2, event3])
- Then: Events stored successfully
- Assert: len(read("goal-events", 0, 100)) == 3

### STOR-03: Read Events by Position
- Given: 5 events stored in stream "tasks"
- When: read("tasks", from_position=2, count=2)
- Then: Returns events at positions 2 and 3
- Assert: len(result) == 2

### STOR-04: Read Beyond Available
- Given: 3 events in stream
- When: read("stream", 0, 10)
- Then: Returns all 3 events (no error)
- Assert: len(result) == 3

### STOR-05: Set and Get State
- Given: Connected backend
- When: set_state("goal-g1", {"status": "executing", "progress": 0.5})
- Then: get_state("goal-g1") returns the stored state
- Assert: state["status"] == "executing"

### STOR-06: Delete State
- Given: State stored for key "temp"
- When: delete_state("temp")
- Then: get_state("temp") returns None
- Assert: result is None

### STOR-07: Snapshots
- Given: Events in stream, state snapshot
- When: create_snapshot("goal-g1", events_position=5, state={...})
- Then: get_snapshot("goal-g1") returns snapshot
- Assert: snapshot["events_position"] == 5

### STOR-08: Connection Failure Recovery
- Given: Backend connection dropped
- When: Operation attempted → reconnect → operation retried
- Then: Operation succeeds after reconnect
- Assert: No permanent data loss

### STOR-09: Multiple Streams Isolation
- Given: Events in "stream-a" and "stream-b"
- When: read("stream-a", 0, 100)
- Then: Only "stream-a" events returned
- Assert: All returned events belong to stream-a

### STOR-10: Empty Stream Read
- Given: Stream with no events
- When: read("empty-stream", 0, 100)
- Then: Returns empty list
- Assert: len(result) == 0

## Backend-Specific

### STOR-11: Redis — Key Pattern
- Given: Redis backend
- When: Events stored
- Then: Redis keys follow pattern zelos:stream:{name}
- Assert: Keys are namespaced

### STOR-12: PostgreSQL — Table Schema
- Given: PostgreSQL backend
- When: First connect
- Then: Auto-creates events and state tables if not exist
- Assert: Tables exist after connect

### STOR-13: MySQL — Same as PostgreSQL
- Given: MySQL backend
- When: First connect
- Then: Auto-creates events and state tables
- Assert: Schema is compatible

### STOR-14: Backend Factory
- Given: type="redis", connection_url="redis://localhost:6379"
- When: create_backend(config)
- Then: Returns RedisStorageBackend instance
- Assert: isinstance(backend, RedisStorageBackend)

### STOR-15: Backend Factory — Unknown Type
- Given: type="cassandra"
- When: create_backend(config)
- Then: ValueError raised
- Assert: "Unsupported storage backend"
