"""
a2a_check handler — validates Google A2A protocol compliance.
Checks Agent Card existence/schema, task endpoint, lifecycle states,
authentication declaration, and streaming capability declaration.

Added: 2026-03-19
"""
import json
import re
from pathlib import Path
from engine.rule_loader import Rule
from engine.report import RuleResult


class A2ACheckHandler:
    async def run(self, rule: Rule, repo_path: Path, agent_type: str) -> RuleResult:
        params = rule.parameters
        check = params.get("check", "")

        if check == "agent_card_exists":
            return self._check_agent_card_exists(rule, repo_path, params)
        elif check == "task_endpoint":
            return self._check_task_endpoint(rule, repo_path, params)
        elif check == "task_states":
            return self._check_task_states(rule, repo_path, params)
        elif check == "agent_card_auth":
            return self._check_agent_card_auth(rule, repo_path, params)
        elif check == "agent_card_streaming":
            return self._check_agent_card_streaming(rule, repo_path, params)
        else:
            return RuleResult(passed=False, message=f"Unknown a2a_check sub-type: {check}")

    # ── Agent Card existence + required fields ──────────────────────────────

    def _check_agent_card_exists(self, rule: Rule, repo_path: Path, params: dict) -> RuleResult:
        card_path = repo_path / ".well-known" / "agent.json"
        if not card_path.exists():
            return RuleResult(
                passed=False,
                message=rule.failure_message,
                details={"missing": ".well-known/agent.json"},
            )

        try:
            card = json.loads(card_path.read_text())
        except Exception as e:
            return RuleResult(
                passed=False,
                message=f"A2A-001: agent.json is not valid JSON — {e}",
                details={"error": str(e)},
            )

        required = params.get("required_fields", ["name", "description", "version", "url", "capabilities", "skills"])
        missing = [f for f in required if f not in card]
        if missing:
            return RuleResult(
                passed=False,
                message=f"A2A-001: agent.json missing required fields: {missing}",
                details={"missing_fields": missing, "present_fields": list(card.keys())},
            )

        return RuleResult(
            passed=True,
            message=f"A2A-001 passed — Agent Card found with all required fields",
            details={"card_name": card.get("name"), "version": card.get("version")},
        )

    # ── Task endpoint (JSON-RPC 2.0 tasks/send) ─────────────────────────────

    def _check_task_endpoint(self, rule: Rule, repo_path: Path, params: dict) -> RuleResult:
        patterns = params.get("patterns", ["tasks/send", "jsonrpc", "JsonRpc", "JSONRPC"])
        file_glob = params.get("file_glob", "**/*.py")
        hits = []

        for py_file in repo_path.glob(file_glob):
            try:
                content = py_file.read_text(errors="ignore")
            except Exception:
                continue
            for pattern in patterns:
                if pattern in content:
                    hits.append({
                        "file": str(py_file.relative_to(repo_path)),
                        "pattern": pattern,
                    })
                    break  # one hit per file is enough

        if not hits:
            return RuleResult(
                passed=False,
                message=rule.failure_message,
                details={"searched_patterns": patterns},
            )

        return RuleResult(
            passed=True,
            message="A2A-002 passed — JSON-RPC 2.0 task endpoint patterns found",
            details={"hits": hits[:5]},
        )

    # ── Task lifecycle states ────────────────────────────────────────────────

    def _check_task_states(self, rule: Rule, repo_path: Path, params: dict) -> RuleResult:
        required_states = params.get("required_states", ["submitted", "working", "completed", "failed"])
        file_glob = params.get("file_glob", "**/*.py")

        # Collect all source content
        all_content = ""
        for py_file in repo_path.glob(file_glob):
            try:
                all_content += py_file.read_text(errors="ignore")
            except Exception:
                continue

        missing_states = [s for s in required_states if s not in all_content]
        if missing_states:
            return RuleResult(
                passed=False,
                message=rule.failure_message,
                details={"missing_states": missing_states, "required_states": required_states},
            )

        return RuleResult(
            passed=True,
            message="A2A-003 passed — all required task lifecycle states found",
            details={"states_found": required_states},
        )

    # ── Auth declaration in Agent Card ──────────────────────────────────────

    def _check_agent_card_auth(self, rule: Rule, repo_path: Path, params: dict) -> RuleResult:
        card_path = repo_path / ".well-known" / "agent.json"
        if not card_path.exists():
            return RuleResult(
                passed=False,
                message="A2A-004: agent.json not found — cannot check authentication",
            )

        try:
            card = json.loads(card_path.read_text())
        except Exception:
            return RuleResult(passed=False, message="A2A-004: agent.json is not valid JSON")

        if "authentication" not in card:
            return RuleResult(
                passed=False,
                message=rule.failure_message,
                details={"card_fields": list(card.keys())},
            )

        auth = card["authentication"]
        valid_schemes = params.get("valid_schemes", ["apiKey", "oauth2", "bearer", "none"])
        schemes = auth.get("schemes", [])
        invalid = [s for s in schemes if s not in valid_schemes]
        if invalid:
            return RuleResult(
                passed=False,
                message=f"A2A-004: Unknown auth schemes: {invalid}. Valid: {valid_schemes}",
                details={"invalid_schemes": invalid},
            )

        return RuleResult(
            passed=True,
            message="A2A-004 passed — authentication declared in Agent Card",
            details={"schemes": schemes},
        )

    # ── Streaming capability declaration ────────────────────────────────────

    def _check_agent_card_streaming(self, rule: Rule, repo_path: Path, params: dict) -> RuleResult:
        card_path = repo_path / ".well-known" / "agent.json"
        if not card_path.exists():
            return RuleResult(
                passed=False,
                message="A2A-005: agent.json not found — cannot check streaming declaration",
            )

        try:
            card = json.loads(card_path.read_text())
        except Exception:
            return RuleResult(passed=False, message="A2A-005: agent.json is not valid JSON")

        capabilities = card.get("capabilities", {})
        if "streaming" not in capabilities:
            return RuleResult(
                passed=False,
                message=rule.failure_message,
                details={"capabilities_found": list(capabilities.keys())},
            )

        return RuleResult(
            passed=True,
            message=f"A2A-005 passed — streaming declared: {capabilities['streaming']}",
            details={"streaming": capabilities["streaming"]},
        )
