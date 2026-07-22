"""
Phase 2 Verifier Framework — CodeReviewer, SecurityScanner, FactChecker.

Extends Phase 1's SchemaVerifier + VerificationGate.
"""
import re
import ast
from typing import Any, Dict, List, Optional

from .verifier import Verifier, Verdict, VerificationCriteria


class CodeReviewer(Verifier):
    """Analyzes code for syntax errors, anti-patterns, and basic quality issues."""

    PATTERNS = {
        "python": {
            "eval_usage": (r"\beval\s*\(", "error", "Use of eval() is dangerous and should be avoided"),
            "exec_usage": (r"\bexec\s*\(", "error", "Use of exec() is dangerous and should be avoided"),
            "hardcoded_password": (r"(password|passwd|pwd|secret|api_key)\s*=\s*[\"'][^\"']+[\"']",
                                   "warning", "Hardcoded credential detected"),
            "bare_except": (r"except\s*:", "warning", "Bare except clause — specify exception type"),
            "print_debug": (r"\bprint\s*\(", "info", "Debug print statement found"),
        },
        "javascript": {
            "eval_usage": (r"\beval\s*\(", "error", "Use of eval() is dangerous"),
            "innerHTML": (r"\.innerHTML\s*=", "warning", "innerHTML assignment may cause XSS"),
            "document_write": (r"document\.write\s*\(", "warning", "document.write() is discouraged"),
        },
        "typescript": {
            "eval_usage": (r"\beval\s*\(", "error", "Use of eval() is dangerous"),
            "any_type": (r":\s*any\b", "info", "Using 'any' type — consider a more specific type"),
        },
    }

    def __init__(self, config: Optional[Dict] = None):
        super().__init__(verifier_id="code-reviewer", config=config)

    def verify(self, artifact_content: Any, criteria: VerificationCriteria) -> Verdict:
        language = criteria.options.get("language", "python")
        code = self._extract_code(artifact_content)
        if not code:
            return Verdict("passed", 1.0, self.verifier_id, summary="No code content to review")

        patterns = self.PATTERNS.get(language, self.PATTERNS["python"])
        issues = []

        for name, (pattern, severity, message) in patterns.items():
            matches = re.finditer(pattern, code, re.IGNORECASE)
            for m in matches:
                line = code[:m.start()].count("\n") + 1
                issues.append({
                    "severity": severity,
                    "message": message,
                    "rule_id": name,
                    "location": f"line {line}",
                })

        # Syntax check for Python
        if language == "python":
            try:
                ast.parse(code)
            except SyntaxError as e:
                issues.append({
                    "severity": "error",
                    "message": f"Syntax error: {e.msg}",
                    "rule_id": "syntax_check",
                    "location": f"line {e.lineno}",
                })

        error_count = sum(1 for i in issues if i["severity"] == "error")
        warning_count = sum(1 for i in issues if i["severity"] == "warning")

        if error_count > 0:
            return Verdict("failed", max(0, 1.0 - error_count * 0.3), self.verifier_id,
                          issues=issues, summary=f"{error_count} error(s), {warning_count} warning(s)")
        if warning_count > 0:
            return Verdict("passed", 0.8, self.verifier_id, issues=issues,
                          summary=f"{warning_count} warning(s)")
        return Verdict("passed", 1.0, self.verifier_id, summary="Code review passed")

    @staticmethod
    def _extract_code(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, dict):
            for key in ("code", "content", "source", "result", "text"):
                if key in content:
                    val = content[key]
                    return val if isinstance(val, str) else str(val)
            return str(content)
        return str(content)


class SecurityScanner(Verifier):
    """Scans code and text for common security vulnerabilities."""

    RULES = [
        ("sql_injection_concat", r'(?:SELECT|INSERT|UPDATE|DELETE)\s.*\+',
         "error", "Potential SQL injection: string concatenation in SQL query"),
        ("sql_injection_format", r'(?:SELECT|INSERT|UPDATE|DELETE)\s.*%\s*\(.*\)',
         "error", "Potential SQL injection: string formatting in SQL query"),
        ("sql_injection_fstring", r'(?:SELECT|INSERT|UPDATE|DELETE)\s.*f[\"\'][{].*[}].*[\"\']',
         "error", "Potential SQL injection: f-string in SQL query"),
        ("xss_innerHTML", r"\.innerHTML\s*=", "error", "XSS vulnerability: innerHTML assignment"),
        ("hardcoded_credential", r"(?:password|passwd|secret|token|api[_-]?key)\s*=\s*[\"'][^\"']{3,}[\"']",
         "error", "Hardcoded credential in source code"),
        ("command_injection", r"(?:os\.system|subprocess\.call|exec\s*\(|popen)\s*\(.*\+",
         "error", "Potential command injection: user input in system call"),
        ("open_redirect", r"redirect\s*\(\s*request\.", "warning", "Potential open redirect"),
        ("unsafe_deserialization", r"(?:pickle\.loads|yaml\.load\s*\()", "error",
         "Unsafe deserialization detected"),
    ]

    def __init__(self, config: Optional[Dict] = None):
        super().__init__(verifier_id="security-scanner", config=config)

    def verify(self, artifact_content: Any, criteria: VerificationCriteria) -> Verdict:
        text = self._to_text(artifact_content)
        if not text:
            return Verdict("passed", 1.0, self.verifier_id, summary="No content to scan")

        issues = []
        for rule_id, pattern, severity, message in self.RULES:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                line = text[:m.start()].count("\n") + 1
                issues.append({
                    "severity": severity, "message": message,
                    "rule_id": rule_id, "location": f"line {line}",
                })

        error_count = sum(1 for i in issues if i["severity"] == "error")
        if error_count > 0:
            return Verdict("failed", max(0, 1.0 - error_count * 0.3), self.verifier_id,
                          issues=issues, summary=f"{error_count} security issue(s)")
        if issues:
            return Verdict("passed", 0.7, self.verifier_id, issues=issues,
                          summary=f"{len(issues)} potential issue(s)")
        return Verdict("passed", 1.0, self.verifier_id, summary="Security scan passed")

    @staticmethod
    def _to_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, dict):
            return str(content)
        return str(content)


class FactChecker(Verifier):
    """Checks claims in Artifacts against known facts / knowledge base."""

    KNOWN_FACTS = {
        "zelos": {
            "created": "2026",
            "license": "Apache 2.0",
            "language": "Python",
        }
    }

    def __init__(self, config: Optional[Dict] = None):
        super().__init__(verifier_id="fact-checker", config=config)
        self._knowledge = dict(self.KNOWN_FACTS)
        if config:
            self._knowledge.update(config.get("facts", {}))

    def verify(self, artifact_content: Any, criteria: VerificationCriteria) -> Verdict:
        text = str(artifact_content) if not isinstance(artifact_content, str) else artifact_content
        issues = []

        # Check for future/prediction claims
        future_patterns = [
            r"will\s+(?:reach|have|achieve|become|grow|surpass)",
            r"by\s+20(?:2[7-9]|3\d)",
            r"projected\s+to",
            r"expected\s+to\s+(?:reach|grow)",
        ]
        for pattern in future_patterns:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                issues.append({
                    "severity": "warning",
                    "message": f"Unverifiable future claim: '{m.group()}'",
                    "rule_id": "future_claim",
                })

        # Check known facts
        for entity, facts in self._knowledge.items():
            if entity.lower() in text.lower():
                for fact_key, fact_value in facts.items():
                    patterns_to_check = [
                        rf"{entity}.*{fact_key}.*?(\d{{4}}|[A-Z][a-z]+ [0-9.]+)",
                        rf"{fact_key}.*{entity}",
                    ]
                    # Simple check: if entity is mentioned, verify at least one known fact
                    pass  # Phase 2: basic check — just flag unverifiable claims

        if issues:
            return Verdict("needs_review", 0.5, self.verifier_id, issues=issues,
                          summary=f"{len(issues)} unverifiable claim(s)")
        return Verdict("passed", 1.0, self.verifier_id, summary="Fact check passed")
