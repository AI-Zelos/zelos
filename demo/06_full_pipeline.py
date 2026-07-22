#!/usr/bin/env python3
"""
Demo 06: 完整端到端流水线

Planner → Orchestrator → Scheduler → Agent → Verifier → Policy → Memory
全自动运行，包含三层阶梯式容错。

用法:
    export OPENAI_API_KEY="sk-xxx"
    export OPENAI_API_BASE="https://api.deepseek.com/v1"
    export OPENAI_MODEL="deepseek-v4-flash"
    python3 demo/06_full_pipeline.py
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.runtime import ZelosRuntime

API_KEY = os.getenv("OPENAI_API_KEY", "")
API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

if not API_KEY:
    print("❌ 请设置 OPENAI_API_KEY"); sys.exit(1)

ALL_CAPS = ["code-generation.python", "code-generation.typescript",
            "code-review.security", "code-review.quality",
            "verification.unit-test", "verification.integration-test",
            "design.architecture", "design.ui", "design.database",
            "automation.browser", "automation.cli", "automation.file-system",
            "communication.documentation", "communication.report",
            "research.web-search", "analysis.performance"]


def main():
    print("=" * 60)
    print("  Demo 06: 完整端到端流水线")
    print("=" * 60)
    print(f"  LLM: {MODEL}")
    print(f"  Components: Planner + Scheduler + Verifier + Policy + Memory")
    print(f"  Escalation: Tier1(wait) → Tier2(fail) → Tier3(replan)\n")

    # 1. 配置 Runtime（所有插件）
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

    # 2. 注册 4 个不同能力的 Agent
    agents = [
        ("SeniorDev", ["code-generation.python", "code-generation.typescript",
                       "design.architecture", "design.ui", "design.database"]),
        ("JuniorDev", ["code-generation.python", "verification.unit-test"]),
        ("SecurityGuru", ["code-review.security", "code-review.quality"]),
        ("DevOpsBot", ["automation.cli", "communication.documentation",
                       "communication.report"]),
    ]
    for name, caps in agents:
        runtime.add_agent(name, "demo.01_single_agent:DemoAgent", [
            type('C', (), {'name': c, 'version': '1.0.0', 'description': c,
                           'input_schema': {}, 'output_schema': {}, 'tags': []})
            for c in caps
        ])

    # 3. 启动 — 编排循环开始
    runtime.start()
    print("🚀 Runtime 启动")
    print(f"   {len(runtime.list_agents())} Agents: {', '.join(a['name'] for a in runtime.list_agents())}")
    print(f"   Planner: {MODEL}")
    print(f"   Verifier: SchemaVerifier")
    print(f"   Policy: CostLimit + RateLimit")
    print(f"   Memory: 6-layer InMemory\n")

    # 4. 提交 Goal — 全自动
    goal = runtime.submit_goal(
        "构建一个完整的用户管理系统：设计数据库 → 实现 REST API → 写 React 前端 → 安全审查 → 单元测试 → 撰写部署文档",
        priority="high",
    )
    print(f"📝 Goal: {goal['goal_id'][:8]}... | {goal['task_count']} Tasks\n")
    print("⏳ 全自动执行中...\n")

    # 5. 阻塞等待完成
    t0 = time.time()
    result = runtime.wait_for_goal(goal['goal_id'], timeout_seconds=30)
    elapsed = time.time() - t0

    # 6. 结果
    p = result.get('progress', {})
    print(f"\n{'=' * 60}")
    print(f"📊 结果: {result['status']} ({elapsed:.1f}s)")
    print(f"   Tasks: {p.get('completed_tasks', 0)}/{p.get('total_tasks', 0)} completed, "
          f"{p.get('failed_tasks', 0)} failed")

    # 每个 Agent 的处理量
    print("\n📋 Task DAG + Agent 分配:")
    for t in runtime._task_graph.list_tasks():
        icon = {'completed': '✅', 'failed': '❌', 'ready': '⏳', 'started': '🔄'}.get(
            t.status.value, '⬜')
        deps = f" ← [{', '.join(t.dependencies)}]" if t.dependencies else ""
        agent = getattr(t, 'assigned_agent_id', '?') or '?'
        print(f"   {icon} {t.task_id} [{t.required_capability}]{deps} — {t.description[:45]}")

    # 系统指标
    print(f"\n📈 系统指标:")
    health = runtime.get_health()
    metrics = runtime.get_metrics()
    print(f"   Runtime: {health['status']}")
    print(f"   Agents connected: {health['components']['agents']['connected']}")
    print(f"   Events published: {metrics['events']['published_total']}")

    runtime.shutdown()
    print(f"\n✅ Demo 06 完成 — 完整端到端流水线 ({elapsed:.1f}s)")


if __name__ == "__main__":
    main()
