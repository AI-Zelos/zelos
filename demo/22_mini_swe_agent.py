#!/usr/bin/env python3
"""
Demo 22: mini-SWE-agent 接入 Zelos Runtime

将 mini-SWE-agent（MIT 开源、SWE-bench 74%+）作为 Zelos 的 coding Capability Provider。

mini-swe-agent v2 使用简单的 bash-based 执行循环：
  - LLM 生成 bash 命令 → subprocess 执行 → 观察输出 → 循环
  - 核心代码仅 ~100 行 Python
  - 通过 litellm 支持所有主流模型

用法:
    # 使用 DeepSeek（默认）
    export OPENAI_API_KEY="sk-xxx"
    export OPENAI_API_BASE="https://api.deepseek.com/v1"
    python3 demo/22_mini_swe_agent.py

    # 使用 Anthropic Claude
    export ANTHROPIC_API_KEY="sk-ant-xxx"
    python3 demo/22_mini_swe_agent.py --model "anthropic/claude-sonnet-4-6"

    # 指定工作目录
    python3 demo/22_mini_swe_agent.py --work-dir /path/to/your/project
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.agents.mini_swe_agent import MiniSWEAgent
from zelos.runtime import ZelosRuntime
from zelos.task_graph import Task


def parse_args():
    p = argparse.ArgumentParser(description="Demo 22: mini-SWE-agent on Zelos")
    p.add_argument(
        "--model", default=None,
        help="LLM model with provider prefix, e.g. 'anthropic/claude-sonnet-4-6'",
    )
    p.add_argument("--work-dir", default=None, help="Working directory for code changes")
    p.add_argument("--step-limit", type=int, default=30, help="Max agent steps")
    p.add_argument("--cost-limit", type=float, default=5.0, help="Max API cost in USD")
    p.add_argument("--goal", default=None, help="Custom goal description")
    p.add_argument("--dry-run", action="store_true", help="Validate without calling LLM")
    return p.parse_args()


def main():
    args = parse_args()

    # ── Model resolution ──
    if args.model:
        model_name = args.model
    elif os.getenv("ANTHROPIC_API_KEY"):
        model_name = "anthropic/claude-sonnet-4-6"
    else:
        model_name = os.getenv("ZELOS_MODEL", "deepseek/deepseek-chat")

    # Support ANTHROPIC_AUTH_TOKEN (DeepSeek Anthropic-compatible endpoint)
    api_key = os.getenv("ANTHROPIC_API_KEY", os.getenv("OPENAI_API_KEY", os.getenv("ANTHROPIC_AUTH_TOKEN", "")))
    if not api_key and not args.dry_run:
        print("❌ 请设置 ANTHROPIC_API_KEY / OPENAI_API_KEY / ANTHROPIC_AUTH_TOKEN")
        sys.exit(1)

    print("=" * 65)
    print("  Demo 22: mini-SWE-agent 接入 Zelos Runtime")
    print("=" * 65)
    print(f"  Model:      {model_name}")
    print(f"  Step Limit: {args.step_limit}")
    print(f"  Cost Limit: ${args.cost_limit}")
    print(f"  Work Dir:   {args.work_dir or os.getcwd()}")
    print()

    # ── Phase 1: Direct unit test ──
    if not args.dry_run:
        print("── Phase 1: 直接单元测试（MiniSWEAgent.execute）──")
        _test_direct_execute(model_name, args)
        print()

    # ── Phase 2: Full Zelos Runtime integration ──
    if not args.dry_run:
        print("── Phase 2: Zelos Runtime 集成测试 ──")
        _test_zelos_integration(model_name, args)


def _test_direct_execute(model_name: str, args):
    """Test MiniSWEAgent.execute() directly without the full Runtime."""
    agent_config = {
        "model_name": model_name,
        "step_limit": args.step_limit,
        "cost_limit": args.cost_limit,
    }
    if args.work_dir:
        agent_config["work_dir"] = args.work_dir

    agent = MiniSWEAgent(name="MiniSWE-Test", **agent_config)

    # Create a mock Task
    test_task = Task(
        task_id="test-001",
        plan_id="plan-test",
        description=args.goal or "Write a Python function fibonacci(n) that returns "
        "the nth Fibonacci number. Write it to a file called fib.py, "
        "test it, and submit.",
        required_capability="code-generation.python",
    )

    print(f"  📝 Task: {test_task.description[:80]}...")
    print(f"  ⏳ Running mini-swe-agent (max {args.step_limit} steps)...")
    t0 = time.time()

    try:
        result = agent.execute(test_task)
        elapsed = time.time() - t0

        status = result.get("status", "unknown")
        if status == "completed":
            artifact = result.get("artifact", {}).get("content", {})
            print(f"  ✅ Completed in {elapsed:.1f}s")
            print(f"     Exit: {artifact.get('exit_status', '?')}")
            print(f"     Cost: ${artifact.get('cost', 0):.4f}")
            print(f"     API Calls: {artifact.get('api_calls', 0)}")
            patch = artifact.get("patch", "")
            if patch:
                lines = patch.split("\n")[:10]
                print(f"     Patch preview ({len(patch)} chars):")
                for line in lines:
                    print(f"     │ {line[:70]}")
        else:
            error = result.get("error", {})
            print(f"  ❌ Failed ({elapsed:.1f}s): {error.get('code', '?')}")
            print(f"     {error.get('message', '')}")
    except Exception as e:
        elapsed = time.time() - t0
        print(f"  💥 Exception ({elapsed:.1f}s): {e}")


def _test_zelos_integration(model_name: str, args):
    """Test MiniSWEAgent registered as a Zelos Runtime agent."""
    # Use mock planner to avoid extra LLM costs for planning
    runtime = ZelosRuntime({
        "plugins": [
            {
                "id": "mock-planner",
                "type": "planner",
                "entrypoint": "zelos.planner.LLMPlanner",
                "config": {"provider": "mock"},
            }
        ]
    })

    # Register MiniSWEAgent with Zelos
    MINI_SWE_CAPS = [
        "code-fix.python",
        "code-generation.python",
        "code-refactor.python",
    ]

    agent_config = {
        "model_name": model_name,
        "step_limit": args.step_limit,
        "cost_limit": args.cost_limit,
    }
    if args.work_dir:
        agent_config["work_dir"] = args.work_dir

    runtime.add_agent(
        name="MiniSWE",
        entrypoint="zelos.agents.mini_swe_agent:MiniSWEAgent",
        capabilities=[
            {
                "name": cap,
                "version": "1.0.0",
                "description": f"mini-SWE-agent provides {cap}",
                "input_schema": {},
                "output_schema": {},
                "tags": ["coding", "python", "mini-swe-agent"],
            }
            for cap in MINI_SWE_CAPS
        ],
        config=agent_config,
    )

    runtime.start()
    print("  🚀 Runtime started with MiniSWE agent")

    # Show registered capabilities
    agents = runtime.list_agents()
    print(f"  📋 Registered agents: {len(agents)}")
    for a in agents:
        print(f"     · {a['name']} ({a['status']})")

    # Verify capabilities are registered
    caps = runtime._capability_registry.list_all()
    mini_caps = [c for c in caps if "mini-swe-agent" in c.tags]
    print(f"  🔧 MiniSWE capabilities: {len(mini_caps)}")
    for c in mini_caps:
        print(f"     · {c.name} v{c.version} [{c.status}]")

    # Submit a goal
    goal_desc = args.goal or (
        "Create a Python file called utils.py with a function 'chunk_list(lst, n)' "
        "that splits a list into chunks of size n. Include a docstring and type hints."
    )
    goal = runtime.submit_goal(goal_desc, priority="high")

    print(f"\n  📝 Goal: {goal['goal_id'][:8]}... | {goal['task_count']} Tasks")
    for t in runtime._task_graph.list_tasks():
        print(f"     · [{t.status.value}] {t.task_id}: {t.required_capability} — {t.description[:50]}")

    print("  ⏳ Waiting for execution...")
    result = runtime.wait_for_goal(goal["goal_id"], timeout_seconds=60)

    p = result.get("progress", {})
    print(f"\n  📊 Result: {result['status']}")
    print(f"     Tasks: {p.get('completed_tasks', 0)}/{p.get('total_tasks', 0)} completed, "
          f"{p.get('failed_tasks', 0)} failed")

    # Task details
    print("\n  📋 Task execution details:")
    for t in runtime._task_graph.list_tasks():
        icon = {"completed": "✅", "failed": "❌", "ready": "⏳", "created": "⬜"}.get(
            t.status.value, "❓"
        )
        print(f"     {icon} {t.task_id}: {t.description[:55]} [{t.required_capability}]")

    runtime.shutdown()
    print("\n  ✅ Demo 22 complete")


if __name__ == "__main__":
    main()
