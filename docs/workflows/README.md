# Workflow Design Contracts

Each workflow is a production module. It is not a prompt folder.

## Required Structure

```text
workflows/<workflow_id>/
├── graph.py              # LangGraph graph definition
├── contracts.py          # Pydantic input/output/state models
├── tools.py              # Typed tool bindings
├── policies.rego         # Workflow-specific policy rules
├── prompts/              # Versioned prompts, if needed
├── evals/                # Workflow eval datasets and rubrics
├── README.md             # Workflow operating guide
└── tests/                # Graph, policy, and tool-contract tests
```

Implementation has started with
`services/api/src/aegisops_api/workflows/engineering_issue_to_pr/`. The current module contains
the first typed LangGraph state/input contract and read-only GitHub issue/file evidence nodes.
It is exposed through a controlled run-scoped evidence collection route that requires a stored
workflow run. Live mode uses read-only GitHub tools; replay mode requires a captured real-run
fixture. Optional planner/evaluator nodes can produce typed patch-plan and test-plan artifacts
when a real planner implementation is injected. The OpenAI Responses API planner adapter
records `model_calls` and is available from the run route with `include_proposal=true` when
OpenAI credentials and a model are configured. The approval-review route
`POST /workflow-runs/{run_id}/engineering-issue-to-pr/approval-review` persists pending
`approvals` rows for proposed branch and pull-request actions, validates action evidence URIs
against the proposal, records audit events, and moves the run to `waiting_for_approval`.
The decision route
`POST /workflow-runs/{run_id}/engineering-issue-to-pr/approvals/{approval_id}/decision`
approves or rejects pending approval records through OPA, stores decision metadata, and audits
the reviewer decision. The PR draft authorization route
`POST /workflow-runs/{run_id}/engineering-issue-to-pr/pr-draft/authorize` accepts approved
approval IDs and creates policy-checked write-class tool-call records in
`authorized_not_executed` or `blocked_before_execution` state. The PR draft preview route
`POST /workflow-runs/{run_id}/engineering-issue-to-pr/pr-draft/preview` verifies the approval,
tool-call state, and input hash before writing a dry-run `evidence_records` artifact with PR
metadata and hashes only. `GET /workflow-runs/{run_id}/trace` exposes the persisted run,
approval, tool-call, model-call, evidence, and audit metadata needed for UI readouts. The web
command center can read that endpoint when `DEMO_WORKFLOW_RUN_ID` or `DEMO_TRACE_RUN_ID` is
configured, then renders approval, PR authorization, and dry-run preview states without fake
fallback records. None of these routes executes branch or pull-request writes. The YAML files
under `configs/workflows` remain the portfolio registry.

`services/api/src/aegisops_api/workflows/incident_response_investigator/` now contains the
first Production Incident Investigator runtime slice. The route
`POST /workflow-runs/{run_id}/incident-response-investigator/evidence` requires a stored
workflow run. Live mode collects read-only observability log, deployment event, and optional
GitHub file evidence through policy-authorized tool calls. Observability and deployment reads
use generic HTTP JSON read adapters when `OBSERVABILITY_*` and `DEPLOYMENTS_*` connector env
vars are configured. Replay mode requires a captured real-run fixture using schema version
`incident_response_investigator.replay.v1`. Persisted evidence records keep hashes and metadata
instead of raw log/code payloads. The route returns source-grounded evidence validation for
every evidence item. When `include_rca=true`, it can create a typed RCA draft contract whose
claims may only cite grounded source evidence URIs and whose persisted draft artifact stores
hashes and metadata only. Rollback, paging, incident updates, and external write actions remain
disabled. The approval-review route
`POST /workflow-runs/{run_id}/incident-response-investigator/approval-review` creates pending
`approvals` rows for rollback, paging, and incident-update proposals from that RCA draft, but
does not execute those actions. The decision route
`POST /workflow-runs/{run_id}/incident-response-investigator/approvals/{approval_id}/decision`
approves or rejects those records through OPA and audits the decision while keeping production
actions disabled.

The command center also contains a multi-agent orchestration contract for
`incident_response_investigator`. It maps the Production Incident Investigator to supervisor,
parallel specialist, evaluator, RCA drafter, and approval nodes so the UI can show why this use
case justifies multi-agent orchestration while runtime support is built incrementally.

`services/api/src/aegisops_api/workflows/customer_support_escalation/` now contains the first
Customer Support Escalation runtime slice. The route
`POST /workflow-runs/{run_id}/customer-support-escalation/context` requires a stored live
workflow run. It collects a support ticket, CRM customer profile, and knowledge base documents
through policy-authorized read tools backed by HTTP JSON adapters. Persisted evidence stores
hashes and redacted metadata instead of raw customer messages or customer profile payloads.
With `include_draft=true`, it creates an internal cited response draft whose citations must
come from retrieved knowledge base source URIs. The approval-review route
`POST /workflow-runs/{run_id}/customer-support-escalation/approval-review` stores a pending
external-message approval record for that draft. The decision route
`POST /workflow-runs/{run_id}/customer-support-escalation/approvals/{approval_id}/decision`
records OPA-checked approve/reject decisions while keeping send execution disabled.
Customer-visible messages, refunds, and account changes remain disabled until send-disabled
authorization and final connector hardening are added.

## Workflow Contract

Every workflow must define:

- Workflow ID.
- Domain.
- Real connector requirements.
- Required scopes.
- Autonomy levels.
- Allowed tools.
- Approval requirements.
- Budget defaults.
- Memory policy.
- Retrieval policy.
- Eval gates.
- Visual surfaces.
- Deployment status.

## State Model

Every workflow graph must use typed state. State should include:

- Run metadata.
- User and organization context.
- Input artifact references.
- Policy context.
- Evidence collected.
- Tool results.
- Model outputs.
- Approval state.
- Cost state.
- Final artifact references.

## Tool Contract

Every tool must declare:

- Input schema.
- Output schema.
- Read/write classification.
- Auth scope.
- Rate limit.
- Cost behavior.
- Approval requirement.
- Observability fields.

## Completion Criteria

A workflow is production-ready only when it has:

- Real connector integration.
- Graph tests.
- Tool-contract tests.
- Policy tests.
- Eval harness.
- Trace view.
- Cost budget.
- Human approval path for sensitive actions.
- Deployment configuration.
