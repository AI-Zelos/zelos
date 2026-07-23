# Zelos Operations Guide v0.7.0

## Deployment Modes

### 1. Bare Metal (Python)

```bash
git clone https://gitee.com/tomliuda/zelos.git && cd zelos
pip install -e ".[dev]"
cp zelos.yaml.example zelos.yaml   # edit config
make dev                            # foreground
# or: python3 start.py              # foreground with dashboard
```

### 2. Docker

```bash
make build          # zelos:0.7.0
make run            # docker compose up -d
make stop           # docker compose down

# With Redis for persistent storage:
make run-storage    # includes redis profile
```

### 3. Kubernetes

```bash
kubectl apply -f deploy/k8s/deployment.yaml
kubectl apply -f deploy/k8s/service.yaml
```

#### K8s Probes

| Endpoint | Probe Type | Port | Response |
|----------|-----------|------|----------|
| `GET /live` | Liveness | 9876 | `{"status": "alive"}` |
| `GET /ready` | Readiness | 9876 | `{"status": "ready"/"not_ready"}` |

Example K8s config:
```yaml
livenessProbe:
  httpGet:
    path: /live
    port: 9876
  initialDelaySeconds: 5
  periodSeconds: 15
readinessProbe:
  httpGet:
    path: /ready
    port: 9876
  initialDelaySeconds: 3
  periodSeconds: 10
```

---

## Observability

### Prometheus Metrics

Scrape `http://<runtime>:9876/metrics` for:

| Metric | Type | Description |
|--------|------|-------------|
| `zelos_goals_active` | Gauge | Currently active goals |
| `zelos_goals_completed_total` | Counter | Total completed goals |
| `zelos_tasks_completed_total` | Counter | Total completed tasks |
| `zelos_tasks_failed_total` | Counter | Total failed tasks |
| `zelos_agents_connected` | Gauge | Currently connected agents |
| `zelos_agents_disconnected` | Gauge | Disconnected agents |

### Grafana Dashboard

Import `deploy/grafana/zelos-dashboard.json` into Grafana.
Requires Prometheus datasource configured.

---

## Security

### API Key Management

```python
from zelos.security import APIKeyManager

mgr = APIKeyManager(
    max_failures=10,         # auto-revoke threshold
    failure_window_seconds=60.0,  # sliding window
    auto_revoke=True,        # enable brute-force protection
)

key = mgr.generate_key("admin", "production-admin-key")
# → "zelos_<128 hex chars>"  — save this, it's shown only once

mgr.validate(key)   # → {"role": "admin", ...}
mgr.revoke(key)     # → True
```

### Anomaly Detection (v0.7.0)

- Tracks failed auth attempts per key hash
- Auto-revokes after `max_failures` within `failure_window_seconds`
- Configurable per deployment
- Failed attempts older than the window are pruned

### Audit Log Export

```python
logger.export_json_file("/var/log/zelos/audit.json")
```

---

## Distributed Coordination (v0.7.0)

### etcd Backend

```python
from zelos.coordination import EtcdCoordinationBackend, CoordinationNode

backend = EtcdCoordinationBackend({"endpoints": "localhost:2379", "prefix": "/zelos/"})
backend.connect()
backend.register_node(CoordinationNode(node_id="node-1", host="10.0.0.1", port=9001))
backend.elect_leader("node-1", ttl_seconds=30)
leader = backend.get_leader()  # → "node-1"
backend.heartbeat("node-1")    # renew lease
```

### NATS Message Bus

```python
from zelos.messaging_nats import NatsMessageBus

bus = NatsMessageBus({"servers": ["nats://localhost:4222"]})
bus.connect()
bus.subscribe("zelos.events", lambda data, headers: process(data))
bus.publish("zelos.events", {"event_type": "task.completed"})
```

### Go SDK

```bash
go get github.com/zelos/zelos-go
```

```go
c := client.New("http://localhost:9876", "zk-client-dev")
health, _ := c.Health()
goal, _ := c.SubmitGoal("Build a landing page", "high")
```

---

## Multi-Node Cluster Deployment

### Architecture

```
┌──────────────────────────────────────────────┐
│                  Node 1 (Leader)             │
│  ZelosRuntime + etcd + NATS                  │
│  IP: 10.0.0.1:9876                           │
└──────────┬──────────┬────────────────────────┘
           │          │
     ┌─────▼───┐  ┌──▼──────┐
     │ Node 2  │  │ Node 3  │
     │ 10.0.0.2│  │ 10.0.0.3│
     └─────────┘  └─────────┘
```

### Prerequisites

| Component | Purpose | Default Port |
|-----------|---------|-------------|
| etcd | Leader election + node discovery | 2379 |
| NATS | Cross-node EventBus + messaging | 4222 |
| Zelos Runtime | Agent orchestration | 9876 |

### Step 1: Start Infrastructure

```bash
# etcd (all nodes connect to same cluster)
docker run -d --name etcd -p 2379:2379 \
  bitnami/etcd:latest

# NATS
docker run -d --name nats -p 4222:4222 \
  nats:latest
```

### Step 2: Configure Each Node

```yaml
# zelos-node-1.yaml
runtime:
  instance_id: "zelos-node-1"
  api:
    host: "10.0.0.1"
    port: 9876

distributed:
  enabled: true
  node_id: "node-1"
  peers: ["10.0.0.1:9877", "10.0.0.2:9877", "10.0.0.3:9877"]

storage:
  type: postgresql
  url: "postgresql://postgres:zelos@10.0.0.1:5432/zelos"

coordination:
  type: etcd
  endpoints: "10.0.0.1:2379"

messaging:
  type: nats
  servers: ["nats://10.0.0.1:4222"]
```

### Step 3: Start Nodes

```bash
# Node 1 (expects to become leader)
python3 start.py --config zelos-node-1.yaml &

# Node 2
python3 start.py --config zelos-node-2.yaml &

# Node 3
python3 start.py --config zelos-node-3.yaml &
```

### Step 4: Verify Cluster

```bash
curl http://10.0.0.1:9876/api/v1/cluster
# → {"is_leader": true, "peers": ["node-1", "node-2", "node-3"], "healthy": 3}

curl http://10.0.0.2:9876/api/v1/cluster
# → {"is_leader": false, "leader": "node-1"}
```

### Leader Election Flow

```
1. All nodes register in etcd: /zelos/nodes/{node_id}
2. Smallest node_id wins (Bully algorithm)
3. Leader holds etcd lease, renews via heartbeat
4. If leader lease expires → new election triggered
5. Watchers (NATS subscribers) notified of leader change
```

### Work Stealing

```
Node-2 idle (queue depth=0) → queries etcd for busiest node → steals READY tasks
Node-3 overloaded (queue depth=15) → Node-1 and Node-2 steal work
```

### Failure Recovery

| Failure | Behavior |
|---------|----------|
| Leader crash | etcd lease expires → Node-2/Node-3 elect new leader (<5s) |
| Worker crash | In-flight tasks re-assigned via NATS |
| etcd down | Falls back to InMemory coordination (single-node mode) |
| NATS down | Falls back to InMemory message bus |

---

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Runtime won't start | `python3 -c "from zelos.runtime import ZelosRuntime; ZelosRuntime().start()"` |
| Agent won't register | Verify API key role >= `agent` |
| Tasks stuck in READY | Check capability name matches agent registration |
| High failure rate | Check anomaly detection — keys may be auto-revoked |
| `/ready` returns 503 | Check `GET /api/v1/health` for component status |

### Health Check Components

```
GET /api/v1/health → {
  "status": "healthy",
  "components": {
    "kernel": "healthy",
    "plugins": {"total": N, "healthy": N},
    "agents": {"connected": N, "disconnected": N},
    "security": {"audit_events": N},
    "cluster": {"enabled": bool, "is_leader": bool}
  }
}
```

---

## Backup & Recovery

### Event Persistence

Enable `PersistentEventStore` with a storage backend to survive restarts:

```python
from zelos.event_bus import PersistentEventStore
from zelos.storage import PostgreSQLStorageBackend

storage = PostgreSQLStorageBackend({"url": "postgresql://..."})
storage.connect()
store = PersistentEventStore(storage)

# After crash:
recovered = store.recover()  # replays all persisted events
```

### State Recovery

Save Goal/Agent state before shutdown:
```python
storage.set_state(f"goal-{goal_id}", goal_state)
# After restart:
saved = storage.get_state(f"goal-{goal_id}")
```

---

## Configuration Reference

See `zelos.yaml` for all options. Key sections:

| Section | Purpose |
|---------|---------|
| `runtime.api` | Host, port, auth keys |
| `runtime.limits` | max_goals, max_tasks_per_goal |
| `security` | audit_max_events, TLS/mTLS paths |
| `multi_tenancy` | enabled, tenant configs |
| `distributed` | enabled, node_id, peers |
| `plugins` | All plugin declarations (storage, memory, policy, verifier, planner, adapter) |
