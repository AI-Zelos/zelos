#!/usr/bin/env python3
"""
Agent Wrapper — wraps Claude Code CLI for all three PoC experiment groups.

Provides:
  - generate_patch(issue, repo_path) → patch
  - repair_patch(issue, repo_path, diagnosis_text, prev_patch) → patch
  - search_location(issue, repo_path) → location_info

Token estimation: character_count / 4 (rough GPT-4 token equivalence).
"""

import json
import os
import re
import subprocess
import time

TIMEOUT = 300  # seconds per call


class ClaudeCodeAgent:
    """Wrapper around Claude Code CLI."""

    def __init__(self, repo_path: str, timeout: int = TIMEOUT):
        self.repo_path = repo_path
        self.timeout = timeout
        self._call_count = 0
        self._total_output_chars = 0

    @property
    def total_tokens_estimate(self) -> int:
        """Rough estimate: chars / 4. Includes prompt + output."""
        return max(0, self._total_output_chars // 4)

    # ── Public API ──

    def generate_patch(self, issue: str) -> dict:
        """
        Generate a patch from scratch. Returns:
        {"patch": str, "elapsed_s": float, "call_count": int}
        """
        prompt = self._build_fix_prompt(issue, extra_context="")
        return self._call_claude(prompt)

    def repair_patch(self, issue: str, diagnosis: str,
                     previous_patch: str) -> dict:
        """
        Repair a failed patch using structured diagnosis. Returns:
        {"patch": str, "elapsed_s": float, "call_count": int}
        """
        prompt = self._build_repair_prompt(issue, diagnosis, previous_patch)
        return self._call_claude(prompt)

    def repair_patch_full_log(self, issue: str, test_output: str,
                              previous_patch: str) -> dict:
        """
        Repair using full pytest output (baseline behavior). Returns:
        {"patch": str, "elapsed_s": float, "call_count": int}
        """
        prompt = self._build_baseline_repair_prompt(issue, test_output, previous_patch)
        return self._call_claude(prompt)

    def search_location(self, issue: str) -> dict:
        """
        Search for relevant code locations. Returns:
        {"location": str, "files": list[str], "elapsed_s": float}
        """
        prompt = self._build_search_prompt(issue)
        result = self._call_claude(prompt)
        # Extract file paths from response
        files = []
        for m in re.finditer(r'(?:File|file|path)[:\s]+([^\s,]+\.py)', result["patch"]):
            files.append(m.group(1))
        result["files"] = list(set(files[:5]))
        result["location"] = result.pop("patch", "")
        return result

    def review_patch(self, issue: str, patch: str) -> dict:
        """
        Review a patch. Returns:
        {"verdict": "pass"|"fail", "issues": str, "elapsed_s": float}
        """
        prompt = self._build_review_prompt(issue, patch)
        result = self._call_claude(prompt)
        verdict = "fail" if "FAIL" in result.get("patch", "").upper()[:500] else "pass"
        return {
            "verdict": verdict,
            "issues": result.get("patch", ""),
            "elapsed_s": result.get("elapsed_s", 0),
        }

    # ── Prompt Builders ──

    def _build_fix_prompt(self, issue: str, extra_context: str = "") -> str:
        tree = self._get_tree()
        return (
            "You are a bug-fixing agent. Read the issue and project structure, "
            "then output ONLY a unified diff patch. No markdown fences, no explanation.\n\n"
            f"Repository structure:\n{tree}\n\n"
            f"Issue:\n{issue[:3000]}\n"
            f"{extra_context}\n"
            "Output the unified diff patch now:"
        )

    def _build_repair_prompt(self, issue: str, diagnosis: str,
                             previous_patch: str) -> str:
        tree = self._get_tree()
        return (
            "You are a bug-fixing agent. Your previous patch FAILED tests. "
            "Below is a structured diagnosis of the failure. "
            "Fix ONLY the specific failures mentioned. "
            "Output ONLY a unified diff patch. No markdown fences, no explanation.\n\n"
            f"Repository structure:\n{tree}\n\n"
            f"Issue:\n{issue[:2000]}\n\n"
            f"Previous (FAILED) patch:\n{previous_patch[:2000]}\n\n"
            f"Test failure diagnosis:\n{diagnosis}\n\n"
            "Output the corrected unified diff patch now:"
        )

    def _build_baseline_repair_prompt(self, issue: str, test_output: str,
                                      previous_patch: str) -> str:
        tree = self._get_tree()
        # Truncate test output to simulate "agent reads log"
        truncated_log = test_output[:4000]
        return (
            "You are a bug-fixing agent. Your previous patch FAILED tests. "
            "Below is the FULL test output. Read it carefully and fix the bug. "
            "Output ONLY a unified diff patch. No markdown fences, no explanation.\n\n"
            f"Repository structure:\n{tree}\n\n"
            f"Issue:\n{issue[:2000]}\n\n"
            f"Previous (FAILED) patch:\n{previous_patch[:2000]}\n\n"
            f"FULL test output:\n{truncated_log}\n\n"
            "Output the corrected unified diff patch now:"
        )

    def _build_search_prompt(self, issue: str) -> str:
        tree = self._get_tree()
        return (
            "Analyze this issue and identify the EXACT files and functions "
            "that need to be modified. Output file paths and function names only.\n\n"
            f"Repository structure:\n{tree}\n\n"
            f"Issue:\n{issue[:3000]}\n\n"
            "List the files and functions to modify:"
        )

    def _build_review_prompt(self, issue: str, patch: str) -> str:
        return (
            "Review this patch against the issue. Does it correctly fix the bug? "
            "Are there any side effects? Output PASS or FAIL with a brief explanation.\n\n"
            f"Issue:\n{issue[:2000]}\n\n"
            f"Patch:\n{patch[:3000]}\n\n"
            "Review result (PASS or FAIL with explanation):"
        )

    # ── Internal ──

    def _get_tree(self, max_depth: int = 2) -> str:
        """Get a compact project tree for LLM context."""
        repo = self.repo_path
        if not os.path.isdir(repo):
            return f"(repo path not available: {repo})"

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

    def _call_claude(self, prompt: str) -> dict:
        """Call Claude Code CLI. Returns {"patch": str, "elapsed_s": float}."""
        self._call_count += 1
        self._total_output_chars += len(prompt)

        t0 = time.perf_counter()
        try:
            r = subprocess.run(
                ["claude", "--print", "--output-format", "text", prompt],
                capture_output=True, text=True,
                timeout=self.timeout, input="",
            )
            output = r.stdout.strip()
            # Clean markdown fences
            for fence in ["```diff", "```python", "```"]:
                output = output.replace(fence, "").strip()
            elapsed = time.perf_counter() - t0
        except subprocess.TimeoutExpired:
            output = ""
            elapsed = self.timeout
        except FileNotFoundError:
            output = ""
            elapsed = 0
            print("  WARNING: 'claude' CLI not found. Is Claude Code installed?")

        self._total_output_chars += len(output)
        return {"patch": output, "elapsed_s": elapsed, "call_count": self._call_count}
