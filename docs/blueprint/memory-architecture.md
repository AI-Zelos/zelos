# Memory Architecture

> Complete memory architecture: Session, Project, User, Knowledge, Execution, Skill layers. Memory Provider interface, memory ownership, context assembly.

---

## Document Status

| Status  | Author                     | Date       |
|---------|----------------------------|------------|
| New     | Zelos Architecture Team  | 2026-07-19 |

---

## 1. Overview

Memory in Zelos belongs to the Runtime, never to Agents. [Invariant 1](../architecture/invariants.md#invariant-1-runtime-owns-orchestration) and [Invariant 6](../architecture/invariants.md#invariant-6-agent-is-stateless).

The Memory Architecture defines:
- Six distinct memory layers with different scopes and lifetimes
- A pluggable Memory Provider interface
- How context is assembled for Task dispatch
- How memory survives Agent restarts

---

## 2. Memory Layers

```
┌────────────────────────────────────────────┐
│              KNOWLEDGE MEMORY               │  Persistent, cross-user
│         (reference facts, docs, etc.)       │
├────────────────────────────────────────────┤
│                USER MEMORY                  │  Per-user, across projects
│         (preferences, history, notes)       │
├────────────────────────────────────────────┤
│               PROJECT MEMORY                │  Per-project, across goals
│       (codebase context, decisions, etc.)    │
├────────────────────────────────────────────┤
│               SESSION MEMORY                │  Per-goal, across tasks
│       (plan context, intermediate results)   │
├────────────────────────────────────────────┤
│             EXECUTION MEMORY                │  Per-task, ephemeral
│       (task input, output, debug info)      │
├────────────────────────────────────────────┤
│               SKILL MEMORY                  │  Persistent, reusable patterns
│       (procedures, templates, examples)     │
└────────────────────────────────────────────┘
```

### 2.1 Session Memory

| Attribute | Value |
|-----------|-------|
| **Scope** | Single Goal execution |
| **Lifetime** | Goal lifespan (created → terminal) |
| **Owner** | Runtime |
| **Content** | Plan state, intermediate results, decisions made, agent interactions |
| **Access Pattern** | Read/write during Goal execution, archived after completion |

### 2.2 Project Memory

| Attribute | Value |
|-----------|-------|
| **Scope** | All Goals within a Project |
| **Lifetime** | Project lifespan (persistent) |
| **Owner** | Runtime |
| **Content** | Codebase context, project conventions, past decisions, architectural knowledge |
| **Access Pattern** | Read-heavy, write on significant decisions or context changes |

### 2.3 User Memory

| Attribute | Value |
|-----------|-------|
| **Scope** | All Goals for a specific User |
| **Lifetime** | User lifespan (persistent) |
| **Owner** | Runtime |
| **Content** | User preferences, interaction history, feedback patterns |
| **Access Pattern** | Read-heavy, write on preference changes or explicit feedback |

### 2.4 Knowledge Memory

| Attribute | Value |
|-----------|-------|
| **Scope** | Cross-user, cross-project |
| **Lifetime** | Persistent |
| **Owner** | Runtime |
| **Content** | Reference documentation, best practices, known facts, external knowledge |
| **Access Pattern** | Read-mostly, write on knowledge ingestion |

### 2.5 Execution Memory

| Attribute | Value |
|-----------|-------|
| **Scope** | Single Task |
| **Lifetime** | Task lifespan (created → terminal) |
| **Owner** | Runtime |
| **Content** | Task input, output artifact, execution metadata, error details |
| **Access Pattern** | Write once (by Agent), read by dependent Tasks and Verifiers |

### 2.6 Skill Memory

| Attribute | Value |
|-----------|-------|
| **Scope** | Cross-project, reusable |
| **Lifetime** | Persistent |
| **Owner** | Runtime |
| **Content** | Reusable procedures, templates, known-good plans, example artifacts |
| **Access Pattern** | Read by Planner, write on successful Goal completion (pattern extraction) |

---

## 3. Memory Ownership

**Memory belongs to the Runtime.**

| Concern | Owner |
|---------|-------|
| Storing memory | Runtime (via Memory Provider plugin) |
| Retrieving memory | Runtime (context assembly) |
| Deciding what to store | Runtime (policies define what gets persisted) |
| Memory schema / structure | Runtime |
| Memory lifecycle | Runtime |
| Searching memory | Runtime (via Memory Provider plugin) |

**Agents never:**

- Store memory directly
- Retrieve memory directly
- Decide what to remember
- Access other Agents' memory
- Manage memory lifecycle

Agents receive **assembled context** as part of their Task payload. They return Artifacts. The Runtime decides what to persist from those Artifacts.

---

## 4. Memory Provider Interface

### 4.1 Plugin Contract

```
interface MemoryProvider {
    // CRUD
    store(layer: MemoryLayer, key: String, value: Any, metadata?: Metadata) → Result
    retrieve(layer: MemoryLayer, key: String) → MemoryEntry?
    update(layer: MemoryLayer, key: String, value: Any) → Result
    delete(layer: MemoryLayer, key: String) → Result
    
    // Search
    search(layer: MemoryLayer, query: String, limit?: Int) → [MemoryEntry]
    search_by_metadata(layer: MemoryLayer, filter: Metadata) → [MemoryEntry]
    
    // Lifecycle
    archive(layer: MemoryLayer, scope_id: UUID) → Result    // Archive completed scope
    purge(layer: MemoryLayer, scope_id: UUID) → Result      // Delete scope data
}
```

### 4.2 Memory Entry

```
MemoryEntry {
    key: String                 // Unique within layer+scope
    value: Any                  // The stored data
    layer: MemoryLayer          // Which memory layer
    scope_id: UUID              // Goal / Project / User / Task ID
    created_at: Timestamp
    updated_at: Timestamp
    metadata: {
        source: String          // What created this entry (Agent ID, Planner ID, etc.)
        tags: [String]          // Searchable tags
        importance: Float       // 0.0-1.0, for retention priority
        ttl_seconds: Int?       // Optional auto-expiry
    }
}
```

---

## 5. Context Assembly

### 5.1 Before Task Dispatch

The Runtime assembles context for each Task before dispatch:

```
assemble_context(task: Task, goal: Goal) → MemoryContext:
    
    context = MemoryContext()
    
    // 1. Execution Memory: Input from dependency artifacts
    for dep_id in task.dependencies:
        artifact = get_artifact_for_task(dep_id)
        context.add(artifact)
    
    // 2. Session Memory: Relevant intermediate results
    session_entries = memory.search(
        layer = SESSION,
        query = task.description,
        limit = 10
    )
    context.add_all(session_entries)
    
    // 3. Project Memory: Project conventions, past decisions
    project_entries = memory.search(
        layer = PROJECT,
        query = task.description,
        limit = 5
    )
    context.add_all(project_entries)
    
    // 4. Knowledge Memory: Reference documentation
    knowledge_entries = memory.search(
        layer = KNOWLEDGE,
        query = task.description,
        limit = 3
    )
    context.add_all(knowledge_entries)
    
    // 5. Skill Memory: Relevant reusable patterns
    skill_entries = memory.search(
        layer = SKILL,
        query = task.required_capability.name,
        limit = 2
    )
    context.add_all(skill_entries)
    
    return context
```

### 5.2 Context Size Budget

Context is limited to prevent overwhelming the Agent:

```
max_context_entries: 20
max_context_size_bytes: 100KB (configurable)
```

The Runtime prioritizes:
1. Dependency artifacts (required for task execution)
2. Session memory (most relevant to current goal)
3. Project memory
4. Knowledge memory
5. Skill memory

---

## 6. After Task Completion

### 6.1 What Gets Persisted

The Runtime decides what to persist from Task execution:

```
persist_from_task(task, artifact):
    
    // Always persist to Execution Memory
    memory.store(EXECUTION, task.task_id, {
        input: task.input,
        output: artifact,
        metadata: artifact.execution_metadata
    })
    
    // Persist to Session Memory (policy-driven)
    if policy.should_persist_to_session(task, artifact):
        memory.store(SESSION, generate_key(task), {
            task_description: task.description,
            artifact_summary: summarize(artifact),
            agent_id: task.assigned_agent_id,
            execution_time_ms: artifact.execution_metadata.execution_time_ms
        })
    
    // Persist to Project Memory (if significant)
    if is_significant_decision(artifact):
        memory.store(PROJECT, generate_key(task), {
            decision: extract_decision(artifact),
            rationale: extract_rationale(artifact),
            task_id: task.task_id
        })
```

---

## 7. Memory Backends

| Backend | Best For | Phase |
|---------|----------|-------|
| **In-Memory** | Development, testing | Phase 1 |
| **File-based** | Local persistence, simple deployments | Phase 2 |
| **Redis** | Fast key-value, Session/Execution memory | Phase 2 |
| **PostgreSQL** | Reliable persistence, Project/User memory | Phase 2 |
| **Vector DB (pgvector, Pinecone)** | Semantic search, Knowledge/Skill memory | Phase 3 |

---

## 8. References

- [Architecture Invariants](../architecture/invariants.md) — Invariants 1, 6 (Runtime owns memory)
- [Domain Model](./domain-model.md) — Entity definitions
- [Kernel Boundary](./kernel-boundary.md) — Memory Provider is a Plugin
- [Execution Model](./execution-model.md) — Context assembly during execution
- [Plugin Architecture](./plugin-architecture.md) — Memory Provider as a Plugin type
