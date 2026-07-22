#!/usr/bin/env python3
"""
Demo 04: 自定义评分策略 + 自动编排

两个 Agent 提供相同能力但成本不同：CheapAgent（$0.02/次）vs FastAgent（$0.15/次）。
演示 CostFirst 策略下的实际调度选择。

用法:
    export OPENAI_API_KEY="sk-xxx"
    python3 demo/04_custom_scoring.py
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.runtime import ZelosRuntime
from zelos.scheduler import ScoringStrategy, ScoredCandidate, AgentCandidate

API_KEY = os.getenv("OPENAI_API_KEY", "")
API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

if not API_KEY:
    print("❌ 请设置 OPENAI_API_KEY"); sys.exit(1)


ALL_CAPS = ["code-generation.python", "code-generation.typescript",
            "verification.unit-test", "design.architecture",
            "communication.documentation", "code-review.quality"]

class CostFirstStrategy(ScoringStrategy):
    """成本优先：便宜的就是最好的"""
    def score(self, task, candidates):
        results = []
        for c in candidates:
            score = 1.0 - min(c.cost_per_call / 0.20, 1.0)
            results.append(ScoredCandidate(c, score=score, reason=f"cost=${c.cost_per_call:.4f}"))
        return sorted(results, key=lambda r: r.score, reverse=True)


def main():
    print("=" * 60)
    print("  Demo 04: 自定义评分策略 + 自动编排")
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

    # 两个 Agent，相同能力，不同成本
    caps = [type('C', (), {'name': c, 'version': '1.0.0',
            'description': '', 'input_schema': {}, 'output_schema': {}, 'tags': ['cheap', 'python']})
            for c in ALL_CAPS]
    faster_caps = [type('C', (), {'name': c, 'version': '1.0.0',
            'description': '', 'input_schema': {}, 'output_schema': {}, 'tags': ['fast', 'python']})
            for c in ALL_CAPS]
    runtime.add_agent("CheapAgent", "demo.01_single_agent:DemoAgent", caps)
    runtime.add_agent("FastAgent", "demo.01_single_agent:DemoAgent", faster_caps)

    # 对比两种策略
    cheap = AgentCandidate("a1", "CheapAgent", "code-generation.python", "1.0", 0.85, 0.02, 8000, 0.99, 0.0, ["cheap"], 100)
    fast = AgentCandidate("a2", "FastAgent", "code-generation.python", "1.0", 0.95, 0.15, 2000, 0.99, 0.0, ["fast"], 100)

    cost_result = CostFirstStrategy().score(None, [cheap, fast])
    default_result = runtime._scoring_strategy.score(None, [cheap, fast]) if runtime._scoring_strategy else []

    print("两个 Agent 提供相同能力 (code-generation.python):")
    print(f"  CheapAgent: success={cheap.success_rate} cost=${cheap.cost_per_call} latency={cheap.avg_latency_ms}ms")
    print(f"  FastAgent:  success={fast.success_rate} cost=${fast.cost_per_call} latency={fast.avg_latency_ms}ms\n")

    print(f"  成本优先策略 → 选中: {cost_result[0].candidate.agent_name} (score={cost_result[0].score:.3f})")
    if default_result:
        print(f"  默认策略     → 选中: {default_result[0].candidate.agent_name} (score={default_result[0].score:.3f})")
    print(f"  💡 同一个能力，不同策略选出不同的 Agent。\n")

    # 实际运行 — 应用 CostFirst
    runtime._scoring_strategy = CostFirstStrategy()
    if runtime._scheduler:
        runtime._scheduler.set_scoring_strategy(CostFirstStrategy())

    runtime.start()

    goal = runtime.submit_goal("Write a Python function that sorts a list", priority="medium")
    result = runtime.wait_for_goal(goal['goal_id'], timeout_seconds=10)
    p = result.get('progress', {})

    print(f"⚡ 实际运行结果:")
    print(f"   Goal: {result['status']} | {p.get('completed_tasks',0)}/{p.get('total_tasks',0)} tasks")

    # 哪个 Agent 被调度了？
    for t in runtime._task_graph.list_tasks():
        if t.assigned_agent_id:
            for a in runtime.list_agents():
                aid = runtime.get_agent(a['name'])
                if aid and aid.get('agent_id') == t.assigned_agent_id:
                    print(f"   → Task '{t.description[:40]}' dispatched to: {a['name']}")

    runtime.shutdown()
    print("\n✅ Demo 04 完成")


if __name__ == "__main__":
    main()
