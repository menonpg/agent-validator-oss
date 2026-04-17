"""
ReportCard — structured output of a validation run.
"""
from dataclasses import dataclass, field
from typing import Optional
from engine.rule_loader import Rule


@dataclass
class RuleResult:
    passed: bool
    score: Optional[float] = None   # 0-10, used for QUALITY checks
    message: str = ""
    details: dict = field(default_factory=dict)


@dataclass
class ReportCard:
    repo_url: str
    submitter: str
    team: str
    rules_version: str
    timestamp: str
    agent_type: str = "unknown"
    _results: list = field(default_factory=list)
    _skipped: list = field(default_factory=list)

    def add_result(self, rule: Rule, result: RuleResult):
        self._results.append({"rule": rule, "result": result})

    def add_skipped(self, rule: Rule, reason: str):
        self._skipped.append({"rule": rule, "reason": reason})

    @property
    def hard_gates(self):
        return [r for r in self._results if r["rule"].tier == "HARD"]

    @property
    def soft_gates(self):
        return [r for r in self._results if r["rule"].tier == "SOFT"]

    @property
    def quality_checks(self):
        return [r for r in self._results if r["rule"].tier == "QUALITY"]

    @property
    def hard_passed(self) -> bool:
        return all(r["result"].passed for r in self.hard_gates)

    @property
    def soft_score(self) -> tuple[int, int]:
        passed = sum(1 for r in self.soft_gates if r["result"].passed)
        return passed, len(self.soft_gates)

    @property
    def quality_score(self) -> float:
        scores = [r["result"].score for r in self.quality_checks if r["result"].score is not None]
        return round(sum(scores) / len(scores) * 10, 1) if scores else 0.0

    @property
    def verdict(self) -> str:
        if not self.hard_passed:
            fails = [r["rule"].id for r in self.hard_gates if not r["result"].passed]
            return f"REJECTED — hard gate failures: {', '.join(fails)}"
        return "APPROVED"

    @property
    def warnings(self) -> list[str]:
        return [
            f"{r['rule'].id}: {r['result'].message}"
            for r in self.soft_gates if not r["result"].passed
        ]

    def to_dict(self) -> dict:
        sp, st = self.soft_score
        return {
            "verdict": self.verdict,
            "approved": self.hard_passed,
            "repo_url": self.repo_url,
            "submitter": self.submitter,
            "team": self.team,
            "agent_type": self.agent_type,
            "rules_version": self.rules_version,
            "timestamp": self.timestamp,
            "hard_gates": {"passed": sum(1 for r in self.hard_gates if r["result"].passed), "total": len(self.hard_gates)},
            "soft_gates": {"passed": sp, "total": st},
            "quality_score": self.quality_score,
            "warnings": self.warnings,
            "failures": [
                {"id": r["rule"].id, "name": r["rule"].name, "message": r["result"].message}
                for r in self.hard_gates if not r["result"].passed
            ],
            "results": [
                {
                    "id": r["rule"].id,
                    "name": r["rule"].name,
                    "tier": r["rule"].tier,
                    "passed": r["result"].passed,
                    "score": r["result"].score,
                    "message": r["result"].message,
                }
                for r in self._results
            ],
            "skipped": [{"id": s["rule"].id, "reason": s["reason"]} for s in self._skipped],
        }
