"""
Mini-SWE-Agent Provider — Integrates mini-swe-agent v2 as a Zelos Runtime Agent.

mini-swe-agent is an MIT-licensed, ~100-line Python coding agent that achieves
74%+ on SWE-bench Verified. It uses a radically simple bash-based execution loop.

v2 API (minisweagent >= 2.0.0):
  DefaultAgent(model=model, env=env, step_limit=N, cost_limit=M)
  LitellmModel(model_name="provider/model-name", model_kwargs={...})
  LocalEnvironment() or DockerEnvironment(...)

Architecture:
  Zelos Runtime → dispatch(task) → MiniSWEAgent.execute(task)
    → mini-swe-agent Agent.run(description)
    → returns {status, artifact} to Runtime

Zelos owns: planning, scheduling, retry, verification, memory, lifecycle.
mini-SWE-agent owns: execution (bash commands → code changes).
"""

import os
from typing import Any

from zelos.task_graph import Task


class MiniSWEAgent:
    """Zelos Agent wrapping mini-swe-agent v2 as a code-fix execution plugin.

    Capabilities provided:
      - code-fix.python: Fix bugs in Python codebases
      - code-generation.python: Generate new Python code/features
      - code-refactor.python: Refactor existing Python code

    Config keys (passed via Runtime.add_agent(config={...})):
      - model_name: LLM with provider prefix (default: "deepseek/deepseek-chat")
                    Examples: "anthropic/claude-sonnet-4-6", "deepseek/deepseek-chat",
                              "openai/gpt-4o", "gpt-4o"
      - api_key: API key (default: from env ANTHROPIC_API_KEY or OPENAI_API_KEY)
      - api_base: API base URL for custom endpoints (default: from env OPENAI_API_BASE)
      - environment: "local" (default) or "docker"
      - work_dir: Working directory for code changes (default: current dir)
      - step_limit: Maximum agent steps (default: 30)
      - cost_limit: Maximum API cost in USD (default: 5.0)
    """

    def __init__(self, name: str = "MiniSWE", **config):
        self.name = name
        self.config = config
        self.agent_id: str | None = None

        # Model config — resolve from config or environment.
        # Supports both Anthropic-native and OpenAI-compatible endpoints.
        # DeepSeek users: ANTHROPIC_AUTH_TOKEN + ANTHROPIC_BASE_URL → Anthropic format.
        self.api_key = config.get(
            "api_key",
            os.getenv("ANTHROPIC_API_KEY",
                os.getenv("ANTHROPIC_AUTH_TOKEN",
                    os.getenv("OPENAI_API_KEY", ""))),
        )
        self.api_base = config.get(
            "api_base",
            os.getenv("ANTHROPIC_BASE_URL",
                os.getenv("OPENAI_API_BASE", None)),
        )

        # Detect endpoint type: "anthropic" or "openai"
        if self.api_base and "anthropic" in self.api_base.lower():
            self._endpoint_type = "anthropic"
        else:
            self._endpoint_type = "openai"

        # Default model: use ANTHROPIC_MODEL for Anthropic endpoints,
        # ZELOS_MODEL for custom, fallback to deepseek-v4-pro
        default_model = os.getenv("ANTHROPIC_MODEL",
                        os.getenv("ZELOS_MODEL",
                            "deepseek/deepseek-chat"))
        self.model_name = config.get("model_name", default_model)

        # Environment config
        self.environment_type = config.get("environment", "local")
        self.work_dir = config.get("work_dir", os.getcwd())

        # Agent behavior
        self.step_limit = config.get("step_limit", 30)
        self.cost_limit = config.get("cost_limit", 5.0)

        # Lazy-initialized mini-swe-agent instance
        self._agent = None

    # ── Zelos Runtime Agent Contract ──

    def execute(self, task: Task) -> dict[str, Any]:
        """Execute a Zelos Task using mini-swe-agent v2.

        Receives a Task from the Zelos Runtime, translates it to a mini-swe-agent
        task string, runs the agent, and returns the result in Zelos format.

        Args:
            task: Zelos Task with description, required_capability, etc.

        Returns:
            {"status": "completed", "artifact": {...}} on success
            {"status": "failed", "error": {...}} on failure
        """
        task_prompt = self._build_prompt(task)

        try:
            result = self._get_agent().run(task_prompt)

            exit_status = result.get("exit_status", "unknown")
            submission = result.get("submission", "")
            info = result.get("info", {})

            # "Submitted" means the agent completed its work.
            # It may or may not have a git diff — files may be modified in-place.
            if exit_status == "Submitted":
                # Capture git diff from work dir as an optional patch
                patch = submission or self._capture_diff()

                return {
                    "status": "completed",
                    "artifact": {
                        "content_type": "text/x-diff",
                        "content": {
                            "task_id": task.task_id,
                            "capability": task.required_capability,
                            "exit_status": exit_status,
                            "patch": patch,
                            "has_patch": bool(patch),
                            "model": self.model_name,
                            "agent": "mini-swe-agent",
                            "cost": info.get("model_stats", {}).get("instance_cost", 0),
                            "api_calls": info.get("model_stats", {}).get("api_calls", 0),
                        },
                    },
                }
            else:
                # Agent hit a limit (step/cost/time) or format error
                return {
                    "status": "failed",
                    "error": {
                        "code": f"mini_swe_agent_{exit_status}",
                        "message": f"Agent exited with status '{exit_status}'",
                        "detail": {
                            "exit_status": exit_status,
                            "model": self.model_name,
                        },
                    },
                }
        except Exception as e:
            return {
                "status": "failed",
                "error": {
                    "code": "mini_swe_agent_error",
                    "message": str(e),
                },
            }

    # ── Internal ──

    # Class-level cache for default templates (loaded from mini-swe-agent YAML config)
    _default_templates: dict | None = None

    def _normalize_model_name(self) -> str:
        """Normalize model name for litellm based on the endpoint type.

        Anthropic endpoint (ANTHROPIC_BASE_URL):
          deepseek-v4-pro → anthropic/deepseek-v4-pro   (no 'anthropic/' prefix in name)
          deepseek/deepseek-chat → anthropic/deepseek-chat (swap provider prefix)

        OpenAI endpoint (OPENAI_API_BASE):
          deepseek/deepseek-chat → openai/deepseek-chat (swap to openai/)
          anthropic/claude-sonnet-4-6 → unchanged (already correct)

        Without any custom api_base: unchanged.
        """
        model = self.model_name
        if not self.api_base:
            return model

        provider = model.split("/")[0] if "/" in model else ""
        model_id = model.split("/", 1)[1] if "/" in model else model

        if self._endpoint_type == "anthropic":
            # For Anthropic endpoints, ensure anthropic/ prefix
            if provider == "anthropic":
                return model
            return f"anthropic/{model_id}"

        # OpenAI endpoint: rewrite known providers to openai/
        if provider in ("deepseek", "zhipuai", "moonshot", "minimax"):
            return f"openai/{model_id}"

        return model

    @classmethod
    def _load_default_templates(cls) -> dict:
        """Load system_template and instance_template from mini-swe-agent defaults.

        Reads the YAML config file directly to avoid triggering litellm imports
        during template loading (which would validate API keys prematurely).
        """
        if cls._default_templates is not None:
            return cls._default_templates

        try:
            import importlib.util
            import yaml

            # Resolve minisweagent package dir without importing it (avoids litellm init)
            spec = importlib.util.find_spec("minisweagent")
            if spec and spec.origin:
                from pathlib import Path

                pkg_dir = Path(spec.origin).parent
                config_path = pkg_dir / "config" / "default.yaml"
                if config_path.exists():
                    with open(config_path) as f:
                        cfg = yaml.safe_load(f).get("agent", {})
                    cls._default_templates = {
                        "system_template": cfg.get("system_template", ""),
                        "instance_template": cfg.get("instance_template", ""),
                    }
                    return cls._default_templates
        except Exception:
            pass

        # Fallback: minimal templates
        cls._default_templates = {
            "system_template": (
                "You are a helpful assistant that can interact with a computer.\n"
                "Your response must contain exactly ONE bash code block.\n"
                "Format your response with a THOUGHT section and a bash command block.\n"
            ),
            "instance_template": (
                "Please solve this issue: {{task}}\n\n"
                "You can execute bash commands and edit files.\n"
                "When done, run: echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\n"
            ),
        }
        return cls._default_templates

    def _get_agent(self):
        """Lazy-init the mini-swe-agent v2 DefaultAgent instance."""
        if self._agent is None:
            from minisweagent.agents.default import DefaultAgent
            from minisweagent.models.litellm_model import LitellmModel
            from minisweagent.environments.local import LocalEnvironment

            # Load default templates
            templates = self._load_default_templates()

            # Set API key env vars for litellm (handles DeepSeek's ANTHROPIC_AUTH_TOKEN)
            if self.api_key:
                if self._endpoint_type == "anthropic":
                    os.environ.setdefault("ANTHROPIC_API_KEY", self.api_key)
                else:
                    os.environ.setdefault("OPENAI_API_KEY", self.api_key)
            if self.api_base:
                os.environ.setdefault("ANTHROPIC_BASE_URL", self.api_base)

            # Normalize model name for the endpoint type
            model_name = self._normalize_model_name()

            # Build model_kwargs for litellm (for custom API endpoints)
            model_kwargs = {}
            if self.api_key:
                model_kwargs["api_key"] = self.api_key
            if self.api_base:
                model_kwargs["api_base"] = self.api_base

            model = LitellmModel(
                model_name=model_name,
                model_kwargs=model_kwargs,
                cost_tracking="ignore_errors",  # tolerate unknown model names (e.g. custom proxies)
            )

            env_kwargs = {}
            if self.work_dir:
                env_kwargs["cwd"] = self.work_dir

            environment = LocalEnvironment(**env_kwargs)

            self._agent = DefaultAgent(
                model=model,
                env=environment,
                system_template=templates["system_template"],
                instance_template=templates["instance_template"],
                step_limit=self.step_limit,
                cost_limit=self.cost_limit,
            )

        return self._agent

    def _capture_diff(self) -> str:
        """Capture git diff in the working directory as the submission patch.

        When mini-swe-agent modifies files in-place (LocalEnvironment), the
        changes are on disk but may not be included in the run() result's
        submission field. We capture them via git diff.
        """
        import subprocess

        try:
            result = subprocess.run(
                ["git", "diff", "--no-color"],
                cwd=self.work_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout.strip()
        except Exception:
            return ""

    @staticmethod
    def _build_prompt(task: Task) -> str:
        """Translate a Zelos Task into a mini-swe-agent prompt.

        The prompt guides mini-swe-agent to work on the codebase and
        produce a concrete fix or implementation.
        """
        description = task.description
        capability = task.required_capability

        # Map capability to prompt style
        capability_hints = {
            "code-fix.python": (
                f"Fix the following issue in this Python codebase:\n\n{description}\n\n"
                "Instructions:\n"
                "1. First, search for and read the relevant source files\n"
                "2. Identify the root cause of the issue\n"
                "3. Make the necessary code changes to fix it\n"
                "4. Verify your fix by running any related tests\n"
                "5. Submit your fix with COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"
            ),
            "code-generation.python": (
                f"Implement the following feature/change in this Python codebase:\n\n{description}\n\n"
                "Instructions:\n"
                "1. First, explore the codebase structure to understand the context\n"
                "2. Write the necessary code changes\n"
                "3. Verify your changes work correctly\n"
                "4. Submit your implementation with COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"
            ),
            "code-refactor.python": (
                f"Refactor the following in this Python codebase:\n\n{description}\n\n"
                "Instructions:\n"
                "1. First, read and understand the existing code\n"
                "2. Make the refactoring changes while preserving behavior\n"
                "3. Run tests to ensure nothing broke\n"
                "4. Submit your refactoring with COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"
            ),
        }

        return capability_hints.get(
            capability,
            f"Complete this task:\n\n{description}",
        )
