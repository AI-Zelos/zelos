#!/usr/bin/env python3
"""
Demo 03: HTTP REST API + 自动编排

启动 HTTP API Server → curl 提交 Goal → 自动分解 + 执行 → curl 查结果。

用法:
    export OPENAI_API_KEY="sk-xxx"
    python3 demo/03_http_api.py
    # 另开终端: curl http://127.0.0.1:19876/api/v1/health
"""
import sys, os, time, json, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.runtime import ZelosRuntime
from zelos.http_adapter import HTTPAdapter

API_KEY = os.getenv("OPENAI_API_KEY", "")
API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

if not API_KEY:
    print("❌ 请设置 OPENAI_API_KEY"); sys.exit(1)

ALL_CAPS = ["code-generation.python", "code-generation.typescript",
            "code-review.security", "code-review.quality",
            "verification.unit-test", "verification.integration-test",
            "design.architecture", "design.database",
            "communication.documentation", "communication.report",
            "automation.browser", "automation.cli"]


def request(method, path, data=None):
    url = f"http://127.0.0.1:19876{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method,
        headers={"Content-Type": "application/json", "Authorization": "Bearer demo"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def main():
    print("=" * 60)
    print("  Demo 03: HTTP REST API + 自动编排")
    print("=" * 60)

    runtime = ZelosRuntime({
        "plugins": [{
            "id": "llm-planner", "type": "planner",
            "entrypoint": "zelos.planner.LLMPlanner",
            "config": {
                "provider": "openai", "model": MODEL,
                "api_key": API_KEY, "base_url": API_BASE,
                "temperature": 0.3, "max_tokens": 4000,
            },
        }]
    })

    runtime.add_agent("HTTPAgent", "demo.01_single_agent:DemoAgent", [
        type('C', (), {'name': c, 'version': '1.0.0', 'description': c,
                       'input_schema': {}, 'output_schema': {}, 'tags': []})
        for c in ALL_CAPS
    ])
    runtime.start()

    adapter = HTTPAdapter(runtime, host="127.0.0.1", port=19876)
    adapter.start()
    print(f"🌍 HTTP API: http://127.0.0.1:19876\n")

    # 1. Health
    code, body = request("GET", "/api/v1/health")
    print(f"GET  /health        → {code} {body.get('status', '?')}")

    # 2. Submit Goal（自动分解 + 执行）
    code, body = request("POST", "/api/v1/goals", {
        "description": "写一个 Python 的 Hello World Web 服务",
        "priority": "high",
    })
    goal_id = body.get("goal_id", "")
    print(f"POST /goals          → {code} {body['status']} | {body.get('task_count','?')} tasks")

    # 3. 轮询直到完成
    print(f"\n⏳ 等待自动完成...")
    for _ in range(60):
        time.sleep(0.5)
        code, body = request("GET", f"/api/v1/goals/{goal_id}")
        p = body.get("progress", {})
        if body.get("status") in ("completed", "failed"):
            print(f"\n📊 Goal: {body['status']} | {p.get('completed_tasks',0)}/{p.get('total_tasks',0)} tasks")
            break
        print(f"\r   ⏳ {p.get('completed_tasks',0)}/{p.get('total_tasks',0)} completed", end="", flush=True)

    # 4. Agents
    code, body = request("GET", "/api/v1/agents")
    print(f"\nGET  /agents         → {len(body.get('agents',[]))} agents")

    # 5. Cancel demo
    g2 = runtime.submit_goal("To cancel")
    code, _ = request("DELETE", f"/api/v1/goals/{g2['goal_id']}")
    print(f"DELETE /goals/{g2['goal_id'][:8]} → {code}")

    print(f"\n💡 另开终端试试:")
    print(f"   curl -X POST http://127.0.0.1:19876/api/v1/goals -H 'Content-Type: application/json' -d '{{\"description\":\"写一个排序算法\"}}'")

    adapter.stop()
    runtime.shutdown()
    print("\n✅ Demo 03 完成")


if __name__ == "__main__":
    main()
