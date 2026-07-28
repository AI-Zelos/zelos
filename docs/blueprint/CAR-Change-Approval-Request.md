# CAR (Change Approval Request) — AI Development Era Team Specification

## 1. Preface: The Paradigm Shift

Team development has entered a new era: **humans define requirements, AI writes code**. The decade-old GitHub PR template is completely inadequate for AI-driven development.

Traditional PRs have core pain points:

- **Code-diff centric**: The PR body is the diff; description is an afterthought
- **Minimal context**: Reviewers see thousands of AI-generated lines with no understanding of intent, scope, or risk
- **No traceability**: Cannot map changes back to requirements
- **No rollback plan**: No way to safely revert if something goes wrong

Based on this, the team formally deprecates the traditional PR paradigm and upgrades to the **CAR (Change Approval Request)** standard. The core paradigm shift:

> **From "approve the code" → "approve a complete, verifiable, controllable, rollback-able system change"**

Code becomes supporting evidence; the change itself becomes the review target.

This specification applies to all R&D, architecture, testing, SRE, security, and product personnel, covering all code merges, system iterations, feature changes, and bug fixes.

---

## 2. Core Definition: CAR vs Traditional PR

### 2.1 Traditional PR Structure (Deprecated)

```
PR
│
├── Code Diff (primary artifact)
└── Description (brief afterthought)
```

Problems: No business boundary, no requirement traceability, no architecture analysis, no risk assessment, no rollback plan. Completely loses review value under AI-generated code at scale.

### 2.2 New CAR Structure (Mandatory)

```
CAR
│
├── Change Proposal (core)
├── Evidence (core)
├── Risk Assessment (core)
└── Code Diff (supporting attachment)
```

Core principle: **Code Diff doesn't disappear — it is downgraded**. Every change must be: **intentional, traceable, evidence-backed, verified, risk-assessed, and reversible**.

---

## 3. Team CAR Standard Template (10 Mandatory Modules)

All production changes and code merges must complete all 10 modules. Any missing module → immediate rejection.

### Module 1: Intent (Change Intent & Business Boundary)

**Requirement**: Reject vague descriptions. Must clearly state business goal, scope, and explicit exclusions so all stakeholders immediately understand "what business problem this change solves."

**Forbidden**: "Implement order refund", "Optimize API", "Fix bug"

**Required format**:

```
Business Goal:
1. Enable users to self-request order refunds within 7 days of payment
2. Open admin forced-refund capability for special after-sales scenarios
3. Ensure full-chain fund data consistency — zero financial loss

Out of Scope:
1. Partial refunds not supported in this iteration
2. Batch refund operations not supported in this iteration
3. No changes to refund fee rates or discount return logic
```

### Module 2: Requirement Mapping (Full-Chain Traceability)

**Requirement**: Complete the requirement → code module → test result traceability chain. Prove **every line of change maps to a specific requirement — no dead code, no redundant development**.

**Required template**:

| Requirement ID | Implementation Module | Status | Supporting Tests |
|---|---|---|---|
| R1 User self-refund | RefundService | ✅ Done | Unit + Integration passed |
| R2 Admin forced refund | AdminRefund, RBAC module | ✅ Done | Permission scenario tests passed |
| R3 Refund idempotency | Redis distributed lock | ✅ Done | Duplicate request load test verified |

**Standard**: 100% requirement coverage. Every requirement has corresponding implementation and test evidence.

### Module 3: Architecture Delta (Architecture Change Diff)

**Requirement**: Proactively disclose all system architecture, module, and link changes. Reviewers should never need to guess from code. Complex changes must include before/after diagrams.

**Required template**:

```
Architecture Changes:
[Added]
1. New Refund Domain (business domain)
2. New Refund Repository (data layer)
3. New RefundEvent (domain event)

[Modified]
1. Order Aggregate Root adapted for refund state transitions

[Removed]
1. Deprecated Legacy Refund API

[Architecture Link Comparison (required for complex changes)]
Before: Order → Payment
After:  Order → Refund → Payment → Notification
```

### Module 4: Implementation Plan (Execution Steps)

**Requirement**: Define the complete rollout steps. Show iterative logic, phased rollout, migration strategy, and go-live cadence. No unplanned, hard-cut deployments.

**Required template**:

```
Step 1: Create refund database tables and fields, initialize data structures
Step 2: Develop core refund API with permission validation
Step 3: Write historical order refund data migration script
Step 4: Configure feature flag for gradual traffic rollout
Step 5: After full verification, decommission legacy refund logic
```

### Module 5: Impact Analysis (Full-Dimensional Impact) **[Critical]**

**Requirement**: Comprehensively identify all system nodes affected by this change — modules, APIs, databases, events, caches, message queues. **No omissions, no hidden impacts**. This is the foundation of production risk control.

**Required template**:

```
[Affected Modules]
Order, Payment, Inventory, Notification, Settlement

[Affected APIs]
Added: POST /refund (order refund endpoint)

[Affected Database]
1. New: refund table
2. Modified: order table — added refund_status column

[Affected Events]
New: RefundCreated event

[Affected Cache]
New: refund_cache (refund status cache)

[Affected MQ]
New: refund_success queue (refund completion delivery)
```

### Module 6: Evidence (Full-Dimensional Verification Evidence)

**Requirement**: Reject vague statements like "tested locally." Must provide quantified, traceable, full-coverage test, compilation, performance, and security verification data. All evidence must be verifiable.

**Required template**:

```
[Compilation] Compile: PASS
[Unit Tests] Unit Test: 548 cases — all passed
[Integration Tests] Integration Test: 82 scenarios — all passed
[E2E Tests] E2E: PASS
[Regression Tests] Regression: PASS
[Contract Tests] Contract Test: PASS
[Security Scan] Security Scan: No high-severity vulnerabilities, PASS
[Performance Test] Performance: API response improved 8%, throughput stable

[Code Coverage]
Before: 82%
After: 84%
Coverage improved; no uncovered core logic
```

### Module 7: Risk Assessment (Risk Evaluation & Mitigation)

**Requirement**: Reject generic "low risk, no risk" statements. Must specify risk level, root cause, impact scope, and concrete mitigation plan. All medium+ risks require fallback strategies.

**Risk Levels**: Low / Medium / High / Critical

**Required template**:

```
[Risk Level] Medium
[Root Cause] This change modifies the core payment chain involving fund transfer logic.
             Edge cases may cause refund state anomalies.
[Potential Impact] Small number of orders may experience refund failures or state inconsistency
[Mitigation Plan]
1. Feature flag for real-time cutover of change logic
2. Full-chain refund logging for issue tracing
3. Rate limiting to prevent refund request flood
```

### Module 8: Rollback Plan (Complete Rollback Strategy)

**Requirement**: Every CAR must include an executable, fast rollback plan. Changes without rollback plans are forbidden from deployment. Must specify steps and estimated duration.

**Required template**:

```
[Rollback Steps]
Step 1: Disable feature flag — cut off new refund logic
Step 2: Roll back database schema changes (new columns and tables)
Step 3: Roll back service image to stable production version
Step 4: Restore original event, MQ, and cache configurations

[Estimated Rollback Duration] 5 minutes
[Rollback Verification] Production refund flow restored to original logic, no errors
```

### Module 9: Generated Artifacts (Change Supporting Assets)

**Requirement**: Automatically collect and attach all supporting outputs for this change. Unified archiving for future review, iteration, operations, and audit.

**Required artifact checklist**:

```
1. OpenAPI specification diff
2. Database ER diagram diff
3. Database migration SQL scripts
4. Performance benchmark report
5. Full-chain change log
6. Security scan report
7. Code coverage report
8. Dependency change manifest
```

### Module 10: Human Decision (Review Decision Record)

**Requirement**: Reviewers are forbidden from replying with just "LGTM". Must make explicit decisions on architecture, business, risk, and deployment strategy. Review accountability is preserved.

**Required decision template**:

```
[Architecture Review] Approve / Reject
[Business Review] Approve / Reject
[Risk Judgment] Accept / Optimize / Reject
[Deployment Strategy] Full rollout / Gradual canary / Off-peak deployment
```

---

## 4. CAR Generation & Workflow (AI Development Adapted)

### 4.1 Generation Source: Runtime Auto-Generates, Not Manual

The team runs an Agent Runtime pipeline. CAR is **auto-aggregated by the pipeline**. No manual authoring:

1. **Planner Agent**: Outputs change execution plan and business intent
2. **Code Agent**: Outputs code change diff and module modifications
3. **Test Agent**: Outputs full test results and coverage data
4. **Security Agent**: Outputs security scan report and vulnerability findings
5. **Performance Agent**: Outputs performance benchmarks and load test data
6. **Architecture Agent**: Outputs architecture changes and impact analysis

The Runtime aggregates all Agent outputs and auto-generates the complete CAR document. Humans only need to supplement judgment and boundary clarifications.

### 4.2 Role-Based Review Focus

One CAR document, multiple roles — each reviews what matters to them:

- **Product**: Reviews Intent (business goals, scope, requirement alignment)
- **Architect**: Reviews Architecture Delta (overall change合理性)
- **Tech Lead**: Reviews Implementation Plan, code logic, requirement traceability
- **QA**: Reviews Evidence, impact scope, test coverage
- **Security**: Reviews security scan results, vulnerability risks
- **SRE**: Reviews Risk Assessment, Rollback Plan, deployment strategy, performance metrics

---

## 5. Team Enforcement Rules

1. **Mandatory for all**: All code merges, iterations, bug fixes, and feature optimizations must submit a complete CAR. Traditional PR templates are deprecated.

2. **All modules required**: Missing any of the 10 core modules → immediate review rejection. No merge, no deployment.

3. **No vague descriptions**: "Tests passed", "low risk", "optimized logic" are forbidden. Everything must be quantified, specific, and verifiable.

4. **Risk & rollback mandatory**: Medium+ risk changes without mitigation plan or rollback strategy → deployment forbidden.

5. **Review accountability**: All reviews must record the four-dimensional decision. Meaningless "LGTM" is prohibited. Review responsibility is enforced.

6. **AI code mandatory gating**: All AI-generated code must pass CAR full-chain verification. Code is only a change attachment. Direct merge of AI code is prohibited.

---

## 6. Value Proposition

1. **Adapts to AI R&D paradigm**: Solves the core problem of uncontrollable, unreviewable, untraceable AI-generated code at scale

2. **Unified multi-role collaboration**: Product, R&D, Architecture, QA, Security, SRE — one document, role-specific views, lower communication cost

3. **Full-chain traceability + risk control + fast rollback**: Dramatically reduces production incident probability

4. **Standardized change assets**: Enables iteration review, technical audit, and continuous improvement

5. **Software engineering paradigm upgrade**: Code moves from review target → change evidence. The system change itself becomes the core approval object. **This is the CAR philosophy.**
