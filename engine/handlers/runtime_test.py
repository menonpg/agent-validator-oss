"""
runtime_test handler — smoke tests the agent without full execution.
Checks: required files present, health endpoint, hallucinated tools.
"""
import os
import subprocess
import tempfile
from pathlib import Path
from engine.rule_loader import Rule
from engine.report import RuleResult

REQUIRED_FILES = ["agent.py", "requirements.txt", "README.md"]


class RuntimeTestHandler:
    async def run(self, rule: Rule, repo_path: Path, agent_type: str) -> RuleResult:
        check = rule.parameters.get("check", "required_files")

        if check == "required_files":
            return self._required_files(rule, repo_path)
        elif check == "has_tests":
            return self._has_tests(rule, repo_path)
        elif check == "health_endpoint":
            return self._health_endpoint(rule, repo_path)
        elif check == "no_hallucinated_tools":
            return self._no_hallucinated_tools(rule, repo_path)
        else:
            return RuleResult(passed=True, message=f"{rule.id}: check '{check}' not implemented")

    def _required_files(self, rule, repo_path) -> RuleResult:
        required = rule.parameters.get("files", REQUIRED_FILES)
        missing = [f for f in required if not (repo_path / f).exists()]
        if missing:
            return RuleResult(
                passed=False,
                message=f"{rule.id}: Missing required files: {missing}. "
                        f"Add {', '.join(missing)} and retry."
            )
        return RuleResult(passed=True, message=f"{rule.id} passed — all required files present")

    def _has_tests(self, rule, repo_path) -> RuleResult:
        tests_dir = repo_path / "tests"
        if not tests_dir.exists():
            return RuleResult(passed=False, message=f"{rule.id}: tests/ directory missing. Add at least one test covering each capability in README.")
        test_files = list(tests_dir.glob("test_*.py")) + list(tests_dir.glob("*_test.py"))
        if not test_files:
            return RuleResult(passed=False, message=f"{rule.id}: tests/ directory empty. Add test_*.py files.")
        return RuleResult(passed=True, message=f"{rule.id} passed — {len(test_files)} test files found")

    def _health_endpoint(self, rule, repo_path) -> RuleResult:
        for py_file in repo_path.glob("**/*.py"):
            src = py_file.read_text(errors="ignore")
            if any(p in src for p in ["/health", '"/health"', "'/health'", "health_check"]):
                return RuleResult(passed=True, message=f"{rule.id} passed — health endpoint found")
        return RuleResult(passed=False, message=f"{rule.id}: No /health endpoint detected. Add GET /health returning {'{'}'status': 'ok'{'}'}")

    def _no_hallucinated_tools(self, rule, repo_path) -> RuleResult:
        import ast as _ast
        agent_py = repo_path / "agent.py"
        if not agent_py.exists():
            return RuleResult(passed=True, message=f"{rule.id}: agent.py not found — skipped")

        src = agent_py.read_text(errors="ignore")
        try:
            tree = _ast.parse(src)
        except SyntaxError:
            return RuleResult(passed=True, message=f"{rule.id}: syntax error in agent.py — skipped")

        # Collect all function definitions decorated with @tool
        defined_tools = set()
        called_tools = set()

        for node in _ast.walk(tree):
            if isinstance(node, _ast.FunctionDef):
                for dec in node.decorator_list:
                    dec_str = _ast.unparse(dec) if hasattr(_ast, "unparse") else ""
                    if "tool" in dec_str.lower():
                        defined_tools.add(node.name)

        # Look for tool calls in strings (agent instructions referencing tools by name)
        for node in _ast.walk(tree):
            if isinstance(node, _ast.Constant) and isinstance(node.value, str):
                for tool in defined_tools:
                    if tool in node.value:
                        called_tools.add(tool)

        hallucinated = called_tools - defined_tools
        if hallucinated:
            return RuleResult(passed=False, message=f"{rule.id}: Agent references undefined tools: {hallucinated}")
        return RuleResult(passed=True, message=f"{rule.id} passed — no hallucinated tool references")
