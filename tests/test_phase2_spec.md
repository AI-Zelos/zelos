# Phase 2 — Acceptance Test Specification

---

## Module A: Verifier Framework (CodeReviewer, SecurityScanner, FactChecker)

### VER2-01: CodeReviewer — Pass
- Given: Python code artifact with no issues
- When: CodeReviewer.verify(artifact, criteria)
- Then: verdict = "passed", score >= 0.8
- Assert: issues list is empty

### VER2-02: CodeReviewer — Detect Syntax Error
- Given: Python code with a syntax error
- When: verify()
- Then: verdict = "failed", issues include the syntax error
- Assert: at least one issue with severity "error"

### VER2-03: CodeReviewer — Detect Security Pattern (eval)
- Given: Python code containing `eval(user_input)`
- When: verify()
- Then: at least one issue about dangerous eval usage
- Assert: issue severity is "error" or "warning", message mentions "eval"

### VER2-04: CodeReviewer — Detect Hardcoded Secret
- Given: Code with `password = "admin123"`
- When: verify()
- Then: issue about hardcoded credential
- Assert: message mentions "hardcoded" or "password" or "secret"

### VER2-05: CodeReviewer — Multiple Languages
- Given: criteria specifies language="javascript"
- When: JavaScript code with `eval()` is verified
- Then: issue detected in JavaScript context
- Assert: language-aware pattern matching works

### VER2-06: SecurityScanner — SQL Injection
- Given: Code containing `"SELECT * FROM users WHERE id=" + user_id`
- When: SecurityScanner.verify()
- Then: SQL injection vulnerability flagged
- Assert: issue severity "error", message mentions "SQL injection"

### VER2-07: SecurityScanner — XSS Detection
- Given: Code with `innerHTML = user_input`
- When: verify()
- Then: XSS vulnerability flagged
- Assert: issue mentions "XSS" or "innerHTML"

### VER2-08: SecurityScanner — Pass Clean Code
- Given: Clean code with no security patterns
- When: verify()
- Then: verdict = "passed"
- Assert: no issues

### VER2-09: FactChecker — Verify Claim
- Given: Artifact claims "Zelos was created in 2026"
- When: FactChecker.verify()
- Then: passes (known fact)
- Assert: verdict = "passed" or "needs_review"

### VER2-10: FactChecker — Flag Unverifiable Claim
- Given: Artifact claims "Zelos will reach 1M users by 2027"
- When: verify()
- Then: verdict = "needs_review" (future claim, unverifiable)
- Assert: issues list flags it as unverifiable

### VER2-11: VerificationGate — Multiple Verifier Types
- Given: Gate with SchemaVerifier + CodeReviewer + SecurityScanner
- When: Code with missing schema field AND eval()
- Then: SchemaVerifier catches schema issue first (short-circuits)
- Assert: first failure returned

### VER2-12: VerificationGate — All Pass
- Given: Valid code artifact
- When: All three verifiers run
- Then: verdict = "passed"
- Assert: score > 0

---

## Module B: Policy Engine (Full Rule Engine)

### POL2-01: Rule Engine — Time Window Policy
- Given: Policy "allow only 9:00-17:00"
- When: evaluate() at 10:00 → evaluate() at 20:00
- Then: 10:00 = "allow", 20:00 = "reject"
- Assert: time-based decisions correct

### POL2-02: Rule Engine — Quota Policy
- Given: Policy "max 100 tasks per day"
- When: 99th task → 100th task → 101st task
- Then: 99="allow", 100="allow", 101="reject"
- Assert: quota enforcement correct

### POL2-03: Rule Engine — Priority-Based Policy
- Given: Policy "reject low-priority tasks when queue > 10"
- When: queue_size=5, priority="low" → queue_size=15, priority="low"
- Then: first="allow", second="reject"
- Assert: conditional decisions work

### POL2-04: Rule Engine — Expression-Based Rules
- Given: Rule "task.cost > budget * 0.5 → reject"
- When: task.cost=60, budget=100 → task.cost=40, budget=100
- Then: 60>50 → "reject", 40<50 → "allow"
- Assert: expression evaluation correct

### POL2-05: Rule Engine — Multiple Rules, First Match Wins
- Given: [Rule1: reject if cost > 100, Rule2: allow all]
- When: cost=150 → cost=50
- Then: first="reject" (Rule1), second="allow" (Rule2)
- Assert: short-circuit on first match

### POL2-06: Rule Persistence — Load from YAML
- Given: policy.yaml with 3 rules
- When: PolicyLoader.load("policy.yaml")
- Then: Returns RuleEngine with 3 rules
- Assert: all rules parsed correctly

---

## Module C: Advanced Scheduler

### SCH2-01: Cost-Aware Scoring
- Given: Two agents with costs $0.02 and $0.15
- When: Task budget = $0.10
- Then: $0.02 agent scores higher
- Assert: cost-aware scoring prefers cheaper agent within budget

### SCH2-02: Latency-Aware Scoring
- Given: Two agents, avg_latency 2000ms vs 5000ms
- When: Task deadline is 3000ms
- Then: 5000ms agent filtered out (exceeds deadline)
- Assert: latency filter works before scoring

### SCH2-03: Affinity Scoring — Same Agent Preference
- Given: Task T2 depends on T1 (completed by Agent A)
- When: Scheduler evaluates candidates for T2
- Then: Agent A gets affinity boost
- Assert: affinity_score > 0 for Agent A

### SCH2-04: Load Balancing
- Given: Agent A (5/10 busy), Agent B (0/10 busy)
- When: Scheduler scores
- Then: Agent B scores higher on load dimension
- Assert: load_score(B) > load_score(A)

### SCH2-05: Historical Success Rate Weighting
- Given: Agent A (success=0.98, 1000 tasks), Agent B (success=0.98, 10 tasks)
- When: Scoring with confidence weighting
- Then: Agent A scores higher (higher confidence due to sample size)
- Assert: confidence-adjusted score differs

### SCH2-06: Multi-Dimensional Pareto Optimization
- Given: Three agents with trade-offs (cost vs speed vs quality)
- When: Scoring with Pareto-aware weights
- Then: Non-dominated agent selected
- Assert: selected agent is on Pareto frontier

---

## Module D: Protocol Adapters (gRPC, MCP, A2A, WebSocket)

### PROT-01: gRPC Adapter — Service Definition
- Given: gRPC adapter with Zelos service proto
- When: Client calls SubmitGoal via gRPC
- Then: Goal submitted successfully
- Assert: Response contains goal_id

### PROT-02: gRPC Adapter — Agent Registration
- Given: gRPC adapter
- When: Agent registers via gRPC RegisterAgent
- Then: agent_id returned
- Assert: Agent appears in list

### PROT-03: MCP Adapter — Tool Registration
- Given: MCP adapter with a tool server
- When: Agent requests tool list via MCP
- Then: Tools returned
- Assert: tools list not empty

### PROT-04: MCP Adapter — Tool Invocation
- Given: Agent executes MCP tool "read_file"
- When: MCP adapter processes tool call
- Then: Result returned
- Assert: content returned correctly

### PROT-05: A2A Adapter — Agent Card Generation
- Given: A2A adapter wrapping a Zelos Agent
- When: External system requests agent card
- Then: Card contains capabilities and endpoint
- Assert: card.skills matches registered capabilities

### PROT-06: A2A Adapter — Task Reception
- Given: External A2A system sends a task
- When: A2A adapter translates to Zelos Task
- Then: Task enters Zelos Task Graph
- Assert: task.status == "created", task has required_capability

### PROT-07: WebSocket Adapter — Event Streaming
- Given: WebSocket adapter connected
- When: Events published on Event Bus
- Then: Client receives events via WebSocket
- Assert: received events match published events

### PROT-08: WebSocket Adapter — Goal Watch
- Given: WebSocket client subscribes to goal events
- When: Goal progresses through states
- Then: Client receives goal.submitted → goal.planned → goal.executing → goal.completed
- Assert: all 4 state transitions received

---

## Module E: Observability

### OBS-01: Structured Logging — JSON Format
- Given: StructuredLogger configured with JSON format
- When: Log an event
- Then: Output is valid JSON with timestamp, level, message, context
- Assert: json.loads(log_line) succeeds

### OBS-02: Structured Logging — Log Levels
- Given: Logger level = "warn"
- When: Log debug, info, warn, error
- Then: Only warn and error are emitted
- Assert: debug and info are suppressed

### OBS-03: Metrics — Task Counter
- Given: MetricsCollector
- When: 5 tasks completed, 2 failed
- Then: task_completed_total = 5, task_failed_total = 2
- Assert: counters match

### OBS-04: Metrics — Agent Gauge
- Given: 3 agents connected, 1 disconnected
- When: Collect metrics
- Then: agent_connected = 3, agent_disconnected = 1
- Assert: gauges accurate

### OBS-05: Metrics — Latency Histogram
- Given: Task execution times: 100ms, 200ms, 500ms, 1000ms, 2000ms
- When: Collect histogram
- Then: p50 ≈ 500ms, p95 ≈ 2000ms
- Assert: percentile calculations correct

### OBS-06: Metrics — Prometheus Export
- Given: MetricsCollector with Prometheus format
- When: Export metrics
- Then: Output is valid Prometheus text format
- Assert: lines match Prometheus exposition format

### OBS-07: Tracing — Span Creation
- Given: Tracer
- When: Start span "goal.submit" → add event → end
- Then: Span recorded with duration and events
- Assert: span.duration > 0, span.events not empty

### OBS-08: Tracing — Span Hierarchy
- Given: Parent span "goal.execute" → child span "task.dispatch"
- When: Both spans completed
- Then: Child span has parent_id
- Assert: parent-child relationship preserved

---

## Module F: Plugin Isolation (Sub-Process)

### ISO-01: Sub-Process Plugin — Start
- Given: Plugin configured with isolation="subprocess"
- When: PLM loads plugin
- Then: Plugin process is spawned, communicates via stdout/stdin JSON
- Assert: plugin.status == "RUNNING"

### ISO-02: Sub-Process Plugin — Crash Recovery
- Given: Sub-process plugin running
- When: Plugin process crashes
- Then: PLM detects crash, restarts plugin
- Assert: plugin restarts < max_restarts, eventually RUNNING

### ISO-03: Sub-Process Plugin — Graceful Shutdown
- Given: Running sub-process plugin
- When: PLM.stop_plugin()
- Then: Shutdown message sent via stdin, process exits cleanly
- Assert: plugin.status == "STOPPED", process no longer running

### ISO-04: Sub-Process Plugin — Health Check
- Given: Sub-process plugin running
- When: PLM sends health check
- Then: Plugin responds with health status via stdout
- Assert: health response received within timeout

### ISO-05: In-Process vs Sub-Process Isolation
- Given: In-process plugin crashes (raises exception)
- When: PLM handles crash
- Then: In-process crash may affect Runtime; sub-process crash is isolated
- Assert: sub-process crash does not affect other plugins
