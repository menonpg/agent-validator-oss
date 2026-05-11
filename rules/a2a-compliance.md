# A2A Compliance Rules
*A2A Protocol v1.0 (Linux Foundation) — https://a2a-protocol.org*
*Added: 2026-03-19 | Last updated: 2026-05-11*

> **⚠️ Update Notice (2026-05-11):** A2A was formally transferred to the Linux Foundation as an open standard on April 9, 2026 (v1.0). All spec URLs, method names, and capability fields have been updated to reflect v1.0. Two new rules (A2A-006, A2A-007) have been added.

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

A2A v1.0 expands required fields to include `provider`, `defaultInputModes`,
and `defaultOutputModes`. Agents may also optionally publish a **Signed Agent Card**
(`signedCard`) for cryptographic identity verification, enabling orchestrators to
verify agent authenticity before dispatching tasks.

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
  - provider              # Added in v1.0
  - defaultInputModes     # Added in v1.0
  - defaultOutputModes    # Added in v1.0
recommended_fields:
  - signedCard            # Added in v1.0 — cryptographic identity
```

### Pass Condition
`.well-known/agent.json` exists and contains all required top-level fields.

### Failure Message
> ❌ No Agent Card found at `.well-known/agent.json`, or required fields are missing.
> A2A-compliant agents must expose a discoverable Agent Card including `provider`,
> `defaultInputModes`, and `defaultOutputModes` as of A2A v1.0.
> See: https://a2a-protocol.org/documentation/agent-card

### References
- A2A v1.0 Spec: Agent Card
- ADK Enterprise Guidelines: Agent Discoverability

---

## RULE: A2A-002 — Task Endpoint Implements JSON-RPC 2.0

**Tier:** HARD (fail = reject)
**Check type:** a2a_check
**Severity:** CRITICAL
**Tags:** a2a, interoperability, json-rpc

### Description
A2A agents must expose a task endpoint that accepts JSON-RPC 2.0 messages.
In A2A v1.0, the protocol unifies task invocation under a messaging model:
`tasks/send` remains valid, and `message/send` is now the canonical v1.0
invocation method. `message/stream` is the corresponding streaming invocation path.
The request/response envelope must conform to the A2A task message format,
enabling any A2A-compatible orchestrator to dispatch work without bespoke integration.

### Parameters
```yaml
check: task_endpoint
patterns:
  - "tasks/send"
  - "message/send"      # Added in v1.0 — canonical invocation method
  - "message/stream"    # Added in v1.0 — streaming invocation
  - "jsonrpc"
  - "json_rpc"
  - "JsonRpc"
  - "JSONRPC"
file_glob: "**/*.py"
```

### Pass Condition
At least one source file contains references to `tasks/send`, `message/send`,
or JSON-RPC 2.0 task handling patterns.

### Failure Message
> ❌ No A2A task endpoint detected.
> Agents must implement a `message/send` (v1.0) or `tasks/send` JSON-RPC 2.0 endpoint.
> See: https://a2a-protocol.org/documentation/tasks

### References
- A2A v1.0 Spec: Task Object & Message Model
- JSON-RPC 2.0 Specification

---

## RULE: A2A-003 — Task Lifecycle States Handled

**Tier:** SOFT (fail = warn + score penalty)
**Check type:** a2a_check
**Severity:** HIGH
**Tags:** a2a, reliability, task-lifecycle

### Description
A2A tasks move through defined lifecycle states: `submitted`, `working`,
`completed`, `failed`, `cancelled`, and — as of A2A v1.0 — `input-required`.
The `input-required` state supports human-in-the-loop workflows, where an agent
pauses execution and awaits user input before proceeding. Agents that do not
implement proper state transitions may leave orchestrators with stale or unknown
task states, causing pipeline failures.

### Parameters
```yaml
check: task_states
required_states:
  - submitted
  - working
  - completed
  - failed
  - input-required    # Added in v1.0 — human-in-the-loop support
file_glob: "**/*.py"
```

### Pass Condition
Source code references at least `submitted`, `working`, `completed`, `failed`,
and `input-required` task states.

### Failure Message
> ⚠️ Incomplete A2A task lifecycle implementation.
> Implement all required states: submitted → working → input-required → completed/failed/cancelled.
> See: https://a2a-protocol.org/documentation/task-states

### References
- A2A v1.0 Spec: Task States
- A2A Best Practices: State Machine Design

---

## RULE: A2A-004 — Authentication Declared in Agent Card

**Tier:** SOFT (fail = warn + score penalty)
**Check type:** a2a_check
**Severity:** HIGH
**Tags:** a2a, security, authentication

### Description
The Agent Card must declare the authentication scheme(s) supported by the agent.
This enables orchestrators to authenticate before dispatching tasks. A2A v1.0
adds `openIdConnect` as a first-class supported scheme alongside existing options,
and introduces enterprise-grade multi-tenancy support for `oauth2` flows.

### Parameters
```yaml
check: agent_card_auth
required_field: authentication
valid_schemes:
  - apiKey
  - oauth2
  - bearer
  - openIdConnect     # Added in v1.0
  - none
```

### Pass Condition
`.well-known/agent.json` contains an `authentication` field with a valid scheme.

### Failure Message
> ⚠️ Agent Card missing `authentication` declaration.
> Declare auth scheme in Agent Card: apiKey, oauth2, bearer, openIdConnect, or none.
> See: https://a2a-protocol.org/documentation/authentication

### References
- A2A v1.0 Spec: Authentication & Multi-Tenancy
- NIST AI RMF: GOVERN 1.2

---

## RULE: A2A-005 — Streaming Support Declared

**Tier:** SOFT (fail = warn + score penalty)
**Check type:** a2a_check
**Severity:** HIGH
**Tags:** a2a, streaming, push-notifications, ux

> **⚠️ Severity upgraded from MEDIUM → HIGH (2026-05-11):** Streaming is now a
> primary invocation path in A2A v1.0, deeply integrated across all major cloud
> platforms (Azure AI Foundry, Amazon Bedrock AgentCore). `pushNotifications` is
> a new v1.0 capability field that must also be declared.

### Description
Long-running A2A tasks must support streaming updates. In A2A v1.0, streaming
is exposed via `message/stream` (superseding `tasks/sendSubscribe`), using
Server-Sent Events (SSE). Additionally, agents must declare `pushNotifications`
support in the Agent Card `capabilities` block. Undeclared streaming or push
notification capability causes orchestrators to assume no streaming and may
degrade UX for long-running tasks.

### Parameters
```yaml
check: agent_card_streaming
capability_fields:
  - streaming           # Declare true/false — required regardless of value
  - pushNotifications   # Added in v1.0 — declare push notification support
```

### Pass Condition
`.well-known/agent.json` `capabilities` block contains both a `streaming` field
and a `pushNotifications` field (true or false — declaration required regardless of value).

### Failure Message
> ⚠️ Agent Card `capabilities.streaming` or `capabilities.pushNotifications` not declared.
> Declare streaming and push notification support (true/false) so orchestrators
> can choose the appropriate invocation method (`message/stream`).
> See: https://a2a-protocol.org/documentation/streaming

### References
- A2A v1.0 Spec: Streaming & Push Notifications
- Server-Sent Events (SSE) standard

---

## RULE: A2A-006 — Runtime and SDK Compatibility Declared

**Tier:** SOFT (fail = warn + score penalty)
**Check type:** a2a_check
**Severity:** MEDIUM
**Tags:** a2a, interoperability, sdk, multi-protocol

> **🆕 New rule added 2026-05-11** — reflects A2A v1.0 multi-language SDK expansion.

### Description
A2A v1.0 expanded the official SDK ecosystem to five production languages:
Python, JavaScript, Java, Go, and .NET. Agents should declare their runtime
environment in the Agent Card to enable orchestrators to select compatible agents
in heterogeneous multi-agent pipelines. This is especially important in
multi-protocol environments where agents may be invoked across different runtimes.

### Parameters
```yaml
check: agent_card_runtime
recommended_field: runtimeEnvironment
valid_runtimes:
  - python
  - javascript
  - java
  - go
  - dotnet
```

### Pass Condition
`.well-known/agent.json` contains a `runtimeEnvironment` or equivalent
capability declaration identifying the agent's SDK/language runtime.

### Failure Message
> ⚠️ Agent Card does not declare a `runtimeEnvironment`.
> Declare runtime/SDK compatibility to support multi-protocol orchestration
> across Python, JavaScript, Java, Go, or .NET environments.
> See: https://a2a-protocol.org/documentation/sdk

### References
- A2A v1.0 Spec: SDK Reference
- Linux Foundation A2A Project: https://a2a-protocol.org

---

## RULE: A2A-007 — Agent Payments Protocol (AP2) Declared (if applicable)

**Tier:** SOFT (fail = warn + score penalty)
**Check type:** a2a_check
**Severity:** MEDIUM
**Tags:** a2a, payments, ap2, financial

> **🆕 New rule added 2026-05-11** — reflects A2A v1.0 Agent Payments Protocol (AP2) launch.

### Description
A2A v1.0 introduced the **Agent Payments Protocol (AP2)** for secure, agent-driven
financial transactions, with 60+ organisations already declaring support at launch.
Agents operating in financial services, procurement, or e-commerce pipelines must
declare AP2 compatibility in their Agent Card `capabilities` block so that
orchestrators can safely route payment-bearing tasks to compliant agents only.

### Parameters
```yaml
check: agent_card_ap2
capability_field: payments
applicable_domains:
  - financial-services
  - procurement
  - e-commerce
required_if: domain in applicable_domains
```

### Pass Condition
If the agent operates in a financial or transactional domain, `.well-known/agent.json`
`capabilities` block declares a `payments` field with an AP2-compliant scheme.
Agents outside these domains may omit this field without penalty.

### Failure Message
> ⚠️ Agent in a financial/transactional domain does not declare AP2 payment capability.
> Add `capabilities.payments` with an AP2 scheme to your Agent Card.
> See: https://a2a-protocol.org/documentation/payments

### References
- A2A v1.0 Spec: Agent Payments Protocol (AP2)
- Linux Foundation A2A Project: https://a2a-protocol.org