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
  and no write adapters.
- `incident_response_investigator`: guarded read-only evidence collection for observability
  logs, deployment events, optional GitHub files, and captured-real replay fixtures. RCA
  generation and production write actions remain disabled until approval and validation paths
  exist.
