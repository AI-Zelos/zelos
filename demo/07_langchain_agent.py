#!/usr/bin/env python3
"""
Demo 07: LangChain Agent 接入 Zelos

展示如何将 LangChain Agent 包装为 Zelos Agent，注册到 Runtime 统一编排。

核心模式:
  LangChain Agent 内部管理 Prompt + Tool + Memory
  → 对外暴露 Zelos 5 方法接口（register/execute/submitResult）
  → Zelos 看到的是一个 Capability Provider，不关心内部是 LangChain

用法:
    pip install langchain langchain-openai
    export OPENAI_API_KEY="sk-xxx"
    python3 demo/07_langchain_agent.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API_KEY = os.getenv("OPENAI_API_KEY", "")
API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

if not API_KEY:
    print("❌ 请设置 OPENAI_API_KEY")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════
# 模式：将 LangChain Agent 包装为 Zelos Agent
# ═══════════════════════════════════════════════════════════


class LangChainZelosAgent:
    """
    通用包装器：任何 LangChain Agent → Zelos Agent。

    Zelos 看到的是一个普通的 Agent，提供 Capability X。
    LangChain 在里面管理 Prompt、Tool 调用、Memory。

    包装要点:
      1. Zelos.execute(task) → 提取 task.description → 发给 LangChain
      2. LangChain 内部使用自己的 Tool（搜索、计算、API 等）
      3. LangChain 返回结果 → 包装为 Zelos Artifact
      4. Zelos 不关心 LangChain 内部如何工作
    """

    def __init__(self, name="LangChainAgent", **kw):
        self.name = name
        self._api_key = kw.get("api_key", API_KEY)
        self._model = kw.get("model", MODEL)
        self._langchain_agent = None  # 实际的 LangChain Agent 实例

    def _init_langchain(self):
        """初始化 LangChain Agent（懒加载）"""
        try:
            from langchain.agents import AgentExecutor, create_openai_functions_agent
            from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
            from langchain.tools import tool
            from langchain_openai import ChatOpenAI

            # 定义 LangChain Tools（Agent 内部使用）
            @tool
            def python_repl(code: str) -> str:
                """Execute Python code and return the result."""
                try:
                    exec_globals = {}
                    exec(code, exec_globals)
                    return str(exec_globals.get("result", "Code executed successfully"))
                except Exception as e:
                    return f"Error: {e}"

            @tool
            def search_knowledge(query: str) -> str:
                """Search internal knowledge base for information."""
                knowledge = {
                    "zelos": "Zelos is an open multi-agent orchestration runtime.",
                    "api": "The Zelos API has 5 endpoints: register, heartbeat, execute, submitResult, shutdown.",
                }
                for k, v in knowledge.items():
                    if k in query.lower():
                        return v
                return f"No information found for: {query}"

            # LangChain LLM
            llm = ChatOpenAI(model=self._model, api_key=self._api_key, temperature=0.3)

            # LangChain Prompt
            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", "You are a coding assistant. Use tools when needed."),
                    ("user", "{input}"),
                    MessagesPlaceholder(variable_name="agent_scratchpad"),
                ]
            )

            # LangChain Agent
            agent = create_openai_functions_agent(llm, [python_repl, search_knowledge], prompt)
            self._langchain_agent = AgentExecutor(agent=agent, tools=[python_repl, search_knowledge], verbose=False)
        except ImportError:
            pass  # LangChain not installed → use mock

    def execute(self, task):
        """
        Zelos 调用此方法。内部使用 LangChain 完成。
        """
        desc = task.description if hasattr(task, "description") else str(task)

        if self._langchain_agent is None:
            self._init_langchain()

        if self._langchain_agent:
            # 真实 LangChain 调用
            result = self._langchain_agent.invoke({"input": desc})
            output = result.get("output", str(result))
        else:
            # Mock（LangChain 未安装时）
            output = f"[LangChain Agent] Completed: {desc[:50]}"

        return type(
            "Artifact",
            (),
            {
                "content_type": "application/json",
                "content": {"result": output, "agent": "LangChain", "model": self._model},
            },
        )()


# ═══════════════════════════════════════════════════════════
# Demo
# ═══════════════════════════════════════════════════════════


def main():
    from zelos.runtime import ZelosRuntime

    print("=" * 60)
    print("  Demo 07: LangChain Agent → Zelos Runtime")
    print("=" * 60)

    ALL_CAPS = [
        "code-generation.python",
        "code-generation.typescript",
        "code-review.quality",
        "verification.unit-test",
        "design.architecture",
        "communication.documentation",
    ]

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

    # 注册 LangChain Agent —— 和普通 Agent 完全一样的接口
    runtime.add_agent(
        "LangChainBot",
        "demo.07_langchain_agent:LangChainZelosAgent",
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
                    "tags": ["langchain"],
                },
            )
            for c in ALL_CAPS
        ],
    )

    runtime.start()
    print("🚀 LangChain Agent 已注册并在线\n")

    goal = runtime.submit_goal("Write a Python hello world and explain how Zelos works", priority="high")
    result = runtime.wait_for_goal(goal["goal_id"], timeout_seconds=15)

    print(
        f"📊 Result: {result['status']} | Tasks: {result['progress']['completed_tasks']}/{result['progress']['total_tasks']}"
    )
    for t in runtime._task_graph.list_tasks():
        icon = {"completed": "✅", "failed": "❌"}.get(t.status.value, "⬜")
        print(f"   {icon} [{t.required_capability}] {t.description[:55]}")

    runtime.shutdown()
    print("\n💡 关键模式:")
    print("   LangChain Agent = 普通的 Zelos Agent（5 方法接口）")
    print("   Zelos 不知道内部是 LangChain —— 它只看 Capability")
    print("\n✅ Demo 07 完成")


if __name__ == "__main__":
    main()
