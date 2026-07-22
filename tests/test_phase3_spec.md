# Phase 3 — Test Specification

> Zelos Phase 3: Runtime Ecosystem — Production-grade distributed infrastructure.
> Version: 0.3.0 | Target: 100+ tests

---

## Module Overview

| # | Module | File | Test Count | Description |
|---|--------|------|------------|-------------|
| 1 | Security | `zelos/security.py` | 22 | Access control, audit logging, API key mgmt |
| 2 | Multi-tenancy | `zelos/multi_tenancy.py` | 16 | Namespace isolation, resource quotas |
| 3 | Advanced Execution | `zelos/advanced_execution.py` | 20 | Dynamic plan, sub-goal, HITL |
| 4 | Container Isolation | `zelos/container_isolation.py` | 10 | Docker/podman container + remote mode |
| 5 | Hot Reload | `zelos/hot_reload.py` | 12 | Plugin upgrade w/o restart |
| 6 | Distributed Runtime | `zelos/distributed.py` | 14 | Leader election, work stealing |
| 7 | CLI Tool | `zelos/cli.py` | 10 | Command-line interface |
| **Total** | | | **104** | |

---

## 1. Security Module (22 tests)

### SEC-01: AccessControl — Role Definitions

| ID | Test | Expected |
|----|------|----------|
| SEC-01a | Create AccessControl with default roles | admin, operator, agent, viewer roles exist |
| SEC-01b | admin role has all permissions | `*` wildcard permission |
| SEC-01c | operator role permissions | goal.submit, goal.cancel, task.*, agent.read |
| SEC-01d | agent role permissions | task.execute, agent.heartbeat, artifact.create |
| SEC-01e | viewer role permissions | goal.read, task.read, agent.read, metrics.read |

### SEC-02: AccessControl — Permission Check

| ID | Test | Expected |
|----|------|----------|
| SEC-02a | admin can do anything | check("admin", "goal.submit") → True |
| SEC-02b | agent cannot submit goals | check("agent", "goal.submit") → False |
| SEC-02c | operator can read agents | check("operator", "agent.read") → True |
| SEC-02d | Wildcard pattern match | operator with "task.*" can "task.create" |
| SEC-02e | Unknown role denied | check("unknown_role", "anything") → False |

### SEC-03: AccessControl — Custom Roles

| ID | Test | Expected |
|----|------|----------|
| SEC-03a | Add custom role | Custom role with specific permissions |
| SEC-03b | Modify role permissions | Updated permissions take effect |
| SEC-03c | Remove role | Removed role returns False for all checks |

### SEC-04: AuditLogger

| ID | Test | Expected |
|----|------|----------|
| SEC-04a | Log audit event | Event recorded with timestamp, actor, action, resource |
| SEC-04b | Query by actor | Filter audit log by actor |
| SEC-04c | Query by action | Filter audit log by action type |
| SEC-04d | Query by time range | Filter audit log by start/end time |
| SEC-04e | Query by resource | Filter audit log by resource ID |
| SEC-04f | Export audit log | JSON export with all events |

### SEC-05: API Key Manager

| ID | Test | Expected |
|----|------|----------|
| SEC-05a | Generate API key | Returns key with prefix "zelos_" |
| SEC-05b | Validate valid key | Returns role and metadata |
| SEC-05c | Reject invalid key | Returns None |
| SEC-05d | Revoke key | Revoked key fails validation |
| SEC-05e | Key expiration | Expired key fails validation |

---

## 2. Multi-tenancy Module (16 tests)

### TEN-01: Namespace

| ID | Test | Expected |
|----|------|----------|
| TEN-01a | Create namespace | Namespace with ID, name, quotas |
| TEN-01b | Namespace isolation | Resources in ns-A invisible to ns-B |
| TEN-01c | List namespaces | All namespaces returned |
| TEN-01d | Delete namespace | Namespace and all resources removed |

### TEN-02: Resource Quotas

| ID | Test | Expected |
|----|------|----------|
| TEN-02a | Goal quota enforcement | Exceeding max_goals rejects new goal |
| TEN-02b | Task quota enforcement | Exceeding max_tasks rejects new task |
| TEN-02c | Agent quota enforcement | Exceeding max_agents rejects registration |
| TEN-02d | Budget quota enforcement | Exceeding budget_per_goal rejects goal |
| TEN-02e | Quota reset | Quota counters reset correctly |
| TEN-02f | Quota usage tracking | Current usage accurately reflected |

### TEN-03: Tenant Manager

| ID | Test | Expected |
|----|------|----------|
| TEN-03a | Register tenant | Tenant with namespace and quotas |
| TEN-03b | Tenant activation/deactivation | Deactivated tenant rejects all operations |
| TEN-03c | Cross-tenant isolation | Tenant A cannot access Tenant B resources |
| TEN-03d | Tenant resource limits | Quota enforcement per tenant |
| TEN-03e | Default tenant | Default tenant for unassigned resources |
| TEN-03f | Tenant metadata | Custom metadata per tenant |

---

## 3. Advanced Execution Module (20 tests)

### ADV-01: Dynamic Plan Modification

| ID | Test | Expected |
|----|------|----------|
| ADV-01a | Add task to running plan | New task inserted into DAG |
| ADV-01b | Remove pending task | Unstarted task removed, dependents updated |
| ADV-01c | Modify task capability | Task capability changed, re-dispatched |
| ADV-01d | Add dependency edge | New dependency enforced |
| ADV-01e | Remove dependency edge | Dependency removed, task becomes ready |
| ADV-01f | Cycle prevention | Adding cyclic dependency rejected |
| ADV-01g | Modify running task rejected | Cannot modify STARTED/COMPLETED task |

### ADV-02: Sub-Goal Spawning

| ID | Test | Expected |
|----|------|----------|
| ADV-02a | Spawn sub-goal from task | Sub-goal created with parent reference |
| ADV-02b | Sub-goal task DAG | Sub-goal has its own plan and tasks |
| ADV-02c | Parent waits for sub-goal | Parent task blocks until sub-goal completes |
| ADV-02d | Sub-goal failure propagation | Failed sub-goal marks parent task failed |
| ADV-02e | Nested sub-goals | Multi-level sub-goal spawning |
| ADV-02f | Sub-goal budget inheritance | Sub-goal inherits/allocates parent budget |

### ADV-03: Human-in-the-Loop (HITL)

| ID | Test | Expected |
|----|------|----------|
| ADV-03a | Create approval request | ApprovalRequest with task, context, options |
| ADV-03b | Approve action | Approved → task continues |
| ADV-03c | Reject action | Rejected → task failed with reason |
| ADV-03d | Request changes | Changes requested → task goes back with feedback |
| ADV-03e | Approval timeout | Unapproved request times out |
| ADV-03f | Approval audit trail | All approval actions logged |
| ADV-03g | Multi-step approval | Chain of approvals for critical tasks |

---

## 4. Container/Remote Plugin Isolation (10 tests)

### ISO2-01: Container Plugin Config

| ID | Test | Expected |
|----|------|----------|
| ISO2-01a | Docker container config | Image, command, env, mounts config valid |
| ISO2-01b | Podman container config | Same as Docker, with podman runtime |
| ISO2-01c | Resource limits config | CPU/memory limits parsed correctly |
| ISO2-01d | Network config | Network mode, port mappings |

### ISO2-02: Remote Plugin

| ID | Test | Expected |
|----|------|----------|
| ISO2-02a | Remote plugin registration | Register via HTTP endpoint |
| ISO2-02b | Remote health check | HTTP health endpoint check |
| ISO2-02c | Remote task dispatch | Task sent via HTTP POST |
| ISO2-02d | Remote result callback | Result received via callback URL |
| ISO2-02e | Remote timeout | Unresponsive remote plugin times out |
| ISO2-02f | Remote reconnection | Auto-reconnect on disconnect |

---

## 5. Hot Reload Module (12 tests)

### HOT-01: File Watcher

| ID | Test | Expected |
|----|------|----------|
| HOT-01a | Watch plugin directory | File changes detected |
| HOT-01b | Plugin reload trigger | Modified plugin file → reload |
| HOT-01c | New plugin detection | New plugin file → auto-register |
| HOT-01d | Deleted plugin cleanup | Deleted plugin → unregister gracefully |
| HOT-01e | Debounce rapid changes | Multiple rapid saves → single reload |

### HOT-02: Hot Upgrade

| ID | Test | Expected |
|----|------|----------|
| HOT-02a | Upgrade without restart | Plugin version bumped, Runtime unchanged |
| HOT-02b | In-flight task completion | Running tasks finish before old plugin stops |
| HOT-02c | New tasks → new version | New tasks routed to upgraded plugin |
| HOT-02d | Rollback support | Failed upgrade rolls back to previous version |
| HOT-02e | Version tracking | Plugin version history maintained |
| HOT-02f | Graceful drain | Old version drains before shutdown |
| HOT-02g | Concurrent upgrade | Multiple plugin upgrades simultaneously |

---

## 6. Distributed Runtime Module (14 tests)

### DIST-01: Leader Election

| ID | Test | Expected |
|----|------|----------|
| DIST-01a | Single node becomes leader | First node elected leader |
| DIST-01b | Leader heartbeat | Leader sends periodic heartbeats |
| DIST-01c | Follower promotion | Leader failure → follower elected |
| DIST-01d | Split brain prevention | Two leaders cannot exist simultaneously |
| DIST-01e | Leader resignation | Graceful leader resignation |

### DIST-02: Work Stealing

| ID | Test | Expected |
|----|------|----------|
| DIST-02a | Idle node steals work | Underutilized node takes tasks |
| DIST-02b | Steal from most loaded | Task taken from busiest node |
| DIST-02c | Steal only ready tasks | Only READY tasks are stolen |
| DIST-02d | Capacity-aware stealing | Node only steals if it has capacity |

### DIST-03: Node Registry

| ID | Test | Expected |
|----|------|----------|
| DIST-03a | Node registration | Node registers with cluster |
| DIST-03b | Node heartbeat | Periodic node health updates |
| DIST-03c | Node removal | Dead node removed after timeout |
| DIST-03d | Node metadata | Node capabilities and load info |
| DIST-03e | Cluster status | Aggregate cluster health info |

---

## 7. CLI Tool Module (10 tests)

### CLI-01: Basic Commands

| ID | Test | Expected |
|----|------|----------|
| CLI-01a | zelos --version | Prints version string |
| CLI-01b | zelos --help | Prints help text with subcommands |
| CLI-01c | zelos start | Starts Runtime server |
| CLI-01d | zelos stop | Stops Runtime server |

### CLI-02: Goal Commands

| ID | Test | Expected |
|----|------|----------|
| CLI-02a | zelos goal submit | Submit goal from CLI |
| CLI-02b | zelos goal status | Get goal status by ID |
| CLI-02c | zelos goal list | List all goals |
| CLI-02d | zelos goal cancel | Cancel a goal |

### CLI-03: Agent Commands

| ID | Test | Expected |
|----|------|----------|
| CLI-03a | zelos agent list | List registered agents |
| CLI-03b | zelos agent info | Get agent details |
