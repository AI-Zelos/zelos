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

from openai import OpenAI

TIMEOUT = 300
# DeepSeek OpenAI-compatible endpoint (more stable than Anthropic-compatible)
MODEL = "deepseek-chat"
BASE_URL = "https://api.deepseek.com/v1"
API_KEY = os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get(
    "DEEPSEEK_API_KEY", os.environ.get("ANTHROPIC_API_KEY", ""))

# Patch-only system prompt — forces clean diff output
PATCH_SYSTEM_PROMPT = (
    "You are a bug-fixing agent. Read the current file content and the "
    "issue, then output the COMPLETE corrected file.\n\n"
    "CRITICAL RULES:\n"
    "1. Output the ENTIRE file — every import, every class, every function.\n"
    "2. Preserve ALL original code. Only change the buggy part.\n"
    "3. Use the EXACT same indentation as the original (4 spaces).\n"
    "4. Output inside a ```python code block.\n"
    "5. The output MUST be syntactically valid Python."
)


def clean_patch(patch_text: str, repo_dir: str = "") -> str:
    """Clean LLM output: extract valid unified diff block, strip preamble.

    If patch has @@ hunks but missing ---/+++ headers, tries to
    auto-detect file path from repo_dir or hunk context.
    """
    if not patch_text:
        return ""

    # Remove markdown fences
    for fence in ["```diff", "```python", "```patch", "```"]:
        patch_text = patch_text.replace(fence, "")

    lines = patch_text.split("\n")

    # Strategy 1: Find first --- line and extract from there
    for i, line in enumerate(lines):
        if line.startswith("--- ") and i + 1 < len(lines):
            if lines[i + 1].startswith("+++ "):
                result = "\n".join(lines[i:]).strip()
                if result and not result.endswith("\n"):
                    result += "\n"
                return result

    # Strategy 2: Find first @@ hunk, try to construct headers
    for i, line in enumerate(lines):
        if line.startswith("@@") and "@@" in line:
            # Extract the hunk and all following content
            hunk_lines = lines[i:]
            # Try to infer file path from hunk function name context
            match = re.search(r'@@[^@]*@@\s*(.*)', line)
            func_hint = match.group(1).strip() if match else ""
            # Search repo for file containing this function
            filepath = _find_file_by_function(repo_dir, func_hint) if repo_dir else ""
            if filepath:
                relpath = filepath.replace(repo_dir + "/", "")
                result = f"--- a/{relpath}\n+++ b/{relpath}\n" + "\n".join(hunk_lines)
            else:
                result = "\n".join(hunk_lines)
            if result and not result.endswith("\n"):
                result += "\n"
            return result

    # Strategy 3: Return original (best effort)
    result = patch_text.strip()
    if result and not result.endswith("\n"):
        result += "\n"
    return result


def _find_file_by_function(repo_dir: str, func_name: str) -> str:
    """Search repo for a Python file containing a function definition."""
    if not repo_dir or not func_name:
        return ""
    func_name = func_name.split("(")[0].strip().rstrip(":")
    if not func_name or len(func_name) < 3:
        return ""
    import subprocess as _sp
    try:
        r = _sp.run(
            ["grep", "-rl", f"def {func_name}", repo_dir],
            capture_output=True, text=True, timeout=10,
        )
        files = [f for f in r.stdout.strip().split("\n") if f.endswith(".py")]
        if files:
            return files[0]
    except Exception:
        pass
    return ""


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
        self._client = OpenAI(
            api_key=API_KEY,
            base_url=BASE_URL,
            timeout=90.0,
            max_retries=0,
        )

    @property
    def total_tokens_estimate(self) -> int:
        """Exact token count from API usage."""
        return self._total_input_tokens + self._total_output_tokens

    # ── Public API ──

    def generate_patch(self, issue: str, target_file: str = "") -> dict:
        tree = self._get_tree()
        # Read target file content (just the relevant section)
        file_content = ""
        if target_file:
            fp = os.path.join(self.repo_path, target_file)
            if os.path.exists(fp):
                with open(fp) as fh:
                    full = fh.read()
                # Only send ~3000 chars around the relevant function
                file_content = full[:3000]  # Start of file is most informative

        user_msg = (
            f"Repository structure:\n{tree}\n\n"
            f"Issue:\n{issue[:3000]}\n\n"
        )
        if file_content:
            user_msg += (
                f"File to fix: {target_file}\n"
                f"Current content:\n```python\n{file_content}\n```\n\n"
                "Output the COMPLETE corrected file content in a ```python block."
            )
        else:
            user_msg += "Find and fix the bug. Output the COMPLETE corrected file content."
        return self._call_api(user_msg, system=PATCH_SYSTEM_PROMPT,
                              hint_filepath=target_file)

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
        """Multi-step search with tool access. LLM can grep, read files, list dirs."""
        tree = self._get_tree()
        # Extract key terms from issue for initial grep
        import re as _re
        # Priority 1: backtick-quoted identifiers (most specific)
        backticked = _re.findall(r'`([^`]+)`', issue)
        # Priority 2: ClassName.method or module.ClassName patterns
        qualified = _re.findall(r'\b([A-Z]\w*\.\w+)', issue)
        # Priority 3: CamelCase identifiers (class names)
        camel = _re.findall(r'\b([A-Z]\w{2,})\b', issue)
        # Priority 4: quoted strings
        quoted = _re.findall(r'"([^"]+)"|\'([^\']+)\'', issue)
        keywords = []
        for t in backticked[:5] + qualified[:5] + camel[:5]:
            if len(t) > 3 and not t.startswith('http'):
                keywords.append(t.strip())
        # Dedupe preserving order
        seen = set()
        keywords = [k for k in keywords if not (k in seen or seen.add(k))]

        # Run initial grep for top keywords, show keyword→files mapping
        import subprocess as _sp
        grep_hits = []
        grep_detail = []
        for kw in keywords[:8]:
            try:
                # Grep for the keyword, and also try "class <kw>" for class names
                patterns = [kw]
                if kw[0].isupper():  # Looks like a class name
                    patterns.append(f"class {kw}")
                for pat in patterns[:2]:
                    r = _sp.run(
                        ["grep", "-rln", "--include=*.py", pat, self.repo_path],
                        capture_output=True, text=True, timeout=15,
                    )
                    files = [f.replace(self.repo_path + "/", "")
                            for f in r.stdout.strip().split("\n")
                            if f.endswith(".py") and "test" not in f.lower()]
                    # Prefer files that match "class <Name>" (definition) over usage
                    if "class " in pat:
                        for f in files:
                            grep_detail.append(f"  grep 'class {kw}' → {f}")
                            grep_hits.insert(0, f)  # Insert at front
                    else:
                        for f in files[:2]:
                            grep_detail.append(f"  grep '{kw}' → {f}")
                        grep_hits.extend(files[:2])
            except Exception:
                pass
        grep_hits = list(dict.fromkeys(grep_hits))[:15]  # dedupe preserving order
        grep_text = "\n".join(grep_detail[:20]) if grep_detail else "(no grep matches)"
        # Also read first 30 lines of top 3 hits for context
        file_previews = ""
        for f in grep_hits[:3]:
            fp = os.path.join(self.repo_path, f)
            if os.path.isfile(fp):
                with open(fp) as fh:
                    preview = "".join(fh.readlines()[:30])
                file_previews += f"\n=== {f} (first 30 lines) ===\n{preview}"

        # Build search prompt with grep results + tool access
        user_msg = (
            f"Repository structure:\n{tree}\n\n"
            f"Issue:\n{issue[:3000]}\n\n"
            f"Grep results for keywords:\n{grep_text}\n"
            f"{file_previews}\n\n"
            "You have access to these tools:\n"
            "- grep <keyword>: search for a keyword in the repo\n"
            "- read <filepath>: read first 50 lines of a file\n"
            "- list <dirpath>: list files in a directory\n\n"
            "To use a tool, output: TOOL: <tool> <arg>\n"
            "When confident, output: FILES: (one file path per line)\n\n"
            "Find the files that need to be modified to fix this issue."
        )

        system = (
            "You are a code search agent with tool access. "
            "Use tools to explore the codebase, then output the exact files "
            "to modify. Output FILES: on the final line."
        )

        conversation = [{"role": "user", "content": user_msg}]
        found_files = list(grep_hits[:3])  # Start with grep results

        for _round in range(3):  # Max 3 tool-calling rounds
            msgs = [{"role": "system", "content": system}] + conversation
            response = self._client.chat.completions.create(
                model=MODEL, max_tokens=1024, messages=msgs, timeout=30,
            )
            text = response.choices[0].message.content or ""
            self._total_input_tokens += response.usage.prompt_tokens
            self._total_output_tokens += response.usage.completion_tokens

            if "FILES:" in text:
                # Extract file list
                files_section = text.split("FILES:", 1)[1]
                for line in files_section.split("\n"):
                    line = line.strip()
                    if line.endswith(".py") and not line.startswith("TOOL"):
                        if line not in found_files:
                            found_files.append(line)
                break

            if "TOOL:" in text:
                tool_line = [l for l in text.split("\n") if "TOOL:" in l]
                if tool_line:
                    cmd = tool_line[0].split("TOOL:", 1)[1].strip()
                    result_text = self._execute_tool(cmd)
                    conversation.append({"role": "assistant", "content": text})
                    conversation.append({"role": "user", "content": f"RESULT:\n{result_text}"})
                    # Also extract any file paths mentioned
                    for f in _re.findall(r'[\w/]+\.py', result_text):
                        if f not in found_files and "test" not in f.lower():
                            found_files.append(f)
                    continue

            # No TOOL or FILES → treat as final answer
            for f in _re.findall(r'[\w/]+\.py', text):
                if f not in found_files and "test" not in f.lower():
                    found_files.append(f)
            break

        return {"files": found_files[:5], "location": "\n".join(found_files[:5]),
                "elapsed_s": 0}

    def _execute_tool(self, cmd: str) -> str:
        """Execute a tool command: grep, read, or list."""
        import subprocess as _sp
        parts = cmd.split(None, 1)
        tool = parts[0] if parts else ""
        arg = parts[1] if len(parts) > 1 else ""

        try:
            if tool == "grep":
                r = _sp.run(
                    ["grep", "-rl", "--include=*.py", arg, self.repo_path],
                    capture_output=True, text=True, timeout=15,
                )
                return r.stdout[:2000] or "(no matches)"
            elif tool == "read":
                fp = os.path.join(self.repo_path, arg)
                if os.path.isfile(fp):
                    with open(fp) as fh:
                        lines = fh.readlines()[:50]
                    return "".join(lines)
                return f"File not found: {arg}"
            elif tool == "list":
                dp = os.path.join(self.repo_path, arg)
                if os.path.isdir(dp):
                    return "\n".join(sorted(os.listdir(dp))[:30])
                return f"Dir not found: {arg}"
            else:
                return f"Unknown tool: {tool}"
        except Exception as e:
            return f"Error: {e}"

    def search_location_legacy(self, issue: str) -> dict:
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
                  system: str = PATCH_SYSTEM_PROMPT,
                  hint_filepath: str = "") -> dict:
        """Call API with 90s timeout. Parse code block → git diff."""
        self._call_count += 1
        t0 = time.perf_counter()

        try:
            messages = [{"role": "system", "content": system},
                       {"role": "user", "content": user_message}]
            response = self._client.chat.completions.create(
                model=MODEL, max_tokens=8192, messages=messages,
                timeout=90,
            )
            elapsed = time.perf_counter() - t0
            output = response.choices[0].message.content or ""
            self._total_input_tokens += response.usage.prompt_tokens
            self._total_output_tokens += response.usage.completion_tokens
            patch = self._file_content_to_patch(output, hint_filepath)

        except Exception as e:
            elapsed = time.perf_counter() - t0
            patch = f"API_ERROR: {e}"

        return {"patch": patch, "elapsed_s": elapsed,
                "call_count": self._call_count}

    def _file_content_to_patch(self, llm_output: str,
                                hint_filepath: str = "") -> str:
        """Extract code block from LLM output, generate real git diff.

        Parsing: finds ```python...``` block. If hint_filepath is given,
        uses it directly. Otherwise infers from code content.
        """
        import subprocess as _sp

        lines = llm_output.split("\n")
        code_start = -1
        code_end = -1

        # Find ```python ... ``` code block
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("```") and code_start < 0:
                code_start = i + 1
            elif stripped == "```" and code_start > 0:
                code_end = i
                break

        if code_start < 0:
            return ""
        if code_end < 0:
            # No closing ``` — use rest of output as code
            code = "\n".join(lines[code_start:])

        code = "\n".join(lines[code_start:code_end])
        if len(code.strip()) < 20:
            return ""

        # Determine file path
        filepath = hint_filepath
        if not filepath:
            # Try FILEPATH: prefix
            for line in lines[:code_start]:
                if line.startswith("FILEPATH:") or line.startswith("FILE:"):
                    filepath = line.split(":", 1)[1].strip()
                    break
        if not filepath:
            # Infer from django/http pattern in code imports
            for line in code.split("\n")[:10]:
                if "from django." in line:
                    parts = line.split()[1].split(".")
                    if len(parts) >= 3:
                        filepath = "/".join(parts[:3]) + ".py"
                        break
        if not filepath:
            return ""  # Can't determine file path

        # Write corrected file → git diff → restore
        full_path = os.path.join(self.repo_path, filepath)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        orig = ""
        if os.path.exists(full_path):
            with open(full_path) as f:
                orig = f.read()

        with open(full_path, "w") as f:
            f.write(code)

        try:
            r = _sp.run(
                ["git", "diff", "HEAD", "--", filepath],
                capture_output=True, text=True, timeout=10,
                cwd=self.repo_path,
            )
            patch = r.stdout.strip()
        except Exception:
            patch = ""

        # Restore original
        if orig:
            with open(full_path, "w") as f:
                f.write(orig)
        else:
            _sp.run(["git", "checkout", "--", filepath],
                   capture_output=True, cwd=self.repo_path, timeout=10)

        return patch if patch else llm_output

        # Write corrected file, then git diff
        full_path = os.path.join(self.repo_path, filepath)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        # Save original
        orig = ""
        if os.path.exists(full_path):
            with open(full_path) as f:
                orig = f.read()

        # Write corrected version
        with open(full_path, "w") as f:
            f.write(code)

        # Generate diff against HEAD (not working tree, which might be dirty)
        try:
            r = _sp.run(
                ["git", "diff", "HEAD", "--", filepath],
                capture_output=True, text=True, timeout=10,
                cwd=self.repo_path,
            )
            patch = r.stdout.strip()
        except Exception:
            patch = ""

        # Restore original
        if orig:
            with open(full_path, "w") as f:
                f.write(orig)
        else:
            _sp.run(["git", "checkout", "--", filepath],
                   capture_output=True, cwd=self.repo_path, timeout=10)

        return patch if patch else llm_output  # fallback to raw output


# ═══════════════════════════════════════════════════════════════
# Shared utility: apply patch and run quick validation
# ═══════════════════════════════════════════════════════════════

def _fix_patch_headers(patch: str, repo_dir: str) -> str:
    """If patch is missing file headers, try to infer them from repo."""
    lines = patch.split("\n")
    # Check if first non-empty line is a hunk (@@), missing ---/+++ headers
    first_real = ""
    for line in lines:
        if line.strip():
            first_real = line.strip()
            break
    if first_real.startswith("@@") and not any(
        l.startswith("--- ") or l.startswith("+++ ") for l in lines[:3]
    ):
        # Try to find the file path from hunk context or repo structure
        # Search for a common file mentioned in the issue or repo
        # For now, try common paths from the hunk
        for root, dirs, files in os.walk(repo_dir):
            for f in files:
                if f.endswith(".py") and not f.startswith("_"):
                    # Try the most common target
                    pass
            break
        # Fallback: guess from known patterns
        # Most django patches target django/http/response.py or similar
        # Just add a generic header — git apply will reject if wrong anyway
        # Better: pass through as-is and let patch -p1 try
        pass
    return patch


def apply_and_verify_patch(patch: str, instance_id: str,
                           repo_dir: str) -> dict:
    """
    Apply patch using multiple methods, then syntax-check changed files.

    Returns: {"all_passed": bool, "raw_output": str, "exit_code": int}
    """
    import subprocess as _sp
    import sys as _sys

    if not os.path.isdir(repo_dir):
        return {"all_passed": False, "raw_output": "repo not found", "exit_code": -1}
    if not patch or len(patch.strip()) < 20:
        return {"all_passed": False, "raw_output": "Empty or too-short patch", "exit_code": -1}

    patch = clean_patch(patch)
    if not patch or len(patch.strip()) < 20:
        return {"all_passed": False, "raw_output": "Patch empty after cleaning", "exit_code": -1}
    pf = f"/tmp/zelos_poc_{instance_id.replace('/', '_')}.patch"
    with open(pf, "w") as f:
        f.write(patch)

    apply_ok = False
    apply_error = ""

    # Method 1: git apply
    r = _sp.run(["git", "apply", "--check", pf],
                capture_output=True, text=True, timeout=30, cwd=repo_dir)
    if r.returncode == 0:
        _sp.run(["git", "apply", pf], capture_output=True, cwd=repo_dir, timeout=10)
        apply_ok = True
    else:
        # Method 2: git apply --reject
        r2 = _sp.run(["git", "apply", "--reject", "--whitespace=fix", pf],
                     capture_output=True, text=True, timeout=30, cwd=repo_dir)
        if r2.returncode == 0:
            apply_ok = True
        else:
            # Method 3: patch -p1
            with open(pf) as fh:
                r3 = _sp.run(["patch", "-p1", "-f", "--dry-run"],
                            stdin=fh, capture_output=True, text=True,
                            timeout=30, cwd=repo_dir)
            if r3.returncode == 0:
                with open(pf) as fh:
                    _sp.run(["patch", "-p1", "-f"], stdin=fh,
                           capture_output=True, text=True, timeout=10, cwd=repo_dir)
                apply_ok = True
            else:
                apply_error = (
                    f"git apply: {r.stderr[:300]}\n"
                    f"git apply --reject: {r2.stderr[:300]}\n"
                    f"patch: {r3.stderr[:300]}"
                )

    if os.path.exists(pf):
        os.remove(pf)

    if not apply_ok:
        return {"all_passed": False, "raw_output": apply_error, "exit_code": -1}

    # Syntax check changed Python files
    changed_files = []
    for line in patch.split("\n"):
        if line.startswith("+++ b/"):
            f = line[6:].split("\t")[0]
            if f != "/dev/null" and f.endswith(".py"):
                changed_files.append(os.path.join(repo_dir, f))

    syntax_ok = True
    syntax_output = ""
    for cf in changed_files[:5]:
        if os.path.exists(cf):
            r = _sp.run([_sys.executable, "-m", "py_compile", cf],
                       capture_output=True, text=True, timeout=30)
            if r.returncode != 0:
                syntax_ok = False
                syntax_output += f"Syntax error in {cf}:\n{r.stderr[:500]}\n"

    # Revert
    _sp.run(["git", "checkout", "--", "."], capture_output=True,
            cwd=repo_dir, timeout=10)
    _sp.run(["git", "clean", "-fd"], capture_output=True,
            cwd=repo_dir, timeout=10)

    all_passed = apply_ok and syntax_ok
    output = syntax_output or (
        f"Patch applied OK, syntax OK ({len(changed_files)} files)"
    )
    return {"all_passed": all_passed, "raw_output": output,
            "exit_code": 0 if all_passed else -1}


def checkout_instance_commit(instance: dict, repo_dir: str) -> bool:
    """Checkout the SWE-bench instance's base_commit. Returns True on success."""
    import subprocess as _sp
    commit = instance.get("base_commit", "")
    if not commit:
        return True  # No commit specified, assume repo is already correct
    try:
        # Clean working tree first
        _sp.run(["git", "checkout", "--", "."],
               capture_output=True, cwd=repo_dir, timeout=30)
        _sp.run(["git", "clean", "-fd"],
               capture_output=True, cwd=repo_dir, timeout=10)
        # Checkout target commit
        r = _sp.run(["git", "checkout", commit],
                   capture_output=True, text=True, timeout=30, cwd=repo_dir)
        return r.returncode == 0
    except Exception:
        return False
