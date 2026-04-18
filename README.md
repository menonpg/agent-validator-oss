# Agent Validator 🛡️

**Rules-as-Markdown governance engine for AI agent deployments. Validates any GitHub repo against enterprise compliance standards before it ships.**

[![PyPI version](https://img.shields.io/pypi/v/soul-agent-validator.svg)](https://pypi.org/project/soul-agent-validator/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Powered by soul.py](https://img.shields.io/badge/memory-soul.py-8B5CF6)](https://github.com/menonpg/soul.py)
[![A2A Compatible](https://img.shields.io/badge/Google%20A2A-compatible-4285F4)](https://github.com/google-deepmind/agent-to-agent)
[![arXiv](https://img.shields.io/badge/arXiv-2604.09588-b31b1b.svg)](https://arxiv.org/abs/2604.09588)

Point it at a GitHub repo. Get back a structured report card: PASS / WARN / FAIL across security, structure, safety, and governance rules — before the agent ever touches production.

```bash
curl -X POST https://your-validator/validate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/your-org/your-agent", "submitter": "you"}'
```

Or install and run locally in seconds:

```bash
pip install soul-validator
soul-validator serve         # starts at http://localhost:8080
soul-validator validate https://github.com/your-org/your-agent
```

---

## Why

AI agents are being deployed into production with no pre-flight checks. They carry hardcoded secrets, call unauthorized APIs, skip PII redaction, have no rate limiting, and lack governance documentation. Agent Validator catches all of this before deployment — running 33 rules in seconds against any public or private GitHub repo.

Rules are plain Markdown. You can read them, edit them, and PR them. No DSL, no YAML schema, no proprietary format.

---

## What It Checks (33 rules across 4 tiers)

| Tier | Rules | Effect |
|------|-------|--------|
| **HARD** — security gates | SEC-001 (hardcoded secrets), SEC-002 (banned imports), SEC-003 (SSRF), A2A-001 (agent card), A2A-002 (A2A endpoint) | ❌ Reject — agent cannot deploy |
| **SOFT** — warnings | Rate limiting, PII redaction, error handling, input validation, data residency | ⚠️ Warn — deployable but flagged |
| **QUALITY** — best practices | README, CHANGELOG, SOUL.md, test coverage, dependency pinning | 📋 Advisory only |
| **A2A compliance** | `.well-known/agent.json`, JSON-RPC 2.0 endpoint, `tasks/send` method | Checked against Google A2A spec |

Full rule definitions: [`rules/`](rules/)

---

## Google A2A Compatible

Agent Validator is itself a Google A2A-compatible agent. It serves:

- `GET /.well-known/agent.json` — agent card with capabilities
- `POST /a2a` — JSON-RPC 2.0 `tasks/send` method

Orchestrators (LangGraph, CrewAI, ADK) can call it as a tool. Pass a GitHub URL, get a validation result.

```json
POST /a2a
{
  "jsonrpc": "2.0",
  "method": "tasks/send",
  "params": {
    "message": {
      "parts": [{"text": "validate https://github.com/your-org/your-agent"}]
    }
  }
}
```

---

## Architecture

```
agent-validator/
├── main.py              # FastAPI app — REST + A2A endpoints
├── engine/
│   ├── validator.py     # Orchestrates all rules, clones repo, runs checks
│   ├── rule_loader.py   # Parses rules/*.md → Rule objects
│   ├── report.py        # Builds structured ReportCard
│   ├── handlers/        # Check implementations (regex, AST, structure)
│   └── soul/            # soul.py identity files (SOUL.md, MEMORY.md)
├── rules/               # All rules as Markdown — edit to customize
│   ├── tier1-hard-gates.md
│   ├── tier2-soft-gates.md
│   ├── tier3-quality.md
│   ├── a2a-compliance.md
│   └── RULES.md         # Rule index + authoring guide
├── ui/                  # Single-page frontend (plain HTML/JS)
└── docs/                # GitHub Pages landing + API reference
```

The rule engine parses Markdown at startup. Each rule has:
- **Tier** (HARD/SOFT/QUALITY)
- **Check type** (`regex_scan`, `ast_check`, `structure_check`)
- **Parameters** (YAML block in the Markdown)
- **Pass condition** and **failure message**

Add a rule = write a Markdown file. No code changes required.

---

## Custom Rules

Copy `rules/tier1-hard-gates.md` as a template and create `rules/custom.md`:

```markdown
## RULE: CUSTOM-001 — No Direct DB Writes

**Tier:** HARD (fail = reject)
**Check type:** regex_scan
**Tags:** data-integrity

### Description
Agents must not write directly to the database. All mutations must go through the data layer.

### Parameters
```yaml
patterns:
  - "execute\\s*\\(.*INSERT"
  - "execute\\s*\\(.*UPDATE"
file_glob: "**/*.py"
```

### Failure Message
> ❌ Direct DB write detected. Use the data access layer instead.
```

---

## Quickstart (Local)

**Prerequisites:** Python 3.11+, `git` installed on PATH (for repo cloning).

```bash
# 1. Clone
git clone https://github.com/menonpg/agent-validator-oss.git
cd agent-validator-oss

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set required env vars
export OPENAI_API_KEY=sk-...           # for LLM-judge checks (optional — rule engine works without it)
export SERVICE_URL=http://localhost:8080

# 4. Run
uvicorn main:app --host 0.0.0.0 --port 8080 --reload

# 5. Validate a repo
curl -X POST http://localhost:8080/validate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/menonpg/soul.py", "submitter": "you"}'
# → {"job_id": "abc123", "status": "queued"}

# 6. Poll for result
curl http://localhost:8080/validate/abc123
```

Open `http://localhost:8080` in your browser for the full UI.

**No LLM key?** The regex, AST, and structure checks all run without one. Only `llm_judge` checks require `OPENAI_API_KEY` — the report will skip those rules gracefully.

---

## Deploy

**Docker:**
```bash
docker build -t agent-validator .
docker run -p 8080:8080 \
  -e RULES_VERSION=v1.0.0 \
  -e SERVICE_URL=https://your-domain.com \
  agent-validator
```

**Cloud Run (GCP):**
```bash
gcloud run deploy agent-validator \
  --source . \
  --region us-central1 \
  --allow-unauthenticated
```

**Railway:**
```bash
railway up
```

---

## soul.py Integration

The validator's governance auditor persona is powered by [soul.py](https://github.com/menonpg/soul.py) — it loads `engine/soul/SOUL.md` and `engine/soul/MEMORY.md` on startup to maintain consistent, principled review behavior across validations.

Related paper: [*Persistent Identity in AI Agents* — arXiv:2604.09588](https://arxiv.org/abs/2604.09588)

---

## License

MIT — use it, fork it, embed it in your CI pipeline.

Built by [The Menon Lab](https://themenonlab.com)
