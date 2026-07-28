# 03 — Execution Plan

## From Goal to Tasks

A Goal is what you want. An Execution Plan is how to get there.

The Planner (an LLM plugin) decomposes the Goal into a DAG of atomic Tasks, each with:
- A required Capability (what kind of agent is needed)
- Dependencies (what must complete first)
- Priority and timeout

```
Goal: "Build a landing page"

Plan:
  t1: Design the page         → design.architecture
  t2: Code the frontend       → code-generation.typescript  (depends on t1)
  t3: Security review         → code-review.security        (depends on t2)
  t4: Fix security issues     → code-generation.typescript  (depends on t3)
  t5: Take screenshot         → automation.browser           (depends on t4)
  t6: Generate report         → code-generation.python       (depends on t5)
```

## Architecture Delta

v0.9.0 adds Architecture Delta to every Plan — the Planner also outputs what will change in the system:

```json
{
  "architecture_delta": {
    "modified_modules": ["landing-page", "cdn-config"],
    "new_dependencies": ["react-helmet@6.1.0"],
    "api_changes": [],
    "risk_level": "low"
  }
}
```

## Dynamic Plans

Plans are not static. The Runtime can modify execution based on:
- Failures (replan to find alternative paths)
- Policy (reject tasks exceeding budget)
- Resource availability (reassign to available agents)

## Next
[04 — Verification and Evidence](04-verification-and-evidence.md)
