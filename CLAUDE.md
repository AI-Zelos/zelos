# CLAUDE.md

# Zelos

> Zelos is an Open Multi-Agent Orchestration Runtime.

Zelos is **NOT** another Agent framework.

It is **NOT** a workflow engine.

It is **NOT** another LangGraph, CrewAI or AutoGen.

Its purpose is to become the Runtime that executes, coordinates and governs intelligent agents.

Think:

Linux manages Processes.

Kubernetes manages Containers.

Temporal manages Workflow Execution.

**Zelos manages Goal Execution across multiple autonomous Agents.**

---

# Project Vision

Modern AI systems are no longer composed of a single model.

A single user request may require:

- Planning
- Research
- Coding
- Browser automation
- Database querying
- Verification
- Human approval

These capabilities are provided by different Agents.

The problem is no longer:

> How to build an Agent?

The problem is:

> How to reliably orchestrate hundreds or thousands of independent Agents?

Zelos exists to solve this problem.

---

# Core Philosophy

Zelos is a Runtime.

Everything starts from Runtime.

Never design from Agent.

Always design from Runtime.

The Runtime owns:

- Scheduling
- Task Lifecycle
- Execution Plan
- Event Sourcing
- Goal State Persistence
- Heartbeat Timeout
- Non-Retryable Errors
- Retry History
- Execution Trace
- Evidence Collection
- Confidence Scoring
- Policy Gate
- Intent Specification
- Architecture Delta
- Impact Analysis
- Rollback Plan
- Change Proposal (CP)
- Constraint Engine
- Verifier Chain
- Merge Executor
- Change Approval Request (CAR)
- Memory
- Context
- Event Bus
- Capability Registry
- Policy
- Verification
- Observability

Agents own only one thing:

Execution.

---

# Runtime Responsibility

The Runtime is responsible for:

Goal

↓

Planning

↓

Execution Plan

↓

Task Graph

↓

Capability Matching

↓

Scheduling

↓

Execution

↓

Verification

↓

Artifact Generation

↓

Completion

The Runtime owns every stage.

---

# Agent Responsibility

An Agent is NOT a workflow.

An Agent is NOT a scheduler.

An Agent is NOT a memory owner.

An Agent is only an execution plugin.

Its responsibility is:

Receive Task

↓

Execute

↓

Return Artifact

↓

Exit

Agents never:

- schedule tasks
- invoke other agents
- manage memory
- retry tasks
- know workflow topology
- know other agents

---

# Execution Model

Execution is centered around an Execution Plan.

Planner produces:

Execution Plan

Execution Plan contains:

- Tasks
- Dependencies
- Constraints
- Capability Requirements
- Priority
- Deadline
- Budget

The Runtime executes the plan.

Execution Plan is dynamic.

The Runtime may modify execution based on:

- failures
- policy
- budget
- runtime state
- resource availability

---

# Capability First

Zelos never dispatches by Agent name.

Everything is dispatched by Capability.

Example:

Need:

coding

↓

Capability Registry

↓

Available Providers

Claude Code

Codex

Gemini

Local Agent

↓

Scheduler

↓

Best Provider Selected

Capabilities are first-class citizens.

Agents are implementations.

---

# Capability Registry

The Runtime maintains a Capability Registry.

Each capability describes:

- Name
- Version
- Description
- Input Schema
- Output Schema
- QoS
- Cost
- Latency
- Tags
- Owner
- Required Resources

Agents register capabilities.

The Runtime discovers providers automatically.

---

# Task Graph

Execution is represented as a Task Graph.

Tasks may be:

Independent

Parallel

Sequential

Conditional

Blocked

Waiting

Cancelled

Failed

Retrying

Succeeded

The Scheduler continuously evaluates the graph.

Only Ready tasks are dispatched.

---

# Runtime Communication

Inside Zelos:

Everything is Event.

Never use direct Agent-to-Agent communication.

Example:

TaskCompleted

↓

ArtifactCreated

↓

EventBus

↓

Scheduler

↓

Next Task Ready

↓

Dispatch

Agents never communicate directly.

---

# Protocol Architecture

Zelos defines its own Runtime API.

External protocols are adapters.

Runtime API

↓

Python SDK

Go SDK

Java SDK

Rust SDK

HTTP Adapter

gRPC Adapter

A2A Adapter

Future Adapters

The Runtime never depends on any external protocol.

---

# MCP

MCP is a Tool Protocol.

Agents use MCP to access:

- GitHub
- Database
- Browser
- Slack
- Filesystem

Runtime is unaware of MCP internals.

---

# A2A

A2A is NOT the Runtime protocol.

A2A is an interoperability protocol.

Primary use cases:

- Runtime ↔ Runtime
- External Agent Integration
- Cross-Organization Collaboration

A2A is implemented through an Adapter.

The Runtime itself remains protocol-independent.

---

# Memory

Memory belongs to Runtime.

Never to Agents.

Memory layers include:

Session Memory

Project Memory

User Memory

Knowledge Memory

Execution Memory

Skill Memory

Memory survives Agent restarts.

---

# Scheduler

The Scheduler is the core of Zelos.

It decides:

Which capability

↓

Which provider

↓

When

↓

Where

↓

How many

↓

Retry strategy

↓

Fallback strategy

Scheduling decisions consider:

- Capability Match
- Cost
- Latency
- Historical Success Rate
- Priority
- Deadline
- Budget
- Current Load
- Resource Availability
- Policy Constraints

---

# Planner

Planner is NOT part of the Kernel.

Planner is a Plugin.

Different planners may exist.

The Planner produces Execution Plans.

The Runtime executes them.

---

# Change Approval Request (CAR)

Zelos implements the CAR paradigm: from "approve the code" to "approve a complete, verifiable, controllable, rollback-able system change."

Code becomes supporting evidence; the system change becomes the review target.

The CAR standard mandates 10 modules: Intent → Requirement Mapping → Architecture Delta → Implementation Plan → Impact Analysis → Evidence → Risk Assessment → Rollback Plan → Generated Artifacts → Human Decision.

See: `docs/blueprint/CAR-Change-Approval-Request.md`

---

# Verifier

Verification is also a Plugin.

Possible verifiers:

Code Review

Fact Check

Security Review

Compliance Review

Style Review

Cost Review

The Runtime decides which verifiers to invoke.

---

# Plugin Architecture

Everything above the Kernel is replaceable.

Kernel

↓

Plugins

Planner

Verifier

Agents

Policies

Memory Providers

Storage

Every plugin follows the Runtime API.

---

# Runtime API

Every execution provider implements:

register()

heartbeat()

execute()

cancel()

shutdown()

metadata()

Nothing more.

The Runtime owns the lifecycle.

---

# Event Driven

Everything is represented as Events.

Examples:

GoalSubmitted

ExecutionPlanCreated

TaskCreated

TaskReady

TaskAssigned

TaskStarted

TaskCompleted

TaskFailed

TaskTimedOut

TaskRetryScheduled

TaskFatalFailed

GoalStatePersisted

GoalStateRecovered

VerificationCompleted

ExecutionFinished

No component communicates through direct invocation.

---

# Specification First

Development follows:

ADR

↓

Architecture Blueprint

↓

RFC

↓

Schema

↓

Acceptance Tests

↓

Reference Implementation

↓

Production Implementation

Code is never the source of truth.

Specification is.

---

# Documentation Structure

docs/

    adr/

    blueprint/

    rfc/

    architecture/

    schema/

    api/

    examples/

    reference/

    benchmark/

Every design starts with documentation.

---

# MVP Scope

Zelos v0.x focuses only on Runtime.

Included:

✅ Runtime Kernel

✅ Scheduler

✅ Execution Engine

✅ Capability Registry

✅ Task Graph

✅ Event Bus

✅ Runtime API

✅ Plugin Runtime

✅ Event Sourcing Engine

✅ Goal State Persistence

✅ Execution Trace

✅ Evidence Collection

✅ Confidence Scoring

✅ Policy Gate v2

✅ Change Approval Request (CAR)

✅ MCP Adapter

✅ A2A Adapter

Excluded:

❌ Marketplace

❌ Agent Store

❌ Cloud Platform

❌ Enterprise Portal

❌ Billing

❌ SaaS

These are future ecosystem projects.

---

# Design Principles

Always prefer:

Runtime First

Capability First

Execution Plan First

Event Driven

Distributed First

Plugin Architecture

Cloud Native

Specification First

High Cohesion

Low Coupling

Observability

Governance

Extensibility

---

# Anti Patterns

Never build:

❌ Agent chains

❌ Workflow-centric architecture

❌ Agent-owned memory

❌ Agent-to-Agent direct calls

❌ Name-based dispatch

❌ Tight coupling

❌ Protocol-dependent Runtime

❌ Business logic inside Runtime

❌ Runtime logic inside Agents

---

# CAR (Change Approval Request) — PR & Commit Standard

All pull requests and significant commits MUST follow the CAR format defined in `docs/blueprint/CAR-Change-Approval-Request.md`.

The core principle: **review the change, not the code**. Code is supporting evidence.

## When to use CAR format

- **All PRs** (to any branch)
- **All commits that introduce a new feature, refactor, or breaking change**
- Bug fix commits: use simplified CAR (Intent + Evidence + Risk only)

## PR / Commit Message Template

```
## Intent
[Why this change? What business problem does it solve?]

## Architecture Delta
[What modules/files changed? New dependencies? API changes?]

## Impact Analysis
[Affected modules, APIs, DB, events, cache, MQ]

## Evidence
- [ ] Compile: PASS
- [ ] Unit Tests: N passed
- [ ] Integration Tests: N passed
- [ ] Regression: PASS
- [ ] Lint: PASS

## Risk Assessment
Risk Level: [low | medium | high | critical]
Root Cause: [why is this risky?]
Mitigation: [rollback steps, feature flags, etc]

## Rollback Plan
Strategy: [event_sourcing_replay | git_revert | feature_flag_off]
Estimated downtime: [N seconds/minutes]
Steps:
1. [step 1]
2. [step 2]
```

## Auto-enforcement

When creating a PR or commit:
1. Run all tests FIRST — include the test results in Evidence
2. List ALL modified modules in Architecture Delta — do not omit any
3. Assign a risk level — never default to "low" without justification
4. Include a rollback plan — "git revert" is acceptable for low-risk changes
5. If evidence is incomplete (tests not run, lint not checked), state it explicitly

Reference: `docs/blueprint/CAR-Change-Approval-Request.md`

---

# Ultimate Goal

The long-term goal is not to build another framework.

The goal is to define the Runtime standard for autonomous multi-agent systems.

Developers should only need to:

1. Build an Agent.
2. Declare its Capabilities.
3. Register it with Zelos.

Everything else—

Planning.

Scheduling.

Coordination.

Execution.

Retry.

Verification.

Memory.

Lifecycle.

Observability.

—is handled by the Runtime.

This is the vision of Zelos.

git提交的时候 需要按照【AI研发时代团队CAR（变更审批请求）.md】文档中的规范进行提交。