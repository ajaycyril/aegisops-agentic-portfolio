# Security and Governance

Production agentic systems need safety outside the prompt.

## Governance Layers

| Layer | Control |
| --- | --- |
| Auth | User identity, org, role, connector scopes |
| Policy | OPA decisions for tools, data, budgets, approvals |
| Tool contracts | Typed inputs, outputs, auth scopes, read/write classification |
| Guardrails | Pydantic validation, structured outputs, safety checks |
| Human approval | Required for sensitive write actions |
| Audit | Immutable trace of decisions, tools, approvals, and outputs |
| Budget | Max runtime, model spend, tool calls, retries |
| Data control | Source metadata, retention rules, PII handling |

## Approval Defaults

Human approval is required for:

- Pull request creation.
- External customer messages.
- Refunds and payments.
- Supplier status changes.
- Access grants.
- Rollbacks and incident updates.
- Audit exports.
- Saved executive reports.

## No Regex Business Logic

Regex is not allowed for business extraction, parsing, routing, or policy decisions.

Use:

- Typed SDKs for APIs.
- OpenAPI clients for external services.
- Pydantic models for structured outputs.
- JSON Schema for tool contracts.
- Markdown/HTML/AST parsers for documents and code.
- SQLAlchemy for database interaction.
- OPA/Rego for policy.

## Real Data Only

Workflows stay disabled until their real connectors are configured. Captured replay mode is
allowed only when the captured source was a real run.

## Threats To Design Against

- Prompt injection through tickets, docs, emails, and web pages.
- Excessive agency through over-permissive tools.
- Data leakage through memory or external messages.
- Tool misuse through malformed arguments.
- Hidden cost escalation through loops and retries.
- Weak auditability through missing traces.
- Policy bypass through model-generated instructions.

## Required Runtime Checks

Every model or tool step must carry:

- Workflow ID.
- Run ID.
- User ID.
- Org ID.
- Autonomy level.
- Policy decision ID.
- Trace ID.
- Budget state.
- Data sensitivity classification.
