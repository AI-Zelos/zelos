# Phase 1 Remaining — Test Specifications

## Module A: Config Loader (zelos.yaml)

### CFG-01: Load valid zelos.yaml
- Given: A valid zelos.yaml file with runtime settings + plugins
- When: ConfigLoader.load("zelos.yaml")
- Then: Returns parsed dict with runtime + plugins sections
- Assert: config["runtime"]["api"]["port"] == 9876, config["plugins"] has items

### CFG-02: File not found
- Given: Non-existent path
- When: load("nonexistent.yaml")
- Then: Raises FileNotFoundError or returns empty defaults
- Assert: Error or default config returned

### CFG-03: Plugin type validation
- Given: Plugin with invalid type (not in storage/memory/policy/scoring_strategy/verifier/planner/adapter)
- When: Config validated
- Then: ValueError raised
- Assert: "Unknown plugin type" in error

### CFG-04: Required fields check
- Given: Plugin missing "id" field
- When: Config validated
- Then: ValueError raised
- Assert: "Missing required field: id"

### CFG-05: Runtime defaults
- Given: Minimal config with only plugins section
- When: load()
- Then: Runtime section filled with defaults (host="127.0.0.1", port=9876, etc.)
- Assert: Defaults applied correctly

### CFG-06: Auth API key parsing
- Given: Config with runtime.auth.keys section
- When: Config loaded
- Then: API keys parsed as list of {key, role}
- Assert: keys[0].key is set, keys[0].role in (admin, agent, client)

---

## Module B: Verifier

### VER-01: Schema Verifier — Pass
- Given: Artifact with content matching expected_output_schema
- When: SchemaVerifier.verify(artifact, criteria)
- Then: Verdict is "passed"
- Assert: verdict.verdict == "passed", score == 1.0

### VER-02: Schema Verifier — Fail (Wrong Type)
- Given: Artifact with string content, schema expects object
- When: verify()
- Then: Verdict is "failed"
- Assert: verdict.verdict == "failed", issues list not empty

### VER-03: Schema Verifier — Fail (Missing Required Field)
- Given: Artifact missing a required field per schema
- When: verify()
- Then: "failed"
- Assert: Issues mention missing field

### VER-04: No Verifier Configured — Accept
- Given: Task with no verification config
- When: Verifier gate runs
- Then: Artifact accepted directly
- Assert: verification_status becomes "accepted"

### VER-05: Multiple Verifiers — Sequential
- Given: Task requires [schema-validator, security-scanner]
- When: First passes, second fails
- Then: Artifact rejected; second verifier's issues reported
- Assert: verification_status == "rejected"

### VER-06: Verdict Structure
- Given: Any verification result
- When: Verdict returned
- Then: Contains verifier_id, score, issues, summary, checked_at
- Assert: All fields present

### VER-07: Large artifact — content_ref
- Given: Artifact with content_ref (no inline content)
- When: Verified
- Then: Verifier accesses via URI reference
- Assert: No error; verifier handles content_ref gracefully

---

## Module C: Policy Engine

### POL-01: Cost Limit — Under Budget
- Given: Policy with max_cost_per_goal=100, task cost=5, cumulative=60
- When: CostLimitPolicy.evaluate()
- Then: Returns "allow"
- Assert: decision == "allow"

### POL-02: Cost Limit — Over Budget
- Given: Policy with max_cost_per_goal=100, task cost=50, cumulative=70
- When: evaluate()
- Then: Returns "reject"
- Assert: decision == "reject"

### POL-03: Rate Limit — Within Limit
- Given: max_tasks_per_minute=60, 30 tasks in last minute
- When: evaluate()
- Then: "allow"
- Assert: decision == "allow"

### POL-04: Rate Limit — Exceeded
- Given: max_tasks_per_minute=60, 61 tasks in last minute
- When: evaluate()
- Then: "reject"
- Assert: decision == "reject"

### POL-05: Allowlist — Agent in List
- Given: allowlist_agents=["agt-1", "agt-2"], candidate agent_id="agt-2"
- When: evaluate()
- Then: "allow"
- Assert: decision == "allow"

### POL-06: Allowlist — Agent NOT in List
- Given: allowlist_agents=["agt-1", "agt-2"], candidate="agt-3"
- When: evaluate()
- Then: "reject"
- Assert: decision == "reject"

### POL-07: Composite Policy — All Pass
- Given: CompositePolicy with [CostLimit, RateLimit, Allowlist], all pass
- When: evaluate()
- Then: "allow"
- Assert: decision == "allow"

### POL-08: Composite Policy — First Fails
- Given: CompositePolicy with [CostLimit, RateLimit], cost over budget
- When: evaluate()
- Then: "reject" (short-circuits, doesn't check RateLimit)
- Assert: decision == "reject"

---

## Module D: Memory Architecture

### MEM-01: Store and Retrieve
- Given: InMemoryMemoryProvider
- When: store("session", "key1", "value1") → retrieve("session", "key1")
- Then: Returns stored value
- Assert: result == "value1"

### MEM-02: Separate Layers
- Given: store("session", "k", "session_val") + store("project", "k", "project_val")
- When: retrieve("session", "k") + retrieve("project", "k")
- Then: Each layer returns its own value
- Assert: session result != project result

### MEM-03: Six Layers Exist
- Given: MemoryProvider
- When: Store/retrieve from each layer (session, project, user, knowledge, execution, skill)
- Then: All 6 work independently
- Assert: All 6 layers store and retrieve correctly

### MEM-04: Update Existing Entry
- Given: store("session", "k", "v1") → update("session", "k", "v2")
- When: retrieve("session", "k")
- Then: Returns "v2"
- Assert: result == "v2"

### MEM-05: Update Non-Existent → Error
- Given: No entry for "session", "nonexistent"
- When: update("session", "nonexistent", "val")
- Then: KeyError raised
- Assert: Exception

### MEM-06: Delete Entry
- Given: store("session", "k", "v") → delete("session", "k")
- When: retrieve("session", "k")
- Then: Returns None or KeyError
- Assert: result is None

### MEM-07: Search by Query
- Given: store("session", "task-1", {"desc": "write code"}) + store("session", "task-2", {"desc": "review code"})
- When: search("session", "code")
- Then: Both entries returned
- Assert: len(results) == 2

### MEM-08: TTL Expiry
- Given: store with ttl_seconds=1
- When: Wait 1.5s, retrieve
- Then: Entry expired, returns None
- Assert: result is None

### MEM-09: Context Assembly
- Given: MemoryProvider with entries in session/project/user/knowledge layers
- When: assemble_context(task_id, goal_id)
- Then: Returns merged MemoryContext with entries from all relevant layers
- Assert: context has session/project/user/knowledge keys

### MEM-10: Max Entries Per Layer
- Given: max_entries_per_layer=3
- When: Store 5 entries in session layer
- Then: Oldest 2 evicted
- Assert: len(layer) == 3
