# A2A Compliance Rules
*Google Agent-to-Agent (A2A) Protocol — https://google.github.io/A2A*
*Added: 2026-03-19*

Agents deployed in enterprise multi-agent pipelines must expose a discoverable,
interoperable interface per the A2A open protocol. These rules ensure agents can
be orchestrated by any A2A-compatible runtime.

---

## RULE: A2A-001 — Agent Card Required

**Tier:** HARD (fail = reject)
**Check type:** a2a_check
**Severity:** CRITICAL
**Tags:** a2a, interoperability, discoverability

### Description
Every A2A-compliant agent must expose a machine-readable Agent Card at
`.well-known/agent.json` in the repository root. The Agent Card declares the
agent's identity, capabilities, skills, and authentication requirements, enabling
orchestrators to discover and invoke the agent without prior configuration.

### Parameters
```yaml
check: agent_card_exists
required_fields:
  - name
  - description
  - version
  - url
  - capabilities
  - skills
```

### Pass Condition
`.well-known/agent.json` exists and contains all required top-level fields.

### Failure Message
> ❌ No Agent Card found at `.well-known/agent.json`.
> A2A-compliant agents must expose a discoverable Agent Card.
> See: https://google.github.io/A2A/#/documentation?id=agent-card

### References
- Google A2A Spec: Agent Card
- ADK Enterprise Guidelines: Agent Discoverability

---

## RULE: A2A-002 — Task Endpoint Implements JSON-RPC 2.0

**Tier:** HARD (fail = reject)
**Check type:** a2a_check
**Severity:** CRITICAL
**Tags:** a2a, interoperability, json-rpc

### Description
A2A agents must expose a task endpoint that accepts JSON-RPC 2.0 messages
using the `tasks/send` method. The request/response envelope must conform to
the A2A task message format, enabling any A2A-compatible orchestrator to
dispatch work without bespoke integration.

### Parameters
```yaml
check: task_endpoint
patterns:
  - "tasks/send"
  - "jsonrpc"
  - "json_rpc"
  - "JsonRpc"
  - "JSONRPC"
file_glob: "**/*.py"
```

### Pass Condition
At least one source file contains references to `tasks/send` or JSON-RPC 2.0
task handling patterns.

### Failure Message
> ❌ No A2A task endpoint detected.
> Agents must implement a `tasks/send` JSON-RPC 2.0 endpoint.
> See: https://google.github.io/A2A/#/documentation?id=tasks

### References
- Google A2A Spec: Task Object
- JSON-RPC 2.0 Specification

---

## RULE: A2A-003 — Task Lifecycle States Handled

**Tier:** SOFT (fail = warn + score penalty)
**Check type:** a2a_check
**Severity:** HIGH
**Tags:** a2a, reliability, task-lifecycle

### Description
A2A tasks move through defined lifecycle states: `submitted`, `working`,
`completed`, `failed`, and `cancelled`. Agents that do not implement proper
state transitions may leave orchestrators with stale or unknown task states,
causing pipeline failures.

### Parameters
```yaml
check: task_states
required_states:
  - submitted
  - working
  - completed
  - failed
file_glob: "**/*.py"
```

### Pass Condition
Source code references at least `submitted`, `working`, `completed`, and
`failed` task states.

### Failure Message
> ⚠️ Incomplete A2A task lifecycle implementation.
> Implement all required states: submitted → working → completed/failed/cancelled.
> See: https://google.github.io/A2A/#/documentation?id=task-states

### References
- Google A2A Spec: Task States
- A2A Best Practices: State Machine Design

---

## RULE: A2A-004 — Authentication Declared in Agent Card

**Tier:** SOFT (fail = warn + score penalty)
**Check type:** a2a_check
**Severity:** HIGH
**Tags:** a2a, security, authentication

### Description
The Agent Card must declare the authentication scheme(s) supported by the agent.
This enables orchestrators to authenticate before dispatching tasks. Supported
schemes include `apiKey`, `oauth2`, `bearer`, and `none` (for internal agents).

### Parameters
```yaml
check: agent_card_auth
required_field: authentication
valid_schemes:
  - apiKey
  - oauth2
  - bearer
  - none
```

### Pass Condition
`.well-known/agent.json` contains an `authentication` field with a valid scheme.

### Failure Message
> ⚠️ Agent Card missing `authentication` declaration.
> Declare auth scheme in Agent Card: apiKey, oauth2, bearer, or none.
> See: https://google.github.io/A2A/#/documentation?id=agent-authentication

### References
- Google A2A Spec: Authentication
- NIST AI RMF: GOVERN 1.2

---

## RULE: A2A-005 — Streaming Support Declared

**Tier:** SOFT (fail = warn + score penalty)
**Check type:** a2a_check
**Severity:** MEDIUM
**Tags:** a2a, streaming, ux

### Description
Long-running A2A tasks should support streaming updates via Server-Sent Events
(SSE) using the `tasks/sendSubscribe` method. The Agent Card's `capabilities`
block must declare `streaming: true|false`. Undeclared streaming capability
causes orchestrators to assume no streaming and may degrade UX for long tasks.

### Parameters
```yaml
check: agent_card_streaming
capability_field: streaming
```

### Pass Condition
`.well-known/agent.json` `capabilities` block contains a `streaming` field
(true or false — declaration required regardless of value).

### Failure Message
> ⚠️ Agent Card `capabilities.streaming` not declared.
> Declare streaming support (true/false) so orchestrators can choose the
> appropriate invocation method.
> See: https://google.github.io/A2A/#/documentation?id=streaming

### References
- Google A2A Spec: Streaming
- Server-Sent Events (SSE) standard
