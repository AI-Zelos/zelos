"""
Event Sourcing Engine — Reconstruct GoalState from Event History.

v0.8.0: Core event sourcing implementation.
  - apply_event(event, state) → GoalState (pure function, state reducer)
  - rebuild_from_events(goal_id, events) → GoalState | None (full replay)
  - restore_goal(goal_id, storage, incremental_events) → GoalState | None (snapshot + replay)
"""

from .event_bus import Event
from .goal_state import GoalState
from .task_graph import Task, TaskStatus


class EventSourcingEngine:
    """Pure-function event sourcing: rebuild GoalState from event history.

    Temporal model: Workflow State = Replay(EventHistory).
    Zelos model: GoalState = apply_event_chain(events).

    Supports snapshot + incremental replay for efficient recovery.
    """

    # ═══ Event type → handler mapping ═══
    # Each handler is a method: (event, state) → GoalState
    # The handler map is built in __init__ for extensibility.

    def __init__(self):
        self._handlers = {
            "goal.submitted": self._on_goal_submitted,
            "plan.created": self._on_plan_created,
            "task.created": self._on_task_created,
            "task.started": self._on_task_started,
            "task.completed": self._on_task_completed,
            "task.failed": self._on_task_failed,
            "task.timed_out": self._on_task_timed_out,
            "task.retry_scheduled": self._on_task_retry_scheduled,
            "task.cancelled": self._on_task_cancelled,
            "goal.completed": self._on_goal_completed,
            "goal.failed": self._on_goal_failed,
            "goal.cancelled": self._on_goal_cancelled,
        }

    # ═══ Public API ═══

    def apply_event(self, event: Event, state: GoalState | None) -> GoalState | None:
        """Apply a single event to a GoalState (pure function).

        Args:
            event: The event to apply.
            state: Current GoalState, or None if this is the first event.

        Returns:
            Updated GoalState (or None if state was None and event is not goal.submitted).
        """
        handler = self._handlers.get(event.event_type)
        if handler is None:
            # Unknown event type → no-op, return state unchanged
            return state
        result = handler(event, state)
        # Update event_position from sequence_id
        if result is not None and event.sequence_id >= 0:
            result.event_position = event.sequence_id
        return result

    def rebuild_from_events(self, goal_id: str, events: list[Event]) -> GoalState | None:
        """Rebuild a complete GoalState from an event chain.

        Only events whose payload contains the given goal_id are applied.
        Events without goal_id in payload are ignored.

        Args:
            goal_id: The goal to rebuild.
            events: Ordered list of events (may contain events for multiple goals).

        Returns:
            Reconstructed GoalState, or None if no goal.submitted event was found.
        """
        state: GoalState | None = None
        for event in events:
            # Filter by goal_id in payload
            payload_goal_id = event.payload.get("goal_id")
            if payload_goal_id and payload_goal_id != goal_id:
                continue
            state = self.apply_event(event, state)
        return state

    def restore_goal(
        self,
        goal_id: str,
        storage,
        incremental_events: list[Event] | None = None,
    ) -> GoalState | None:
        """Restore a GoalState from snapshot + incremental events.

        1. Try to load the latest snapshot from storage.
        2. If snapshot exists, start from that state.
        3. Apply incremental events (events after the snapshot position).
        4. If no snapshot, rebuild entirely from incremental events.

        Args:
            goal_id: The goal to restore.
            storage: StorageBackend instance (for snapshot retrieval).
            incremental_events: Events to apply on top of snapshot.
                               If None, builds from an empty list.

        Returns:
            Reconstructed GoalState, or None if no state can be built.
        """
        state: GoalState | None = None

        # Try to load snapshot
        snapshot = storage.get_snapshot(goal_id)
        if snapshot and "state" in snapshot:
            state = GoalState.from_dict(snapshot["state"])
            state.event_position = snapshot.get("events_position", 0)

        # Apply incremental events
        events = incremental_events or []
        for event in events:
            # Only apply events for this goal
            payload_goal_id = event.payload.get("goal_id")
            if payload_goal_id and payload_goal_id != goal_id:
                continue
            # Skip events already covered by snapshot
            if state and event.sequence_id >= 0 and event.sequence_id <= state.event_position:
                continue
            state = self.apply_event(event, state)

        return state

    # ═══ Event Handlers (pure functions: event + state → new state) ═══

    def _ensure_state(self, event: Event, state: GoalState | None) -> GoalState:
        """Ensure we have a GoalState, creating one if this is a goal.submitted event."""
        if state is not None:
            return state
        # Auto-create state from goal.submitted
        if event.event_type == "goal.submitted":
            return GoalState(
                goal_id=event.payload.get("goal_id", ""),
                status="accepted",
                description=event.payload.get("description", ""),
                priority=event.payload.get("priority", "medium"),
                budget=event.payload.get("budget"),
                deadline=event.payload.get("deadline"),
                created_at=event.timestamp,
                updated_at=event.timestamp,
            )
        return GoalState(goal_id=event.payload.get("goal_id", "unknown"))

    def _on_goal_submitted(self, event: Event, state: GoalState | None) -> GoalState:
        """goal.submitted → create initial GoalState."""
        return GoalState(
            goal_id=event.payload.get("goal_id", ""),
            status="accepted",
            description=event.payload.get("description", ""),
            priority=event.payload.get("priority", "medium"),
            budget=event.payload.get("budget"),
            deadline=event.payload.get("deadline"),
            created_at=event.timestamp,
            updated_at=event.timestamp,
        )

    def _on_plan_created(self, event: Event, state: GoalState | None) -> GoalState:
        """plan.created → set plan_id, status → planned."""
        s = self._ensure_state(event, state)
        s.status = "planned"
        s.plan_id = event.payload.get("plan_id", s.plan_id)
        s.updated_at = event.timestamp
        return s

    def _on_task_created(self, event: Event, state: GoalState | None) -> GoalState:
        """task.created → add new Task to state."""
        s = self._ensure_state(event, state)
        task = Task(
            task_id=event.payload.get("task_id", ""),
            plan_id=event.payload.get("plan_id", s.plan_id),
            description=event.payload.get("description", ""),
            required_capability=event.payload.get("required_capability", ""),
            status=TaskStatus.CREATED,
            dependencies=list(event.payload.get("dependencies", [])),
            priority=event.payload.get("priority", "medium"),
            timeout_ms=int(event.payload.get("timeout_ms", 30000)),
        )
        # Avoid duplicates
        existing_ids = {t.task_id for t in s.tasks}
        if task.task_id not in existing_ids:
            s.tasks.append(task)
        s.updated_at = event.timestamp
        return s

    def _on_task_started(self, event: Event, state: GoalState | None) -> GoalState:
        """task.started → mark task as STARTED."""
        s = self._ensure_state(event, state)
        task = s.get_task(event.payload.get("task_id", ""))
        if task and task.status in (TaskStatus.CREATED, TaskStatus.READY, TaskStatus.ASSIGNED):
            task.status = TaskStatus.STARTED
            task.updated_at = event.timestamp
        s.updated_at = event.timestamp
        return s

    def _on_task_completed(self, event: Event, state: GoalState | None) -> GoalState:
        """task.completed → mark task as COMPLETED."""
        s = self._ensure_state(event, state)
        task = s.get_task(event.payload.get("task_id", ""))
        if task:
            task.status = TaskStatus.COMPLETED
            task.updated_at = event.timestamp
        s.updated_at = event.timestamp
        return s

    def _on_task_failed(self, event: Event, state: GoalState | None) -> GoalState:
        """task.failed → mark task as FAILED."""
        s = self._ensure_state(event, state)
        task = s.get_task(event.payload.get("task_id", ""))
        if task:
            task.status = TaskStatus.FAILED
            task.updated_at = event.timestamp
        s.updated_at = event.timestamp
        return s

    def _on_task_timed_out(self, event: Event, state: GoalState | None) -> GoalState:
        """task.timed_out → mark task as TIMED_OUT."""
        s = self._ensure_state(event, state)
        task = s.get_task(event.payload.get("task_id", ""))
        if task:
            task.status = TaskStatus.TIMED_OUT
            task.updated_at = event.timestamp
        s.updated_at = event.timestamp
        return s

    def _on_task_retry_scheduled(self, event: Event, state: GoalState | None) -> GoalState:
        """task.retry_scheduled → increment attempt, set status to READY."""
        s = self._ensure_state(event, state)
        task = s.get_task(event.payload.get("task_id", ""))
        if task:
            task.attempt = event.payload.get("attempt", task.attempt + 1)
            task.status = TaskStatus.READY
            task.updated_at = event.timestamp
        s.updated_at = event.timestamp
        return s

    def _on_task_cancelled(self, event: Event, state: GoalState | None) -> GoalState:
        """task.cancelled → mark task as CANCELLED."""
        s = self._ensure_state(event, state)
        task = s.get_task(event.payload.get("task_id", ""))
        if task:
            task.status = TaskStatus.CANCELLED
            task.updated_at = event.timestamp
        s.updated_at = event.timestamp
        return s

    def _on_goal_completed(self, event: Event, state: GoalState | None) -> GoalState:
        """goal.completed → mark goal as completed."""
        s = self._ensure_state(event, state)
        s.status = "completed"
        s.completed_at = event.timestamp
        s.updated_at = event.timestamp
        return s

    def _on_goal_failed(self, event: Event, state: GoalState | None) -> GoalState:
        """goal.failed → mark goal as failed."""
        s = self._ensure_state(event, state)
        s.status = "failed"
        s.completed_at = event.timestamp
        s.updated_at = event.timestamp
        return s

    def _on_goal_cancelled(self, event: Event, state: GoalState | None) -> GoalState:
        """goal.cancelled → mark goal as cancelled."""
        s = self._ensure_state(event, state)
        s.status = "cancelled"
        s.completed_at = event.timestamp
        s.updated_at = event.timestamp
        return s
