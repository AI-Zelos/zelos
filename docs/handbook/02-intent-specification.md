# 02 — Intent Specification

## The Problem: Vague Goals

`submit_goal("Implement login")` is the equivalent of telling a contractor "build a house" and walking away.

Without structure, agents:
- Implement the wrong thing (OAuth vs. password vs. both)
- Miss constraints (must not break existing login)
- Expand scope uncontrollably

## The Solution: IntentSpec

IntentSpec forces the user to articulate **what success looks like** before any agent runs:

```python
intent = IntentSpec(
    description="Implement OAuth2 login with Google and GitHub",
    success_criteria=[
        "Users can sign in with Google OAuth",
        "Users can sign in with GitHub OAuth",
        "Auth tokens expire after 24 hours",
        "Existing password login still works"
    ],
    constraints=[
        "Do not modify password hashing logic",
        "Use standard OAuth2.0 libraries",
        "No client_secret in frontend code"
    ],
    scope="single_module",
)
```

## Key Principles

1. **Success criteria must be verifiable.** "Better UX" is not verifiable. "Page load < 200ms at p95" is.
2. **Constraints are non-negotiable.** If violated, the entire change is invalid.
3. **Out of scope is as important as in scope.** Prevents scope creep.
4. **Intent is a contract between human and runtime.** The Runtime validates against it.

## Without IntentSpec (Backward Compatible)

The `intent` parameter is optional. If omitted, Zelos falls back to the legacy `description`-only mode. This preserves backward compatibility with v0.8.x code.

## Next
[03 — Execution Plan](03-execution-plan.md)
