"""
RuleLoader — parses rules/*.md files into Rule objects at startup.

Rule markdown format:
  ## RULE: SEC-001 — No Hardcoded Secrets
  **Tier:** HARD
  **Check type:** regex_scan
  **Severity:** CRITICAL
  **Tags:** security, owasp-llm-top10

  ### Parameters
  ```yaml
  patterns: [...]
  ```

  ### Pass Condition
  ...

  ### Failure Message
  ...
"""
import re
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Rule:
    id: str
    name: str
    tier: str          # HARD | SOFT | QUALITY
    check_type: str    # regex_scan | dep_scan | ast_check | llm_judge | runtime_test
    severity: str      # CRITICAL | HIGH | MEDIUM | LOW
    tags: list[str]
    description: str
    parameters: dict[str, Any]
    pass_condition: str
    failure_message: str
    references: str
    source_file: str


class RuleLoader:
    def __init__(self, rules_dir: Path):
        self.rules_dir = rules_dir

    def load_all(self) -> list[Rule]:
        rules = []
        for md_file in sorted(self.rules_dir.glob("*.md")):
            if md_file.name == "RULES.md":
                continue
            rules.extend(self._parse_file(md_file))
        # Sort: HARD first, then SOFT, then QUALITY
        order = {"HARD": 0, "SOFT": 1, "QUALITY": 2}
        rules.sort(key=lambda r: order.get(r.tier, 9))
        return rules

    def _parse_file(self, path: Path) -> list[Rule]:
        text = path.read_text()
        # Split on rule headers: ## RULE: ID — Name
        pattern = r"## RULE: ([A-Z][A-Z0-9]+-\d+) — (.+)"
        splits = re.split(pattern, text)
        rules = []
        # splits = [preamble, id1, name1, body1, id2, name2, body2, ...]
        for i in range(1, len(splits), 3):
            rule_id = splits[i].strip()
            rule_name = splits[i+1].strip()
            body = splits[i+2]
            try:
                rule = self._parse_rule_body(rule_id, rule_name, body, str(path.name))
                rules.append(rule)
            except Exception as e:
                print(f"[RuleLoader] Warning: failed to parse {rule_id} in {path.name}: {e}")
        return rules

    def _parse_rule_body(self, rule_id: str, name: str, body: str, source: str) -> Rule:
        def extract(label: str) -> str:
            m = re.search(rf"\*\*{label}:\*\*\s*(.+)", body)
            return m.group(1).strip() if m else ""

        def extract_section(header: str) -> str:
            m = re.search(rf"### {header}\n(.*?)(?=\n###|\Z)", body, re.DOTALL)
            return m.group(1).strip() if m else ""

        # Extract YAML params block
        params = {}
        yaml_m = re.search(r"```yaml\n(.*?)```", extract_section("Parameters"), re.DOTALL)
        if yaml_m:
            try:
                params = yaml.safe_load(yaml_m.group(1)) or {}
            except Exception:
                params = {}

        tags_raw = extract("Tags")
        tags = [t.strip() for t in tags_raw.split(",")] if tags_raw else []

        return Rule(
            id=rule_id,
            name=name,
            tier=extract("Tier").split()[0],   # "HARD (fail = reject)" → "HARD"
            check_type=extract("Check type"),
            severity=extract("Severity"),
            tags=tags,
            description=extract_section("Description"),
            parameters=params,
            pass_condition=extract_section("Pass Condition"),
            failure_message=extract_section("Failure Message"),
            references=extract_section("References"),
            source_file=source,
        )
