#!/usr/bin/env python3
"""
Demo 02: 多 Agent 协作（编码 + 审查 + 测试 + 文档）

4 个不同能力的 Agent → Planner 分解 Goal → Scheduler 按能力分派 → 全自动完成。

用法:
    export OPENAI_API_KEY="sk-xxx"
    export OPENAI_API_BASE="https://api.deepseek.com/v1"
    export OPENAI_MODEL="deepseek-v4-flash"
    python3 demo/02_multi_agent.py
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
    print("  Demo 02: 多 Agent 协作（自动分派 + 自动编排）")
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

    # 4 个不同能力的 Agent
    agents = [
        ("SeniorDev", ["code-generation.python", "code-generation.typescript",
                       "design.architecture", "design.database"]),
        ("JuniorDev", ["code-generation.python", "verification.unit-test", "verification.integration-test"]),
        ("SecurityGuru", ["code-review.security", "code-review.quality", "analysis.performance"]),
        ("DevOpsBot", ["automation.cli", "automation.file-system",
                       "communication.documentation", "communication.report"]),
    ]
    for name, _ in agents:
        runtime.add_agent(name, "demo.01_single_agent:DemoAgent", [
            type('C', (), {'name': c, 'version': '1.0.0', 'description': c,
                           'input_schema': {}, 'output_schema': {}, 'tags': []})
            for c in ALL_CAPS
        ])

    runtime.start()
    print(f"🚀 {len(agents)} Agents 上线:")
    for a in runtime.list_agents():
        print(f"   · {a['name']} ({a['status']})")
    print()

    goal = runtime.submit_goal(
        "写一个用户注册登录的前端页面（React），包含表单验证和单元测试，并进行安全审查",
        priority="high",
    )
    print(f"📝 Goal | {goal['task_count']} Tasks | Planner 已分解\n")

    t0 = time.time()
    result = runtime.wait_for_goal(goal['goal_id'], timeout_seconds=30)

    print(f"📊 结果: {result['status']} ({time.time()-t0:.1f}s)")
    p = result.get('progress', {})
    print(f"   {p.get('completed_tasks',0)}/{p.get('total_tasks',0)} completed")

    # 各 Agent 贡献
    print("\n📋 各 Agent 处理的任务:")
    for a in runtime.list_agents():
        aid = runtime.get_agent(a['name'])
        agent_tasks = sum(1 for t in runtime._task_graph.list_tasks()
                          if getattr(t, 'assigned_agent_id', None) == aid.get('agent_id'))
        if agent_tasks > 0:
            print(f"   {a['name']}: {agent_tasks} tasks")

    runtime.shutdown()
    print("\n✅ Demo 02 完成")


if __name__ == "__main__":
    main()
