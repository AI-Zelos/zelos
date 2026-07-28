# 10 — From Code Review to Change Review

## The Old Paradigm

For 50 years, software engineering relied on code review:

```
Human writes code → Human reviews code → Merge → Deploy
```

This worked when:
- Humans wrote all the code
- Changes were small (hundreds of lines)
- Reviewers had time to read every line

## The Breaking Point

In 2026, AI can produce 35,000+ lines per hour. The old model collapses:

- **Volume**: No human can read 35,000 lines per change
- **Speed**: Review becomes the bottleneck, defeating the purpose of AI assistance
- **Quality**: Reviewers skim, missing subtle bugs in AI-generated code
- **Accountability**: When something breaks, "the reviewer missed it" is not a defense

## The New Paradigm

```
Human defines Intent
    → AI produces implementation
    → Verifiers check every output
    → Evidence is collected automatically
    → Confidence is scored objectively
    → Human approves the change proposal, not the code
    → System deploys with rollback plan
```

## What Changes

| From | To |
|------|-----|
| Review code line by line | Review evidence summary |
| "Does this look right?" | "Confidence is 0.97 — should we ship?" |
| Reviewer finds bugs | Verifiers find bugs |
| Description is optional | Intent is mandatory and structured |
| No rollback plan | Every change has a rollback plan |
| PR is the unit of review | CAR is the unit of review |
| LGTM | Explicit decisions on Architecture/Business/Risk/Deployment |

## What Stays the Same

- Human judgment is still required for high-risk or low-confidence changes
- Architecture decisions still need human oversight
- Business priorities still come from humans
- The final "ship it" decision is still human

The change is not that humans are removed. It's that humans are **elevated** — from code readers to change governors.

## The Future

We believe this shift is as fundamental as the shift from waterfall to agile, or from manual deployment to CI/CD. Code review served us well for 50 years. It's time for the next evolution:

> **Stop reviewing code. Start reviewing trust.**
