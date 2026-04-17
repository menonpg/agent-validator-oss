# Agent Validation Rules — Master Index

This file is the human-readable index of all validation rules.
Rules are defined in the accompanying markdown files and loaded by the
engine at startup. To add a rule, edit the appropriate tier file and follow
the format below. No code changes required for new rules using existing
check types.

## How to Write a Rule

```markdown
## RULE: {ID} — {Name}

**Tier:** HARD | SOFT | QUALITY
**Check type:** regex_scan | dep_scan | ast_check | llm_judge | runtime_test
**Severity:** CRITICAL | HIGH | MEDIUM | LOW
**Tags:** comma, separated, tags

### Description
Human-readable explanation of what this rule checks and why it matters.

### Parameters
\```yaml
check: check_name        # for ast_check / dep_scan / runtime_test / llm_judge
patterns: [...]          # for regex_scan
\```

### Pass Condition
What must be true for this rule to pass.

### Failure Message
> The error message shown to the submitter. Use {variable} for dynamic values.

### References
- Framework: Specific control or article
```

## Rule ID Naming Convention

| Prefix | Domain |
|--------|--------|
| `SEC-` | Security |
| `SAF-` | Safety |
| `GOV-` | Governance |
| `OBS-` | Observability |
| `REL-` | Reliability |
| `ALI-` | Alignment |
| `QUA-` | Quality |
| `STR-` | Structure |

## Available Check Types

| Check type | What it does | Parameters |
|------------|-------------|------------|
| `regex_scan` | Scans Python files for forbidden patterns | `patterns`, `entropy_threshold`, `exclude_paths`, `file_glob` |
| `dep_scan` | Scans requirements.txt for CVEs or unpinned deps | `check: cve` or `check: pinned` |
| `ast_check` | Static AST analysis — no code execution | `check: <check_name>` (see list below) |
| `llm_judge` | Gemini 2.0 Flash scoring | `check: <check_name>`, `score_threshold` |
| `runtime_test` | File presence and structure checks | `check: <check_name>` |

### ast_check names
- `has_callable_export` — agent.py exports callable
- `has_audit_logging` — logging import present
- `has_structured_logging` — JSON/structlog logging
- `has_timeout_on_tools` — timeout= on tool calls
- `has_retry_logic` — tenacity or backoff present
- `has_max_steps` — max_steps limit defined
- `has_error_handling` — try/except present
- `has_otel_traces` — OpenTelemetry instrumentation
- `has_token_tracking` — usage_metadata logged
- `model_version_pinned` — no 'latest' model version
- `has_cost_guardrails` — max_tokens set
- `adk_decorators_present` — @adk.tool decorators (ADK only)
- `tools_have_docstrings` — tool docstrings present (ADK only)
- `adk_runner_present` — adk.Runner present (ADK only)
- `bq_uses_parameterized` — parameterized BigQuery queries
- `no_outbound_http_raw` — no unrestricted HTTP calls
- `pii_redaction_present` — redact() or presidio used
- `data_residency_gcp` — no disallowed external LLM domains

### llm_judge check names
- `capability_fidelity` — README claims vs implementation
- `prompt_injection` — prompt injection resistance
- `jailbreak` — jailbreak resistance
- `pii_leakage` — PII leakage risk
- `scope_adherence` — stays within README scope
- `ai_disclosure` — discloses AI nature

### runtime_test check names
- `required_files` — agent.py, requirements.txt, README.md, tests/
- `has_tests` — test files in tests/ directory
- `health_endpoint` — /health endpoint present
- `no_hallucinated_tools` — no undefined tool references

## Current Rule Registry

| ID | Name | Tier | File |
|----|------|------|------|
| SEC-001 | No Hardcoded Secrets | HARD | tier1-hard-gates.md |
| SEC-002 | Dependency CVE Scan | HARD | tier1-hard-gates.md |
| SEC-003 | Pinned Dependencies | SOFT | tier2-soft-gates.md |
| SEC-004 | No Overprivileged Tools | SOFT | tier2-soft-gates.md |
| SAF-001 | Prompt Injection Resistance | HARD | tier1-hard-gates.md |
| SAF-002 | Jailbreak Resistance | SOFT | tier2-soft-gates.md |
| SAF-003 | PII Leakage Test | HARD | tier1-hard-gates.md |
| SAF-004 | Data Exfiltration Risk | HARD | tier1-hard-gates.md |
| GOV-001 | Audit Logging Present | HARD | tier1-hard-gates.md |
| GOV-002 | Structured Log Format | SOFT | tier2-soft-gates.md |
| GOV-003 | Model Version Pinned | SOFT | tier2-soft-gates.md |
| GOV-004 | Cost Guardrails | SOFT | tier2-soft-gates.md |
| OBS-001 | Health Endpoint | SOFT | tier2-soft-gates.md |
| OBS-002 | OpenTelemetry Traces | SOFT | tier2-soft-gates.md |
| OBS-003 | Token Usage Tracked | SOFT | tier2-soft-gates.md |
| REL-001 | Timeout on Tool Calls | SOFT | tier2-soft-gates.md |
| REL-002 | Retry with Backoff | SOFT | tier2-soft-gates.md |
| REL-003 | Max Steps Limit | HARD | tier1-hard-gates.md |
| REL-004 | Error Handling | SOFT | tier2-soft-gates.md |
| ALI-001 | Scope Adherence | QUALITY | tier3-quality.md |
| ALI-002 | AI Disclosure | SOFT | tier2-soft-gates.md |
| QUA-001 | Capability Fidelity | QUALITY | tier3-quality.md |
| STR-001 | Required Files Present | HARD | tier1-hard-gates.md |
| STR-002 | Test Coverage Required | HARD | tier1-hard-gates.md |

**Total: 28 rules | 9 HARD gates | 17 SOFT gates | 2 QUALITY checks**

## Adding Rules Without Code Changes

Any rule using an existing `check_type` can be added to the markdown files
without touching the engine. The loader parses rules at startup.

To add a new check type, add one handler function to `engine/handlers/ast_check.py`
(or the appropriate handler file). After that, rules can use it in markdown immediately.

## Rule Versioning

Rules are tagged via Git. The running validator pins `RULES_VERSION` at deploy time.
Every agent's governance report includes the rules version it was validated against —
creating a permanent audit trail.
