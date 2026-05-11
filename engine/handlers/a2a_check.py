"""
a2a_check handler — validates A2A Protocol v1.0 (Linux Foundation) compliance.
Checks Agent Card existence/schema, task endpoint, lifecycle states,
authentication declaration, streaming capability, runtime declaration,
and AP2 payments declaration.

Added: 2026-03-19
Updated: 2026-05-11 — A2A v1.0 (Linux Foundation): new fields provider,
  defaultInputModes, defaultOutputModes, pushNotifications, runtimeEnvironment,
  payments. New rules A2A-006, A2A-007. message/send + message/stream patterns.
  input-required task state. openIdConnect auth scheme.
"""
import json
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
        elif check == "agent_card_runtime":
            return self._check_agent_card_runtime(rule, repo_path, params)
        elif check == "agent_card_ap2":
            return self._check_agent_card_ap2(rule, repo_path, params)
        else:
            return RuleResult(passed=False, message=f"Unknown a2a_check sub-type: {check}")

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _load_agent_card(self, repo_path: Path, rule_id: str):
        card_path = repo_path / ".well-known" / "agent.json"
        if not card_path.exists():
            return None, RuleResult(
                passed=False,
                message=f"{rule_id}: agent.json not found at .well-known/agent.json",
                details={"missing": ".well-known/agent.json"},
            )
        try:
            card = json.loads(card_path.read_text())
            return card, None
        except Exception as e:
            return None, RuleResult(
                passed=False,
                message=f"{rule_id}: agent.json is not valid JSON — {e}",
                details={"error": str(e)},
            )

    # ── A2A-001: Agent Card existence + required fields ──────────────────────

    def _check_agent_card_exists(self, rule: Rule, repo_path: Path, params: dict) -> RuleResult:
        card, err = self._load_agent_card(repo_path, "A2A-001")
        if err:
            return err

        default_required = [
            "name", "description", "version", "url",
            "capabilities", "skills",
            "provider",
            "defaultInputModes",
            "defaultOutputModes",
        ]
        required = params.get("required_fields", default_required)
        missing = [f for f in required if f not in card]
        recommended = params.get("recommended_fields", ["signedCard"])
        missing_recommended = [f for f in recommended if f not in card]

        if missing:
            return RuleResult(
                passed=False,
                message=rule.failure_message,
                details={"missing_fields": missing, "present_fields": list(card.keys())},
            )

        details = {"card_name": card.get("name"), "version": card.get("version")}
        if missing_recommended:
            details["recommended_missing"] = missing_recommended
            details["hint"] = "Consider adding signedCard for cryptographic identity (A2A v1.0)"

        return RuleResult(
            passed=True,
            message="A2A-001 passed — Agent Card found with all required fields",
            details=details,
        )

    # ── A2A-002: Task endpoint (JSON-RPC 2.0) ───────────────────────────────

    def _check_task_endpoint(self, rule: Rule, repo_path: Path, params: dict) -> RuleResult:
        default_patterns = [
            "tasks/send",
            "message/send",
            "message/stream",
            "jsonrpc",
            "json_rpc",
            "JsonRpc",
            "JSONRPC",
        ]
        patterns = params.get("patterns", default_patterns)
        file_glob = params.get("file_glob", "**/*.py")
        hits = []

        for py_file in repo_path.glob(file_glob):
            try:
                content = py_file.read_text(errors="ignore")
            except Exception:
                continue
            for pattern in patterns:
                if pattern in content:
                    hits.append({"file": str(py_file.relative_to(repo_path)), "pattern": pattern})
                    break

        if not hits:
            return RuleResult(passed=False, message=rule.failure_message, details={"searched_patterns": patterns})

        return RuleResult(
            passed=True,
            message="A2A-002 passed — JSON-RPC 2.0 task endpoint patterns found",
            details={"hits": hits[:5]},
        )

    # ── A2A-003: Task lifecycle states ──────────────────────────────────────

    def _check_task_states(self, rule: Rule, repo_path: Path, params: dict) -> RuleResult:
        default_states = ["submitted", "working", "completed", "failed", "input-required"]
        required_states = params.get("required_states", default_states)
        file_glob = params.get("file_glob", "**/*.py")

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

    # ── A2A-004: Auth declaration in Agent Card ──────────────────────────────

    def _check_agent_card_auth(self, rule: Rule, repo_path: Path, params: dict) -> RuleResult:
        card, err = self._load_agent_card(repo_path, "A2A-004")
        if err:
            return err

        if "authentication" not in card:
            return RuleResult(passed=False, message=rule.failure_message, details={"card_fields": list(card.keys())})

        auth = card["authentication"]
        default_valid = ["apiKey", "oauth2", "bearer", "openIdConnect", "none"]
        valid_schemes = params.get("valid_schemes", default_valid)
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

    # ── A2A-005: Streaming + pushNotifications ───────────────────────────────

    def _check_agent_card_streaming(self, rule: Rule, repo_path: Path, params: dict) -> RuleResult:
        card, err = self._load_agent_card(repo_path, "A2A-005")
        if err:
            return err

        capabilities = card.get("capabilities", {})
        required_fields = params.get("capability_fields", ["streaming", "pushNotifications"])
        missing = [f for f in required_fields if f not in capabilities]

        if missing:
            return RuleResult(
                passed=False,
                message=rule.failure_message,
                details={"missing_capability_fields": missing, "capabilities_found": list(capabilities.keys())},
            )

        return RuleResult(
            passed=True,
            message="A2A-005 passed — streaming and pushNotifications declared",
            details={
                "streaming": capabilities.get("streaming"),
                "pushNotifications": capabilities.get("pushNotifications"),
            },
        )

    # ── A2A-006: Runtime and SDK Compatibility (NEW v1.0) ────────────────────

    def _check_agent_card_runtime(self, rule: Rule, repo_path: Path, params: dict) -> RuleResult:
        card, err = self._load_agent_card(repo_path, "A2A-006")
        if err:
            return err

        recommended_field = params.get("recommended_field", "runtimeEnvironment")
        valid_runtimes = params.get("valid_runtimes", ["python", "javascript", "java", "go", "dotnet"])

        runtime = card.get(recommended_field) or card.get("capabilities", {}).get(recommended_field)

        if not runtime:
            return RuleResult(
                passed=False,
                message=rule.failure_message,
                details={"missing_field": recommended_field, "valid_runtimes": valid_runtimes},
            )

        runtime_lower = runtime.lower() if isinstance(runtime, str) else ""
        if runtime_lower not in valid_runtimes:
            return RuleResult(
                passed=False,
                message=f"A2A-006: Unknown runtimeEnvironment '{runtime}'. Valid: {valid_runtimes}",
                details={"declared_runtime": runtime, "valid_runtimes": valid_runtimes},
            )

        return RuleResult(
            passed=True,
            message=f"A2A-006 passed — runtimeEnvironment declared: {runtime}",
            details={"runtimeEnvironment": runtime},
        )

    # ── A2A-007: Agent Payments Protocol AP2 (NEW v1.0) ──────────────────────

    def _check_agent_card_ap2(self, rule: Rule, repo_path: Path, params: dict) -> RuleResult:
        card, err = self._load_agent_card(repo_path, "A2A-007")
        if err:
            return err

        capability_field = params.get("capability_field", "payments")
        applicable_domains = params.get("applicable_domains", ["financial-services", "procurement", "e-commerce"])

        capabilities = card.get("capabilities", {})
        agent_domain = (
            card.get("domain") or card.get("category") or capabilities.get("domain") or ""
        ).lower()

        is_applicable = any(d in agent_domain for d in applicable_domains)

        if not is_applicable:
            return RuleResult(
                passed=True,
                message="A2A-007 skipped — agent domain not in financial/transactional scope",
                details={"agent_domain": agent_domain or "(not declared)", "applicable_domains": applicable_domains},
            )

        if capability_field not in capabilities:
            return RuleResult(
                passed=False,
                message=rule.failure_message,
                details={"agent_domain": agent_domain, "missing_capability": capability_field, "capabilities_found": list(capabilities.keys())},
            )

        return RuleResult(
            passed=True,
            message="A2A-007 passed — AP2 payments capability declared",
            details={"domain": agent_domain, "payments": capabilities[capability_field]},
        )
