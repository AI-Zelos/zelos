# Verifier

> Complete verification subsystem: role in the execution pipeline, verdict model, verifier types, verification gate, retry integration, plugin interface, and lifecycle.

---

## Document Status

| Status  | Author                     | Date       |
|---------|----------------------------|------------|
| New     | Zelos Architecture Team  | 2026-07-19 |

---

## 1. Overview

The Verifier is the quality gate in the Zelos execution model. After an Agent produces an Artifact, the Runtime may invoke one or more Verifiers to validate the Artifact before it is accepted and passed to dependent Tasks. Verification is not optional in the architecture — it is a first-class phase of execution.

### 1.1 Why Verification Exists

Agents are autonomous and fallible. An Agent may produce:
- Syntactically invalid output
- Semantically incorrect results
- Security vulnerabilities
- Policy violations
- Incomplete work

The Runtime cannot trust Agent output blindly. Verification provides a structured, pluggable quality gate that runs **before** dependent Tasks consume the Artifact.

### 1.2 Position in the Execution Model

```
Agent produces Artifact
       │
       ▼
┌──────────────┐
│   VERIFIER   │  ← Plugin, invoked by Runtime
│              │
│ verify()     │
└──────┬───────┘
       │
       ├── Verdict: Passed → Artifact accepted → Dependent Tasks unblocked
       │
       └── Verdict: Failed → Artifact rejected → Retry / Re-plan
```

**See:** [Execution Model](./execution-model.md) §6 for the full execution phase.

---

## 2. Verdict Model

### 2.1 Verdict States

| Verdict | Meaning | Action |
|---------|---------|--------|
| `passed` | Artifact meets all criteria | Artifact → `accepted`. Task → `completed`. Dependent Tasks evaluated. |
| `failed` | Artifact fails criteria | Artifact → `rejected`. Task retry evaluated by Scheduler. |
| `needs_review` | Verifier cannot decide automatically | Task paused. Human intervention requested. |

### 2.2 Verdict Structure

```
Verdict {
    verdict: "passed" | "failed" | "needs_review"
    score: Float              // 0.0 - 1.0, confidence or quality score
    verifier_id: String
    verifier_version: String
    issues: [Issue]           // Empty if passed
    summary: String           // Human-readable explanation
    checked_at: Timestamp
}

Issue {
    severity: "error" | "warning" | "info"
    message: String
    location: String?         // Where in the artifact the issue was found
    rule_id: String?          // Which verification rule was violated
}
```

---

## 3. Verification Gate

### 3.1 Gate Logic

```
verify_artifact(artifact, task):
    verifiers = resolve_verifiers(task)
    
    if verifiers is empty:
        // No verification required
        artifact.status → accepted
        task.status → completed
        return
    
    for verifier in verifiers:
        verdict = verifier.verify(artifact, task.verification_criteria)
        
        if verdict == "failed":
            artifact.status → rejected
            publish artifact.rejected
            scheduler.evaluate_retry(task)
            return  // Short-circuit on first failure
        
        if verdict == "needs_review":
            artifact.status → pending_review
            publish verification.needs_review
            notify_human(task, verdict)
            return  // Wait for human
    
    // All verifiers passed
    artifact.status → accepted
    publish artifact.validated
    task.status → completed
    publish task.completed
    task_graph.evaluate_dependents(task)
```

### 3.2 Multiple Verifiers

A Task may require multiple verifiers. They run **sequentially** in priority order. First failure stops the chain.

| Verifier Priority | Example |
|-------------------|---------|
| 1. Schema | Validate output matches expected_output_schema |
| 2. Security | Scan for vulnerabilities |
| 3. Policy | Check compliance with policies |
| 4. Quality | Code review, style check, fact check |

### 3.3 Verification Criteria

Each Task may specify verification criteria:

```
task.verification = {
    required_verifiers: ["schema-validator"],   // Specific verifiers to run
    criteria: {                                  // Passed to verifier
        max_issues: 0,
        min_score: 0.8,
        rules: ["no-secrets", "valid-json"]
    },
    on_failure: "retry" | "escalate" | "skip"  // What to do on failure
}
```

---

## 4. Verifier Types

### 4.1 Built-in / Reference Verifiers

| Verifier | Checks | Phase |
|----------|--------|-------|
| **Schema Validator** | Artifact matches expected_output_schema (JSON Schema) | Phase 1 |
| **Code Reviewer** | Code quality, linting, static analysis | Phase 2 |
| **Security Scanner** | Credential leaks, SQL injection, dependency CVEs | Phase 2 |
| **Fact Checker** | Claims against known facts (RAG-based) | Phase 2 |
| **Policy Verifier** | Content policy, licensing, compliance rules | Phase 2 |
| **Consistency Checker** | Artifact consistent with Plan intent and previous artifacts | Phase 3 |
| **Human Reviewer** | Human-in-the-loop approval | Phase 2 |

### 4.2 Verifier Selection

The Runtime selects which verifiers to invoke based on:
1. Task `verification.required_verifiers` (explicit)
2. Capability defaults (e.g., all `code-generation` tasks get Code Reviewer)
3. Goal-level verification policy
4. Global Runtime verification policy

---

## 5. Verification and Retry

### 5.1 Retry on Verification Failure

When verification fails:

```
artifact.rejected
    │
    ▼
Scheduler evaluates retry:
    task.attempt < max_retries?
    ├── Yes → Retry with SAME agent (agent may fix its output)
    │         OR different agent (if policy prefers diversity)
    │
    └── No → fallback_capability exists?
              ├── Yes → switch capability, retry
              └── No → Task → Failed (terminal)
                       Evaluate Plan modification
```

### 5.2 Verification-Aware Scheduling

After a verification failure, the Scheduler may:
- Prefer a different Agent (the first one produced invalid output)
- Increase the `min_success_rate` requirement
- Add a `required_tags: ["high-quality"]` constraint

---

## 6. Verifier Plugin Interface

### 6.1 Contract

```
interface Verifier {
    // Lifecycle (from Plugin base)
    configure(config: PluginConfig) → Result
    initialize() → Result
    start() → Result
    stop() → Result
    health() → HealthStatus
    metadata() → PluginMetadata
    
    // Verification
    verify(artifact: Artifact, criteria: VerificationCriteria) → Verdict
}
```

### 6.2 VerificationCriteria

```
VerificationCriteria {
    expected_output_schema: JSON Schema?   // For schema validation
    rules: [String]                         // Specific rules to check
    context: {                              // Additional context
        goal_description: String
        task_description: String
        dependency_artifacts: [Artifact]    // For cross-reference
    }
    options: Map                            // Verifier-specific options
}
```

---

## 7. Verifier Lifecycle

### 7.1 States

```
Unloaded → Loaded → Configured → Initialized → Running → Stopped
```

Standard Plugin lifecycle. See [Plugin Architecture](./plugin-architecture.md).

### 7.2 Health

The Runtime health-checks verifiers. An unhealthy verifier causes:
- In-flight verifications: wait for recovery or timeout
- New verifications: skip (log warning) or block (configurable)
- `plugin.failed` event published; Runtime may enter DEGRADED

---

## 8. Events

| Event | When |
|-------|------|
| `verification.requested` | Verifier invoked for an Artifact |
| `verification.completed` | Verifier returned a Verdict |
| `verification.needs_review` | Verdict is `needs_review` — human intervention |

---

## 9. Observability

| Metric | Type | Description |
|--------|------|-------------|
| `verifier.requests_total` | Counter | Verification invocations |
| `verifier.passed_total` | Counter | Passed verdicts |
| `verifier.failed_total` | Counter | Failed verdicts |
| `verifier.needs_review_total` | Counter | Needs-review verdicts |
| `verifier.duration_ms` | Histogram | Verification duration |
| `verifier.score_distribution` | Histogram | Distribution of verdict scores |

---

## 10. References

- [Architecture Invariants](../architecture/invariants.md) — Invariants 1, 8, 10
- [Domain Model](./domain-model.md) — Artifact, Task definitions
- [Execution Model](./execution-model.md) — §6 Verification phase
- [Scheduler](./scheduler.md) — Retry evaluation on verification failure
- [Plugin Architecture](./plugin-architecture.md) — Verifier as a Plugin type
- [Kernel Boundary](./kernel-boundary.md) — Verifier is a Plugin, not Kernel
- [Schema: Artifact](../schema/artifact.json) — verification_status field
