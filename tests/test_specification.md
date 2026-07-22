# Zelos Phase 1 — Acceptance Test Specification

> Each test case is an acceptance criterion. All tests MUST pass before Phase 1 is considered complete.

---

## Module 1: Event Bus

### EB-01: Publish and Subscribe — Exact Type
- **Given:** An Event Bus with no subscribers
- **When:** Subscribe to `task.completed`, publish a `task.completed` event, then publish a `task.started` event
- **Then:** Subscriber receives `task.completed` event exactly once; `task.started` is NOT received
- **Assert:** `received_events == 1`, event type is `task.completed`

### EB-02: Publish and Subscribe — Pattern Matching
- **Given:** An Event Bus with a subscriber using pattern `task.*`
- **When:** Publish `task.created`, `task.started`, `task.completed`, and `goal.submitted`
- **Then:** Subscriber receives the 3 `task.*` events; `goal.submitted` is NOT received
- **Assert:** `received_events == 3`

### EB-03: Correlation ID Subscription
- **Given:** Subscriber subscribes to `correlation_id = "G1"`
- **When:** Publish events with `correlation_id = "G1"` (x3) and `correlation_id = "G2"` (x2)
- **Then:** Subscriber receives only the 3 `G1` events
- **Assert:** `received_events == 3`

### EB-04: Multiple Subscribers — Same Event Type
- **Given:** Two subscribers both subscribed to `task.completed`
- **When:** Publish one `task.completed` event
- **Then:** Both subscribers receive the event
- **Assert:** `received_by_A == 1`, `received_by_B == 1`

### EB-05: Event Immutability
- **Given:** A published event
- **When:** Attempt to modify the event payload after publication
- **Then:** The stored event is unchanged
- **Assert:** stored event payload equals original payload; modification to returned copy does not affect stored event

### EB-06: Event ID Idempotency
- **Given:** An in-memory Event Store
- **When:** Publish the same `event_id` twice
- **Then:** The second publish is silently ignored (no duplicate)
- **Assert:** `total_events == 1`, subscriber invoked once

### EB-07: Causation Chain
- **Given:** Events E1, E2, E3 with E2.causation_id = E1.event_id, E3.causation_id = E2.event_id
- **When:** Query causation chain from E3
- **Then:** Can trace back E3 → E2 → E1
- **Assert:** Chain resolves to [E1, E2, E3]

### EB-08: Handler Ack / Retry / Skip
- **Given:** A subscriber whose handler returns `Retry` on first call, then `Ack`
- **When:** Publish one event
- **Then:** Handler is called twice; event is marked processed after Ack
- **Assert:** `handler_call_count == 2`, event eventually marked as processed

### EB-09: Replay from Position
- **Given:** Event Store with 10 events (positions 0–9)
- **When:** Replay from position 5
- **Then:** Handler receives events at positions 5, 6, 7, 8, 9
- **Assert:** `received_count == 5`

### EB-10: Replay by Correlation ID
- **Given:** Event Store with events for G1 (5 events) and G2 (3 events)
- **When:** Replay by `correlation_id = "G1"`
- **Then:** Handler receives only G1's 5 events, in order
- **Assert:** `received_count == 5`, all have correlation_id `"G1"`

### EB-11: 1MB Event Size Limit
- **Given:** An event payload of 1.5 MB
- **When:** Attempt to publish
- **Then:** Publication is rejected with an error
- **Assert:** Exception raised, event not stored

### EB-12: In-Memory Ring Buffer Overflow
- **Given:** Ring buffer with `max_events = 100`
- **When:** Publish 150 events
- **Then:** Oldest 50 events are evicted; newest 100 remain
- **Assert:** `total_stored == 100`, position 0 is the 51st published event

---

## Module 2: Capability Registry

### CR-01: Register a Capability
- **Given:** An empty Capability Registry
- **When:** Agent registers `code-generation.python@1.0.0`
- **Then:** Capability is indexed and queryable
- **Assert:** `find_by_name("code-generation.python")` returns 1 result, status is `registered`

### CR-02: Register Multiple Capabilities for One Agent
- **Given:** An empty Registry
- **When:** Agent registers `code-generation.python`, `code-review`, `automation.browser`
- **Then:** All 3 are indexed under the agent
- **Assert:** `find_providers_for("code-generation.python")` returns 1 agent; agent has 3 capabilities

### CR-03: Multiple Agents — Same Capability
- **Given:** Agent A and Agent B both register `code-generation.python`
- **When:** Query providers for `code-generation.python`
- **Then:** Both agents are returned
- **Assert:** `len(providers) == 2`

### CR-04: Capability Not Found
- **Given:** Registry with `code-generation.python`
- **When:** Query `data-query.sql` (not registered)
- **Then:** Empty result
- **Assert:** `find_by_name(...)` returns empty list

### CR-05: Version Compatibility Check
- **Given:** Capability `code-generation.python@1.0.0` and `code-generation.python@1.5.0` registered
- **When:** Query with version requirement `>=1.0, <2.0`
- **Then:** Both match
- **Assert:** `len(results) == 2`

### CR-06: Mark Available / Unavailable
- **Given:** Registered capability
- **When:** `mark_available(agent_id)` → `mark_unavailable(agent_id)`
- **Then:** State transitions: registered → available → unavailable
- **Assert:** After mark_available: status is `available`; after mark_unavailable: status is `unavailable`

### CR-07: Deprecate Capability
- **Given:** Available capability
- **When:** `deprecate(agent_id, "code-generation.python", "1.0.0")`
- **Then:** Status becomes `deprecated`
- **Assert:** Scheduler deprioritizes but does not exclude deprecated capabilities

### CR-08: Remove Capability
- **Given:** Deprecated capability
- **When:** `remove(agent_id, "code-generation.python", "1.0.0")`
- **Then:** Capability is permanently removed
- **Assert:** `find_by_name(...)` returns empty

### CR-09: Tag-Based Query
- **Given:** Capabilities with tags: Cap-A `["python","fast"]`, Cap-B `["python","secure"]`, Cap-C `["rust","fast"]`
- **When:** `find_by_tag(["python", "fast"])`
- **Then:** Only Cap-A matches (AND logic)
- **Assert:** `len(results) == 1`, result is Cap-A

### CR-10: Prefix Matching
- **Given:** `code-generation.python`, `code-generation.typescript`, `code-review.security`
- **When:** `find_by_prefix("code-generation")`
- **Then:** The two `code-generation.*` capabilities are returned
- **Assert:** `len(results) == 2`

### CR-11: Agent Re-Registration (Reconnect)
- **Given:** Agent previously registered and disconnected
- **When:** Agent re-registers with same name and agent_id
- **Then:** Capabilities are restored, status becomes `registered`
- **Assert:** Old capabilities preserved; new capabilities merged

---

## Module 3: Task Graph Engine

### TG-01: Create Task — Initial State
- **Given:** A new Task with no dependencies
- **When:** Task is created
- **Then:** Status is `created`
- **Assert:** `task.status == "created"`

### TG-02: Task Becomes Ready — Dependencies Met
- **Given:** Task T2 depends on T1
- **When:** T1 transitions to `completed`
- **Then:** T2 transitions to `ready`
- **Assert:** `T2.status == "ready"`

### TG-03: Task Remains Blocked — Dependencies Not Met
- **Given:** Task T2 depends on T1 (T1 is still `started`)
- **When:** Evaluate dependencies for T2
- **Then:** T2 remains `created` (blocked)
- **Assert:** `T2.status == "created"`

### TG-04: Multiple Dependencies — All Must Complete
- **Given:** Task T3 depends on T1 AND T2
- **When:** T1 completes, but T2 is still running
- **Then:** T3 remains `created`
- **Assert:** `T3.status == "created"`

### TG-05: Multiple Dependents — All Unblocked
- **Given:** T1 → T2, T1 → T3 (T2 and T3 both depend on T1)
- **When:** T1 completes
- **Then:** Both T2 and T3 become `ready`
- **Assert:** `T2.status == "ready"`, `T3.status == "ready"`

### TG-06: Task State Transitions — Happy Path
- **Given:** A Task in `created` state
- **When:** dependencies_met → ready → assigned → started → completed
- **Then:** Each transition succeeds
- **Assert:** Final status is `completed`

### TG-07: Invalid State Transition
- **Given:** A Task in `created` state (dependencies not met)
- **When:** Attempt to transition directly to `completed`
- **Then:** Transition is rejected
- **Assert:** Exception raised, status remains `created`

### TG-08: DAG Acyclicity — Add Valid Edge
- **Given:** Tasks T1, T2, T3 with T1 → T2
- **When:** Add edge T2 → T3
- **Then:** Edge is accepted
- **Assert:** DAG validation passes

### TG-09: DAG Acyclicity — Reject Cycle
- **Given:** Tasks T1 → T2 → T3
- **When:** Attempt to add edge T3 → T1 (creates cycle)
- **Then:** Edge is rejected
- **Assert:** Exception raised, graph unchanged

### TG-10: Dynamic Modification — Add Task Mid-Execution
- **Given:** Existing Plan with Tasks T1, T2 (T1 → T2). T1 is `completed`.
- **When:** Add Task T3 that depends on T1
- **Then:** T3 added, evaluates to `ready` (T1 is done)
- **Assert:** `T3.status == "ready"`

### TG-11: Dynamic Modification — Cannot Modify In-Flight Task
- **Given:** Task T1 is `started`
- **When:** Attempt to remove T1
- **Then:** Operation rejected
- **Assert:** Exception raised, T1 still `started`

### TG-12: Failure Propagation — Hard Dependency
- **Given:** T1 → T2 (hard dep). T1 fails with retry exhausted.
- **When:** T1 becomes terminal `failed`
- **Then:** T2 remains `created` (blocked, not auto-failed)
- **Assert:** `T2.status == "created"`, system may trigger re-plan

---

## Module 4: Scheduler

### SC-01: Basic FIFO Dispatch
- **Given:** 2 Ready tasks (T1 created before T2), 1 agent providing the capability
- **When:** Scheduler runs
- **Then:** T1 is dispatched first, T2 is queued
- **Assert:** `T1.status == "assigned"`, agent assigned to T1

### SC-02: Capability Match — Exact Name
- **Given:** Task requires `code-generation.python`, Agent provides `code-generation.python`
- **When:** Scheduler filters
- **Then:** Agent passes filter
- **Assert:** Agent is in filtered candidates

### SC-03: Capability Mismatch — Filtered Out
- **Given:** Task requires `code-generation.python`, Agent provides `code-review`
- **When:** Scheduler filters
- **Then:** Agent fails filter
- **Assert:** Agent is NOT in filtered candidates

### SC-04: Agent Capacity Enforcement
- **Given:** Agent with `max_concurrent_tasks = 2`, currently has 2 in-flight tasks
- **When:** Scheduler evaluates this agent for a new Task
- **Then:** Agent fails capacity filter
- **Assert:** Agent filtered out

### SC-05: Agent Disconnected — Filtered Out
- **Given:** Agent status is `disconnected`
- **When:** Scheduler evaluates
- **Then:** Agent fails "Agent alive" filter
- **Assert:** Agent filtered out

### SC-06: Budget Enforcement
- **Given:** Goal has budget $10, cumulative cost so far $9.50, candidate Agent costs $1.00/call
- **When:** Scheduler evaluates
- **Then:** Agent fails budget filter
- **Assert:** Agent filtered out

### SC-07: Deadline Enforcement
- **Given:** Goal deadline is 1 minute from now, Agent avg_latency is 90 seconds
- **When:** Scheduler evaluates
- **Then:** Agent fails deadline feasibility check
- **Assert:** Agent filtered out

### SC-08: Scoring — Higher Success Rate Wins
- **Given:** Agent A (success=0.95), Agent B (success=0.80), all else equal
- **When:** Scheduler scores
- **Then:** Agent A scores higher than Agent B
- **Assert:** `score(A) > score(B)`

### SC-09: Scoring — Lower Cost Wins
- **Given:** Agent A ($0.05/call), Agent B ($0.10/call), all else equal
- **When:** Scheduler scores
- **Then:** Agent A scores higher on cost dimension
- **Assert:** Agent A has better cost_score

### SC-10: Preferred Agent Constraint
- **Given:** Task has `preferred_agent_id = "agt-002"`, Filter returns [agt-001, agt-002, agt-003]
- **When:** Scheduler selects
- **Then:** agt-002 is selected (affinity boost or direct selection)
- **Assert:** Selected agent is agt-002

### SC-11: Excluded Agents
- **Given:** Task has `excluded_agent_ids = ["agt-001"]`, Filter returns [agt-001, agt-002]
- **When:** Scheduler filters
- **Then:** agt-001 is filtered out
- **Assert:** Filtered candidates do not contain agt-001

### SC-12: Fallback Capability on No Candidates
- **Given:** Task requires `code-generation.rust` (no provider), `fallback_capability = "code-generation.python"` (has provider)
- **When:** Scheduler finds 0 candidates for primary capability
- **Then:** Scheduler re-queries with fallback, finds 1 candidate
- **Assert:** Task is dispatched using fallback capability

### SC-13: Min Success Rate Filter
- **Given:** Task requires `min_success_rate = 0.85`, Agent A (0.90), Agent B (0.70)
- **When:** Scheduler filters
- **Then:** Agent B filtered out; Agent A passes
- **Assert:** Only Agent A in candidates

### SC-14: Tag Requirement
- **Given:** Task `required_tags = ["production"]`, Agent A tags=["production","fast"], Agent B tags=["staging","fast"]
- **When:** Scheduler filters
- **Then:** Agent B filtered out
- **Assert:** Only Agent A passes tag filter

### SC-15: Custom ScoringStrategy Plugin
- **Given:** A custom ScoringStrategy that returns score=0 for agents without `soc2-compliant` tag
- **When:** Scheduler invokes custom strategy with [Agent-A(tags=["soc2-compliant"]), Agent-B(tags=["fast"])]
- **Then:** Agent-B gets score=0 (excluded); Agent-A gets positive score
- **Assert:** `score(Agent-B) == 0`, `score(Agent-A) > 0`

### SC-16: Policy Plugin — Reject
- **Given:** A Policy that rejects any agent with cost > $0.05
- **When:** Scheduler evaluates Agent (cost=$0.08)
- **Then:** Policy returns `Reject`
- **Assert:** Agent excluded from selection

### SC-17: Retry — Exponential Backoff
- **Given:** Task fails first attempt
- **When:** Scheduler evaluates retry with `base_ms=1000`, `max_retries=3`, `attempt=1`
- **Then:** Backoff = 1000 * 2^1 + jitter ≈ 2000ms
- **Assert:** Task transitions to `ready` after backoff

### SC-18: Retry Exhausted
- **Given:** Task failed 3 times, `max_retries = 3`
- **When:** Scheduler evaluates retry
- **Then:** Retry exhausted, Task → `failed` (terminal)
- **Assert:** `task.status == "failed"`, no more retries

---

## Module 5: Execution Engine

### EE-01: Dispatch Task to Agent
- **Given:** An assigned Task and a connected Agent
- **When:** Execution Engine dispatches
- **Then:** Agent receives Task via `execute()` call
- **Assert:** `agent.received_tasks` contains the task_id

### EE-02: Track In-Flight Tasks
- **Given:** Execution Engine with no in-flight tasks
- **When:** Dispatch 3 tasks to an agent
- **Then:** `in_flight_count == 3`
- **Assert:** All 3 task_ids tracked

### EE-03: Agent Accepts — Task → Started
- **Given:** Dispatched Task
- **When:** Agent returns `status: "accepted"`
- **Then:** Task transitions to `started`
- **Assert:** Task status becomes `started`

### EE-04: Agent Rejects — Task → Ready (Re-Schedule)
- **Given:** Dispatched Task
- **When:** Agent returns `status: "rejected"`
- **Then:** Task transitions back to `ready`; Scheduler notified
- **Assert:** Task status becomes `ready`

### EE-05: SubmitResult — Success
- **Given:** A `started` Task
- **When:** Agent calls `SubmitResult(task_id, {status: "completed", artifact: {...}})`
- **Then:** Task transitions to `completed`; Artifact is stored; Verifier invoked
- **Assert:** Task status is `completed`, Artifact accessible

### EE-06: SubmitResult — Agent Reports Failure
- **Given:** A `started` Task
- **When:** Agent calls `SubmitResult(task_id, {status: "failed", error: {...}})`
- **Then:** Task enters retry evaluation; Scheduler notified
- **Assert:** Task status transitions based on retry policy

### EE-07: Timeout — Task Exceeds Time Limit
- **Given:** Task with `timeout_ms = 1000`
- **When:** 1000ms elapses without SubmitResult
- **Then:** Task transitions to `timed_out`; Agent receives `cancel()`
- **Assert:** Task status is `timed_out`

### EE-08: Cancel Task — Agent Acknowledges
- **Given:** A `started` Task
- **When:** Execution Engine calls `cancel(task_id)` and Agent responds with `"acknowledged"`
- **Then:** Task transitions to `cancelled`
- **Assert:** Task status is `cancelled`

### EE-09: Cancel Task — Agent Does Not Acknowledge (Force-Fail)
- **Given:** A `started` Task, Agent not responding to cancel
- **When:** `cancel_timeout_ms` passes
- **Then:** Task force-failed
- **Assert:** Task transitions to `failed`

### EE-10: Heartbeat Tracking — Agent Alive
- **Given:** Agent heartbeat interval 5s
- **When:** Agent sends heartbeat at t=0, t=5, t=10
- **Then:** Agent remains `heartbeating`
- **Assert:** Agent status is `heartbeating`

### EE-11: Heartbeat Timeout — Agent Disconnected
- **Given:** Agent heartbeat interval 5s (timeout = 3 × 5s = 15s)
- **When:** Last heartbeat at t=0, now t=16s
- **Then:** Agent transitions to `disconnected`
- **Assert:** Agent status is `disconnected`; In-flight tasks reassessed

### EE-12: Artifact Validation — Content Type Check
- **Given:** Agent submits Artifact with `content_type = "application/json"` but content is not valid JSON
- **When:** Execution Engine validates
- **Then:** Artifact rejected
- **Assert:** Task fails, error recorded

### EE-13: Large Artifact — content_ref
- **Given:** Agent produces a 50MB Artifact
- **When:** Agent returns `content_ref` URI instead of inline `content`
- **Then:** Artifact stored with `content_ref`; downstream Tasks access via URI
- **Assert:** `artifact.content_ref` is set, `artifact.content` is null

---

## Module 6: Plugin Lifecycle Manager

### PL-01: Load Plugin from Config
- **Given:** A `zelos.yaml` with 1 Storage Backend plugin
- **When:** PLM loads plugins
- **Then:** Plugin is loaded, configured, initialized, started
- **Assert:** Plugin status is `RUNNING`

### PL-02: Load Order Enforcement
- **Given:** Config with plugins of types: Adapter, Storage, Planner, Policy (unordered)
- **When:** PLM loads plugins
- **Then:** Plugins are loaded in order: Storage → Policy → Planner → Adapter
- **Assert:** Load order matches specification (storage → memory → policy → scoring_strategy → verifier → planner → adapter)

### PL-03: Plugin Dependency Resolution
- **Given:** Plugin A depends on B; Plugin B depends on C
- **When:** PLM resolves dependencies
- **Then:** Load order is C → B → A
- **Assert:** Topological sort correct

### PL-04: Circular Dependency Rejection
- **Given:** Plugin A depends on B; Plugin B depends on A
- **When:** PLM resolves dependencies
- **Then:** Circular dependency detected and rejected
- **Assert:** Exception raised, neither plugin loaded

### PL-05: Plugin Health Check
- **Given:** A RUNNING plugin with health check interval 10s
- **When:** PLM runs health check
- **Then:** `health()` returns healthy status
- **Assert:** Plugin remains RUNNING

### PL-06: Plugin Failure — Restart
- **Given:** Plugin with `restart_policy = "always"`, `max_restarts = 3`
- **When:** Plugin crashes
- **Then:** Plugin is restarted; restart count incremented
- **Assert:** Plugin eventually returns to RUNNING

### PL-07: Plugin Failure — Max Restarts Exceeded
- **Given:** Plugin with `max_restarts = 2`, crashed 2 times already
- **When:** Plugin crashes a 3rd time
- **Then:** Plugin stays in ERROR; Runtime enters DEGRADED
- **Assert:** Plugin status is ERROR; Runtime status is DEGRADED

### PL-08: Plugin Stop — Graceful
- **Given:** A RUNNING plugin
- **When:** `stop(plugin)` is called
- **Then:** Plugin transitions: RUNNING → STOPPING → STOPPED
- **Assert:** Plugin status is STOPPED

### PL-09: Version Compatibility Check
- **Given:** Plugin requires `runtime_api_version >= "1.0.0"`, Runtime API is "1.0.0"
- **When:** PLM validates compatibility
- **Then:** Plugin accepted
- **Assert:** Load succeeds

### PL-10: Version Incompatibility
- **Given:** Plugin requires `runtime_api_version >= "2.0.0"`, Runtime API is "1.0.0"
- **When:** PLM validates compatibility
- **Then:** Plugin rejected
- **Assert:** Exception raised, plugin not loaded

### PL-11: Config Validation Against config_schema
- **Given:** Plugin declares `config_schema` requiring `max_events: int (minimum 100)`
- **When:** Config provides `max_events: 50`
- **Then:** Config rejected
- **Assert:** Exception raised, plugin not configured

### PL-12: Agent as Async Plugin
- **Given:** An Agent registered via `add_agent()` (not in zelos.yaml)
- **When:** PLM processes agents after static plugins
- **Then:** Agent is started, registered, and heartbeating
- **Assert:** Agent status is `heartbeating`

---

## Module 7: Runtime API

### RA-01: Submit Goal — Accepted
- **Given:** A running Runtime
- **When:** `SubmitGoal(description="Build a website", priority="high")`
- **Then:** Goal accepted, goal_id assigned, status = "accepted"
- **Assert:** Response has goal_id (UUID), status "accepted"

### RA-02: Submit Goal — Rejected (Empty Description)
- **Given:** Running Runtime
- **When:** `SubmitGoal(description="")`
- **Then:** Goal rejected
- **Assert:** status = "rejected", reason present

### RA-03: Submit Goal — Rejected (Invalid Priority)
- **Given:** Running Runtime
- **When:** `SubmitGoal(description="X", priority="super-urgent")`
- **Then:** Goal rejected
- **Assert:** status = "rejected", validation_errors not empty

### RA-04: Get Goal Status — Active Goal
- **Given:** A Goal in `executing` state
- **When:** `GetGoalStatus(goal_id)`
- **Then:** Returns full status with progress
- **Assert:** status = "executing", progress object has total/completed/failed/ready/in_flight/blocked/percent_complete

### RA-05: Get Goal Status — Non-Existent
- **Given:** No Goal with id "nonexistent"
- **When:** `GetGoalStatus("nonexistent")`
- **Then:** Error response
- **Assert:** Error code = "not_found"

### RA-06: Cancel Goal — Active
- **Given:** Goal in `executing` state
- **When:** `CancelGoal(goal_id)`
- **Then:** Goal transitions to `cancelling`, then `cancelled`
- **Assert:** Final status is "cancelled"

### RA-07: Cancel Goal — Already Terminal
- **Given:** Goal in `completed` state
- **When:** `CancelGoal(goal_id)`
- **Then:** Error response
- **Assert:** Error code = "conflict"

### RA-08: Agent Register — Success
- **Given:** Running Runtime
- **When:** `Register(name="TestAgent", capabilities=[...], protocol="http", protocol_version="1.0")`
- **Then:** Agent registered, agent_id assigned, heartbeat_interval returned
- **Assert:** Response has agent_id (UUID), status "registered"

### RA-09: Agent Register — Zero Capabilities
- **Given:** Running Runtime
- **When:** `Register(name="TestAgent", capabilities=[])`
- **Then:** Registration rejected
- **Assert:** status = "rejected"

### RA-10: Heartbeat — OK
- **Given:** Registered Agent
- **When:** `Heartbeat(agent_id)`
- **Then:** Response status "ok"
- **Assert:** pending_tasks field present

### RA-11: Heartbeat — Unknown Agent
- **Given:** Non-existent agent_id
- **When:** `Heartbeat("nonexistent")`
- **Then:** Response status "re-register"
- **Assert:** Response directs agent to re-register

### RA-12: List Agents — Filtered
- **Given:** 2 connected agents, 1 disconnected
- **When:** `ListAgents(filter={status: "connected"})`
- **Then:** Returns 2 agents
- **Assert:** `len(response.agents) == 2`

### RA-13: Get Agent Detail
- **Given:** Registered agent with capabilities
- **When:** `GetAgent(agent_id)`
- **Then:** Full agent detail returned
- **Assert:** Agent has capabilities array, status, operational_state

### RA-14: List Capabilities
- **Given:** 5 registered capabilities
- **When:** `ListCapabilities()`
- **Then:** All 5 returned
- **Assert:** `len(response.capabilities) == 5`

### RA-15: Get Health — Healthy
- **Given:** All components healthy
- **When:** `GetHealth()`
- **Then:** status = "healthy"
- **Assert:** All components report healthy

### RA-16: Get Metrics
- **Given:** Runtime with 2 active goals, 5 completed tasks
- **When:** `GetMetrics()`
- **Then:** Metrics reflect current state
- **Assert:** goals.active = 2, tasks.completed_total ≥ 5

---

## Module 8: HTTP Protocol Adapter

### HTTP-01: POST /api/v1/goals → SubmitGoal
- **Given:** HTTP Adapter running
- **When:** `POST /api/v1/goals` with `{"description": "Test"}`
- **Then:** Returns 200 with goal_id
- **Assert:** Response JSON has goal_id, status "accepted"

### HTTP-02: POST /api/v1/goals — Empty Body
- **Given:** HTTP Adapter running
- **When:** `POST /api/v1/goals` with empty body
- **Then:** Returns 400
- **Assert:** Error code "invalid_input"

### HTTP-03: GET /api/v1/goals/{id} → GetGoalStatus
- **Given:** A submitted Goal
- **When:** `GET /api/v1/goals/{goal_id}`
- **Then:** Returns 200 with status
- **Assert:** Response has progress object

### HTTP-04: DELETE /api/v1/goals/{id} → CancelGoal
- **Given:** An active Goal
- **When:** `DELETE /api/v1/goals/{goal_id}`
- **Then:** Returns 200
- **Assert:** Goal status becomes "cancelled"

### HTTP-05: POST /api/v1/agents → Register
- **Given:** HTTP Adapter running
- **When:** `POST /api/v1/agents` with agent registration payload
- **Then:** Returns 200 with agent_id
- **Assert:** Response has agent_id

### HTTP-06: POST /api/v1/agents/{id}/heartbeat → Heartbeat
- **Given:** Registered agent
- **When:** `POST /api/v1/agents/{id}/heartbeat`
- **Then:** Returns 200
- **Assert:** Response status "ok"

### HTTP-07: POST /api/v1/agents/{id}/tasks/{tid}/result → SubmitResult
- **Given:** Agent with in-flight task
- **When:** `POST .../result` with Artifact
- **Then:** Returns 200
- **Assert:** Task status becomes "completed"

### HTTP-08: GET /api/v1/health → GetHealth
- **Given:** Running Runtime
- **When:** `GET /api/v1/health`
- **Then:** Returns 200
- **Assert:** Response has status "healthy"

### HTTP-09: GET /api/v1/admin/metrics → GetMetrics
- **Given:** Running Runtime
- **When:** `GET /api/v1/admin/metrics`
- **Then:** Returns 200
- **Assert:** Response has goals, tasks, agents sections

### HTTP-10: 401 Unauthorized — No API Key
- **Given:** HTTP Adapter with auth enabled
- **When:** Request without Authorization header
- **Then:** Returns 401
- **Assert:** Error code "unauthorized"

### HTTP-11: 404 Not Found — Unknown Endpoint
- **Given:** HTTP Adapter running
- **When:** `GET /api/v1/nonexistent`
- **Then:** Returns 404
- **Assert:** Error code "not_found"

---

## Module 9: Python SDK

### SDK-01: ZelosRuntime — Start and Shutdown
- **Given:** A ZelosRuntime with no agents
- **When:** `runtime.start()` → `runtime.shutdown()`
- **Then:** Runtime starts and stops cleanly
- **Assert:** No exceptions; Runtime status transitions: STOPPED → RUNNING → STOPPED

### SDK-02: ZelosRuntime — Add Agent Before Start
- **Given:** ZelosRuntime with 1 agent added before start()
- **When:** `runtime.start()`
- **Then:** Agent is registered and heartbeating after start
- **Assert:** `runtime.get_agent("agent-name").status == "heartbeating"`

### SDK-03: ZelosRuntime — Add Agent After Start (Hot-Join)
- **Given:** Running Runtime
- **When:** `runtime.add_agent("NewAgent", ...)`
- **Then:** Agent is registered and eligible for dispatch
- **Assert:** Agent appears in `runtime.list_agents()`, status becomes "heartbeating"

### SDK-04: ZelosRuntime — Remove Agent (Hot-Leave)
- **Given:** Running Runtime with agent "MyAgent"
- **When:** `runtime.remove_agent("MyAgent")`
- **Then:** Agent stops; capabilities removed
- **Assert:** Agent no longer in `runtime.list_agents()`

### SDK-05: ZelosRuntime — Submit Goal and Wait
- **Given:** Running Runtime with coding agent
- **When:** `runtime.submit_goal("Write hello world")` → `runtime.wait_for_goal(goal_id, timeout=30)`
- **Then:** Goal completes
- **Assert:** Result status is "completed"

### SDK-06: ZelosRuntime — Submit Goal with Budget
- **Given:** Running Runtime
- **When:** `runtime.submit_goal("Task", budget=10.0)` — then tasks cost more than $10
- **Then:** Goal fails with budget_exceeded
- **Assert:** Result status is "failed"

### SDK-07: Agent Base Class — execute() Must Be Overridden
- **Given:** An Agent subclass that does NOT override execute()
- **When:** Agent receives a Task
- **Then:** NotImplementedError raised
- **Assert:** Exception caught, Task marked as failed

### SDK-08: Agent Base Class — declare_capabilities() Must Be Overridden
- **Given:** An Agent subclass without declare_capabilities()
- **When:** Agent is added to Runtime
- **Then:** Registration fails
- **Assert:** error raised during registration

### SDK-09: Agent Base Class — validate_task() Hook
- **Given:** Agent overrides validate_task() to reject tasks with priority="low"
- **When:** Agent receives Task with priority="low"
- **Then:** Task is rejected → re-scheduled
- **Assert:** `agent.received_tasks` does not contain the rejected task

### SDK-10: In-Memory Runtime Stub — Test Agent Isolation
- **Given:** `InMemoryRuntime` test stub
- **When:** Start stub, register test agent, dispatch task, collect result
- **Then:** Agent produces expected Artifact
- **Assert:** Artifact content matches expected output

### SDK-11: Multiple Agents — One Goal, Multiple Capabilities
- **Given:** Runtime with 3 agents (coder, reviewer, browser)
- **When:** Submit goal requiring all 3 capabilities
- **Then:** Each agent receives appropriate Tasks
- **Assert:** All 3 agents contributed Artifacts

---

## Integration Tests

### INT-01: End-to-End — Single Agent, Single Task
- **Given:** Runtime with one agent providing `code-generation.python`
- **When:** Submit Goal "Write a hello world function"
- **Then:** Planner creates 1 Task → Scheduler dispatches → Agent executes → Artifact returned → Goal completed
- **Assert:** `goal.status == "completed"`, 1 task completed, Artifact exists

### INT-02: End-to-End — DAG with Dependencies
- **Given:** Runtime with coding agent and review agent
- **When:** Submit Goal that generates code then reviews it
- **Then:** Code generation Task completes → Review Task unblocked → Review Task completes → Goal completed
- **Assert:** Both tasks completed in correct order

### INT-03: End-to-End — Task Failure and Retry
- **Given:** Agent that fails first attempt, succeeds on retry
- **When:** Task dispatched
- **Then:** First attempt fails → retry with backoff → second attempt succeeds
- **Assert:** Task eventually completed, retry_count == 1

### INT-04: End-to-End — Hot-Join Mid-Goal
- **Given:** Goal requires capability that no current agent provides
- **When:** Goal is stuck waiting → new agent joins with needed capability
- **Then:** Blocked task becomes Ready → dispatched to new agent → Goal progresses
- **Assert:** Goal completes after hot-join

### INT-05: End-to-End — Agent Disconnect and Recovery
- **Given:** Agent processing a Task disconnects
- **When:** Heartbeat times out
- **Then:** Task cancelled and rescheduled to another agent (or marked failed)
- **Assert:** System continues; Goal eventually completes or fails gracefully
