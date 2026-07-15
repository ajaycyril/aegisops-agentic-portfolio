# AegisOps Incremental Project Plan

This document is the canonical execution plan for the repository. It is written so a future
agent can continue the project without chat context.

## Product Goal

Build a production-grade, visual-first agentic workflow platform that demonstrates enterprise
agentic AI across multiple real business domains.

The platform must show:

- Many production agentic workflow categories.
- Real integrations and real data readiness.
- Clear segmentation between deterministic, dynamic policy, AI workflow, and agentic execution.
- Full stack depth: orchestration, tools, memory, guardrails, policy, approval, observability,
  evals, deployment, and cost controls.
- A visual peel-the-layers UI for CEOs, CTOs, and engineers.

## Current Status

Phases 0 and 1 are complete. Phases 2, 3, and 4 are implemented at code/test level, with
live Docker/Postgres/OPA verification still pending on a machine with Docker available.

The repo has architecture docs, dependency manifests, workflow registry configs, local infra
scaffolding, ADRs, CI scaffolding, a minimal API health skeleton, a deployed web shell,
database migrations, governance tables, OPA policy scaffolding, an audit writer, typed
workflow registry/read endpoints, a policy-gated workflow run-start API, and a registry-aware
visual command center. Phase 5 has started with typed tool contracts, read-only tool registry
endpoints, an MCP contract server skeleton, a connector auth/readiness registry, and a
policy-checked tool authorization boundary. The first read-only GitHub App adapter is in place
for issue and file reads through a stored authorized tool call, and the Engineering Issue-to-PR
LangGraph module now orchestrates those read-only nodes through a controlled run-scoped
evidence collection route. Captured-real-run replay schema and loading are wired for the same
route without committing fabricated replay payloads. Optional proposal and evaluator graph
nodes now exist with typed patch-plan, test-plan, and evaluation contracts, but no write
actions are enabled. A model-backed OpenAI Responses API planner adapter now records
`model_calls` and can be invoked from the run-scoped Engineering route with
`include_proposal=true` when OpenAI credentials and an explicit model are configured. The
visual command center now surfaces the proposal/evaluation contract, planner readiness,
model-call audit path, and approval stop-points without showing fake run output or enabling
branch/PR writes. It also includes a React Flow multi-agent orchestration cockpit for the
Production Incident Investigator, showing a supervisor-worker fan-out, specialist evidence
streams, evaluator reconciliation, and approval-gated production actions as a visual contract
only. The Production Incident Investigator now also has a first backend runtime slice: a typed
LangGraph evidence-collection graph and run-scoped API route for read-only observability log,
deployment event, and GitHub file evidence collection, with policy-authorized tool calls,
evidence metadata persistence, captured-real-run replay loading, and no RCA or write actions
enabled.

Current production web deployment:

- https://aegisops-agentic-portfolio.vercel.app

## Milestone Map

| Phase | Name                                 | Status                                       | Outcome                                                                             |
| ----- | ------------------------------------ | -------------------------------------------- | ----------------------------------------------------------------------------------- |
| 0     | Architecture baseline                | Complete                                     | Docs, stack decisions, workflow portfolio, scaffold                                 |
| 1     | Foundation runtime                   | Complete                                     | Installable web/API skeleton with health checks                                     |
| 2     | Governance and data layer            | Implemented, Docker verification pending     | Postgres, migrations, policy checks, audit model                                    |
| 3     | Workflow registry and run lifecycle  | Implemented, live infra verification pending | Config-driven workflow catalog and run API                                          |
| 4     | Visual command center shell          | Implemented                                  | Portfolio UI, graph canvas, multi-agent canvas, review, trace/evidence placeholders |
| 5     | Tool and connector substrate         | In progress                                  | MCP tool contracts, GitHub connector foundation                                     |
| 6     | Engineering Issue-to-PR workflow     | In progress                                  | First real production workflow                                                      |
| 7     | Incident Investigator workflow       | In progress                                  | Real observability/deployment investigation workflow                                |
| 8     | Customer Support Escalation workflow | Not started                                  | Real support/KB/CRM workflow path                                                   |
| 9     | Evals, replay, and demo hardening    | Not started                                  | Captured real-run replay and quality gates                                          |
| 10    | Deployment and portfolio polish      | Not started                                  | Public free-tier deployment and executive-grade UI                                  |

## Phase 0: Architecture Baseline

Status: Complete.

Completed artifacts:

- `README.md`
- `docs/architecture/*`
- `docs/use-cases/README.md`
- `docs/workflows/README.md`
- `docs/adrs/*`
- `configs/workflows/*`
- `configs/policies/policy-map.yaml`
- `infra/docker-compose.yml`
- `services/api/pyproject.toml`
- `apps/web/package.json`
- `pnpm-lock.yaml`
- `.github/workflows/ci.yml`

Acceptance checks already run:

- `pnpm install --lockfile-only`
- Python dependency dry-run in a temporary virtualenv.
- `node scripts/check-docs-placeholders.mjs`

## Phase 1: Foundation Runtime

Status: Complete.

Completed in current phase:

- Minimal FastAPI app at `services/api/src/aegisops_api/main.py`.
- Environment settings with `pydantic-settings`.
- `/health`, `/ready`, and `/version` endpoints.
- Structured logging setup.
- Minimal Next.js visual command-center shell under `apps/web`.
- Animated visual command-center UI using Framer Motion and Recharts.
- Mobile-first responsive command-center pass verified across 360, 390, 768, and 1440 px
  browser viewports.
- API health endpoint tests.
- Vercel production deployment for the visual shell.
- Basic API status wiring from the web app to `NEXT_PUBLIC_API_BASE_URL`.
- Local development setup documentation.

Goal: Make the repo installable and runnable with minimal skeleton services.

Tasks:

1. Done: add a minimal FastAPI app at `services/api/src/aegisops_api/main.py`.
2. Done: add environment settings with `pydantic-settings`.
3. Done: add `/health`, `/ready`, and `/version` endpoints.
4. Done: add structured logging setup.
5. Done: add a minimal Next.js app shell under `apps/web`.
6. Done: add basic API client wiring from web to backend.
7. Done: add local development docs for install/run commands.
8. Done: update CI to install dependencies and run lightweight validation.

Acceptance criteria:

- `make install` completes on a clean machine with supported runtimes.
- `make api-dev` starts FastAPI.
- `make web-dev` starts Next.js.
- Health endpoints return structured JSON.
- No OpenAI key is required for health checks.
- No workflow business logic exists yet.

Validation commands:

```bash
pnpm install
pnpm typecheck
python3 -m venv services/api/.venv
services/api/.venv/bin/python -m pip install -e "services/api[dev]"
services/api/.venv/bin/pytest
```

## Phase 2: Governance and Data Layer

Status: Implemented. Live Docker/Postgres migration verification is pending because Docker was
not available in the current local environment.

Completed artifacts:

- SQLAlchemy database module under `services/api/src/aegisops_api/db/`.
- Alembic setup under `services/api/alembic/`.
- Initial migration for workflow registry snapshots, workflow runs, audit events, approvals,
  tool calls, model calls, memory records, and evidence records.
- pgvector extension migration plus HNSW embedding index for memory records.
- OPA HTTP client under `services/api/src/aegisops_api/policy/`.
- Baseline Rego packages under `policies/aegisops/`.
- Structured JSON policy fixtures under `configs/policies/fixtures/`.
- Audit event writer under `services/api/src/aegisops_api/audit/`.
- Tests for schema metadata, Alembic head, OPA client behavior, policy fixtures, and audit
  writer behavior.

Goal: Add durable system state before agent behavior.

Tasks:

1. Done: add SQLAlchemy database module.
2. Done: add Alembic migration setup.
3. Done: create tables for workflow registry snapshots, workflow runs, audit events, approvals,
   tool calls, model calls, memory records, and evidence records.
4. Done: enable pgvector extension migration.
5. Done: add OPA client.
6. Done: add baseline Rego packages for tool access, approvals, budget, and data sensitivity.
7. Done: add policy test fixtures using structured JSON inputs.
8. Done: add audit event writer.

Acceptance criteria:

- `docker compose -f infra/docker-compose.yml up -d` starts Postgres, Redis, and OPA.
- Migrations apply locally.
- Policy checks are callable from API code.
- Audit events can be written and queried.
- No policy decision is delegated to the model.

Validation commands:

```bash
make infra-up
services/api/.venv/bin/alembic upgrade head
services/api/.venv/bin/pytest services/api/tests
services/api/.venv/bin/ruff check services/api
cd services/api && .venv/bin/mypy .
```

Validated in current environment:

```bash
services/api/.venv/bin/pytest services/api/tests
services/api/.venv/bin/ruff check services/api
cd services/api && .venv/bin/mypy .
cd services/api && .venv/bin/alembic upgrade head --sql
```

Not run: `make infra-up` and live `alembic upgrade head`, because Docker is not installed.

## Phase 2 Follow-Up: Live Infra Verification

Goal: verify Phase 2 against local containers before starting durable run APIs.

Tasks:

1. Install/start Docker Desktop.
2. Run `make infra-up`.
3. Run `cd services/api && .venv/bin/alembic upgrade head`.
4. Confirm OPA loads `policies/aegisops/*.rego`.
5. Run `services/api/.venv/bin/pytest services/api/tests`.

## Phase 3: Workflow Registry and Run Lifecycle

Status: Implemented. Live Postgres/OPA verification is pending because Docker and the OPA CLI
were not available in the current local environment.

Completed artifacts:

- Pydantic workflow config models under `services/api/src/aegisops_api/workflows/`.
- YAML loader for `configs/workflows/*.yaml`.
- `GET /workflows`.
- `GET /workflows/{workflow_id}`.
- Connector readiness reporting for registry reads. Workflows remain disabled unless real
  connector names are configured through `CONFIGURED_CONNECTORS`.
- `POST /workflow-runs` with typed request/response models.
- Run-start readiness checks for workflow status, required connectors, replay source, replay
  eligibility, budget envelope, live-run feature flag, and OPA run eligibility.
- Durable run creation through the governance data model when policy allows or requires
  approval.
- Workflow registry snapshots and audit events written during run creation.
- `aegisops.run_eligibility` Rego policy plus replay/live policy fixtures.
- Tests for workflow config loading, real-data policy enforcement, disabled-by-default
  readiness, list/detail endpoints, unknown workflow 404s, run-start persistence, approval
  gating, pre-policy rejects, policy rejects, and API rejection responses.

Goal: Convert YAML workflow configs into a typed runtime registry and run lifecycle.

Tasks:

1. Done: add Pydantic models for workflow config files.
2. Done: load and validate `configs/workflows/*.yaml`.
3. Done: expose `GET /workflows`.
4. Done: expose `GET /workflows/{workflow_id}`.
5. Done: add `POST /workflow-runs` with run eligibility checks.
6. Done: add run status states: queued, running, waiting_for_approval, completed, failed,
   canceled.
7. Done: add budget envelope model.
8. Done: add replay/live execution mode model.
9. Done: add connector readiness checks for registry reads and run starts.

Acceptance criteria:

- Invalid workflow YAML fails fast.
- Workflows are disabled until connector requirements are satisfied.
- Starting a workflow creates a durable run record.
- Run creation calls OPA before execution.

Validated in current environment:

```bash
services/api/.venv/bin/pytest services/api/tests
services/api/.venv/bin/ruff check services/api
cd services/api && .venv/bin/mypy .
```

Not run: live Postgres migration and live OPA policy loading/evaluation, because Docker and
the OPA CLI are not installed in the current environment.

Current next task:

1. Run live Phase 2/3 infrastructure verification on a machine with Docker.
2. Continue Phase 5 with connector auth registry and real connector adapters behind the
   policy-checked tool authorization boundary.

## Phase 4: Visual Command Center Shell

Status: Implemented.

Completed artifacts:

- Registry-aware web catalog loader in `apps/web/lib/api.ts`.
- Repository workflow catalog mirror in `apps/web/lib/workflows.ts` used only when the live
  API registry is not configured or reachable.
- Interactive command center in `apps/web/components/command-center.tsx`.
- Selectable enterprise workflow portfolio.
- Safe disabled run-start controls for replay and live mode.
- React Flow graph canvas with config-driven workflow nodes.
- Evidence Board empty state derived from required connectors and scopes.
- Policy Lens derived from workflow data policy, OPA run-start rules, and approval actions.
- Trace Timeline empty state showing implemented run-start gates and runtime-pending events.
- Code Lens rendering the selected workflow YAML contract.
- Proposal Review surface showing run route, readiness gates, typed planner/evaluator output
  contracts, model-call audit path, and approval stop-points.
- Multi-Agent Orchestration surface for Production Incident Investigator, with custom React
  Flow supervisor, specialist worker, evaluator, RCA, and approval nodes.
- Favicon and mobile-first responsive styling.

Goal: Build the UI surface before deep workflow implementation.

Tasks:

1. Done: add app layout and navigation.
2. Done: add Portfolio page listing workflow modules from the API with repository mirror
   fallback when no backend is deployed.
3. Done: add Command Center page for a selected workflow.
4. Done: add React Flow graph canvas with static config-driven nodes.
5. Done: add Evidence Board empty state.
6. Done: add Policy Lens empty state.
7. Done: add Trace Timeline empty state.
8. Done: add Code Lens read-only panes for YAML config and policy metadata.
9. Done: add visual status for connector readiness, replay availability, and live-run
   eligibility.
10. Done: add Proposal Review surface and graph node for planner/evaluator contracts.
11. Done: add multi-agent incident orchestration visual contract with specialist handoff
    inspection.

Acceptance criteria:

- A CEO can understand what each workflow does.
- A CTO can see the platform layers.
- An engineer can inspect the config and contracts.
- The UI does not imply fake data is available.

Validated in current environment:

```bash
pnpm --filter @aegisops/web lint
pnpm --filter @aegisops/web typecheck
pnpm --filter @aegisops/web build
```

Browser smoke checks were run with Playwright against `http://localhost:3000` at 1440 px and
390 px widths. Both passed with no console errors, no horizontal overflow, no clipped text,
all seven primary graph nodes rendered, and all nine multi-agent orchestration nodes rendered.

## Phase 5: Tool and Connector Substrate

Status: In progress.

Completed artifacts:

- Tool contract YAML configs under `configs/tools/`.
- Pydantic tool registry models under `services/api/src/aegisops_api/tools/`.
- Risk classes: read, draft, write, external_message, financial, access_change.
- Read-only `GET /tools` and `GET /tools/{tool_id}` endpoints.
- Non-executing MCP contract server skeleton under
  `services/api/src/aegisops_api/tools/mcp_server.py`.
- `POST /tool-calls/authorize` policy gate for schema-validated, OPA-checked, audit-logged
  tool calls.
- Connector auth/readiness YAML configs under `configs/connectors/`.
- Pydantic connector registry models under `services/api/src/aegisops_api/connectors/`.
- Read-only `GET /connectors` and `GET /connectors/{connector_id}` endpoints.
- Coverage tests requiring every workflow/tool connector to have an explicit readiness
  contract.
- Tool adapter package under `services/api/src/aegisops_api/tools/adapters/`.
- Read-only GitHub App adapter for issue and file reads through GitHub REST.
- `POST /tool-calls/{tool_call_id}/execute` endpoint for executing a previously authorized
  `tool_calls` record only after input hash revalidation.
- Tool execution updates durable status, output hash, latency, completion timestamp, and audit
  events. Response payload returns the live tool output, while persistence stores hashes and
  metadata rather than full retrieved content.
- Engineering Issue-to-PR LangGraph module under
  `services/api/src/aegisops_api/workflows/engineering_issue_to_pr/`.
- Typed graph input contract, read issue node, read context files node, evidence assembly node,
  and policy-backed tool runtime adapter.
- `POST /workflow-runs/{run_id}/engineering-issue-to-pr/evidence` runtime route for running
  the implemented read-only graph stage only after a stored live workflow run exists.
- Evidence metadata persistence for GitHub issue and code-file sources through
  `evidence_records`, with hashes and source URIs rather than full code content in metadata.
- Captured-real-run replay fixture schema and loader under
  `services/api/src/aegisops_api/workflows/engineering_issue_to_pr/replay.py`.
- Replay fixture directory contract under `configs/replays/engineering_issue_to_pr/`.
- Optional planner/evaluator graph nodes and contracts for patch proposals, test plans,
  evidence grounding, and risk evaluation.
- OpenAI Responses API planner adapter for patch planning and plan evaluation.
- `model_calls` audit persistence for planner/evaluator model calls, including prompt version,
  token counts, latency, trace ID, status, and request/response metadata.
- `include_proposal=true` request support for the Engineering route, gated by explicit OpenAI
  configuration. Proposal and evaluation outputs are returned but do not enable write actions.
- GitHub issue/file/PR draft tool contracts.
- Approved SQL read-only query tool contract.
- Document retrieval tool contract.
- Observability log search tool contract.
- Validation that write-class tools require approval by default.
- JSON Schema validation for tool input payloads before policy evaluation.
- Durable `tool_calls` and audit events for allowed, blocked, and approval-required tool call
  authorization attempts.

Goal: Add typed tool infrastructure before workflow-specific tool usage.

Tasks:

1. Done: define tool contract Pydantic models.
2. Done: define tool risk classes: read, draft, write, external_message, financial,
   access_change.
3. Done: add MCP server skeleton.
4. Done: add tool registry endpoint.
5. Done: add connector auth registry, GitHub auth placeholder, and enterprise connector
   readiness contracts.
6. Done: add approved SQL read-only tool contract.
7. Done: add document retrieval tool contract.
8. Done: add observability/log retrieval tool contract.
9. Done: add per-tool OPA authorization before execution.

Acceptance criteria:

- Every tool has input/output schemas.
- Every tool has required auth scopes.
- Every tool call produces an audit event.
- Write-class tools require approval by default.

Validated in current environment:

```bash
services/api/.venv/bin/pytest services/api/tests/test_tool_execution.py services/api/tests/test_tool_registry.py
services/api/.venv/bin/ruff check services/api
cd services/api && .venv/bin/mypy .
```

Next slice:

1. Add approval-review records and UI state for proposed branch/PR actions.
2. Keep branch and PR write adapters disabled until approval persistence and UI review are
   wired.

## Phase 6: Engineering Issue-to-PR Workflow

Status: In progress.

Completed artifacts:

- Workflow package under `services/api/src/aegisops_api/workflows/engineering_issue_to_pr/`.
- Typed graph input/state contract for read-only issue context collection.
- LangGraph nodes for GitHub issue ingestion, repository context file reads, and evidence
  assembly.
- Policy-backed graph runtime that routes tool use through authorization and execution
  boundaries.
- Run-scoped API route for live evidence collection after `POST /workflow-runs`.
- Evidence metadata persistence and audit events for the implemented read-only stage.

Goal: Implement the first flagship production workflow against a real GitHub repository.

Tasks:

1. Done: create `services/api/src/aegisops_api/workflows/engineering_issue_to_pr/`.
2. Done: add typed state and contracts for issue context collection.
3. In progress: add graph nodes. Done for issue ingestion, repo context reads, optional
   planning, patch proposal contract, test plan contract, and evaluator contract. Pending
   approval request and PR draft.
4. In progress: add GitHub tools. Done for issue read and file read; branch and PR draft write
   adapters remain disabled.
5. Add policy rules for branch and PR approval.
6. Add visual graph mapping for UI.
7. Add tests for branch decisions and approval paths.
8. Add first captured real-run replay format.

Acceptance criteria:

- Workflow can read a real GitHub issue.
- Workflow can inspect real repo files.
- Workflow can propose a patch plan.
- Workflow cannot create a branch or PR without policy and approval.
- UI shows graph, evidence, policy, trace, and diff preview.

## Phase 7: Production Incident Investigator Workflow

Goal: Add real incident investigation across logs, deployments, and code changes.

Status note: the visual multi-agent orchestration contract is present in the command center.
The first runtime slice is implemented as guarded read-only evidence collection for logs,
deployment events, and optional repository files. Live connector adapters for observability and
deployment systems, RCA generation, approval requests, and production write actions remain
future work. Captured-real-run replay schema and loading are implemented without committing
fabricated replay payloads.

Tasks:

1. Done: add visual multi-agent orchestration contract for supervisor-worker incident
   investigation.
2. Done: add workflow module under
   `services/api/src/aegisops_api/workflows/incident_response_investigator/`.
3. Done: add connector/tool contracts for deployment events and logs/traces.
4. In progress: add graph nodes. Done for read-only log investigator, deployment investigator,
   code investigator, and evidence auditor. Pending hypothesis generation, RCA draft, and
   approval nodes.
5. Add source-grounded evidence board.
6. Add policy rules for rollback and incident update actions.
7. Done: add captured-real-run replay format and loader.
8. Add eval rubric for RCA quality.

Acceptance criteria:

- Workflow uses real observability/deployment data when configured.
- RCA claims link to evidence.
- Rollback/update actions require approval.

## Phase 8: Customer Support Escalation Workflow

Goal: Add real support workflow with knowledge retrieval and human-approved response drafting.

Tasks:

1. Add support connector abstraction.
2. Add CRM/account context abstraction.
3. Add knowledge base retrieval over real docs.
4. Add graph nodes for triage, account lookup, KB search, policy check, response draft,
   evaluator, approval, and handoff.
5. Add memory policy for customer preferences and prior incidents.
6. Add approval workflow for customer-visible messages.

Acceptance criteria:

- Workflow can ingest a real ticket/email from a configured connector.
- Response draft cites real sources.
- Customer-visible message cannot be sent without approval.
- Memory writes are visible and policy-controlled.

## Phase 9: Evals, Replay, and Demo Hardening

Goal: Make the demo reliable without fake data or uncontrolled API spend.

Tasks:

1. Define captured real-run replay schema.
2. Add replay loader and UI replay mode.
3. Add promptfoo config for red-team and regression checks.
4. Add Ragas or custom grounding evals for RAG outputs.
5. Add trace evals for tool validity, policy compliance, cost, and grounding.
6. Add admin-only live-run gate.
7. Add per-run budget enforcement.
8. Add demo reset and seed from captured real traces only.

Acceptance criteria:

- Public demo can run from captured real traces with no live API spend.
- Live runs require admin configuration.
- Eval results are visible in the UI.
- Replay mode is clearly labeled.

## Phase 10: Deployment and Portfolio Polish

Goal: Deploy a polished public demo with production-grade engineering posture.

Tasks:

1. Add Vercel deployment config for web.
2. Add API deployment config for selected free-tier host.
3. Add production env var documentation.
4. Add database migration deployment steps.
5. Add health, readiness, and connector status panels.
6. Add final visual polish for command center screens.
7. Add portfolio walkthrough script.
8. Add README deployment guide.

Acceptance criteria:

- Public URL loads the visual command center.
- Demo does not require unrestricted live credentials.
- Free-tier limits and production upgrade path are documented.
- The portfolio clearly presents stack depth and enterprise breadth.

## Build Order Rules

Follow this order unless explicitly changed:

1. Foundation before workflows.
2. Policy before write actions.
3. Typed tools before agent tool use.
4. Persistence before long-running runs.
5. Observability before live demos.
6. Real connectors before workflow enablement.
7. Captured real replay before public demos.

## Definition of Done For Any Feature

A feature is done only when:

- It is typed.
- It is documented.
- It has relevant tests or evals.
- It records audit/trace metadata when runtime behavior is involved.
- It respects policy and approval rules.
- It does not introduce fake business data.
- It does not rely on regex for business logic.

## Current Next Task

Continue by adding approval-review persistence and UI state for proposed branch/PR actions. Do
not enable branch or pull-request writes.
