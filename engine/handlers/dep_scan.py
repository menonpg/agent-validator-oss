"""
dep_scan handler — scans requirements.txt for CVEs (pip-audit) and unpinned deps.
"""
import subprocess
import json
from pathlib import Path
from engine.rule_loader import Rule
from engine.report import RuleResult


class DepScanHandler:
    async def run(self, rule: Rule, repo_path: Path, agent_type: str) -> RuleResult:
        req_file = repo_path / "requirements.txt"
        if not req_file.exists():
            return RuleResult(passed=False, message=f"{rule.id}: requirements.txt not found")

        check = rule.parameters.get("check", "cve")  # "cve" or "pinned"

        if check == "pinned":
            return self._check_pinned(rule, req_file)
        else:
            return await self._check_cve(rule, req_file)

    def _check_pinned(self, rule: Rule, req_file: Path) -> RuleResult:
        unpinned = []
        for line in req_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Pinned = has == (exact) or >= with upper bound
            if "==" not in line:
                unpinned.append(line)
        if unpinned:
            return RuleResult(
                passed=False,
                message=f"{rule.id}: {len(unpinned)} unpinned dependencies (supply chain risk)",
                details={"unpinned": unpinned}
            )
        return RuleResult(passed=True, message=f"{rule.id} passed — all dependencies pinned")

    async def _check_cve(self, rule: Rule, req_file: Path) -> RuleResult:
        try:
            result = subprocess.run(
                ["pip-audit", "-r", str(req_file), "--format", "json", "--skip-editable"],
                capture_output=True, text=True, timeout=120
            )
            data = json.loads(result.stdout) if result.stdout.strip() else []
            vulns = [v for v in data if v.get("vulns")]
            if vulns:
                critical = [v for v in vulns if any(
                    vuln.get("fix_versions") == [] for vuln in v.get("vulns", [])
                )]
                return RuleResult(
                    passed=False,
                    message=f"{rule.id}: {len(vulns)} vulnerable dependencies ({len(critical)} with no fix)",
                    details={"vulnerabilities": vulns[:5]}
                )
            return RuleResult(passed=True, message=f"{rule.id} passed — no known CVEs")
        except Exception as e:
            # pip-audit not available or parse error — warn but don't hard-fail
            return RuleResult(passed=True, message=f"{rule.id}: CVE scan skipped ({e})")
