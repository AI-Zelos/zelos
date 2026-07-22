#!/usr/bin/env python3
"""
Demo 09: AutoGen Agent 接入 Zelos

AutoGen 擅长多 Agent 对话式协作。Zelos 把整个 AutoGen GroupChat 看作一个 Agent。

模式:
  AutoGen 内部: UserProxy ↔ AssistantAgent（对话式协作）
  对外（Zelos）: 整个 GroupChat 就是一个 Agent，提供 "code-generation.python" 能力
  Zelos 调度 Task → AutoGen 内部对话解决 → 返回结果

用法:
    pip install pyautogen
    export OPENAI_API_KEY="sk-xxx"
    python3 demo/09_autogen_agent.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API_KEY = os.getenv("OPENAI_API_KEY", "")
API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

if not API_KEY:
    print("❌ 请设置 OPENAI_API_KEY"); sys.exit(1)


class AutoGenZelosAgent:
    """
    将 AutoGen 的 GroupChat 包装为一个 Zelos Agent。

    关键设计:
      - Zelos.execute(task) → 启动 AutoGen 内部对话
      - AutoGen 的多个 Agent 在内部对话协作（Zelos 看不见）
      - 对话完成后提取最终结果 → 返回 Zelos Artifact
    """

    def __init__(self, name="AutoGenAgent", **kw):
        self.name = name
        self._model = kw.get("model", MODEL)
        self._api_key = kw.get("api_key", API_KEY)
        self._base_url = kw.get("base_url", API_BASE)

    def execute(self, task):
        desc = task.description if hasattr(task, 'description') else str(task)
        cap = task.required_capability if hasattr(task, 'required_capability') else 'code'

        try:
            import autogen

            config_list = [{
                "model": self._model,
                "api_key": self._api_key,
                "base_url": self._base_url,
            }]

            # AutoGen 的两个角色
            assistant = autogen.AssistantAgent(
                name="Assistant",
                system_message=f"You are a helpful coding assistant. Capability: {cap}",
                llm_config={"config_list": config_list},
            )
            user_proxy = autogen.UserProxyAgent(
                name="User",
                human_input_mode="NEVER",
                max_consecutive_auto_reply=3,
                code_execution_config={"work_dir": "/tmp/autogen"},
            )

            # 启动 AutoGen 内部对话
            user_proxy.initiate_chat(
                assistant,
                message=f"Task: {desc}\nComplete this task and return the result.",
            )

            # 提取最终结果
            output = assistant.last_message() if hasattr(assistant, 'last_message') else "Task completed"
            if isinstance(output, dict):
                output = output.get("content", str(output))

        except ImportError:
            output = f"[AutoGen Mock] Task completed: {desc[:50]}"

        return type('Artifact', (), {
            'content_type': 'application/json',
            'content': {'result': output, 'agent': 'AutoGen', 'capability': cap}
        })()


def main():
    from zelos.runtime import ZelosRuntime

    print("=" * 60)
    print("  Demo 09: AutoGen → Zelos Runtime")
    print("=" * 60)
    print("  AutoGen 内部有多 Agent 对话协作")
    print("  Zelos 只看到 1 个 Agent\n")

    ALL_CAPS = ["code-generation.python", "code-review.quality", "verification.unit-test",
                "design.architecture", "communication.documentation"]

    runtime = ZelosRuntime({
        "plugins": [{
            "id": "llm-planner", "type": "planner",
            "entrypoint": "zelos.planner.LLMPlanner",
            "config": {"provider": "openai", "model": MODEL,
                       "api_key": API_KEY, "base_url": API_BASE,
                       "temperature": 0.3, "max_tokens": 4000},
        }]
    })

    runtime.add_agent("AutoGenBot", "demo.09_autogen_agent:AutoGenZelosAgent", [
        type('C', (), {'name': c, 'version': '1.0.0', 'description': c,
                       'input_schema': {}, 'output_schema': {}, 'tags': ['autogen']})
        for c in ALL_CAPS
    ])

    runtime.start()
    goal = runtime.submit_goal("Write a Python function that calculates fibonacci numbers")
    result = runtime.wait_for_goal(goal['goal_id'], timeout_seconds=15)

    print(f"📊 {result['status']} | {result['progress']['completed_tasks']}/{result['progress']['total_tasks']}")
    for t in runtime._task_graph.list_tasks():
        print(f"   {'✅' if t.status.value=='completed' else '⬜'} {t.description[:50]} [{t.required_capability}]")

    runtime.shutdown()
    print(f"\n💡 AutoGen 内部对话对 Zelos 完全透明")
    print(f"✅ Demo 09 完成")


if __name__ == "__main__":
    main()
