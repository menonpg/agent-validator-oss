"""
Validator — orchestrates the full pipeline:
  1. Clone repo
  2. Detect: ADK SDK or Convention
  3. Run rules in tier order (HARD → SOFT → QUALITY)
  4. Update soul.py MEMORY.md with patterns
  5. Return ReportCard
"""
import os
import tempfile
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

from engine.rule_loader import Rule
from engine.report import ReportCard, RuleResult
from engine.handlers.regex_scan import RegexScanHandler
from engine.handlers.dep_scan import DepScanHandler
from engine.handlers.ast_check import AstCheckHandler
from engine.handlers.llm_judge import LLMJudgeHandler
from engine.handlers.runtime_test import RuntimeTestHandler
from engine.handlers.a2a_check import A2ACheckHandler
from engine.soul_memory import SoulMemory


DISPATCH = {
    "regex_scan":   RegexScanHandler(),
    "dep_scan":     DepScanHandler(),
    "ast_check":    AstCheckHandler(),
    "llm_judge":    LLMJudgeHandler(),
    "runtime_test": RuntimeTestHandler(),
    "a2a_check":    A2ACheckHandler(),
}


class Validator:
    def __init__(self, rules: list[Rule], rules_version: str):
        self.rules = rules
        self.rules_version = rules_version
        self.soul = SoulMemory()

    async def validate(self, repo_url: str, submitter: str, team: str, branch: str | None = None) -> ReportCard:
        report = ReportCard(
            repo_url=repo_url,
            submitter=submitter,
            team=team,
            rules_version=self.rules_version,
            timestamp=datetime.utcnow().isoformat(),
        )

        # Clone repo to temp dir
        tmpdir = tempfile.mkdtemp()
        try:
            _clone(repo_url, tmpdir, branch=branch)
            repo_path = Path(tmpdir)

            # Detect agent type
            agent_type = _detect_agent_type(repo_path)
            report.agent_type = agent_type

            # Run rules in tier order (HARD first — fail fast)
            hard_failed = False
            for rule in self.rules:
                # Skip quality checks if hard gates failed
                if hard_failed and rule.tier == "QUALITY":
                    report.add_skipped(rule, "Hard gate failure — quality checks skipped")
                    continue

                handler = DISPATCH.get(rule.check_type)
                if not handler:
                    report.add_skipped(rule, f"Unknown check type: {rule.check_type}")
                    continue

                result: RuleResult = await handler.run(rule, repo_path, agent_type)
                report.add_result(rule, result)

                if rule.tier == "HARD" and not result.passed:
                    hard_failed = True

            # Update soul.py memory with patterns from this run
            self.soul.update(report)

        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

        return report


def _parse_repo_url(repo_url: str) -> tuple[str, str | None]:
    """
    Parse GitHub URL into (clean_clone_url, branch).
    Handles:
      https://github.com/owner/repo
      https://github.com/owner/repo/tree/branch-name
      https://github.com/owner/repo/tree/branch-name/subpath
    """
    import re
    m = re.match(r"(https://github\.com/[^/]+/[^/]+)(?:/tree/([^/]+))?", repo_url)
    if m:
        return m.group(1), m.group(2)
    return repo_url, None


def _clone(repo_url: str, dest: str, branch: str | None = None):
    clean_url, url_branch = _parse_repo_url(repo_url)
    effective_branch = branch or url_branch  # explicit branch wins over URL-parsed

    github_pat = os.getenv("GITHUB_PAT", "")
    if "github.com" in clean_url and github_pat:
        clean_url = clean_url.replace("https://", f"https://x-access-token:{github_pat}@")

    cmd = ["git", "clone", "--depth", "1"]
    if effective_branch:
        cmd += ["--branch", effective_branch]
    cmd += [clean_url, dest]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"Clone failed: {result.stderr}")


def _detect_agent_type(repo_path: Path) -> str:
    req = repo_path / "requirements.txt"
    if req.exists() and "google-adk" in req.read_text().lower():
        return "adk"
    return "convention"
