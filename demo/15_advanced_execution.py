"""
Demo 15: Advanced Execution — Dynamic Plans, Sub-Goals, Human-in-the-Loop

Demonstrates Phase 3 advanced execution features:
  - Dynamic plan modification (add/remove/modify tasks in running DAG)
  - Sub-goal spawning from task execution
  - Human-in-the-loop approval workflows

Run: python3 demo/15_advanced_execution.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.advanced_execution import (
    DynamicPlanModifier,
    HumanInTheLoop,
    SubGoalManager,
)
from zelos.task_graph import Task, TaskGraphEngine


def main():
    print("=" * 60)
    print("  DEMO 15: Advanced Execution")
    print("=" * 60)

    # ── 1. Dynamic Plan Modification ──
    print("\n🔧 1. Dynamic Plan Modification")
    tg = TaskGraphEngine()
    dpm = DynamicPlanModifier(tg)

    # Create initial plan: 3 tasks
    for i in range(1, 4):
        tg.add_task(
            Task(
                task_id=f"t{i}",
                plan_id="demo-plan",
                description=f"Task {i}",
                required_capability=f"cap.{i}",
            )
        )

    print(f"   Initial plan: {len(tg.list_tasks())} tasks")

    # Add a new task dynamically
    dpm.add_task("t4", "demo-plan", "New dynamic task", "cap.4", dependencies=["t3"])
    print(f"   After dynamic add: {len(tg.list_tasks())} tasks")
    print(f"   t4 depends on: {tg.get_task('t4').dependencies}")

    # Remove task
    dpm.remove_task("t4")
    print(f"   After dynamic remove: {len(tg.list_tasks())} tasks")

    # Modify existing task
    dpm.modify_task("t2", priority="critical", timeout_ms=60000)
    t2 = tg.get_task("t2")
    print(f"   t2 modified: priority={t2.priority}, timeout={t2.timeout_ms}ms")

    # Show modification log
    log = dpm.get_modification_log()
    print(f"   Modification log: {len(log)} entries")
    for entry in log:
        print(f"     [{entry['operation']}] {entry['target_id']}")

    # ── 2. Sub-Goal Spawning ──
    print("\n🎯 2. Sub-Goal Spawning")
    tg2 = TaskGraphEngine()
    tg2.add_task(
        Task(
            task_id="main-1",
            plan_id="main-plan",
            description="Main research task",
            required_capability="research.analysis",
        )
    )

    sgm = SubGoalManager(tg2)

    # Parent task spawns sub-goals
    sub1 = sgm.spawn_sub_goal("main-1", "Investigate competitor features", budget=25.0, num_tasks=2)
    sub2 = sgm.spawn_sub_goal(
        "main-1", "Benchmark performance metrics", budget=15.0, required_capability="data-analysis.sql"
    )
    sub3 = sgm.spawn_sub_goal("main-1", "Generate comparison report", budget=10.0)

    print(f"   Sub-goals spawned: {sgm.get_sub_goal_count()}")
    for sg in sgm.list_sub_goals():
        print(f"   - {sg['sub_goal_id']}: {sg['description'][:50]} ({len(sg['task_ids'])} tasks, ${sg['budget']})")

    # Mark some as complete, one as failed
    sgm.mark_sub_goal_completed(sub1["sub_goal_id"])
    sgm.mark_sub_goal_completed(sub2["sub_goal_id"])
    sgm.mark_sub_goal_failed(sub3["sub_goal_id"])

    completed = sgm.are_all_completed("main-1")
    print(f"\n   All sub-goals done (completed | failed): {completed}")

    # ── 3. Human-in-the-Loop (HITL) ──
    print("\n👤 3. Human-in-the-Loop Approval Workflow")
    hitl = HumanInTheLoop()

    # Create approval requests
    req1 = hitl.create_request(
        task_id="deploy-prod",
        description="Deploy v2.0 to production (US-East)",
        approvers=["alice", "bob"],
        require_all=True,  # Both must approve
        context={"version": "2.0", "env": "prod", "risk": "medium"},
    )

    req2 = hitl.create_request(
        task_id="config-change",
        description="Update rate limit from 100→200 req/s",
        approvers=["alice"],
        context={"service": "api-gateway", "change": "rate-limit"},
    )

    req3 = hitl.create_request(
        task_id="schema-migration",
        description="Add email column to users table",
        approvers=["dba-team"],
        timeout_seconds=60,
    )

    print(f"   Pending approvals: {hitl.get_pending_count()}")

    # Approve req2 (single approver)
    hitl.approve(req2.request_id, "alice", "Rate limit increase looks safe")
    print(f"\n   req2 (config-change) status: {req2.status.value}")

    # Multi-step: alice approves, bob still pending
    hitl.approve(req1.request_id, "alice", "Code review passed, tests green")
    print(f"   req1 (deploy-prod) after alice: {req1.status.value} (waiting for bob)")

    hitl.approve(req1.request_id, "bob", "Monitoring dashboards look good")
    print(f"   req1 (deploy-prod) after bob: {req1.status.value}")

    # Request changes
    hitl.request_changes(req3.request_id, "dba-team", "Please add an index on email column too")
    print(f"   req3 (schema-migration) status: {req3.status.value} — feedback: {req3.resolution_comment}")

    # ── 4. Audit Trail ──
    print("\n📋 Approval Audit Trail for req1:")
    for entry in hitl.get_history(req1.request_id):
        print(
            f"   [{entry['action']}] at {entry['timestamp']:.0f} — "
            f"{entry.get('approver', 'system')}: {entry.get('comment', entry.get('detail', ''))}"
        )

    print(f"\n{'=' * 60}")
    print("  Demo complete. Advanced execution features working.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
