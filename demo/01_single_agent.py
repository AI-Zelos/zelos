#!/usr/bin/env python3
"""
Demo 01: 单 Agent + LLM Planner + 自动编排 + 阶梯式容错

三层阶梯式处理 READY Task 无 Agent 的情况：
  Tier 1 (< 60s stuck): 等待（给热加入 Agent 时间窗口）
  Tier 2 (> 60s stuck): 标记 FAILED — Goal 能到达终端状态
  Tier 3 (on failure):   触发 Planner.replan() — LLM 找替代方案

用法:
    export OPENAI_API_KEY="sk-xxx"
    export OPENAI_API_BASE="https://api.deepseek.com/v1"
    export OPENAI_MODEL="deepseek-v4-flash"
    python3 demo/01_single_agent.py
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
            "design.architecture", "design.ui", "automation.browser",
            "automation.cli", "automation.file-system",
            "communication.documentation", "communication.report",
            "research.web-search", "analysis.performance"]


def main():
    print("=" * 60)
    print("  Demo 01: 单 Agent + 自动编排 + 阶梯式容错")
    print("=" * 60)
    print(f"  LLM: {MODEL}")
    print(f"  Tier 1: {0}-60s 等待热加入 | Tier 2: >60s → FAIL | Tier 3: Replan\n")

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

    # 注册 Agent（覆盖 Planner 可能用到的全部能力）
    runtime.add_agent("DemoCoder", "demo.01_single_agent:DemoAgent", [
        type('C', (), {'name': c, 'version': '1.0.0', 'description': c,
                        'input_schema': {}, 'output_schema': {}, 'tags': []})
        for c in ALL_CAPS
    ])

    runtime.start()
    print("🚀 Runtime 启动（后台自动编排运行中）\n")

    goal = runtime.submit_goal(
        "写一个 Python REST API 服务，包含用户认证、数据库查询、单元测试和 README 文档",
        priority="high",
    )
    print(f"📝 Goal: {goal['goal_id'][:8]}... | {goal['task_count']} Tasks | Planner 已分解\n")
    print("⏳ 自动编排中（Planner → Scheduler → Agent → Verifier）...\n")

    result = runtime.wait_for_goal(goal['goal_id'], timeout_seconds=30)
    p = result.get('progress', {})

    print(f"\n📊 结果: {result['status']}")
    print(f"   Tasks: {p.get('completed_tasks', 0)}/{p.get('total_tasks', 0)} completed, "
          f"{p.get('failed_tasks', 0)} failed")

    print("\n📋 Task 执行明细:")
    for t in runtime._task_graph.list_tasks():
        icon = {'completed': '✅', 'failed': '❌', 'ready': '⏳', 'created': '⬜'}.get(
            t.status.value, '❓')
        deps = f" ← [{', '.join(t.dependencies)}]" if t.dependencies else ""
        print(f"   {icon} {t.task_id}: {t.description[:55]} [{t.required_capability}]{deps}")

    runtime.shutdown()
    print("\n✅ Demo 01 完成")


if __name__ == "__main__":
    main()
