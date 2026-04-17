"""
regex_scan handler — scans source files for forbidden patterns.
Used for: secret detection, overprivileged tool definitions, API allowlist checks.
"""
import re
import math
from pathlib import Path
from engine.rule_loader import Rule
from engine.report import RuleResult


class RegexScanHandler:
    async def run(self, rule: Rule, repo_path: Path, agent_type: str) -> RuleResult:
        params = rule.parameters
        patterns = params.get("patterns", [])
        entropy_threshold = params.get("entropy_threshold", None)
        exclude_paths = params.get("exclude_paths", [])
        file_glob = params.get("file_glob", "**/*.py")

        hits = []
        for py_file in repo_path.glob(file_glob):
            rel = str(py_file.relative_to(repo_path))
            if any(excl in rel for excl in exclude_paths):
                continue
            try:
                content = py_file.read_text(errors="ignore")
            except Exception:
                continue

            for lineno, line in enumerate(content.splitlines(), 1):
                for pattern in patterns:
                    if re.search(pattern, line):
                        # Entropy check — skip low-entropy matches (variable names etc.)
                        if entropy_threshold:
                            match = re.search(pattern, line)
                            if match and _entropy(match.group(0)) < entropy_threshold:
                                continue
                        hits.append({"file": rel, "line": lineno, "pattern": pattern, "content": line.strip()[:120]})

        if hits:
            msg = rule.failure_message
            msg = msg.replace("{file}", hits[0]["file"]).replace("{line}", str(hits[0]["line"]))
            return RuleResult(passed=False, message=msg, details={"hits": hits[:10]})

        return RuleResult(passed=True, message=f"{rule.id} passed — no forbidden patterns found")


def _entropy(s: str) -> float:
    if not s:
        return 0.0
    freq = {}
    for c in s:
        freq[c] = freq.get(c, 0) + 1
    length = len(s)
    return -sum((f / length) * math.log2(f / length) for f in freq.values())
