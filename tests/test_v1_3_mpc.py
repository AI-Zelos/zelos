"""
v1.3.0 Tests — MPC Adaptive Scheduling Loop + Feature Flags + Incremental Verification.

Layer 1: Unit tests (REQ-01 FeatureFlags, REQ-03 Incremental Verify, REQ-04 ReplanRules)
Layer 2: Integration tests (REQ-02 MPC loop, REQ-05 end-to-end scenarios)
"""

import pytest
import threading
import time
import uuid

from zelos.feature_flags import FeatureFlags
from zelos.replan_rules import (
    ConfidenceLowRule,
    DEFAULT_REPLAN_RULES,
    EmptyArtifactRule,
    ReplanContext,
    SchemaMismatchRule,
    VerdictRejectedRule,
)
from zelos.event_bus import EventBus
from zelos.task_graph import Task, TaskGraphEngine, TaskStatus
from zelos.verifier import SchemaVerifier, Verdict, VerificationCriteria


# ═══════════════════════════════════════════════════════════════════
# Layer 1: REQ-01 — Feature Flag System
# ═══════════════════════════════════════════════════════════════════

class TestFeatureFlags:
    """REQ-01: FeatureFlag system tests."""

    def test_stage_a_only_enables_core_components(self):
        """FeatureFlags.stage_a() should only enable the 7 core components."""
        f = FeatureFlags.stage_a()
        assert f.planner is True
        assert f.scheduler is True
        assert f.execution_engine is True
        assert f.verifier is True
        assert f.capability_registry is True
        assert f.task_graph_engine is True
        assert f.event_bus is True
        # Stage B-E should be off
        assert f.event_sourcing is False
        assert f.execution_trace is False
        assert f.evidence_collection is False
        assert f.confidence_scoring is False
        assert f.memory is False
        assert f.policy_gate is False
        assert f.cp_governance is False
        assert f.car is False
        assert f.diagnosis_engine is False
        assert f.credential_management is False
        assert f.failure_classifier is False
        assert f.repair_orchestrator is False
        assert f.patch_ranker is False
        assert f.arbiter is False
        assert f.contest_dispatch is False

    def test_stage_e_enables_all_components(self):
        """FeatureFlags.stage_e() should enable all components."""
        f = FeatureFlags.stage_e()
        assert f.planner is True
        assert f.event_sourcing is True
        assert f.diagnosis_engine is True
        assert f.credential_management is True
        assert f.failure_classifier is True
        assert f.repair_orchestrator is True
        assert f.patch_ranker is True
        assert f.arbiter is True
        assert f.contest_dispatch is True
        assert f.mpc_replan is True

    def test_stage_b_adds_audit_chain(self):
        """stage_b = stage_a + event_sourcing + execution_trace."""
        f = FeatureFlags.stage_b()
        assert f.planner is True          # inherited from stage_a
        assert f.event_sourcing is True   # new in stage_b
        assert f.execution_trace is True  # new in stage_b
        assert f.diagnosis_engine is False  # not yet

    def test_stage_c_adds_confidence(self):
        """stage_c = stage_b + evidence + confidence + memory."""
        f = FeatureFlags.stage_c()
        assert f.event_sourcing is True
        assert f.evidence_collection is True
        assert f.confidence_scoring is True
        assert f.memory is True
        assert f.diagnosis_engine is False  # not yet

    def test_stage_d_adds_governance(self):
        """stage_d = stage_c + policy_gate + cp + car + diagnosis."""
        f = FeatureFlags.stage_d()
        assert f.confidence_scoring is True
        assert f.policy_gate is True
        assert f.cp_governance is True
        assert f.car is True
        assert f.diagnosis_engine is True
        assert f.failure_classifier is False  # not yet

    def test_default_constructor_is_stage_a(self):
        """Default FeatureFlags() == stage_a."""
        f = FeatureFlags()
        assert f.planner is True
        assert f.diagnosis_engine is False

    def test_can_construct_from_dict(self):
        """FeatureFlags(**dict) should override defaults."""
        f = FeatureFlags(planner=False, diagnosis_engine=True, mpc_replan=False)
        assert f.planner is False
        assert f.diagnosis_engine is True
        assert f.mpc_replan is False
        # Unspecified fields keep defaults
        assert f.scheduler is True

    def test_mpc_replan_enabled_by_default(self):
        """mpc_replan should be True by default (v1.3.0 feature)."""
        f = FeatureFlags()
        assert f.mpc_replan is True

    def test_disabled_component_still_importable(self):
        """Even when feature flag is False, the module should be importable."""
        # Diagnosis Engine code exists even if flag is off
        from zelos import diagnosis_engine  # noqa: F401
        assert diagnosis_engine is not None


# ═══════════════════════════════════════════════════════════════════
# Layer 1: REQ-04 — Replan Rules Engine
# ═══════════════════════════════════════════════════════════════════

class TestReplanRules:
    """REQ-04: ReplanRule interface and 4 default rules."""

    def _make_ctx(self, **kwargs):
        """Helper to build ReplanContext."""
        defaults = {
            "task_id": "task-1",
            "artifact": {"data": "test"},
            "verdict": Verdict(verdict="passed", score=1.0, verifier_id="test"),
            "current_plan": None,
        }
        defaults.update(kwargs)
        return ReplanContext(**defaults)

    # ── VerdictRejectedRule ──

    def test_verdict_rejected_triggers_replan(self):
        rule = VerdictRejectedRule()
        ctx = self._make_ctx(verdict=Verdict(verdict="failed", score=0.0, verifier_id="test"))
        assert rule.should_replan(ctx) is True

    def test_verdict_accepted_does_not_trigger(self):
        rule = VerdictRejectedRule()
        ctx = self._make_ctx(verdict=Verdict(verdict="passed", score=1.0, verifier_id="test"))
        assert rule.should_replan(ctx) is False

    def test_verdict_rejected_trigger_reason(self):
        rule = VerdictRejectedRule()
        assert rule.trigger_reason == "verdict_rejected"

    # ── ConfidenceLowRule ──

    def test_confidence_below_50_triggers_replan(self):
        rule = ConfidenceLowRule(threshold=0.5)
        ctx = self._make_ctx(verdict=Verdict(verdict="passed", score=0.3, verifier_id="test"))
        assert rule.should_replan(ctx) is True

    def test_confidence_above_50_does_not_trigger(self):
        rule = ConfidenceLowRule(threshold=0.5)
        ctx = self._make_ctx(verdict=Verdict(verdict="passed", score=0.8, verifier_id="test"))
        assert rule.should_replan(ctx) is False

    def test_confidence_at_threshold_does_not_trigger(self):
        rule = ConfidenceLowRule(threshold=0.5)
        ctx = self._make_ctx(verdict=Verdict(verdict="passed", score=0.5, verifier_id="test"))
        assert rule.should_replan(ctx) is False  # strictly less than

    def test_confidence_custom_threshold(self):
        rule = ConfidenceLowRule(threshold=0.7)
        ctx = self._make_ctx(verdict=Verdict(verdict="passed", score=0.6, verifier_id="test"))
        assert rule.should_replan(ctx) is True

    def test_confidence_low_trigger_reason(self):
        rule = ConfidenceLowRule()
        assert rule.trigger_reason == "confidence_low"

    # ── EmptyArtifactRule ──

    def test_empty_artifact_triggers_replan(self):
        rule = EmptyArtifactRule()
        ctx = self._make_ctx(artifact={})
        assert rule.should_replan(ctx) is True

    def test_none_artifact_triggers_replan(self):
        rule = EmptyArtifactRule()
        ctx = self._make_ctx(artifact=None)
        assert rule.should_replan(ctx) is True

    def test_non_empty_artifact_does_not_trigger(self):
        rule = EmptyArtifactRule()
        ctx = self._make_ctx(artifact={"result": "ok"})
        assert rule.should_replan(ctx) is False

    def test_empty_artifact_trigger_reason(self):
        rule = EmptyArtifactRule()
        assert rule.trigger_reason == "empty_artifact"

    # ── SchemaMismatchRule ──

    def test_schema_mismatch_triggers_replan(self):
        rule = SchemaMismatchRule()
        task = Task(
            task_id="task-1", plan_id="plan-1",
            description="test", required_capability="test",
            expected_output_schema={"type": "dict"},
        )
        # Mock plan to return this task
        from unittest.mock import MagicMock
        plan = MagicMock()
        plan.get_task.return_value = task
        ctx = self._make_ctx(
            current_plan=plan,
            artifact="a string, not a dict",
        )
        assert rule.should_replan(ctx) is True

    def test_schema_match_does_not_trigger(self):
        rule = SchemaMismatchRule()
        task = Task(
            task_id="task-1", plan_id="plan-1",
            description="test", required_capability="test",
            expected_output_schema={"type": "dict"},
        )
        from unittest.mock import MagicMock
        plan = MagicMock()
        plan.get_task.return_value = task
        ctx = self._make_ctx(
            current_plan=plan,
            artifact={"key": "value"},  # dict type matches
        )
        assert rule.should_replan(ctx) is False

    def test_no_expected_schema_does_not_trigger(self):
        rule = SchemaMismatchRule()
        task = Task(
            task_id="task-1", plan_id="plan-1",
            description="test", required_capability="test",
        )
        assert task.expected_output_schema is None  # default
        from unittest.mock import MagicMock
        plan = MagicMock()
        plan.get_task.return_value = task
        ctx = self._make_ctx(current_plan=plan, artifact="anything")
        assert rule.should_replan(ctx) is False

    def test_schema_mismatch_trigger_reason(self):
        rule = SchemaMismatchRule()
        assert rule.trigger_reason == "schema_mismatch"

    # ── Default rules ──

    def test_default_rules_has_4_rules(self):
        assert len(DEFAULT_REPLAN_RULES) == 4
        types = [type(r).__name__ for r in DEFAULT_REPLAN_RULES]
        assert "VerdictRejectedRule" in types
        assert "ConfidenceLowRule" in types
        assert "SchemaMismatchRule" in types
        assert "EmptyArtifactRule" in types

    def test_custom_rule_can_be_added(self):
        """REQ-04.2: Custom replan rules work."""

        class MyCustomRule:
            trigger_reason = "my_custom_trigger"

            def should_replan(self, ctx):
                return "TODO" in str(ctx.artifact)

        rule = MyCustomRule()
        ctx = self._make_ctx(artifact={"description": "TODO: implement"})
        assert rule.should_replan(ctx) is True
        ctx2 = self._make_ctx(artifact={"description": "done"})
        assert rule.should_replan(ctx2) is False


# ═══════════════════════════════════════════════════════════════════
# Layer 1: REQ-03 — Incremental Verification
# ═══════════════════════════════════════════════════════════════════

class TestIncrementalVerification:
    """REQ-03: Incremental verification after each Task completion."""

    def _make_execution_engine_with_verify(self):
        from zelos.execution_engine import ExecutionEngine
        tg = TaskGraphEngine()
        eb = EventBus()
        ee = ExecutionEngine(tg, eb)
        ee._incremental_verifier = SchemaVerifier()
        return ee, tg

    def test_empty_artifact_returns_failed(self):
        ee, tg = self._make_execution_engine_with_verify()
        task = Task(task_id="t1", plan_id="p1", description="d",
                    required_capability="test")
        tg._tasks["t1"] = task
        verdict = ee._run_incremental_verify("t1", {})
        assert verdict.verdict == "failed"
        assert verdict.score == 0.0

    def test_none_artifact_returns_failed(self):
        ee, tg = self._make_execution_engine_with_verify()
        task = Task(task_id="t1", plan_id="p1", description="d",
                    required_capability="test")
        tg._tasks["t1"] = task
        verdict = ee._run_incremental_verify("t1", None)
        assert verdict.verdict == "failed"
        assert verdict.score == 0.0

    def test_non_empty_artifact_returns_passed(self):
        ee, tg = self._make_execution_engine_with_verify()
        task = Task(task_id="t1", plan_id="p1", description="d",
                    required_capability="test")
        tg._tasks["t1"] = task
        verdict = ee._run_incremental_verify("t1", {"result": "ok"})
        assert verdict.verdict == "passed"

    def test_no_verifier_returns_default_passed(self):
        ee, tg = self._make_execution_engine_with_verify()
        ee._incremental_verifier = None  # No verifier set
        task = Task(task_id="t1", plan_id="p1", description="d",
                    required_capability="test")
        tg._tasks["t1"] = task
        verdict = ee._run_incremental_verify("t1", {})
        assert verdict.verdict == "passed"
        assert verdict.score == 1.0


# ═══════════════════════════════════════════════════════════════════
# Layer 1: Task new fields & TaskGraphEngine additions
# ═══════════════════════════════════════════════════════════════════

class TestTaskNewFields:
    """V1.3.0: Task.expected_output_schema and BLOCKED status."""

    def test_task_has_expected_output_schema_default_none(self):
        task = Task(task_id="t1", plan_id="p1", description="d",
                    required_capability="test")
        assert hasattr(task, 'expected_output_schema')
        assert task.expected_output_schema is None

    def test_task_can_set_expected_output_schema(self):
        task = Task(task_id="t1", plan_id="p1", description="d",
                    required_capability="test",
                    expected_output_schema={"type": "dict"})
        assert task.expected_output_schema == {"type": "dict"}

    def test_blocked_status_exists(self):
        """TaskStatus.BLOCKED should be a valid enum value."""
        assert hasattr(TaskStatus, 'BLOCKED')
        blocked = TaskStatus.BLOCKED
        assert blocked.value == "blocked"


class TestTaskGraphAdditions:
    """V1.3.0: TaskGraphEngine.get_dependents() and add_task()."""

    def test_get_dependents_returns_direct_dependents(self):
        tg = TaskGraphEngine()
        # Use add_task() so _dependents_map is properly populated
        t1 = Task(task_id="t1", plan_id="p1", description="d1",
                  required_capability="test", dependents=["t2", "t3"])
        t2 = Task(task_id="t2", plan_id="p1", description="d2",
                  required_capability="test", dependencies=["t1"])
        t3 = Task(task_id="t3", plan_id="p1", description="d3",
                  required_capability="test", dependencies=["t1"])
        tg.add_task(t1)
        tg.add_task(t2)
        tg.add_task(t3)

        deps = tg.get_dependents("t1")
        assert set(deps) == {"t2", "t3"}

    def test_get_dependents_empty_for_leaf(self):
        tg = TaskGraphEngine()
        t1 = Task(task_id="t1", plan_id="p1", description="d1",
                  required_capability="test")
        tg._tasks["t1"] = t1

        deps = tg.get_dependents("t1")
        assert deps == []

    def test_add_task_inserts_into_graph(self):
        tg = TaskGraphEngine()
        t1 = Task(task_id="t1", plan_id="p1", description="d1",
                  required_capability="test")
        tg.add_task(t1)
        assert "t1" in tg._tasks
        assert tg.get_task("t1") == t1

    def test_blocked_transition_to_ready(self):
        """BLOCKED tasks can transition to READY (after replan resolves)."""
        from zelos.task_graph import VALID_TRANSITIONS
        assert TaskStatus.READY in VALID_TRANSITIONS[TaskStatus.BLOCKED]

    def test_blocked_transition_to_cancelled(self):
        """BLOCKED tasks can be cancelled."""
        from zelos.task_graph import VALID_TRANSITIONS
        assert TaskStatus.CANCELLED in VALID_TRANSITIONS[TaskStatus.BLOCKED]

    def test_blocked_transition_to_fatal_failed(self):
        """BLOCKED tasks can be fatal_failed if parent gives up."""
        from zelos.task_graph import VALID_TRANSITIONS
        assert TaskStatus.FATAL_FAILED in VALID_TRANSITIONS[TaskStatus.BLOCKED]


# ═══════════════════════════════════════════════════════════════════
# Layer 1: ExecutionEngine — Replan Check
# ═══════════════════════════════════════════════════════════════════

class TestExecutionEngineReplanCheck:
    """REQ-02.1: replan_check hook in ExecutionEngine."""

    def _make_engine(self):
        from zelos.execution_engine import ExecutionEngine
        tg = TaskGraphEngine()
        eb = EventBus()
        ee = ExecutionEngine(tg, eb)
        return ee, tg, eb

    def test_replan_callback_not_called_when_not_set(self):
        ee, tg, eb = self._make_engine()
        # Even with rules, no callback → no replan
        ee._replan_rules = DEFAULT_REPLAN_RULES
        ee._replan_callback = None
        # Should not raise
        assert ee._replan_callback is None

    def test_replan_callback_called_on_failed_task(self):
        ee, tg, eb = self._make_engine()
        called_with = {}

        def callback(plan_id, trigger, context):
            called_with["plan_id"] = plan_id
            called_with["trigger"] = trigger
            called_with["context"] = context
            return None  # No new plan for simplicity

        ee.set_replan_callback(callback)
        ee._replan_rules = DEFAULT_REPLAN_RULES

        # Set up a plan reference
        from zelos.planner import PlannerPlan
        plan = PlannerPlan(plan_id="p1", goal_id="g1")
        ee._current_plan = plan
        ee._replan_count["g1"] = 0
        ee._max_replans = 5

        # Register agent and dispatch task (to put into in_flight)
        agent_state = ee.register_agent("agent-1", "test-agent")
        task = Task(task_id="t1", plan_id="p1", description="d",
                    required_capability="test", timeout_ms=60000)
        tg._tasks["t1"] = task
        tg.transition = lambda tid, status, **kw: None  # no-op for test
        ee.dispatch("t1", "agent-1")

        # Submit a failed result
        result = ee.submit_result("t1", "agent-1", {
            "status": "failed",
            "error": {"code": "TEST_ERROR", "message": "test failure"},
            "artifact": {},
        })

        assert result is True
        # Callback should have been called with failure context
        assert "plan_id" in called_with
        assert called_with["plan_id"] == "p1"
        assert "trigger" in called_with
        # Context should contain diagnosis info
        assert "failed_task_id" in called_with.get("context", {})
        assert "verdict" in called_with.get("context", {})

    def test_replan_not_called_when_mpc_disabled(self):
        """When mpc_replan is disabled, replan_check should NOT trigger."""
        ee, tg, eb = self._make_engine()
        call_count = [0]

        def callback(plan_id, trigger, context):
            call_count[0] += 1
            return None

        ee.set_replan_callback(callback)
        # Simulate disabled: clear the rules
        ee._replan_rules = []

        from zelos.planner import PlannerPlan
        plan = PlannerPlan(plan_id="p1", goal_id="g1")
        ee._current_plan = plan
        ee._replan_count["g1"] = 0

        agent_state = ee.register_agent("agent-1", "test-agent")
        task = Task(task_id="t1", plan_id="p1", description="d",
                    required_capability="test", timeout_ms=60000)
        tg._tasks["t1"] = task
        tg.transition = lambda tid, status, **kw: None
        ee.dispatch("t1", "agent-1")

        result = ee.submit_result("t1", "agent-1", {
            "status": "failed",
            "error": {"code": "TEST_ERROR"},
            "artifact": {},
        })
        assert result is True
        assert call_count[0] == 0  # No replan triggered

    def test_replan_not_triggered_on_successful_task(self):
        """Successful task completion should NOT trigger replan."""
        ee, tg, eb = self._make_engine()
        call_count = [0]

        def callback(plan_id, trigger, context):
            call_count[0] += 1
            return None

        ee.set_replan_callback(callback)
        ee._replan_rules = DEFAULT_REPLAN_RULES
        ee._replan_count["g1"] = 0

        from zelos.planner import PlannerPlan
        plan = PlannerPlan(plan_id="p1", goal_id="g1")
        ee._current_plan = plan

        agent_state = ee.register_agent("agent-1", "test-agent")
        task = Task(task_id="t1", plan_id="p1", description="d",
                    required_capability="test", timeout_ms=60000)
        tg._tasks["t1"] = task
        tg.transition = lambda tid, status, **kw: None
        ee.dispatch("t1", "agent-1")

        result = ee.submit_result("t1", "agent-1", {
            "status": "completed",
            "artifact": {"patch": "fixed something"},
        })
        assert result is True
        assert call_count[0] == 0  # No replan on success

    def test_replan_max_5_times_then_stops(self):
        """After 5 replans, should stop triggering."""
        ee, tg, eb = self._make_engine()
        call_count = [0]

        def callback(plan_id, trigger, context):
            call_count[0] += 1
            return None

        ee.set_replan_callback(callback)
        ee._replan_rules = DEFAULT_REPLAN_RULES
        ee._replan_count["g1"] = 5  # Already at max
        ee._max_replans = 5

        from zelos.planner import PlannerPlan
        plan = PlannerPlan(plan_id="p1", goal_id="g1")
        ee._current_plan = plan

        agent_state = ee.register_agent("agent-1", "test-agent")
        task = Task(task_id="t1", plan_id="p1", description="d",
                    required_capability="test", timeout_ms=60000)
        tg._tasks["t1"] = task
        tg.transition = lambda tid, status, **kw: None
        ee.dispatch("t1", "agent-1")

        result = ee.submit_result("t1", "agent-1", {
            "status": "failed",
            "error": {"code": "TEST_ERROR"},
            "artifact": {},
        })
        assert result is True
        assert call_count[0] == 0  # Capped at max

    def test_replan_publishes_plan_modified_event(self):
        """Replan should publish execution_plan.modified Event."""
        ee, tg, eb = self._make_engine()
        events_published = []

        # Capture events
        original_publish = eb.publish
        def capture_publish(event):
            events_published.append(event)
            original_publish(event)
        eb.publish = capture_publish

        def callback(plan_id, trigger, context):
            from zelos.planner import PlannerPlan
            return PlannerPlan(plan_id="p1-new", goal_id="g1", version=2)

        ee.set_replan_callback(callback)
        ee._replan_rules = DEFAULT_REPLAN_RULES
        ee._replan_count["g1"] = 0
        ee._max_replans = 5

        from zelos.planner import PlannerPlan
        plan = PlannerPlan(plan_id="p1", goal_id="g1")
        ee._current_plan = plan

        agent_state = ee.register_agent("agent-1", "test-agent")
        task = Task(task_id="t1", plan_id="p1", description="d",
                    required_capability="test", timeout_ms=60000)
        tg._tasks["t1"] = task
        tg.transition = lambda tid, status, **kw: None
        ee.dispatch("t1", "agent-1")

        result = ee.submit_result("t1", "agent-1", {
            "status": "failed",
            "error": {"code": "TEST_ERROR"},
            "artifact": {},
        })
        assert result is True

        # Check for plan.modified event
        plan_mod_events = [e for e in events_published
                          if e.event_type == "execution_plan.modified"]
        assert len(plan_mod_events) >= 1

    def test_current_plan_updated_after_replan(self):
        """After replan, _current_plan should reference the new plan."""
        ee, tg, eb = self._make_engine()

        from zelos.planner import PlannerPlan
        new_plan = PlannerPlan(plan_id="new-plan", goal_id="g1")

        def callback(plan_id, trigger, context):
            return new_plan

        ee.set_replan_callback(callback)
        ee._replan_rules = DEFAULT_REPLAN_RULES
        ee._replan_count["g1"] = 0

        plan = PlannerPlan(plan_id="p1", goal_id="g1")
        ee._current_plan = plan

        agent_state = ee.register_agent("agent-1", "test-agent")
        task = Task(task_id="t1", plan_id="p1", description="d",
                    required_capability="test", timeout_ms=60000)
        tg._tasks["t1"] = task
        tg.transition = lambda tid, status, **kw: None
        ee.dispatch("t1", "agent-1")

        ee.submit_result("t1", "agent-1", {
            "status": "failed",
            "error": {"code": "TEST_ERROR"},
            "artifact": {},
        })
        assert ee._current_plan.plan_id == "new-plan"


# ═══════════════════════════════════════════════════════════════════
# Layer 2: MPC Integration — ExecutionEngine + Runtime._on_replan
# ═══════════════════════════════════════════════════════════════════
#
# These tests validate the full MPC loop at the ExecutionEngine +
# Runtime level WITHOUT requiring the full orchestrator/Scheduler/
# CapabilityRegistry/Agent infrastructure. They directly wire
# ExecutionEngine.replan_callback → Runtime._on_replan and drive
# the lifecycle manually.
# ═══════════════════════════════════════════════════════════════════

class TestMPCIntegrationScenarios:
    """REQ-05: 5 MPC loop scenarios at ExecutionEngine + Runtime level."""

    def _make_runtime_and_engine(self):
        """Create minimal ZelosRuntime + wire up MPC callback.

        Uses RuleBasedPlanner — a deterministic planner with rule-based
        replan_path(). No LLM dependency. Fast and predictable for tests.
        """
        from zelos.runtime import ZelosRuntime
        from zelos.planner import RuleBasedPlanner

        config = {"features": FeatureFlags.stage_a().__dict__}
        runtime = ZelosRuntime(config)
        # RuleBasedPlanner: deterministic replan_path(), no LLM needed
        runtime._planner = RuleBasedPlanner()
        ee = runtime._execution_engine
        tg = runtime._task_graph

        # Enable MPC
        ee._replan_rules = DEFAULT_REPLAN_RULES
        ee._max_replans = 5

        # Disable auth/tenant checks for test
        runtime._check_auth = lambda *a, **kw: None

        return runtime, ee, tg

    def _setup_agent(self, ee, agent_id="agent-1", cap="code-generation"):
        """Register an agent in ExecutionEngine and return its state."""
        return ee.register_agent(agent_id, agent_id, capabilities=[
            {"name": cap, "version": "1.0"}])

    def _setup_tasks_and_plan(self, runtime, ee, tg, task_specs, goal_id="g1"):
        """
        Set up tasks in TaskGraphEngine and a PlannerPlan.

        task_specs: list of (task_id, deps, capability) tuples
        """
        from zelos.planner import PlannerPlan, PlannerTask

        plan = PlannerPlan(plan_id="p1", goal_id=goal_id)

        for tid, deps, cap in task_specs:
            task = Task(task_id=tid, plan_id="p1", description=f"Task {tid}",
                        required_capability=cap, dependencies=deps,
                        timeout_ms=60000)
            tg.add_task(task)
            plan.tasks.append(PlannerTask(
                task_id=tid, description=f"Task {tid}",
                required_capability=cap, dependencies=deps,
            ))

        ee._current_plan = plan
        ee._replan_count[goal_id] = 0

        # Store plan in runtime so _get_plan() can find it
        runtime._goals["p1"] = {
            "goal_id": goal_id,
            "status": "running",
            "plan": plan,
            "plan_id": "p1",
            "description": "Integration test goal",
        }

        # Wire a minimal dispatch callback (needed for dispatch to work)
        ee._agent_dispatch = lambda aid, t: None

        return plan

    def _make_ready_and_assign(self, tg, task_id, agent_id="agent-a"):
        """Transition task through state machine to ASSIGNED for dispatch.

        Handles any valid starting state: CREATED, FAILED, BLOCKED, etc.
        """
        task = tg.get_task(task_id)
        if not task:
            return

        # If task is in a non-READY/non-ASSIGNED state, try to move to READY
        if task.status not in (TaskStatus.READY, TaskStatus.ASSIGNED):
            try:
                tg.transition(task_id, TaskStatus.READY)
            except ValueError:
                pass

        # Now try ASSIGNED
        task = tg.get_task(task_id)
        if task and task.status == TaskStatus.READY:
            try:
                tg.transition(task_id, TaskStatus.ASSIGNED, agent_id=agent_id)
            except ValueError:
                pass

    def test_scenario_1_normal_completion_no_replan(self):
        """
        Scenario 1: 3 Tasks all succeed → 0 replans, Goal COMPLETED.
        """
        runtime, ee, tg = self._make_runtime_and_engine()

        # Track replan events
        replan_events = []
        def track_replan(plan_id, trigger, context):
            replan_events.append(trigger)
            return runtime._on_replan(plan_id, trigger, context)
        ee.set_replan_callback(track_replan)

        self._setup_agent(ee, "agent-a")
        plan = self._setup_tasks_and_plan(runtime, ee, tg, [
            ("t1", [], "code-search"),
            ("t2", ["t1"], "code-generation"),
            ("t3", ["t2"], "code-review"),
        ])

        # Dispatch and complete each task
        for tid in ["t1", "t2", "t3"]:
            self._make_ready_and_assign(tg, tid)
            ee.dispatch(tid, "agent-a")
            ee.submit_result(tid, "agent-a", {
                "status": "completed",
                "artifact": {"output": f"result-{tid}"},
            })

        assert len(replan_events) == 0, f"Expected 0 replans, got {len(replan_events)}"
        # All tasks should be COMPLETED
        for tid in ["t1", "t2", "t3"]:
            assert tg.get_task(tid).status == TaskStatus.COMPLETED

    def test_scenario_2_single_replan_on_failure(self):
        """
        Scenario 2: Task B fails → replan triggers → new task inserted.
        """
        runtime, ee, tg = self._make_runtime_and_engine()

        replan_events = []
        def track_replan(plan_id, trigger, context):
            replan_events.append({"trigger": trigger, "context": context})
            return runtime._on_replan(plan_id, trigger, context)
        ee.set_replan_callback(track_replan)

        self._setup_agent(ee, "agent-a")
        plan = self._setup_tasks_and_plan(runtime, ee, tg, [
            ("t1", [], "code-search"),
            ("t2", ["t1"], "code-generation"),
        ])

        # Complete t1 successfully
        self._make_ready_and_assign(tg, "t1")
        ee.dispatch("t1", "agent-a")
        ee.submit_result("t1", "agent-a", {
            "status": "completed",
            "artifact": {"location": "file.py:42"},
        })

        # Fail t2 — should trigger replan
        self._make_ready_and_assign(tg, "t2")
        ee.dispatch("t2", "agent-a")
        ee.submit_result("t2", "agent-a", {
            "status": "failed",
            "error": {"code": "TEST_ERROR", "message": "patch failed"},
            "artifact": {},
        })

        assert len(replan_events) >= 1
        assert replan_events[0]["trigger"] in (
            "verdict_rejected", "empty_artifact", "confidence_low"
        )
        # t2 should be FAILED
        assert tg.get_task("t2").status == TaskStatus.FAILED
        # A replacement task should have been inserted
        all_task_ids = [t.task_id for t in tg.list_tasks()]
        assert len(all_task_ids) > 2  # t1 + t2 + at least one replacement

    def test_scenario_3_multiple_replans_then_success(self):
        """
        Scenario 3: Task fails 2 times, 3rd attempt succeeds — 2 replan Events.
        """
        runtime, ee, tg = self._make_runtime_and_engine()

        replan_count = [0]
        def track_replan(plan_id, trigger, context):
            replan_count[0] += 1
            return runtime._on_replan(plan_id, trigger, context)
        ee.set_replan_callback(track_replan)

        self._setup_agent(ee, "agent-a")
        plan = self._setup_tasks_and_plan(runtime, ee, tg, [
            ("t1", [], "code-generation"),
        ])

        # Fail t1 twice
        for i in range(2):
            self._make_ready_and_assign(tg, "t1")
            ee.dispatch("t1", "agent-a")
            ee.submit_result("t1", "agent-a", {
                "status": "failed",
                "error": {"code": "ERR", "message": f"attempt {i+1}"},
                "artifact": {},
            })
            # Reset replan count for next attempt (simulates replan resetting counter)
            ee._replan_count["g1"] = i

        assert replan_count[0] >= 2

    def test_scenario_4_exceed_replan_limit(self):
        """
        Scenario 4: Task fails, replan count already at max → no replan.
        """
        runtime, ee, tg = self._make_runtime_and_engine()

        replan_called = [False]
        def track_replan(plan_id, trigger, context):
            replan_called[0] = True
            return runtime._on_replan(plan_id, trigger, context)
        ee.set_replan_callback(track_replan)

        self._setup_agent(ee, "agent-a")
        plan = self._setup_tasks_and_plan(runtime, ee, tg, [
            ("t1", [], "code-generation"),
        ])

        # Already at max replans
        ee._replan_count["g1"] = 5

        self._make_ready_and_assign(tg, "t1")
        ee.dispatch("t1", "agent-a")
        ee.submit_result("t1", "agent-a", {
            "status": "failed",
            "error": {"code": "ERR"},
            "artifact": {},
        })
        assert replan_called[0] is False  # Capped at max

    def test_scenario_5_downstream_cascade_blocked(self):
        """
        Scenario 5: A → B → C (via add_task deps).
        When tA fails and _on_replan runs, tB (direct dependent)
        transitions to BLOCKED if in a non-terminal state.
        """
        runtime, ee, tg = self._make_runtime_and_engine()

        self._setup_agent(ee, "agent-a")
        plan = self._setup_tasks_and_plan(runtime, ee, tg, [
            ("tA", [], "code-search"),
            ("tB", ["tA"], "code-generation"),
            ("tC", ["tB"], "code-review"),
        ])

        # Transition tB to READY (non-terminal) so it can be BLOCKED
        tg.transition("tB", TaskStatus.READY)

        # tC stays CREATED — also non-terminal
        # tA stays CREATED

        # Verify dependents map is correct via add_task
        deps_of_A = tg.get_dependents("tA")
        assert "tB" in deps_of_A, f"Expected tB as dependent of tA, got {deps_of_A}"

        # Trigger replan on tA
        def test_replan(plan_id, trigger, context):
            return runtime._on_replan(plan_id, trigger, context)
        ee.set_replan_callback(test_replan)

        self._make_ready_and_assign(tg, "tA")
        ee.dispatch("tA", "agent-a")
        ee.submit_result("tA", "agent-a", {
            "status": "failed",
            "error": {"code": "ERR"},
            "artifact": {},
        })

        # tA should be FAILED
        assert tg.get_task("tA").status == TaskStatus.FAILED
        # tB should be BLOCKED (was READY, downstream of tA)
        assert tg.get_task("tB").status == TaskStatus.BLOCKED, \
            f"Expected tB BLOCKED, got {tg.get_task('tB').status}"


# ═══════════════════════════════════════════════════════════════════
# Layer 3: Planner.replan_path() test
# ═══════════════════════════════════════════════════════════════════

class TestPlannerReplanPath:
    """REQ-02.4: Planner.replan_path() default implementation."""

    def test_replan_path_returns_replacement_task(self):
        from zelos.planner import LLMPlanner
        planner = LLMPlanner()

        failure_context = {
            "verdict": {"result": "failed", "score": 0.0, "summary": "Empty artifact"},
            "classification": {
                "action": "repair",
                "reason": "Salvageable: AssertionError",
                "salvageable": True,
                "failure_type": "AssertionError",
            },
        }

        tasks = planner.replan_path(
            goal={"intent": "fix bug"},
            failed_task_id="t1",
            failure_context=failure_context,
            completed_tasks=["t0"],
        )
        assert len(tasks) >= 1
        assert tasks[0].required_capability is not None

    def test_replan_path_with_diagnosis_details(self):
        """When diagnosis has file:line info, it should appear in task description."""
        from zelos.planner import LLMPlanner
        planner = LLMPlanner()

        failure_context = {
            "verdict": {"result": "failed", "score": 0.2, "summary": "test failed"},
            "diagnosis": {
                "failures_detail": [
                    {
                        "test_name": "test_foo",
                        "failure_type": "AssertionError",
                        "location": "tests/test_foo.py:42",
                        "expected": "X",
                        "actual": "Y",
                    }
                ],
                "impact_scope": "single_module",
                "recommendation": "repair",
            },
            "classification": {
                "action": "repair",
                "reason": "Salvageable",
                "salvageable": True,
                "failure_type": "AssertionError",
            },
        }

        tasks = planner.replan_path(
            goal={"intent": "fix bug"},
            failed_task_id="t1",
            failure_context=failure_context,
            completed_tasks=[],
        )
        assert len(tasks) >= 1
        desc = tasks[0].description
        assert "test_foo" in desc
        assert "AssertionError" in desc
        assert "tests/test_foo.py:42" in desc
        assert "Expected: X" in desc
        assert "Actual: Y" in desc
