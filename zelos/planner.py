"""
LLM-Based Planner — Decomposes Goals into ExecutionPlans using configurable LLM providers.

Supports: OpenAI, Anthropic, Google, OpenAI-compatible endpoints, and Mock for testing.
Phase 1: Single-call decomposition with structured JSON output.
"""

import json
import re
import time
import urllib.error
import urllib.request
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

# ═══════════════════════════════════════════
# Data Structures
# ═══════════════════════════════════════════


@dataclass
class PlannerTask:
    task_id: str = ""
    description: str = ""
    required_capability: str = ""
    dependencies: list[str] = field(default_factory=list)
    priority: str = "medium"
    timeout_ms: int = 30000

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id or str(uuid.uuid4()),
            "description": self.description,
            "required_capability": self.required_capability,
            "dependencies": self.dependencies,
            "priority": self.priority,
            "timeout_ms": self.timeout_ms,
        }


@dataclass
class PlannerPlan:
    plan_id: str = ""
    goal_id: str = ""
    tasks: list[PlannerTask] = field(default_factory=list)
    dependencies: list[dict[str, Any]] = field(default_factory=list)
    planner_id: str = "llm-planner"
    planner_version: str = "0.1.0"
    created_at: float = 0.0
    version: int = 1
    architecture_delta: dict[str, Any] | None = None  # v0.9.0

    def to_dict(self) -> dict:
        result = {
            "plan_id": self.plan_id or str(uuid.uuid4()),
            "goal_id": self.goal_id,
            "tasks": [t.to_dict() for t in self.tasks],
            "dependencies": self.dependencies,
            "planner_id": self.planner_id,
            "planner_version": self.planner_version,
            "created_at": self.created_at or time.time(),
            "version": self.version,
        }
        if self.architecture_delta:
            result["architecture_delta"] = self.architecture_delta
        return result

    def get_task(self, task_id: str) -> PlannerTask | None:
        """v1.3.0: Find a PlannerTask by ID within this plan."""
        for t in self.tasks:
            if t.task_id == task_id:
                return t
        return None


# ═══════════════════════════════════════════
# LLM Providers
# ═══════════════════════════════════════════


class LLMProvider(ABC):
    """Abstract base for LLM providers."""

    @abstractmethod
    def chat(self, messages: list[dict[str, str]], **kwargs) -> str:
        """Send a chat completion request. Returns the response text."""
        ...

    @abstractmethod
    def provider_name(self) -> str: ...


class OpenAICompatibleProvider(LLMProvider):
    """Works with OpenAI API and any OpenAI-compatible endpoint (vLLM, Ollama, etc.)."""

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        temperature: float = 0.3,
        max_tokens: int = 4000,
        **kwargs,
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._extra = kwargs

    def provider_name(self) -> str:
        return "openai"

    def chat(self, messages: list[dict[str, str]], **kwargs) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
        }
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read())
                return result["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"OpenAI API error {e.code}: {e.read().decode()}") from e


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider."""

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str = "https://api.anthropic.com/v1",
        temperature: float = 0.3,
        max_tokens: int = 4000,
        **kwargs,
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._extra = kwargs

    def provider_name(self) -> str:
        return "anthropic"

    def chat(self, messages: list[dict[str, str]], **kwargs) -> str:
        # Extract system message
        system = ""
        user_messages = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            else:
                user_messages.append(m)

        payload = {
            "model": self.model,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
            "system": system,
            "messages": user_messages,
        }
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{self.base_url}/messages",
            data=data,
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read())
                return result["content"][0]["text"]
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Anthropic API error {e.code}: {e.read().decode()}") from e


class GoogleProvider(LLMProvider):
    """Google Gemini API provider."""

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        temperature: float = 0.3,
        max_tokens: int = 4000,
        **kwargs,
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._extra = kwargs

    def provider_name(self) -> str:
        return "google"

    def chat(self, messages: list[dict[str, str]], **kwargs) -> str:
        # Convert to Gemini format
        contents = []
        system_instruction = ""
        for m in messages:
            if m["role"] == "system":
                system_instruction = m["content"]
            elif m["role"] == "user":
                contents.append({"role": "user", "parts": [{"text": m["content"]}]})
            elif m["role"] == "assistant":
                contents.append({"role": "model", "parts": [{"text": m["content"]}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": kwargs.get("temperature", self.temperature),
                "maxOutputTokens": kwargs.get("max_tokens", self.max_tokens),
            },
        }
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        data = json.dumps(payload).encode()
        url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read())
                return result["candidates"][0]["content"]["parts"][0]["text"]
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Google API error {e.code}: {e.read().decode()}") from e


class MockLLMProvider(LLMProvider):
    """Mock provider for testing. Returns predefined responses."""

    def __init__(self, response: str = "", **kwargs):
        self._response = response
        self._call_count = 0
        self._call_args: list[dict] = []
        self._fail_count = 0
        self.model = kwargs.get("model", "mock")
        self.temperature = kwargs.get("temperature", 0.3)
        self.max_tokens = kwargs.get("max_tokens", 4000)

    def provider_name(self) -> str:
        return "mock"

    def set_response(self, response: str) -> None:
        self._response = response

    def set_fail_count(self, count: int) -> None:
        """Fail the first N calls, then succeed."""
        self._fail_count = count

    def chat(self, messages: list[dict[str, str]], **kwargs) -> str:
        self._call_count += 1
        self._call_args.append({"messages": messages, "kwargs": kwargs})
        if self._fail_count > 0:
            self._fail_count -= 1
            raise RuntimeError("Mock provider: simulated API failure")
        return self._response


# ═══════════════════════════════════════════
# Provider Factory
# ═══════════════════════════════════════════

SUPPORTED_PROVIDERS = {
    "openai": OpenAICompatibleProvider,
    "anthropic": AnthropicProvider,
    "google": GoogleProvider,
    "mock": MockLLMProvider,
}


def create_provider(config: dict[str, Any]) -> LLMProvider:
    """Factory: create an LLM provider from configuration."""
    provider_name = config.get("provider", "openai").lower()
    if provider_name not in SUPPORTED_PROVIDERS:
        raise ValueError(f"Unsupported provider: '{provider_name}'. Supported: {', '.join(SUPPORTED_PROVIDERS.keys())}")
    cls = SUPPORTED_PROVIDERS[provider_name]
    return cls(
        model=config.get("model", "gpt-4o"),
        api_key=config.get("api_key", ""),
        base_url=config.get("base_url", ""),
        temperature=config.get("temperature", 0.3),
        max_tokens=config.get("max_tokens", 4000),
    )


# ═══════════════════════════════════════════
# Planner
# ═══════════════════════════════════════════

DEFAULT_SYSTEM_PROMPT = """You are a senior software architect and task planner for an AI agent orchestration system called Zelos.

Your job is to decompose a user's Goal into a structured ExecutionPlan — a list of atomic Tasks with dependencies forming a Directed Acyclic Graph (DAG).

## Output Format
Respond with ONLY valid JSON. No markdown, no explanation, no code fences.

{
  "tasks": [
    {
      "task_id": "t1",
      "description": "Clear, actionable description of what this task does",
      "required_capability": "domain.subdomain",
      "dependencies": [],
      "priority": "medium",
      "timeout_ms": 30000
    }
  ],
  "dependencies": [
    {"from_task_id": "t1", "to_task_id": "t2", "type": "hard", "data_required": true}
  ],
  "architecture_delta": {
    "modified_modules": ["auth-service", "user-model"],
    "new_dependencies": ["oauth2-client-lib"],
    "removed_dependencies": [],
    "api_changes": [
      {"endpoint": "POST /auth/login", "change_type": "modified", "compatibility": "backward_compatible"}
    ],
    "data_model_changes": ["users.add(oauth_provider, oauth_id)"],
    "risk_level": "medium",
    "explanation": "Short explanation of why this risk level"
  }
}

## Capability Naming
Use these capability domains:
- code-generation.{language} — Writing code (python, typescript, go, rust, etc.)
- code-review.{type} — Reviewing code (security, quality, style)
- design.{type} — Design artifacts (architecture, ui, database)
- research.{type} — Finding information (web-search, documentation, api-reference)
- automation.{type} — Automated actions (browser, file-system, cli)
- data-query.{type} — Database queries (sql, graphql, analytics)
- analysis.{type} — Analyzing data/code (static-analysis, performance, data-science)
- communication.{type} — Generating messages (email, report, documentation)
- verification.{type} — Testing and validation (unit-test, integration-test, e2e-test)

## Rules
1. Every task MUST have a required_capability from the list above
2. The dependency graph MUST be acyclic (no cycles)
3. task_id values MUST be unique
4. Break work into atomic, single-purpose tasks
5. Order tasks logically: design → implement → review → test → deploy
6. Prioritize tasks: "critical" for blockers, "high" for core work, "medium" for normal, "low" for nice-to-have
"""


class Planner(ABC):
    """v1.3.0: Base class for all Planners. Extracted from LLMPlanner.

    All planner implementations must implement plan(). replan_path()
    has a default rule-based implementation that subclasses can override.
    """

    @abstractmethod
    def plan(self, goal_description: str, goal_id: str = "",
             context: dict | None = None) -> PlannerPlan:
        """Generate an execution plan for a goal."""
        ...

    def replan_path(
        self,
        goal,
        failed_task_id: str,
        failure_context: dict,
        completed_tasks: list[str],
    ) -> list[PlannerTask]:
        """
        v1.3.0: Generate replacement tasks for a failed path.

        Default implementation: creates a single replacement task with
        diagnostic details embedded in its description. LLM-based planners
        can override this for full-context decomposition.

        failure_context keys:
          - verdict: {"result": "failed"|"passed", "confidence": float, "reason": str}
          - diagnosis: DiagnosisResult.to_dict() (if available)
          - classification: ClassificationResult fields (if available)
        """
        diag = failure_context.get("diagnosis", {})
        classification = failure_context.get("classification", {})

        # Build a description enriched with diagnostic details
        desc_parts = [
            f"Previous attempt failed. "
            f"Reason: {classification.get('reason', failure_context.get('verdict', {}).get('summary', 'unknown'))}"
        ]
        for f_detail in diag.get("failures_detail", []):
            loc = f_detail.get("location", "unknown")
            desc_parts.append(
                f"  FAILED: {f_detail.get('test_name', '?')} — "
                f"{f_detail.get('failure_type', '?')} at {loc}"
            )
            if f_detail.get("expected"):
                desc_parts.append(f"    Expected: {f_detail['expected']}")
            if f_detail.get("actual"):
                desc_parts.append(f"    Actual: {f_detail['actual']}")

        cap = self._infer_capability(failed_task_id)
        deps = self._infer_dependencies(failed_task_id, completed_tasks)

        return [PlannerTask(
            task_id=str(uuid.uuid4()),
            description="\n".join(desc_parts),
            required_capability=cap,
            dependencies=deps,
        )]

    def _infer_capability(self, failed_task_id: str) -> str:
        """Default: return 'code-generation' as most common replan target."""
        return "code-generation"

    def _infer_dependencies(self, failed_task_id: str,
                           completed_tasks: list[str]) -> list[str]:
        """Default: depend on all completed tasks."""
        return list(completed_tasks)


class RuleBasedPlanner(Planner):
    """v1.3.0: Deterministic rule-based planner — no LLM dependency.

    Used for testing the MPC replan loop. replan_path() uses the parent's
    rule-based default. plan() produces a trivial single-task plan.
    """

    def plan(self, goal_description: str, goal_id: str = "",
             context: dict | None = None) -> PlannerPlan:
        """Trivial plan: single task for the goal."""
        plan_id = goal_id or str(uuid.uuid4())
        return PlannerPlan(
            plan_id=plan_id,
            goal_id=goal_id,
            tasks=[PlannerTask(
                task_id=str(uuid.uuid4()),
                description=goal_description,
                required_capability="code-generation",
            )],
            planner_id="rule-based",
            planner_version="1.3.0",
            created_at=time.time(),
        )


class LLMPlanner(Planner):
    """Default LLM-based Planner plugin.

    v1.3.0: Overrides replan_path() to use the LLM provider for intelligent
    replan analysis. Falls back to parent's rule-based default on LLM error.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        config = config or {}
        self.planner_id = config.get("planner_id", "llm-planner")
        self.planner_version = config.get("planner_version", "0.1.0")
        self.max_retries = config.get("max_retries", 2)
        self.system_prompt = config.get("system_prompt", DEFAULT_SYSTEM_PROMPT)

        # Create provider
        self._provider = create_provider(config)

    @property
    def provider_name(self) -> str:
        return self._provider.provider_name()

    @property
    def model(self) -> str:
        return getattr(self._provider, "model", "unknown")

    # ── Plugin Interface ──

    def plan(self, goal_description: str, goal_id: str = "", context: dict | None = None) -> PlannerPlan:
        """Decompose a Goal into an ExecutionPlan."""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Goal: {goal_description}"},
        ]

        response_text = self._call_llm_with_retry(messages)
        plan = self._parse_response(response_text, goal_id or str(uuid.uuid4()))
        self._validate_plan(plan)
        return plan

    def replan(self, goal_description: str, current_plan: PlannerPlan, events: list[dict] | None = None) -> PlannerPlan:
        """Modify an existing plan based on events (failed tasks, new requirements)."""
        events_text = json.dumps(events or [], indent=2)
        existing = json.dumps(current_plan.to_dict(), indent=2)

        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": f"""
Goal: {goal_description}

Current plan (DO NOT remove completed tasks):
{existing}

Recent events that triggered re-planning:
{events_text}

Add new tasks and dependencies to handle the events. Preserve all existing tasks.
Respond with the COMPLETE updated plan as JSON (existing tasks + new tasks).
""",
            },
        ]

        response_text = self._call_llm_with_retry(messages)
        new_plan = self._parse_response(response_text, current_plan.goal_id)

        # Preserve plan identity
        new_plan.plan_id = current_plan.plan_id
        new_plan.planner_id = current_plan.planner_id
        new_plan.planner_version = current_plan.planner_version
        new_plan.version = current_plan.version + 1

        # Merge: keep completed tasks from old plan
        {t.task_id for t in current_plan.tasks}
        for old_t in current_plan.tasks:
            if old_t.task_id not in {t.task_id for t in new_plan.tasks}:
                new_plan.tasks.append(old_t)

        self._validate_plan(new_plan)
        return new_plan

    # ── v1.3.0: LLM-powered replan_path ──

    def replan_path(
        self,
        goal,
        failed_task_id: str,
        failure_context: dict,
        completed_tasks: list[str],
    ) -> list[PlannerTask]:
        """
        v1.3.0: Use LLM to analyze failure context and produce an
        intelligent repair task. Falls back to parent's rule-based
        default on LLM error.

        Calls the LLM provider (OpenAI / DeepSeek / Anthropic) with
        the structured failure context and asks for a focused fix.
        """
        import json as _json

        diag = failure_context.get("diagnosis", {})
        classification = failure_context.get("classification", {})
        verdict = failure_context.get("verdict", {})

        # Build a concise failure summary for the LLM
        failure_summary = _json.dumps({
            "failed_task_id": failed_task_id,
            "verdict": verdict,
            "diagnosis": diag,
            "classification": classification,
            "completed_tasks": completed_tasks,
        }, indent=2, ensure_ascii=False)

        goal_text = goal.get("intent", str(goal)) if isinstance(goal, dict) else str(goal)

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a repair planner. Given a task failure with structured "
                    "diagnostic information (test name, failure type, file:line, "
                    "expected vs actual), produce ONE focused repair task.\n\n"
                    "Output a JSON object with a single 'tasks' array containing "
                    "exactly one task:\n"
                    '{"tasks": [{"description": "...", "required_capability": "..."}]}\n\n'
                    "The task description must include:\n"
                    "- What specific file/line to fix\n"
                    "- What assertion failed and why (expected X, got Y)\n"
                    "- What the fix should accomplish"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Goal: {goal_text}\n\n"
                    f"Failure context:\n{failure_summary}\n\n"
                    "Produce a single repair task based on this diagnostic info. "
                    "Be specific: mention the exact file, line, and assertion to fix."
                ),
            },
        ]

        try:
            response_text = self._call_llm_with_retry(messages)
            data = _json.loads(response_text.strip().lstrip("```json").rstrip("```").strip())
            tasks_data = data.get("tasks", [])
            if tasks_data:
                cap = self._infer_capability(failed_task_id)
                deps = self._infer_dependencies(failed_task_id, completed_tasks)
                return [PlannerTask(
                    task_id=str(uuid.uuid4()),
                    description=tasks_data[0].get("description", "LLM-generated repair"),
                    required_capability=tasks_data[0].get("required_capability", cap),
                    dependencies=deps,
                )]
        except Exception:
            pass  # Fall through to parent's rule-based default

        # Fallback: parent's rule-based replan
        return super().replan_path(
            goal=goal,
            failed_task_id=failed_task_id,
            failure_context=failure_context,
            completed_tasks=completed_tasks,
        )

    # ── LLM Call ──

    def _call_llm_with_retry(self, messages: list[dict]) -> str:
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                return self._provider.chat(messages)
            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    time.sleep(1 * (attempt + 1))  # Linear backoff
        raise RuntimeError(f"LLM call failed after {self.max_retries + 1} attempts: {last_error}")

    # ── Response Parsing ──

    def _parse_response(self, text: str, goal_id: str) -> PlannerPlan:
        """Parse LLM JSON response into a PlannerPlan. v0.9.0: also extracts architecture_delta."""
        # Strip markdown code fences if present
        text = text.strip()
        if text.startswith("```"):
            # Remove opening fence (```json or ```)
            text = re.sub(r"^```(?:json)?\s*\n", "", text)
            # Remove closing fence
            text = re.sub(r"\n```\s*$", "", text)

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse LLM response as JSON: {e}\nRaw response:\n{text[:500]}") from e

        plan = PlannerPlan(
            plan_id=str(uuid.uuid4()),
            goal_id=goal_id,
            planner_id=self.planner_id,
            planner_version=self.planner_version,
            created_at=time.time(),
        )

        tasks_data = data.get("tasks", [])
        for td in tasks_data:
            task = PlannerTask(
                task_id=td.get("task_id", str(uuid.uuid4())),
                description=td.get("description", ""),
                required_capability=td.get("required_capability", ""),
                dependencies=td.get("dependencies", []),
                priority=td.get("priority", "medium"),
                timeout_ms=td.get("timeout_ms", 30000),
            )
            plan.tasks.append(task)

        plan.dependencies = data.get("dependencies", [])

        # v0.9.0: Extract architecture_delta from LLM response
        arch_delta = data.get("architecture_delta")
        if arch_delta and isinstance(arch_delta, dict):
            plan.architecture_delta = {
                "modified_modules": arch_delta.get("modified_modules", []),
                "new_dependencies": arch_delta.get("new_dependencies", []),
                "removed_dependencies": arch_delta.get("removed_dependencies", []),
                "api_changes": arch_delta.get("api_changes", []),
                "data_model_changes": arch_delta.get("data_model_changes", []),
                "risk_level": arch_delta.get("risk_level", "unknown"),
                "explanation": arch_delta.get("explanation", ""),
            }

        return plan

    # ── Validation ──

    def _validate_plan(self, plan: PlannerPlan) -> None:
        """Validate plan structure and reject invalid plans."""
        if not plan.tasks:
            raise ValueError("Plan must contain at least one task")

        task_ids = set()
        for task in plan.tasks:
            # Auto-generate task_id if missing
            if not task.task_id:
                task.task_id = str(uuid.uuid4())

            if task.task_id in task_ids:
                raise ValueError(f"Duplicate task_id: {task.task_id}")
            task_ids.add(task.task_id)

            if not task.required_capability:
                raise ValueError(f"Task '{task.task_id}' has no required_capability")
            if not task.description or len(task.description.strip()) < 3:
                raise ValueError(f"Task '{task.task_id}' has empty or too-short description")

        # Validate dependency references
        for dep in plan.dependencies:
            from_id = dep.get("from_task_id", "")
            to_id = dep.get("to_task_id", "")
            if from_id not in task_ids:
                raise ValueError(f"Dependency references unknown task: {from_id}")
            if to_id not in task_ids:
                raise ValueError(f"Dependency references unknown task: {to_id}")

        # Check acyclicity
        self._check_acyclic(plan, task_ids)

    def _check_acyclic(self, plan: PlannerPlan, task_ids: set) -> None:
        """DFS-based cycle detection."""
        adjacency = {tid: [] for tid in task_ids}
        for dep in plan.dependencies:
            adjacency[dep["from_task_id"]].append(dep["to_task_id"])

        WHITE, GRAY, BLACK = 0, 1, 2
        color = dict.fromkeys(task_ids, WHITE)

        def dfs(node):
            color[node] = GRAY
            for neighbor in adjacency[node]:
                if color[neighbor] == GRAY:
                    raise ValueError(f"Cycle detected in plan: {node} → {neighbor}")
                if color[neighbor] == WHITE:
                    dfs(neighbor)
            color[node] = BLACK

        for tid in task_ids:
            if color[tid] == WHITE:
                dfs(tid)
