#!/usr/bin/env python3
"""
Demo 10: 混合框架编排 — LangChain + CrewAI + AutoGen + 原生 Agent

Zelos 的核心价值：不同框架的 Agent 被统一编排。

场景:
  - LangChain Agent 负责 research（内部自己管 tools/prompt）
  - CrewAI Agent 负责 content creation（内部 3 角色协作）
  - AutoGen Agent 负责 code generation（内部对话式协作）
  - 原生 Python Agent 负责 verification（纯代码，无框架）

  Zelos Planner 分解 Goal → Scheduler 按 Capability 分派 → 各框架 Agent 各司其职。
  没有 Agent 知道其他 Agent 用什么框架。没有 Agent 知道 DAG 拓扑。

用法:
    export OPENAI_API_KEY="sk-xxx"
    python3 demo/10_mixed_frameworks.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API_KEY = os.getenv("OPENAI_API_KEY", "")
API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

if not API_KEY:
    print("❌ 请设置 OPENAI_API_KEY")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════
# 四个不同框架 / 模式的 Agent
# ═══════════════════════════════════════════════════════════


class MockFrameworkAgent:
    """
    模拟框架 Agent。实际使用时替换为真实的 LangChain/CrewAI/AutoGen 调用。
    框架名称写在 name 里，Zelos 不感知。
    """

    def __init__(self, name="Agent", **kw):
        self.name = name
        self._framework = kw.get("framework", "native")

    def execute(self, task):
        cap = task.required_capability if hasattr(task, "required_capability") else "?"
        desc = task.description if hasattr(task, "description") else str(task)[:50]

        # 模拟不同框架的执行方式
        if self._framework == "langchain":
            # LangChain: AgentExecutor.run(task)
            result = f"[LangChain] Used tools to: {desc}"
        elif self._framework == "crewai":
            # CrewAI: crew.kickoff(inputs={topic})
            result = f"[CrewAI] Researcher→Writer→Reviewer completed: {desc}"
        elif self._framework == "autogen":
            # AutoGen: user_proxy.initiate_chat(assistant, message=task)
            result = f"[AutoGen] Assistant↔User dialogue solved: {desc}"
        else:
            # Native: 直接调用 LLM 或纯代码
            result = f"[Native Python] Executed: {desc}"

        return type(
            "Artifact",
            (),
            {
                "content_type": "application/json",
                "content": {"result": result, "framework": self._framework, "capability": cap},
            },
        )()


def main():
    from zelos.runtime import ZelosRuntime

    print("=" * 70)
    print("  Demo 10: 混合框架编排")
    print("=" * 70)
    print()

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

    # ── 注册 4 个不同框架的 Agent ──
    print("📋 注册 Agent:")
    agents_config = [
        (
            "LangChain-Researcher",
            "demo.10_mixed_frameworks:MockFrameworkAgent",
            ["research.web-search", "analysis.performance"],
            {"framework": "langchain"},
            "🔗 内部: LangChain Agent + Tools",
        ),
        (
            "CrewAI-Writer",
            "demo.10_mixed_frameworks:MockFrameworkAgent",
            ["communication.documentation", "communication.report", "design.ui"],
            {"framework": "crewai"},
            "👥 内部: CrewAI 3 角色协作 (Researcher/Writer/Reviewer)",
        ),
        (
            "AutoGen-Coder",
            "demo.10_mixed_frameworks:MockFrameworkAgent",
            ["code-generation.python", "code-generation.typescript", "design.architecture"],
            {"framework": "autogen"},
            "💬 内部: AutoGen Assistant↔User 对话式编程",
        ),
        (
            "Native-Tester",
            "demo.10_mixed_frameworks:MockFrameworkAgent",
            ["verification.unit-test", "verification.integration-test", "code-review.security", "code-review.quality"],
            {"framework": "native"},
            "🐍 原生 Python，无框架依赖",
        ),
    ]

    for name, entry, caps_list, config, desc in agents_config:
        runtime.add_agent(
            name,
            entry,
            [
                type(
                    "C",
                    (),
                    {
                        "name": c,
                        "version": "1.0.0",
                        "description": c,
                        "input_schema": {},
                        "output_schema": {},
                        "tags": [config.get("framework", "native")],
                    },
                )
                for c in caps_list
            ],
            config=config,
        )
        print(f"   · {name}: {', '.join(caps_list)}")
        print(f"     {desc}")

    runtime.start()
    print(f"\n🚀 Runtime 启动 | {len(runtime.list_agents())} Agents 在线\n")

    # ── 提交一个需要跨框架协作的 Goal ──
    goal = runtime.submit_goal(
        "Research the Zelos architecture → Design a comparison doc with other frameworks → "
        "Build a Python demo script → Write unit tests → Do a security review",
        priority="high",
    )
    print(f"📝 Goal: {goal['task_count']} Tasks | Planner 已分解\n")
    print("⏳ 自动编排中...\n")

    t0 = time.time()
    result = runtime.wait_for_goal(goal["goal_id"], timeout_seconds=30)

    print(f"📊 结果: {result['status']} ({time.time() - t0:.1f}s)")
    p = result.get("progress", {})
    print(f"   {p.get('completed_tasks', 0)}/{p.get('total_tasks', 0)} completed\n")

    # ── 展示哪个框架处理了哪些 Task ──
    print("📋 Task → Agent → 内部框架:")
    for t in runtime._task_graph.list_tasks():
        icon = {"completed": "✅", "failed": "❌", "ready": "⏳"}.get(t.status.value, "⬜")
        aid = getattr(t, "assigned_agent_id", None)
        agent_name = "?"
        framework = "?"
        for a in runtime.list_agents():
            info = runtime.get_agent(a["name"])
            if info and info.get("agent_id") == aid:
                agent_name = a["name"]
                break

        # 从 agent 配置中取 framework
        for name, _, _, config, _ in agents_config:
            if name == agent_name:
                framework = config.get("framework", "?")
                break

        print(f"   {icon} [{framework:>10}] {agent_name:<22} → {t.description[:45]}")

    runtime.shutdown()
    print(f"\n{'=' * 70}")
    print("  关键架构洞察:")
    print("  1. Zelos 不知道任何 Agent 内部用什么框架")
    print("  2. Agent 之间不知道彼此用什么框架")
    print("  3. LangChain ↔ AutoGen ↔ CrewAI 通过 Zelos 间接协作")
    print("  4. Planner 分解 + Scheduler 分派 = 零硬编码协调")
    print(f"{'=' * 70}")
    print("\n✅ Demo 10 完成")


if __name__ == "__main__":
    main()
