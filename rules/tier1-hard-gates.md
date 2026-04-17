# Tier 1 — Hard Gates
*Fail any one of these = agent rejected. No exceptions.*

---

## RULE: SEC-001 — No Hardcoded Secrets

**Tier:** HARD (fail = reject)
**Check type:** regex_scan
**Severity:** CRITICAL
**Tags:** security, owasp-llm-top10, nist-ai-rmf

### Description
Scans all Python files for patterns matching API keys, tokens, and passwords
embedded directly in source code. Secrets must be loaded from environment
variables or Secret Manager.

### Parameters
```yaml
patterns:
  - "sk-" + "[a-zA-Z0-9]{32,}"  # pattern: OpenAI key  # OpenAI key pattern
  - "AIza" + "[0-9A-Za-z\\-_]{35}"  # pattern: GCP key
  - "AKIA" + "[0-9A-Z]{16}"  # pattern: AWS key
  - "ghp_" + "[a-zA-Z0-9]{36}"  # pattern: GitHub PAT  # GitHub PAT pattern
  - "xoxb-[0-9]{11}-[0-9]{11}-[a-zA-Z0-9]{24}"
entropy_threshold: 4.2
exclude_paths: [".env.example", "tests/fixtures/"]
file_glob: "**/*.py"
```

### Pass Condition
Zero pattern matches with entropy above threshold.

### Failure Message
> ❌ Hardcoded credential detected in `{file}` line {line}.
> Move all secrets to environment variables or Secret Manager.

### References
- OWASP LLM Top 10: LLM06 (Sensitive Information Disclosure)
- NIST AI RMF: GOVERN 1.2
- Google SAIF: Secure deployment principle

---

## RULE: SEC-002 — Dependency CVE Scan

**Tier:** HARD (fail = reject)
**Check type:** dep_scan
**Severity:** CRITICAL
**Tags:** security, supply-chain, owasp

### Description
Scans requirements.txt for dependencies with known CVEs using pip-audit.
Any critical or high severity CVE with a known fix blocks deployment.

### Parameters
```yaml
check: cve
severity_threshold: HIGH
```

### Pass Condition
Zero HIGH or CRITICAL CVEs with available fixes.

### Failure Message
> ❌ Vulnerable dependency detected: `{package}` has {cve_id}.
> Run `pip-audit -r requirements.txt` and upgrade affected packages.

### References
- OWASP A06: Vulnerable and Outdated Components
- NIST AI RMF: MANAGE 2.4

---

## RULE: SAF-004 — Data Exfiltration Risk

**Tier:** HARD (fail = reject)
**Check type:** ast_check
**Severity:** CRITICAL
**Tags:** safety, owasp-llm02

### Description
Checks whether the agent has outbound HTTP tool definitions without domain
allowlisting. An agent that can make arbitrary outbound HTTP calls could
exfiltrate internal data to external services.

### Parameters
```yaml
check: no_outbound_http_raw
allowlist:
  - "googleapis.com"
  - "bigquery.googleapis.com"
  - "secretmanager.googleapis.com"
```

### Pass Condition
No outbound HTTP calls outside the GCP domain allowlist.

### Failure Message
> ❌ Unrestricted outbound HTTP detected.
> Restrict tool definitions to approved domains. All external calls must go
> through approved infrastructure.

### References
- OWASP LLM Top 10: LLM02 (Insecure Output Handling)
- NIST AI RMF: GOVERN 1.7

---

## RULE: GOV-001 — Audit Logging Present

**Tier:** HARD (fail = reject)
**Check type:** ast_check
**Severity:** HIGH
**Tags:** governance, soc2, nist-ai-rmf

### Description
Every agent must import and use a logging library. Every tool call must be
logged with: caller identity, tool name, inputs (redacted), outputs (redacted),
and timestamp. Required for SOC2 compliance and incident investigation.

### Parameters
```yaml
check: has_audit_logging
```

### Pass Condition
At least one logging import (`logging`, `structlog`, `google.cloud.logging`) detected.

### Failure Message
> ❌ No audit logging detected.
> Import `logging` or `structlog` and log every tool call.
> Required fields: timestamp, tool_name, inputs_hash, outcome, latency_ms.

### References
- SOC2 CC7.2 (System monitoring)
- NIST AI RMF: GOVERN 1.4
- EU AI Act Article 12 (Record-keeping)

---

## RULE: REL-003 — Max Steps Limit

**Tier:** HARD (fail = reject)
**Check type:** ast_check
**Severity:** HIGH
**Tags:** reliability, owasp-llm08

### Description
Agents without a maximum step or iteration limit can loop indefinitely,
consuming resources and racking up LLM API costs. Every agent must define
a hard cap on the number of reasoning steps.

### Parameters
```yaml
check: has_max_steps
```

### Pass Condition
`max_steps`, `max_iterations`, `MAX_STEPS`, or `MAX_ITER` defined in source.

### Failure Message
> ❌ No max steps limit detected.
> Define MAX_STEPS = N and enforce it in the agent loop.
> Recommended: 10-20 steps for most tasks; never unbounded.

### References
- OWASP LLM Top 10: LLM08 (Excessive Agency)
- NIST AI RMF: MANAGE 2.5

---

## RULE: STR-001 — Required Files Present

**Tier:** HARD (fail = reject)
**Check type:** runtime_test
**Severity:** HIGH
**Tags:** structure, governance

### Description
Every submitted agent must include the four required files. Missing files
indicate an incomplete or improperly packaged submission.

### Parameters
```yaml
check: required_files
files:
  - agent.py
  - requirements.txt
  - README.md
  - tests/
```

### Pass Condition
All four required files/directories present in repo root.

### Failure Message
> ❌ Missing required files: {missing}.
> Add {missing} and resubmit. See docs/how-to-submit.md for requirements.

### References
- Internal: Agent Submission Standards v1.0

---

## RULE: STR-002 — Test Coverage Required

**Tier:** HARD (fail = reject)
**Check type:** runtime_test
**Severity:** HIGH
**Tags:** structure, quality

### Description
Every agent must include at least one test file in `tests/` directory covering
each capability listed in README.md. Untested agents are not deployable.

### Parameters
```yaml
check: has_tests
```

### Pass Condition
`tests/` directory exists and contains at least one `test_*.py` file.

### Failure Message
> ❌ No tests found in tests/ directory.
> Add test_*.py files covering each capability claim in README.md.
> Tests must be runnable with `pytest tests/`.

### References
- Internal: Agent Quality Standards v1.0
