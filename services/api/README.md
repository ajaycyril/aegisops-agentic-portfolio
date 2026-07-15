# API and Agent Runtime

The API service hosts the backend control plane and agent runtime.

## Responsibilities

- Authenticated workflow execution API.
- LangGraph runtime and graph registry.
- OpenAI Responses API calls.
- OpenAI Agents SDK specialist agents.
- MCP tool server/client boundaries.
- OPA policy checks.
- Human approval state.
- Postgres persistence, checkpoints, memory, and audit logs.
- Retrieval over authorized real data.
- Observability and trace export.
- Evaluation harness.

## Non-Goals

- No fake data workflows.
- No regex-based business extraction.
- No untyped tool calls.
- No autonomous write actions without policy and approval.

## Package Strategy

The initial manifest defines the production dependency surface. Implementation will be added
after the architecture baseline is accepted.

## Implemented Runtime Slices

- `engineering_issue_to_pr`: guarded GitHub issue/file evidence collection, captured-real
  replay loading, optional OpenAI proposal/evaluator contracts, pending approval-review
  persistence for proposed branch/PR actions, approve/reject decision persistence through OPA,
  approved-approval-ID PR draft authorization, dry-run PR preview evidence artifacts, and no
  write adapters.
- Tool adapters: read-only GitHub App REST access plus generic HTTP JSON read adapters for
  observability log search and deployment event search. The HTTP JSON adapters post typed tool
  inputs with a configured connection ID, normalize source URI identifiers, and convert
  upstream failures into controlled tool errors.
- `GET /workflow-runs/{run_id}/trace`: generic run metadata readout for approvals, tool calls,
  model calls, evidence records, and audit events.
- `incident_response_investigator`: guarded read-only evidence collection for observability
  logs, deployment events, optional GitHub files, and captured-real replay fixtures. Live
  observability/deployment reads use the HTTP JSON adapters when connector env vars are
  configured. The route returns source-grounded evidence validation and can create a typed
  hash-only RCA draft contract with `include_rca=true`. Its approval-review route can create
  pending approval records for rollback, paging, and incident-update proposals. Its decision
  route approves or rejects those records through policy without executing production write
  actions.
- `customer_support_escalation`: guarded read-only context collection for a real support
  ticket, CRM customer profile, and knowledge base citations. It persists hash-only/redacted
  evidence metadata, returns no raw customer messages, can create an internal cited response
  draft with `include_draft=true`, and can queue that draft for human approval without sending
  any customer-visible message. Its approval decision route records OPA-checked approve/reject
  outcomes without enabling send execution.
- `configs/evals/rubrics`: structured eval contracts for Engineering patch proposals and
  Incident RCA drafts, validated in tests without model calls or fake data.
