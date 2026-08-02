#!/usr/bin/env python3
"""
Agent Wrapper — wraps Anthropic API for all three PoC experiment groups.

Uses Claude API (NOT CLI) for:
  - Exact token counting via response.usage
  - Forced patch format via system prompt + stop_sequences
  - Structured output control

Provides:
  - generate_patch(issue, repo_path) → patch
  - repair_patch(issue, repo_path, diagnosis_text, prev_patch) → patch
  - search_location(issue, repo_path) → location_info
  - review_patch(issue, patch) → verdict
"""

import os
import re
import time

import anthropic

TIMEOUT = 300
# Use settings from ~/.claude/settings.json if ANTHROPIC_BASE_URL is set
# (e.g., DeepSeek as Anthropic-compatible backend)
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
API_KEY = os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get(
    "ANTHROPIC_API_KEY", "")

# Patch-only system prompt — forces clean diff output
PATCH_SYSTEM_PROMPT = (
    "You are a bug-fixing agent. Output ONLY a unified diff patch. "
    "The patch MUST start with '--- a/' on the first line. "
    "Do NOT use markdown fences. Do NOT add explanations. "
    "Every hunk header (@@ ... @@) MUST have correct line numbers."
)


def clean_patch(patch_text: str) -> str:
    """Clean Claude-generated patch: strip markdown, fix common issues."""
    for fence in ["```diff", "```python", "```patch", "```"]:
        patch_text = patch_text.replace(fence, "")
    lines = patch_text.split("\n")
    cleaned = []
    in_patch = False
    for line in lines:
        if line.startswith("--- ") or line.startswith("+++ ") or \
           line.startswith("diff ") or (line.startswith("@@") and "@@" in line):
            in_patch = True
        if in_patch:
            cleaned.append(line)
        elif line.startswith("Index:") or line.startswith("==="):
            cleaned.append(line)
    result = "\n".join(cleaned if cleaned else lines).strip()
    if result and not result.endswith("\n"):
        result += "\n"
    return result


class ClaudeCodeAgent:
    """Wrapper around Anthropic Claude API."""

    def __init__(self, repo_path: str, timeout: int = TIMEOUT,
                 model: str = MODEL):
        self.repo_path = repo_path
        self.timeout = timeout
        self.model = model
        self._call_count = 0
        self._total_input_tokens = 0
        self._total_output_tokens = 0

        if not API_KEY:
            print("  WARNING: ANTHROPIC_AUTH_TOKEN / ANTHROPIC_API_KEY not set.")
        self._client = anthropic.Anthropic(
            api_key=API_KEY,
            base_url=BASE_URL,
            timeout=timeout,
        )

    @property
    def total_tokens_estimate(self) -> int:
        """Exact token count from API usage."""
        return self._total_input_tokens + self._total_output_tokens

    # ── Public API ──

    def generate_patch(self, issue: str) -> dict:
        tree = self._get_tree()
        user_msg = (
            f"Repository structure:\n{tree}\n\n"
            f"Issue:\n{issue[:3000]}\n\n"
            "Generate a unified diff patch to fix this bug."
        )
        return self._call_api(user_msg, system=PATCH_SYSTEM_PROMPT)

    def repair_patch(self, issue: str, diagnosis: str,
                     previous_patch: str) -> dict:
        tree = self._get_tree()
        user_msg = (
            f"Repository structure:\n{tree}\n\n"
            f"Issue:\n{issue[:2000]}\n\n"
            f"Previous (FAILED) patch:\n{previous_patch[:2000]}\n\n"
            f"Test failure diagnosis:\n{diagnosis}\n\n"
            "Fix ONLY the specific failures mentioned above."
        )
        return self._call_api(user_msg, system=PATCH_SYSTEM_PROMPT)

    def repair_patch_full_log(self, issue: str, test_output: str,
                              previous_patch: str) -> dict:
        tree = self._get_tree()
        user_msg = (
            f"Repository structure:\n{tree}\n\n"
            f"Issue:\n{issue[:2000]}\n\n"
            f"Previous (FAILED) patch:\n{previous_patch[:2000]}\n\n"
            f"Test output:\n{test_output[:4000]}\n\n"
            "Read the test output, find the failures, and fix them."
        )
        return self._call_api(user_msg, system=PATCH_SYSTEM_PROMPT)

    def search_location(self, issue: str) -> dict:
        tree = self._get_tree()
        user_msg = (
            f"Repository structure:\n{tree}\n\n"
            f"Issue:\n{issue[:3000]}\n\n"
            "Identify the EXACT files and functions that need modification. "
            "Output one file path per line."
        )
        result = self._call_api(user_msg, system=(
            "You are a code search agent. Output ONLY file paths, "
            "one per line. No explanations."
        ))
        files = re.findall(r'[\w/]+\.py', result.get("patch", ""))
        result["files"] = list(set(files[:5]))
        result["location"] = result.pop("patch", "")
        return result

    def review_patch(self, issue: str, patch: str) -> dict:
        user_msg = (
            f"Issue:\n{issue[:2000]}\n\n"
            f"Patch:\n{patch[:3000]}\n\n"
            "Does this patch correctly fix the issue? Any side effects? "
            "Output ONLY one word: PASS or FAIL, then a brief reason."
        )
        result = self._call_api(user_msg, system=(
            "You are a code reviewer. Output PASS or FAIL on the first line, "
            "then a one-sentence reason."
        ))
        text = result.get("patch", "")
        verdict = "fail" if text.upper().startswith("FAIL") else "pass"
        return {"verdict": verdict, "issues": text,
                "elapsed_s": result.get("elapsed_s", 0)}

    # ── Internal ──

    def _get_tree(self, max_depth: int = 2) -> str:
        repo = self.repo_path
        if not os.path.isdir(repo):
            return f"(repo not available: {repo})"
        lines = []
        for root, dirs, files in os.walk(repo):
            depth = root.replace(repo, "").count(os.sep)
            if depth > max_depth:
                dirs[:] = []
                continue
            dirs[:] = [d for d in sorted(dirs)
                       if not d.startswith('.') and d != '__pycache__']
            rel = root.replace(repo, "").lstrip(os.sep) or "."
            if depth <= 1:
                lines.append(f"{'  ' * depth}{rel}/")
            elif depth == 2:
                py_files = [f for f in sorted(files) if f.endswith('.py')][:8]
                lines.append(f"{'  ' * depth}{rel}/")
                for f in py_files:
                    lines.append(f"{'  ' * (depth+1)}{f}")
            if len(lines) > 100:
                break
        return "\n".join(lines[:120])

    def _call_api(self, user_message: str,
                  system: str = PATCH_SYSTEM_PROMPT) -> dict:
        """Call Anthropic API. Returns {"patch": str, "elapsed_s": float}."""
        self._call_count += 1
        t0 = time.perf_counter()

        try:
            response = self._client.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=system,
                stop_sequences=["```"],
                messages=[{"role": "user", "content": user_message}],
            )
            elapsed = time.perf_counter() - t0

            # Extract text
            output = ""
            for block in response.content:
                if block.type == "text":
                    output += block.text

            # Clean + track tokens
            output = clean_patch(output)
            self._total_input_tokens += response.usage.input_tokens
            self._total_output_tokens += response.usage.output_tokens

        except Exception as e:
            elapsed = time.perf_counter() - t0
            output = f"API_ERROR: {e}"

        return {"patch": output, "elapsed_s": elapsed,
                "call_count": self._call_count}
