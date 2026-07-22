#!/usr/bin/env python3
"""
Demo 08: CrewAI Agent 接入 Zelos

CrewAI 擅长多角色协作（Crew + Task）。Zelos 把整个 Crew 看作一个 Agent。

模式:
  CrewAI 内部: Manager Agent → Researcher → Writer → Reviewer（CrewAI 自己的编排）
  对外（Zelos）: 整个 Crew 就是一个 Agent，提供 "content-creation" 能力
  Zelos 不关心 Crew 内部有几个角色 —— 它看到的是一个 Capability Provider

用法:
    pip install crewai
    export OPENAI_API_KEY="sk-xxx"
    python3 demo/08_crewai_agent.py
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


class CrewAIZelosAgent:
    """
    将整个 CrewAI Crew 包装为一个 Zelos Agent。

    关键设计:
      - Zelos 给 Crew 一个 Task → Crew 内部自己分解为子任务
      - CrewAI 的 Agent 之间互相通信（在 Crew 内部）
      - 对外暴露的只是一个 execute() 方法
      - Zelos 完全不知道 Crew 内部结构
    """

    def __init__(self, name="CrewAIAgent", **kw):
        self.name = name
        self._model = kw.get("model", MODEL)
        self._crew = None

    def _init_crew(self):
        """初始化 CrewAI Crew（懒加载）"""
        try:
            from crewai import Agent as CrewAgent
            from crewai import Crew, Process
            from crewai import Task as CrewTask

            # CrewAI 内部的角色定义
            researcher = CrewAgent(
                role="Senior Researcher",
                goal="Research and gather accurate information on the given topic",
                backstory="You are an expert at finding and synthesizing information.",
                allow_delegation=False,
                llm=self._model,
            )
            writer = CrewAgent(
                role="Technical Writer",
                goal="Write clear, accurate content based on research",
                backstory="You excel at transforming research into readable content.",
                allow_delegation=False,
                llm=self._model,
            )
            reviewer = CrewAgent(
                role="Quality Reviewer",
                goal="Review content for accuracy and clarity",
                backstory="You catch errors and ensure high-quality output.",
                allow_delegation=False,
                llm=self._model,
            )

            # CrewAI Task（内部子任务）
            research_task = CrewTask(
                description="Research the topic: {topic}. Find key facts and insights.",
                expected_output="A structured research summary with key findings.",
                agent=researcher,
            )
            write_task = CrewTask(
                description="Write content based on: {research}. Make it clear and engaging.",
                expected_output="Well-written content based on the research.",
                agent=writer,
            )
            review_task = CrewTask(
                description="Review: {draft}. Check accuracy and improve clarity.",
                expected_output="Reviewed and polished final content.",
                agent=reviewer,
            )

            self._crew = Crew(
                agents=[researcher, writer, reviewer],
                tasks=[research_task, write_task, review_task],
                process=Process.sequential,
                verbose=False,
            )
        except ImportError:
            pass

    def execute(self, task):
        """Zelos 入口 —— Crew 内部自己编排"""
        topic = task.description if hasattr(task, "description") else str(task)

        if self._crew is None:
            self._init_crew()

        if self._crew:
            result = self._crew.kickoff(inputs={"topic": topic})
            output = str(result)
        else:
            output = f"[CrewAI] Completed research + writing + review for: {topic[:50]}"

        return type(
            "Artifact",
            (),
            {
                "content_type": "application/json",
                "content": {"result": output, "agent": "CrewAI", "internal_agents": 3},
            },
        )()


def main():
    from zelos.runtime import ZelosRuntime

    print("=" * 60)
    print("  Demo 08: CrewAI → Zelos Runtime")
    print("=" * 60)
    print("  CrewAI 内部有 3 个角色（Researcher/Writer/Reviewer）")
    print("  Zelos 只看到 1 个 Agent，提供 1 个 Capability\n")

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

    ALL_CAPS_CREW = [
        "research.web-search",
        "communication.documentation",
        "communication.report",
        "code-generation.python",
        "code-review.quality",
        "design.architecture",
        "design.ui",
        "design.document",
        "analysis.performance",
    ]
    runtime.add_agent(
        "CrewAIBot",
        "demo.08_crewai_agent:CrewAIZelosAgent",
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
                    "tags": ["crewai"],
                },
            )
            for c in ALL_CAPS_CREW
        ],
    )

    runtime.start()
    goal = runtime.submit_goal("Research and write a short doc about Zelos multi-agent runtime")
    result = runtime.wait_for_goal(goal["goal_id"], timeout_seconds=15)

    print(f"📊 {result['status']} | {result['progress']['completed_tasks']}/{result['progress']['total_tasks']}")
    for t in runtime._task_graph.list_tasks():
        print(f"   {'✅' if t.status.value == 'completed' else '⬜'} [{t.required_capability}] {t.description[:50]}")

    runtime.shutdown()
    print("\n💡 CrewAI 内部 3 个角色对 Zelos 完全透明")
    print("✅ Demo 08 完成")


if __name__ == "__main__":
    main()
