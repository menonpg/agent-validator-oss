"""
ast_check handler — static analysis via Python AST.
No code execution. Checks structure, imports, decorators, function signatures.
"""
import ast
from pathlib import Path
from engine.rule_loader import Rule
from engine.report import RuleResult


class AstCheckHandler:
    async def run(self, rule: Rule, repo_path: Path, agent_type: str) -> RuleResult:
        check_name = rule.parameters.get("check")

        CHECK_MAP = {
            "has_callable_export":      self._has_callable_export,
            "has_audit_logging":        self._has_audit_logging,
            "has_structured_logging":   self._has_structured_logging,
            "has_timeout_on_tools":     self._has_timeout_on_tools,
            "has_retry_logic":          self._has_retry_logic,
            "has_max_steps":            self._has_max_steps,
            "has_error_handling":       self._has_error_handling,
            "has_otel_traces":          self._has_otel_traces,
            "has_token_tracking":       self._has_token_tracking,
            "model_version_pinned":     self._model_version_pinned,
            "has_cost_guardrails":      self._has_cost_guardrails,
            "adk_decorators_present":   self._adk_decorators_present,
            "tools_have_docstrings":    self._tools_have_docstrings,
            "adk_runner_present":       self._adk_runner_present,
            "bq_uses_parameterized":    self._bq_uses_parameterized,
            "no_outbound_http_raw":     self._no_outbound_http_raw,
            "pii_redaction_present":    self._pii_redaction_present,
            "data_residency_gcp":       self._data_residency_gcp,
        }

        fn = CHECK_MAP.get(check_name)
        if not fn:
            return RuleResult(passed=True, message=f"{rule.id}: check '{check_name}' not implemented — skipped")

        py_files = list(repo_path.glob("**/*.py"))
        trees = []
        for f in py_files:
            try:
                trees.append((f, ast.parse(f.read_text(errors="ignore"), filename=str(f))))
            except SyntaxError:
                pass

        return fn(rule, repo_path, trees)

    # ── Check implementations ───────────────────────────────────────

    def _has_callable_export(self, rule, repo_path, trees) -> RuleResult:
        agent_py = repo_path / "agent.py"
        if not agent_py.exists():
            return RuleResult(passed=False, message=f"{rule.id}: agent.py not found")
        names = {n.id for tree in [t for f, t in trees if f.name == "agent.py"]
                 for n in ast.walk(tree) if isinstance(n, ast.Name)}
        exports = {"Agent", "run", "invoke", "main", "agent"}
        if names & exports:
            return RuleResult(passed=True, message=f"{rule.id} passed")
        return RuleResult(passed=False, message=f"{rule.id}: agent.py must export Agent, run, or invoke")

    def _has_audit_logging(self, rule, repo_path, trees) -> RuleResult:
        for f, tree in trees:
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    names = [a.name for a in getattr(node, "names", [])]
                    mod = getattr(node, "module", "") or ""
                    if "logging" in names or "logging" in mod or "structlog" in mod:
                        return RuleResult(passed=True, message=f"{rule.id} passed — logging imported in {f.name}")
        return RuleResult(passed=False, message=f"{rule.id}: No audit logging detected. Import `logging` or `structlog` and log every tool call.")

    def _has_structured_logging(self, rule, repo_path, trees) -> RuleResult:
        for f, tree in trees:
            src = f.read_text(errors="ignore")
            if "structlog" in src or "logging.getLogger" in src:
                return RuleResult(passed=True, message=f"{rule.id} passed")
        return RuleResult(passed=False, message=f"{rule.id}: Use structured logging (structlog or logging.getLogger + JSONFormatter)")

    def _has_timeout_on_tools(self, rule, repo_path, trees) -> RuleResult:
        for f, tree in trees:
            src = f.read_text(errors="ignore")
            if "timeout=" in src or "asyncio.wait_for" in src:
                return RuleResult(passed=True, message=f"{rule.id} passed")
        return RuleResult(passed=False, message=f"{rule.id}: No timeout detected on tool calls. Add timeout= parameter or asyncio.wait_for()")

    def _has_retry_logic(self, rule, repo_path, trees) -> RuleResult:
        for f, tree in trees:
            src = f.read_text(errors="ignore")
            if any(kw in src for kw in ["tenacity", "retry", "backoff", "Retry"]):
                return RuleResult(passed=True, message=f"{rule.id} passed")
        return RuleResult(passed=False, message=f"{rule.id}: No retry logic detected. Use tenacity or implement exponential backoff.")

    def _has_max_steps(self, rule, repo_path, trees) -> RuleResult:
        for f, tree in trees:
            src = f.read_text(errors="ignore")
            if any(kw in src for kw in ["max_steps", "max_iterations", "MAX_STEPS", "MAX_ITER"]):
                return RuleResult(passed=True, message=f"{rule.id} passed")
        return RuleResult(passed=False, message=f"{rule.id}: No max_steps limit detected. Unbounded agents can loop indefinitely.")

    def _has_error_handling(self, rule, repo_path, trees) -> RuleResult:
        for f, tree in trees:
            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler):
                    return RuleResult(passed=True, message=f"{rule.id} passed")
        return RuleResult(passed=False, message=f"{rule.id}: No exception handling detected. Wrap tool calls in try/except.")

    def _has_otel_traces(self, rule, repo_path, trees) -> RuleResult:
        for f, tree in trees:
            src = f.read_text(errors="ignore")
            if "opentelemetry" in src or "cloud_trace" in src or "tracing" in src:
                return RuleResult(passed=True, message=f"{rule.id} passed")
        return RuleResult(passed=False, message=f"{rule.id}: No OpenTelemetry traces detected. Add opentelemetry-sdk instrumentation.")

    def _has_token_tracking(self, rule, repo_path, trees) -> RuleResult:
        for f, tree in trees:
            src = f.read_text(errors="ignore")
            if any(kw in src for kw in ["usage_metadata", "usage.total_tokens", "prompt_tokens", "token_count"]):
                return RuleResult(passed=True, message=f"{rule.id} passed")
        return RuleResult(passed=False, message=f"{rule.id}: Token usage not tracked. Log usage_metadata from API responses for cost observability.")

    def _model_version_pinned(self, rule, repo_path, trees) -> RuleResult:
        import re
        # Only flag string literals assigned to model variables containing "latest"
        # Not comments (e.g. "# never 'latest'" should not trigger)
        pattern = re.compile(r"""(?:MODEL[_A-Z]*|model[_a-z]*)\s*=\s*["'][^"']*latest[^"']*["']""")
        for f, tree in trees:
            src = f.read_text(errors="ignore")
            if pattern.search(src):
                return RuleResult(passed=False, message=f"{rule.id}: Model version set to \'latest\' -- pin to specific version for reproducibility")
        return RuleResult(passed=True, message=f"{rule.id} passed -- model version is pinned")

    def _has_cost_guardrails(self, rule, repo_path, trees) -> RuleResult:
        for f, tree in trees:
            src = f.read_text(errors="ignore")
            if any(kw in src for kw in ["max_tokens", "MAX_TOKENS", "token_budget", "cost_limit"]):
                return RuleResult(passed=True, message=f"{rule.id} passed")
        return RuleResult(passed=False, message=f"{rule.id}: No cost guardrails detected. Set max_tokens on all LLM calls.")

    def _adk_decorators_present(self, rule, repo_path, trees) -> RuleResult:
        for f, tree in trees:
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    for dec in node.decorator_list:
                        dec_str = ast.unparse(dec) if hasattr(ast, "unparse") else ""
                        if "adk.tool" in dec_str or "tool" in dec_str:
                            return RuleResult(passed=True, message=f"{rule.id} passed — @adk.tool decorator found")
        return RuleResult(passed=False, message=f"{rule.id}: No @adk.tool decorators found. ADK agents must use decorator-based tool registration.")

    def _tools_have_docstrings(self, rule, repo_path, trees) -> RuleResult:
        missing = []
        for f, tree in trees:
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    for dec in node.decorator_list:
                        dec_str = ast.unparse(dec) if hasattr(ast, "unparse") else ""
                        if "tool" in dec_str:
                            if not (node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant)):
                                missing.append(node.name)
        if missing:
            return RuleResult(passed=False, message=f"{rule.id}: Tools missing docstrings: {missing}. ADK requires docstrings for tool discovery.")
        return RuleResult(passed=True, message=f"{rule.id} passed — all tools have docstrings")

    def _adk_runner_present(self, rule, repo_path, trees) -> RuleResult:
        for f, tree in trees:
            src = f.read_text(errors="ignore")
            if "adk.Runner" in src or "Runner(" in src:
                return RuleResult(passed=True, message=f"{rule.id} passed")
        return RuleResult(passed=False, message=f"{rule.id}: adk.Runner not found. ADK agents require a Runner for execution.")

    def _bq_uses_parameterized(self, rule, repo_path, trees) -> RuleResult:
        for f, tree in trees:
            src = f.read_text(errors="ignore")
            if "bigquery" in src.lower():
                if "query_parameters" in src or "ScalarQueryParameter" in src:
                    return RuleResult(passed=True, message=f"{rule.id} passed — parameterized BigQuery queries detected")
                # Has BQ but no params — potential SQL injection
                if "f\"" in src or "format(" in src or "%" in src:
                    return RuleResult(passed=False, message=f"{rule.id}: BigQuery queries appear to use string formatting. Use query_parameters to prevent injection.")
        return RuleResult(passed=True, message=f"{rule.id} passed — no BigQuery usage detected")

    def _no_outbound_http_raw(self, rule, repo_path, trees) -> RuleResult:
        allowlist = rule.parameters.get("allowlist", [])
        for f, tree in trees:
            src = f.read_text(errors="ignore")
            # Look for raw HTTP calls (requests, httpx) without domain filtering
            if any(lib in src for lib in ["requests.get", "requests.post", "httpx.get", "httpx.post"]):
                if not allowlist:
                    return RuleResult(passed=False, message=f"{rule.id}: Outbound HTTP calls detected without domain allowlist. Restrict to approved endpoints.")
        return RuleResult(passed=True, message=f"{rule.id} passed")

    def _pii_redaction_present(self, rule, repo_path, trees) -> RuleResult:
        for f, tree in trees:
            src = f.read_text(errors="ignore")
            if any(kw in src for kw in ["redact", "scrub_pii", "anonymize", "mask_pii", "presidio"]):
                return RuleResult(passed=True, message=f"{rule.id} passed")
        return RuleResult(passed=False, message=f"{rule.id}: No PII redaction detected. Implement redact() before writing to logs.")

    def _data_residency_gcp(self, rule, repo_path, trees) -> RuleResult:
        disallowed = rule.parameters.get("disallowed_domains", ["openai.com", "anthropic.com"])
        for f, tree in trees:
            src = f.read_text(errors="ignore")
            for domain in disallowed:
                if domain in src:
                    return RuleResult(passed=False, message=f"{rule.id}: External API call to {domain} detected. Data must stay within approved infrastructure.")
        return RuleResult(passed=True, message=f"{rule.id} passed — no disallowed external domains detected")
