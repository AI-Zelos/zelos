"""
HTTP Protocol Adapter — REST/JSON wrapper for the Zelos Runtime API.

Phase 3:
  - TLS/mTLS support via Python's built-in ssl module.
  - Built-in Dashboard at GET / (auto-served, no external files needed).
  - Full REST API: goals, agents, audit, tenants, cluster, approvals.
  - CORS headers for browser-based Dashboard access.
"""

import json
import ssl
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import urlparse

# ═══════════════════ Inline Dashboard HTML ═══════════════════
# Served at GET / — no external files needed.

_DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Zelos Dashboard</title>
<style>
:root{--bg:#0d1117;--card:#161b22;--border:#30363d;--text:#c9d1d9;--muted:#8b949e;--accent:#58a6ff;--green:#3fb950;--red:#f85149;--yellow:#d2991d;--purple:#a371f7}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;background:var(--bg);color:var(--text);display:flex;min-height:100vh}
nav{width:240px;background:var(--card);border-right:1px solid var(--border);padding:20px 0;position:fixed;top:0;left:0;bottom:0;overflow-y:auto;z-index:100}
nav .logo{padding:0 20px 20px;font-size:22px;font-weight:700;border-bottom:1px solid var(--border);margin-bottom:10px}
nav .logo span{color:var(--accent)}
nav a{display:block;padding:10px 20px;color:var(--muted);text-decoration:none;font-size:14px;border-left:3px solid transparent;cursor:pointer}
nav a:hover,nav a.active{color:var(--text);background:rgba(88,166,255,0.06);border-left-color:var(--accent)}
nav .section{padding:15px 20px 5px;font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}
main{margin-left:240px;flex:1;padding:30px;max-width:1200px}
h1{font-size:28px;margin-bottom:8px}h2{font-size:20px;margin:30px 0 15px;padding-bottom:8px;border-bottom:1px solid var(--border)}
.subtitle{color:var(--muted);margin-bottom:25px;font-size:14px}
.sbar{display:flex;gap:15px;margin-bottom:30px;flex-wrap:wrap}
.scard{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:18px 22px;flex:1;min-width:150px}
.scard .label{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.03em;margin-bottom:6px}
.scard .value{font-size:28px;font-weight:700}
.scard .detail{font-size:12px;color:var(--muted);margin-top:4px}
.ok{color:var(--green)}.warn{color:var(--yellow)}.err{color:var(--red)}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{padding:10px 14px;text-align:left;border-bottom:1px solid var(--border)}
th{color:var(--muted);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.03em}
tr:hover{background:rgba(88,166,255,0.03)}
.badge{display:inline-block;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600}
.badge-ok{background:rgba(63,185,80,0.15);color:var(--green)}.badge-warn{background:rgba(210,153,29,0.15);color:var(--yellow)}.badge-err{background:rgba(248,81,73,0.15);color:var(--red)}.badge-info{background:rgba(88,166,255,0.15);color:var(--accent)}
.pbar{width:100%;height:6px;background:var(--border);border-radius:3px;overflow:hidden;margin-top:4px}
.pfill{height:100%;background:var(--accent);border-radius:3px;transition:width .3s}
.refresh{display:flex;align-items:center;gap:10px;margin-bottom:20px}
.refresh span{font-size:12px;color:var(--muted)}
button{background:var(--accent);color:#fff;border:none;padding:8px 16px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:600}
button:hover{opacity:.9}
.empty{color:var(--muted);padding:30px;text-align:center;font-style:italic}
pre{background:var(--card);border:1px solid var(--border);border-radius:6px;padding:15px;overflow-x:auto;font-size:12px;max-height:300px}
</style></head><body>
<nav>
<div class="logo">⚡ Zel<span>os</span> <small style="color:var(--muted);font-size:11px">v0.3.0</small></div>
<div class="section">Overview</div>
<a class="active" onclick="show('dashboard')">Dashboard</a>
<a onclick="show('goals')">Goals</a>
<a onclick="show('agents')">Agents</a>
<a onclick="show('tasks')">Tasks</a>
<div class="section">Operations</div>
<a onclick="show('audit')">Audit Log</a>
<a onclick="show('tenants')">Tenants</a>
<a onclick="show('cluster')">Cluster</a>
<a onclick="show('plugins')">Plugins</a>
<div class="section">System</div>
<a onclick="show('health')">Health &amp; Metrics</a>
<a onclick="show('api')">API</a>
</nav>
<main>
<div class="refresh"><button onclick="refresh()">🔄 Refresh</button><span>Auto: every 5s</span></div>
<div id="dashboard"><h1>Zelos Runtime Dashboard</h1><p class="subtitle">Open Multi-Agent Orchestration Runtime</p><div class="sbar" id="cards"></div><h2>Recent Goals</h2><div id="rgoals"></div><h2>Active Agents</h2><div id="ragents"></div></div>
<div id="goals" style="display:none"><h1>Goals</h1><div id="glist"></div></div>
<div id="agents" style="display:none"><h1>Agents</h1><div id="alist"></div></div>
<div id="tasks" style="display:none"><h1>Tasks</h1><div id="tlist"></div></div>
<div id="audit" style="display:none"><h1>Audit Log</h1><div id="aulist"></div></div>
<div id="tenants" style="display:none"><h1>Tenants</h1><div id="telist"></div></div>
<div id="cluster" style="display:none"><h1>Cluster Status</h1><div id="clstatus"></div></div>
<div id="plugins" style="display:none"><h1>Plugins</h1><div id="plist"></div></div>
<div id="health" style="display:none"><h1>Health &amp; Metrics</h1><pre id="raw"></pre></div>
<div id="api" style="display:none"><h1>REST API Reference</h1><pre>GET  /api/v1/health              — Runtime health
GET  /api/v1/metrics             — Runtime metrics
POST /api/v1/goals               — Submit a new goal
GET  /api/v1/goals               — List all goals
GET  /api/v1/goals/{id}          — Get goal status
DELETE /api/v1/goals/{id}        — Cancel a goal
GET  /api/v1/agents              — List registered agents
GET  /api/v1/agents/{id}         — Get agent details
GET  /api/v1/audit               — Query audit log
GET  /api/v1/tenants             — List tenants
GET  /api/v1/cluster             — Cluster status
GET  /api/v1/approvals/pending   — Pending HITL approvals
POST /api/v1/approvals/{id}/approve  — Approve
POST /api/v1/approvals/{id}/reject   — Reject

Auth: Bearer {api_key} header</pre></div>
</main>
<script>
const API=window.location.origin+'/api/v1';
function show(n){document.querySelectorAll('[id]').forEach(e=>{if(['dashboard','goals','agents','tasks','audit','tenants','cluster','plugins','health','api'].includes(e.id))e.style.display='none'});document.getElementById(n).style.display='block';document.querySelectorAll('nav a').forEach(a=>a.classList.remove('active'));event.target.classList.add('active')}
async function api(p){try{let r=await fetch(API+p);return r.ok?r.json():null}catch(e){return null}}
async function refresh(){
let h=await api('/health'),m=await api('/metrics');
document.getElementById('cards').innerHTML=`
<div class="scard"><div class="label">Runtime</div><div class="value ${h?.status==='healthy'?'ok':'warn'}">${h?.status||'offline'}</div><div class="detail">Uptime: ${Math.round((h?.uptime_seconds||0)/60)}min</div></div>
<div class="scard"><div class="label">Goals</div><div class="value">${m?.goals?.active||0}</div><div class="detail">${m?.goals?.completed_total||0} done</div></div>
<div class="scard"><div class="label">Agents</div><div class="value">${m?.agents?.connected||0}/${m?.agents?.registered||0}</div><div class="detail">connected</div></div>
<div class="scard"><div class="label">Events</div><div class="value">${m?.events?.published_total||0}</div><div class="detail">published</div></div>
<div class="scard"><div class="label">Tenants</div><div class="value">${m?.multi_tenancy?.tenants||0}</div><div class="detail">active</div></div>`;
let goals=await api('/goals');
let gh=goals&&Array.isArray(goals)?goals.slice(0,10).map(g=>`<tr><td style="font-family:monospace;font-size:12px">${(g.goal_id||'').slice(0,12)}..</td><td>${(g.description||'').slice(0,60)}</td><td><span class="badge badge-${g.status==='completed'?'ok':g.status==='failed'?'err':'info'}">${g.status}</span></td><td><div class="pbar"><div class="pfill" style="width:${g.progress?.percent_complete||0}%"></div></div><small>${g.progress?.completed_tasks||0}/${g.progress?.total_tasks||0}</small></td></tr>`).join(''):'';
document.getElementById('rgoals').innerHTML=gh?`<table><tr><th>ID</th><th>Description</th><th>Status</th><th>Progress</th></tr>${gh}</table>`:'<div class="empty">No goals yet — submit one via <code>zelos goal submit</code></div>';
document.getElementById('glist').innerHTML=document.getElementById('rgoals').innerHTML;
let agents=await api('/agents');
let ah=agents&&Array.isArray(agents)?agents.map(a=>`<tr><td>${a.name||'N/A'}</td><td style="font-family:monospace;font-size:12px">${(a.agent_id||'').slice(0,12)}..</td><td><span class="badge badge-${a.status==='heartbeating'?'ok':'warn'}">${a.status}</span></td><td>${a.current_tasks||0}/${a.max_concurrent_tasks||0}</td></tr>`).join(''):'';
document.getElementById('ragents').innerHTML=ah?`<table><tr><th>Name</th><th>ID</th><th>Status</th><th>Tasks</th></tr>${ah}</table>`:'<div class="empty">No agents registered</div>';
document.getElementById('alist').innerHTML=document.getElementById('ragents').innerHTML;
let audit=await api('/audit');
let auh=audit&&Array.isArray(audit)?audit.slice(-20).reverse().map(e=>`<tr><td style="font-size:12px">${new Date(e.timestamp*1000).toLocaleTimeString()}</td><td>${e.actor}</td><td>${e.action}</td><td style="font-family:monospace;font-size:12px">${(e.resource||'').slice(0,12)}</td><td><span class="badge badge-${e.result==='success'?'ok':'err'}">${e.result}</span></td></tr>`).join(''):'';
document.getElementById('aulist').innerHTML=auh?`<table><tr><th>Time</th><th>Actor</th><th>Action</th><th>Resource</th><th>Result</th></tr>${auh}</table>`:'<div class="empty">No audit events yet</div>';
let tenants=await api('/tenants');
let teh=tenants&&Array.isArray(tenants)?tenants.map(t=>`<tr><td>${t.tenant_id}</td><td>${t.name}</td><td><span class="badge badge-${t.active?'ok':'err'}">${t.active?'active':'inactive'}</span></td><td>${t.namespace?.goal_count||0}/${t.namespace?.quotas?.max_goals||'-'}</td><td>\$${t.namespace?.quotas?.budget_per_goal||'-'}</td></tr>`).join(''):'';
document.getElementById('telist').innerHTML=teh?`<table><tr><th>ID</th><th>Name</th><th>Active</th><th>Goals</th><th>Budget</th></tr>${teh}</table>`:'<div class="empty">Multi-tenancy not enabled</div>';
let cluster=await api('/cluster');
document.getElementById('clstatus').innerHTML=cluster?`<div class="sbar"><div class="scard"><div class="label">Nodes</div><div class="value">${cluster.total_nodes||0}</div></div><div class="scard"><div class="label">Healthy</div><div class="value ok">${cluster.healthy_nodes||0}</div></div><div class="scard"><div class="label">This Node</div><div class="value">${cluster.this_node||'N/A'}</div></div><div class="scard"><div class="label">Leader</div><div class="value">${cluster.is_leader?'👑 Leader':'Follower'}</div></div></div><pre>${JSON.stringify(cluster,null,2)}</pre>`:'<div class="empty">Distributed mode not enabled</div>';
document.getElementById('raw').textContent='Health:\n'+JSON.stringify(h,null,2)+'\n\nMetrics:\n'+JSON.stringify(m,null,2);
}
refresh();setInterval(refresh,5000);
</script></body></html>"""


class ZelosHTTPHandler(BaseHTTPRequestHandler):
    """HTTP request handler that translates REST calls to Runtime API."""

    _runtime: Any = None
    _api_keys: dict[str, str] = {}

    def log_message(self, format, *args):
        pass

    def _add_cors(self) -> None:
        """Add CORS headers for browser Dashboard access."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _authenticate(self) -> str | None:
        keys = self._api_keys
        if not keys:
            return "admin"
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return keys.get(auth[7:])
        return None

    def _send_html(self, status: int, html: str):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self._add_cors()
        self.end_headers()
        self.wfile.write(html.encode())

    def _send_json(self, status: int, data: dict):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self._add_cors()
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _send_prometheus_metrics(self):
        """Export metrics in Prometheus text exposition format."""
        m = self._runtime.get_metrics()
        lines = []
        ts = int(time.time() * 1000)

        # Goal metrics
        goals = m.get("goals", {})
        lines.append("# HELP zelos_goals_active Number of active goals")
        lines.append("# TYPE zelos_goals_active gauge")
        lines.append(f"zelos_goals_active {goals.get('active', 0)} {ts}")

        lines.append("# HELP zelos_goals_completed_total Total completed goals")
        lines.append("# TYPE zelos_goals_completed_total counter")
        lines.append(f"zelos_goals_completed_total {goals.get('completed', 0)} {ts}")

        # Task metrics
        tasks = m.get("tasks", {})
        lines.append("# HELP zelos_tasks_completed_total Total completed tasks")
        lines.append("# TYPE zelos_tasks_completed_total counter")
        lines.append(f"zelos_tasks_completed_total {tasks.get('completed_total', 0)} {ts}")

        lines.append("# HELP zelos_tasks_failed_total Total failed tasks")
        lines.append("# TYPE zelos_tasks_failed_total counter")
        lines.append(f"zelos_tasks_failed_total {tasks.get('failed_total', 0)} {ts}")

        # Agent metrics
        agents = m.get("agents", {})
        lines.append("# HELP zelos_agents_connected Connected agents")
        lines.append("# TYPE zelos_agents_connected gauge")
        lines.append(f"zelos_agents_connected {agents.get('connected', 0)} {ts}")

        lines.append("# HELP zelos_agents_disconnected Disconnected agents")
        lines.append("# TYPE zelos_agents_disconnected gauge")
        lines.append(f"zelos_agents_disconnected {agents.get('disconnected', 0)} {ts}")

        body = "\n".join(lines) + "\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.end_headers()
        self.wfile.write(body.encode())

    def _send_error(self, status: int, code: str, message: str):
        self._send_json(status, {"error_code": code, "message": message, "correlation_id": str(uuid.uuid4())})

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw) if raw else {}

    def _check_auth(self) -> str | None:
        role = self._authenticate()
        if role is None:
            self._send_error(401, "unauthorized", "Missing or invalid API key")
            return None
        return role

    # ── CORS preflight ──
    def do_OPTIONS(self):
        self.send_response(204)
        self._add_cors()
        self.end_headers()

    # ── Routing ──

    def do_GET(self):
        path = urlparse(self.path).path
        parts = [p for p in path.split("/") if p]

        # ── Dashboard: GET / ──
        if path == "/" or path == "/dashboard":
            self._send_html(200, _DASHBOARD_HTML)
            return

        # ── Prometheus metrics endpoint (no auth required) ──
        if path == "/metrics":
            self._send_prometheus_metrics()
            return

        # ── API routes require auth ──
        role = self._check_auth()
        if not role:
            return

        try:
            if path == "/api/v1/health":
                self._send_json(200, self._runtime.get_health())

            elif path == "/api/v1/metrics" or path == "/api/v1/admin/metrics":
                self._send_json(200, self._runtime.get_metrics())

            elif path == "/api/v1/goals":
                goals_list = []
                for gid, _g in self._runtime._goals.items():
                    goals_list.append(self._runtime.get_goal_status(gid))
                self._send_json(200, goals_list)

            elif parts[0] == "api" and parts[1] == "v1":
                # 3-segment paths: /api/v1/{resource}
                if len(parts) == 3:
                    if parts[2] == "agents":
                        self._send_json(200, self._runtime.list_agents())
                    elif parts[2] == "audit":
                        self._send_json(200, self._runtime.get_audit_log() or [])
                    elif parts[2] == "tenants":
                        self._send_json(200, self._runtime.list_tenants())
                    elif parts[2] == "cluster":
                        self._send_json(200, self._runtime.get_cluster_status())
                    elif parts[2] == "capabilities":
                        self._send_json(200, {"capabilities": []})
                    else:
                        self._send_error(404, "not_found", f"Unknown resource: {parts[2]}")

                # 4+ segment paths: /api/v1/{resource}/{id}[/...]
                elif len(parts) >= 4:
                    if parts[2] == "goals":
                        goal_id = parts[3]
                        status = self._runtime.get_goal_status(goal_id)
                        if status:
                            self._send_json(200, status)
                        else:
                            self._send_error(404, "not_found", "Goal not found")

                    elif parts[2] == "agents":
                        agent = self._runtime.get_agent(parts[3])
                        if agent:
                            self._send_json(200, agent)
                        else:
                            self._send_error(404, "not_found", "Agent not found")

                    elif parts[2] == "approvals":
                        if parts[3] == "pending":
                            self._send_json(200, self._runtime.list_pending_approvals() or [])
                        else:
                            self._send_error(404, "not_found", "Not found")

                    else:
                        self._send_error(404, "not_found", "Not found")
                else:
                    self._send_error(404, "not_found", "Not found")
            else:
                self._send_error(404, "not_found", "Not found")
        except Exception as e:
            self._send_error(500, "internal_error", str(e))

    def do_POST(self):
        role = self._check_auth()
        if not role:
            return
        path = urlparse(self.path).path
        parts = [p for p in path.split("/") if p]

        try:
            if path == "/api/v1/goals":
                body = self._read_body()
                if not body.get("description"):
                    self._send_json(
                        400, {"goal_id": str(uuid.uuid4()), "status": "rejected", "reason": "Description is required"}
                    )
                    return
                result = self._runtime.submit_goal(
                    description=body["description"],
                    budget=body.get("budget"),
                    deadline=body.get("deadline"),
                    priority=body.get("priority", "medium"),
                )
                code = 200 if result["status"] in ("accepted", "planned") else 400
                self._send_json(code, result)

            elif path == "/api/v1/agents":
                body = self._read_body()
                if not body.get("capabilities"):
                    self._send_json(400, {"status": "rejected", "reason": "At least one capability required"})
                    return
                agent_id = self._runtime.add_agent(
                    name=body.get("name", "agent-" + str(uuid.uuid4())[:8]),
                    entrypoint=body.get("entrypoint", "builtin:Agent"),
                    capabilities=body.get("capabilities", []),
                )
                self._send_json(
                    200,
                    {
                        "agent_id": agent_id,
                        "status": "registered",
                        "heartbeat_interval_ms": 30000,
                        "runtime_version": "0.3.0",
                    },
                )

            elif len(parts) >= 5 and parts[2] == "agents":
                agent_id = parts[3]
                if parts[4] == "heartbeat":
                    ok = self._runtime._execution_engine.heartbeat(agent_id)
                    self._send_json(200, {"status": "ok" if ok else "re-register", "pending_tasks": 0})
                elif len(parts) >= 7 and parts[4] == "tasks" and parts[6] == "result":
                    task_id = parts[5]
                    body = self._read_body()
                    ok = self._runtime._execution_engine.submit_result(task_id, agent_id, body.get("result", body))
                    self._send_json(200 if ok else 400, {"status": "accepted" if ok else "rejected"})
                else:
                    self._send_error(404, "not_found", "Not found")

            # POST /api/v1/approvals/{id}/approve
            elif len(parts) >= 5 and parts[2] == "approvals" and parts[4] == "approve":
                req_id = parts[3]
                body = self._read_body()
                result = self._runtime.approve_task(req_id, body.get("approver", "admin"), body.get("comment", ""))
                self._send_json(200, result)

            # POST /api/v1/approvals/{id}/reject
            elif len(parts) >= 5 and parts[2] == "approvals" and parts[4] == "reject":
                req_id = parts[3]
                body = self._read_body()
                result = self._runtime.reject_task(req_id, body.get("approver", "admin"), body.get("reason", ""))
                self._send_json(200, result)

            else:
                self._send_error(404, "not_found", "Not found")
        except Exception as e:
            self._send_error(500, "internal_error", str(e))

    def do_DELETE(self):
        role = self._check_auth()
        if not role:
            return
        parts = [p for p in urlparse(self.path).path.split("/") if p]
        try:
            if len(parts) >= 4 and parts[2] == "goals":
                goal_id = parts[3]
                result = self._runtime.cancel_goal(goal_id)
                if result:
                    if "error" in result:
                        self._send_json(409, result)
                    else:
                        self._send_json(200, result)
                else:
                    self._send_error(404, "not_found", "Goal not found")
            else:
                self._send_error(404, "not_found", "Not found")
        except Exception as e:
            self._send_error(500, "internal_error", str(e))


class HTTPAdapter:
    """HTTP Protocol Adapter — wraps ZelosRuntime with REST/JSON interface.

    Phase 3:
      - Dashboard served at GET / (no external files)
      - TLS/mTLS support via tls_config
      - CORS headers for browser access
    """

    def __init__(
        self, runtime, host: str = "127.0.0.1", port: int = 9876, api_keys: dict | None = None, tls_config=None
    ):
        self.runtime = runtime
        self.host = host
        self.port = port
        self._api_keys = api_keys or {}
        self._tls_config = tls_config
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None

        adapter_runtime = runtime
        adapter_api_keys = api_keys or {}

        class Handler(ZelosHTTPHandler):
            _runtime = adapter_runtime
            _api_keys = adapter_api_keys

        self._handler_class = Handler

    def start(self) -> None:
        self._server = HTTPServer((self.host, self.port), self._handler_class)

        # ── TLS / mTLS ──
        if self._tls_config and self._tls_config.is_configured():
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(
                certfile=self._tls_config.cert_file,
                keyfile=self._tls_config.key_file,
            )
            if self._tls_config.ca_file:
                ctx.load_verify_locations(cafile=self._tls_config.ca_file)
                ctx.verify_mode = ssl.CERT_REQUIRED if self._tls_config.require_client_cert else ssl.CERT_OPTIONAL
            min_v = self._tls_config.min_tls_version
            if min_v == "TLSv1.3":
                ctx.minimum_version = ssl.TLSVersion.TLSv1_3
            elif min_v == "TLSv1.2":
                ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            self._server.socket = ctx.wrap_socket(self._server.socket, server_side=True)

        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server = None
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    @property
    def url(self) -> str:
        proto = "https" if (self._tls_config and self._tls_config.is_configured()) else "http"
        return f"{proto}://{self.host}:{self.port}"
