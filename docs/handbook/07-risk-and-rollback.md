# 07 — Risk and Rollback

## Risk Assessment

Every change carries risk. The question is not "is there risk?" — it's "do we understand the risk and have a plan?"

A proper risk assessment answers:

1. **Risk Level**: low / medium / high / critical
2. **Root Cause**: what specifically makes this risky?
3. **Potential Impact**: what happens if it goes wrong?
4. **Mitigation**: what reduces the risk?

```
Risk Level: Medium
Root Cause: Modifies core payment chain involving fund transfers.
            Edge cases may cause refund state anomalies.
Potential Impact: Small number of orders may experience refund failures.
Mitigation:
  1. Feature flag for real-time cutover
  2. Full-chain refund logging for issue tracing
  3. Rate limiting to prevent request flood
```

## Rollback Plan

Every change must have a rollback plan. A change without a rollback plan should never ship.

```
Strategy: event_sourcing_replay
Restore to: event_position 42
Estimated downtime: 5 seconds
Steps:
  1. Pause new task dispatch
  2. Restore goal state to event_position 42
  3. Verify state consistency
  4. Resume normal operation
```

## Rollback Strategies

| Strategy | Use Case | Downtime |
|----------|----------|----------|
| `event_sourcing_replay` | Any Zelos-managed change | ~5s |
| `feature_flag_off` | Changes behind feature flags | <1s |
| `git_revert` | Code-only changes | CI/CD cycle |
| `db_rollback` | Schema changes with migration scripts | Varies |

## The Rule

> **Risk ≥ medium AND no rollback plan → deployment forbidden.**

## Next
[08 — Change Approval Request](08-change-approval-request.md)
