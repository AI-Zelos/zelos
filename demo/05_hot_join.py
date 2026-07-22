#!/usr/bin/env python3
"""
Demo 05: Agent 热加入 + 三层阶梯式容错

1. 启动时只注册 Coder（只能写代码）
2. 提交需要多种能力的 Goal
3. Task 需要 review → 无 Agent → Tier 1 等待
4. 热加入 SecurityReviewer → Task 被调度 ✅
5. 热退出 Coder → 展示 Agent 动态管理

用法:
    export OPENAI_API_KEY="sk-xxx"
    python3 demo/05_hot_join.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.runtime import ZelosRuntime

API_KEY = os.getenv("OPENAI_API_KEY", "")
API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

if not API_KEY:
    print("❌ 请设置 OPENAI_API_KEY")
    sys.exit(1)


def main():
    print("=" * 60)
    print("  Demo 05: Agent 热加入 + 阶梯式容错")
    print("=" * 60)

    runtime = ZelosRuntime(
        {
            "plugins": [
                {
                    "id": "llm-planner",
                    "type": "planner",
                    "entrypoint": "zelos.planner.LLMPlanner",
                    "config": {
                        "provider": "openai",
                        "model": MODEL,
                        "api_key": API_KEY,
                        "base_url": API_BASE,
                        "temperature": 0.3,
                        "max_tokens": 4000,
                    },
                }
            ]
        }
    )

    # 初始：只有 Coder（只有基础能力，故意缺少 code-review）
    CODER_CAPS = [
        "code-generation.python",
        "code-generation.typescript",
        "design.architecture",
        "design.ui",
        "communication.documentation",
        "verification.unit-test",
    ]
    runtime.add_agent(
        "Coder",
        "demo.01_single_agent:DemoAgent",
        [
            type(
                "C",
                (),
                {"name": c, "version": "1.0.0", "description": "", "input_schema": {}, "output_schema": {}, "tags": []},
            )
            for c in CODER_CAPS
        ],
    )

    runtime.start()
    print(f"🚀 启动 | {len(runtime.list_agents())} Agent: Coder (code-generation + design only)")
    print("   💡 故意缺少: code-review, verification — 等热加入\n")

    # 提交需要 review + test 的 Goal
    goal = runtime.submit_goal(
        "Write a Python login function AND do a security review",
        priority="high",
    )
    print(f"📝 Goal | {goal['task_count']} Tasks | 包含 code-review.security\n")

    # Coding task should complete immediately
    time.sleep(3)
    tasks = runtime._task_graph.list_tasks()
    completed_now = sum(1 for t in tasks if t.status.value == "completed")
    ready_now = sum(1 for t in tasks if t.status.value == "ready")
    print(f"💡 3 秒后: {completed_now} completed, {ready_now} READY (stuck — no review agent)\n")

    # 热加入 Reviewer
    print("🔥 热加入 SecurityReviewer...")
    runtime.add_agent(
        "SecurityReviewer",
        "demo.01_single_agent:DemoAgent",
        [
            type(
                "C",
                (),
                {
                    "name": "code-review.security",
                    "version": "1.0.0",
                    "description": "",
                    "input_schema": {},
                    "output_schema": {},
                    "tags": [],
                },
            ),
            type(
                "C",
                (),
                {
                    "name": "verification.unit-test",
                    "version": "1.0.0",
                    "description": "",
                    "input_schema": {},
                    "output_schema": {},
                    "tags": [],
                },
            ),
        ],
    )
    print(f"   ✅ {len(runtime.list_agents())} Agents 在线\n")

    # 等待完成
    result = runtime.wait_for_goal(goal["goal_id"], timeout_seconds=20)
    p = result.get("progress", {})

    print(f"📊 结果: {result['status']} | {p.get('completed_tasks', 0)}/{p.get('total_tasks', 0)} completed\n")

    for t in runtime._task_graph.list_tasks():
        icon = {"completed": "✅", "failed": "❌", "ready": "⏳"}.get(t.status.value, "⬜")
        agent = ""
        for a in runtime.list_agents():
            aid = runtime.get_agent(a["name"])
            if aid and aid.get("agent_id") == getattr(t, "assigned_agent_id", None):
                agent = f" → {a['name']}"
        print(f"   {icon} {t.description[:50]} [{t.required_capability}]{agent}")

    # 热退出
    print("\n👋 热退出 Coder...")
    runtime.remove_agent("Coder")
    print(f"   Agent 数量: {len(runtime.list_agents())}")

    runtime.shutdown()
    print("\n✅ Demo 05 完成 — 热加入无需重启 Runtime")


if __name__ == "__main__":
    main()
