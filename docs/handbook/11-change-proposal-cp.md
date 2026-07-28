# 11 — Change Proposal (CP)

## From PR to CP

The Pull Request (PR) was designed in 2008. It assumes:
- A human writes the code
- A human reviews the code
- Changes are small enough to read

In 2026, none of these hold. The CP (Change Proposal) replaces PR with an intention-driven, evidence-backed governance model.

## The CP Five-Tuple

A CP is not a document. It is an executable governance object:

```
CP = (Intent, Knowledge Constraints, Structural Constraints, Risk Spec, Verification Criteria)
```

- **I (Intent)**: What problem, what success criteria, what scope
- **K (Knowledge)**: Coding standards, tech stack limits, forbidden patterns
- **S (Structural)**: Modified modules, protected modules, dependency whitelist
- **R (Risk)**: Risk level, security requirements, performance baselines
- **E (Verification)**: Required test pass rate, coverage thresholds, required verifiers

## CP Workflow

```
Intent Definition → Constraint Solidification → Constrained Generation → Evidence Verification → Compliant Merge
```

Every stage is owned by the Runtime. Agents execute within constraints. Verifiers check the output. Evidence is collected. Confidence is scored. Merge is automatic when evidence passes.

## Key Insight

> The bottleneck is not code generation. It's trust. CP replaces "review the code" with "review the evidence."
