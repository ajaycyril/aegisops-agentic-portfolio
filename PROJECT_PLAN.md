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

### Active Live Workbench Milestone - 2026-07-17

The obsolete browser path that forwarded to the registry-only `/live-run/start` gateway has been
replaced by `POST /api/agent-runs`. The new Next.js runtime is implemented and locally verified:

- Four scenario-specific live-source workflows switch graph, inputs, tools, rules, and prompts.
- LangGraph streams graph updates and checkpoints through `PostgresSaver` when `DATABASE_URL` is
  configured, with an explicit `MemorySaver` fallback for the free demo.
- The incident workflow is a real multi-agent graph: two AI SDK specialist agents execute in
  parallel, call separate MCP tools, and hand reports to a supervisor for reconciliation.
- A `json-rules-engine` lane executes concurrently against the same live evidence.
- OPA/Rego WASM gates intake and holds every requested side effect for approval.
- React Flow animates active graph edges and every node exposes trace, latency, actor, data,
  evidence, and policy state through the inspector.
- The UI reports actual tool calls, validated source payloads, model tokens, free-tier charge, and
  direct-API equivalent unit economics.
- Vitest covers typed run contracts, scenario topology, and policy allow/block/approval behavior.

Production end-to-end evidence: the incident run completed both lanes with 36 streamed events,
two specialist MCP calls, two evidence records, three model agents, OPA side-effect blocking, a
passing grounding evaluator, 1,909 measured tokens, and a `$0.00167` direct-API equivalent.
Managed Postgres/Redis activation remains.

Phases 0 and 1 are complete. Phases 2, 3, and 4 are implemented at code/test level. Live
verification now follows a cloud-only path: managed Postgres/pgvector, a hosted
OPA-compatible policy endpoint, deployed full API runtime, connector secrets, and an
admin-gated real-run validation.

The repo has architecture docs, dependency manifests, workflow registry configs, cloud-first infra
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
visual command center has been refactored into a live-contract-first cockpit: five priority
use cases share one workflow player, one real run-start bridge, trace-backed step inspection,
runtime readiness gates, tuning controls, and an immediate rule-engine comparison. It does not
render fabricated tool calls, evidence, memory, or model reasoning. A run-scoped Engineering approval-review
route creates pending `approvals` rows for proposed branch/PR actions, records audit events,
and moves runs to `waiting_for_approval` without executing GitHub writes. A second run-scoped
decision route now approves or rejects those pending records through OPA, enforces a four-eyes
review policy, audits the decision, and still returns a no-write execution state. The
Engineering PR draft authorization route now accepts approved approval IDs and creates
policy-checked `github_pull_request_draft` tool calls in `authorized_not_executed` or
`blocked_before_execution` state, without executing GitHub writes. The PR preview route now
verifies the approved authorization, input hash, and approval record before writing a dry-run
preview evidence artifact with hashes and metadata only. The web command center now fetches a
configured real run trace by `DEMO_WORKFLOW_RUN_ID`/`DEMO_TRACE_RUN_ID` and renders approval,
PR authorization, dry-run preview evidence, record-count, and recent trace metadata states
without fake fallback records. It also includes a React Flow
multi-agent orchestration cockpit for the
Production Incident Investigator, showing a supervisor-worker fan-out, specialist evidence
streams, evaluator reconciliation, and approval-gated production actions as a visual contract
only. The Production Incident Investigator now also has a first backend runtime slice: a typed
LangGraph evidence-collection graph and run-scoped API route for read-only observability log,
deployment event, and GitHub file evidence collection, with policy-authorized tool calls,
evidence metadata persistence, captured-real-run replay loading, source-grounded evidence
validation, and typed hash-only RCA draft contracts. Rollback, paging, incident updates, and
external write actions remain disabled. Rubric-only eval contracts now cover Engineering patch
proposal quality and Incident RCA grounding, and structured incident approval policy fixtures
cover rollback, paging, and incident-update decisions. The Incident approval-review route now
creates pending `approvals` rows for those proposed production actions without executing them.
The Incident approval decision route now approves or rejects those records through OPA, audits
the reviewer decision, and still returns no-write execution state. Read-only HTTP JSON adapters
now provide live observability log and deployment event search when connector connection IDs,
base URLs, and optional bearer tokens are configured. Phase 8 is implemented at code/test level
with read-only Customer Support Escalation context collection across support ticket, CRM
customer profile, and knowledge base search connectors, hash-only/redacted evidence
persistence, an internal cited response draft contract, a pending approval-review queue for
customer messages, OPA-checked customer-message approval decisions, run-scoped redacted memory
policy records, and blocked send authorization while customer-visible send actions remain
disabled. Phase 9 has started with executable trace evals and UI eval-result display over real
persisted run traces. The command center now includes a novice-friendly autonomy taxonomy
that separates fixed deterministic gates, dynamic OPA policy, structured AI workflows, and
true LangGraph/MCP agentic execution with cost, controls, failure modes, and selected-workflow
fit. It also includes a peel-the-layers stack panel that maps executive, architect, and
engineer views to the actual orchestration, model, tool, governance, memory, observability,
eval, and deployment layers.
The production Vercel deployment now uses Vercel Services for the web app plus a slim
read-only FastAPI registry gateway under `/api`. That public gateway exposes real workflow,
connector, and tool contracts from a checked config snapshot, reports registry counts in
readiness, and intentionally excludes live workflow-run, model, database, OPA, connector, and
write-action routes.

Current production web deployment:

- https://aegisops-agentic-portfolio.vercel.app
- Public read-only API checks:
  `/api/ready`, `/api/workflows`, `/api/connectors`, `/api/tools`

## Milestone Map

| Phase | Name                                 | Status                                       | Outcome                                                                             |
| ----- | ------------------------------------ | -------------------------------------------- | ----------------------------------------------------------------------------------- |
| 0     | Architecture baseline                | Complete                                     | Docs, stack decisions, workflow portfolio, scaffold                                 |
| 1     | Foundation runtime                   | Complete                                     | Installable web/API skeleton with health checks                                     |
| 2     | Governance and data layer            | Implemented, cloud verification pending      | Postgres, migrations, policy checks, audit model                                    |
| 3     | Workflow registry and run lifecycle  | Implemented, cloud verification pending      | Config-driven workflow catalog and run API                                          |
| 4     | Visual command center shell          | Implemented                                  | Portfolio UI, graph canvas, multi-agent canvas, review, trace/evidence placeholders |
| 5     | Tool and connector substrate         | In progress                                  | MCP tool contracts, GitHub and HTTP JSON read adapters                              |
| 6     | Engineering Issue-to-PR workflow     | In progress                                  | First real production workflow                                                      |
| 7     | Incident Investigator workflow       | In progress                                  | Real observability/deployment investigation workflow                                |
| 8     | Customer Support Escalation workflow | Implemented                                  | Real support/KB/CRM workflow path                                                   |
| 9     | Evals, replay, and demo hardening    | In progress                                  | Captured real-run replay and quality gates                                          |
| 10    | Deployment and portfolio polish      | Production verified; managed state pending | Public free-tier deployment and executive-grade UI                                |

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
- `infra/docker-compose.yml` as an optional local emulator, not a project prerequisite
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

Status: Implemented. Live cloud Postgres migration verification is pending until a managed
Postgres/pgvector database is provisioned. Local Docker is not a project prerequisite.

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

- Managed Postgres/pgvector URL is configured.
- Migrations apply against the managed database.
- A hosted OPA-compatible policy endpoint loads the repository Rego packages.
- Policy checks are callable from API code.
- Audit events can be written and queried.
- No policy decision is delegated to the model.

Validation commands:

```bash
cd services/api && DATABASE_URL=<managed-postgres-url> .venv/bin/alembic upgrade head
OPA_BASE_URL=<policy-url> services/api/.venv/bin/pytest services/api/tests
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

Not run: live cloud `alembic upgrade head` and hosted OPA policy loading, because managed
services are not yet provisioned.

## Phase 2 Follow-Up: Cloud Infra Verification

Goal: verify Phase 2 against managed cloud services before starting durable live run APIs.

Tasks:

1. Provision managed Postgres with pgvector enabled.
2. Set `DATABASE_URL` for the full API runtime and one-off migration shell.
3. Run `cd services/api && .venv/bin/alembic upgrade head` against the managed database.
4. Deploy a hosted OPA-compatible policy endpoint with `policies/aegisops/*.rego` loaded.
5. Set `OPA_BASE_URL`, budget limits, `CONFIGURED_CONNECTORS`, and connector gateway secrets
   in the cloud API host.
6. Verify `GET /ready` reports database and policy configured.
7. Run `services/api/.venv/bin/pytest services/api/tests`.

## Phase 3: Workflow Registry and Run Lifecycle

Status: Implemented. Live Postgres/OPA verification is pending until the managed database and
hosted policy endpoint are provisioned.

Completed artifacts:

- Pydantic workflow config models under `services/api/src/aegisops_api/workflows/`.
- YAML loader for `configs/workflows/*.yaml`.
- `GET /workflows`.
- `GET /workflows/{workflow_id}`.
- Connector readiness reporting for registry reads. Workflows remain disabled unless real
  connector names are configured through `CONFIGURED_CONNECTORS`.
- `POST /workflow-runs` with typed request/response models.
- Run-start readiness checks for workflow status, required connectors, replay source, replay
  eligibility, budget envelope, live-run feature flag, admin live-run key, and OPA run
  eligibility.
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

Not run: live Postgres migration and live OPA policy loading/evaluation, because managed cloud
services are not yet provisioned.

Historical next task at the end of Phase 3 has been superseded by the active milestone and the
canonical `Current Next Task` at the end of this document.

## Phase 4: Visual Command Center Shell

Status: Implemented.

Completed artifacts:

- Registry-aware web catalog loader in `apps/web/lib/api.ts`.
- Repository workflow catalog mirror in `apps/web/lib/workflows.ts` used only when the live
  API registry is not configured or reachable.
- Live workbench in `apps/web/components/agentic-workbench.tsx`.
- Four real-source use cases: incident response, engineering triage, supplier risk, and finance
  evidence analysis.
- Shared React Flow workflow player driven by the streamed `RunEvent` contract.
- Real `POST /api/agent-runs` route running LangGraph and json-rules-engine concurrently.
- Step inspector for nodes, agents, tool arguments, evidence, model usage, policy, latency, and
  trace metadata from the live stream.
- Workflow tuning controls for autonomy, tool budget, spend cap, approval requirement, model
  planning flag, and use-case-specific input payload fields.
- Immediate traditional-system lane using an executable rules engine against the same evidence.
- Contract depth panels for connectors, scopes, data policy, approval requirements, and source
  config path.
- Favicon and mobile-first responsive styling.

Goal: Build the UI surface before deep workflow implementation.

Tasks:

1. Done: add app layout and navigation.
2. Done: add Portfolio page listing workflow modules from the API with repository mirror
   fallback when no backend is deployed.
3. Done: add Command Center page for a selected workflow.
4. Done: replace static section-heavy UI with a first-viewport live workflow cockpit.
5. Done: add React Flow workflow player driven by contracts and real trace metadata.
6. Done: add real run-start bridge to the configured full API.
7. Done: add runtime gate, step inspector, tuning controls, and rule-engine comparison.
8. Done: add contract depth panels for connectors, data policy, approvals, and source paths.

Acceptance criteria:

- A CEO can understand what the selected agent is trying to accomplish from the first viewport.
- A novice can watch the same workflow shape across multiple use cases and compare it directly
  with a traditional rule-based system.
- A CTO can see runtime gates, connector readiness, policy, memory, approvals, and deployment
  state without scrolling through unrelated sections.
- An engineer can inspect config-derived contracts, trace-derived steps, upstream run-start
  responses, and tuning payloads.
- The UI does not imply fake data, fake traces, fake tool calls, or fake reasoning are available.

Validated in current environment:

```bash
pnpm --filter @aegisops/web lint
pnpm --filter @aegisops/web typecheck
pnpm --filter @aegisops/web build
```

Browser smoke checks were run with Playwright/Chrome against `http://localhost:3000` at 1440 px
and 390 px widths. Both passed with no error overlays. The real run-start button was clicked
and returned the actual upstream 404 gate from the read-only public API with no console errors.

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
- Read-only HTTP JSON adapters for observability log search, deployment event search, support
  ticket read, CRM customer profile read, and knowledge base search, with explicit connection
  IDs, configurable base URLs/paths, optional bearer tokens, normalized source identifiers, and
  controlled upstream error handling.
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
- Run-scoped Engineering approval-review route at
  `POST /workflow-runs/{run_id}/engineering-issue-to-pr/approval-review`.
- Pending `approvals` row persistence for proposed branch creation and pull request creation,
  with proposal/evaluation/action payloads, evidence URI validation, 24-hour expiry, run status
  transition to `waiting_for_approval`, and audit events. No branch or pull-request write
  adapter is enabled.
- Run-scoped Engineering approval decision route at
  `POST /workflow-runs/{run_id}/engineering-issue-to-pr/approvals/{approval_id}/decision`.
- OPA approval-decision fixtures for branch approval, PR rejection, missing approver rejection,
  and self-approval rejection.
- Approval decision persistence for approve/reject transitions, including policy decision
  metadata, approver ID, decision payload, audit events, four-eyes enforcement input, and
  `approval_decision_recorded_no_write_execution`.
- Run-scoped Engineering PR draft authorization route at
  `POST /workflow-runs/{run_id}/engineering-issue-to-pr/pr-draft/authorize`.
- Approved approval ID wiring into the GitHub PR draft tool authorization boundary. Approved
  approvals can create an authorized-but-not-executed write-class `tool_calls` record; missing
  approvals create a blocked record. No PR write adapter is executed.
- Run-scoped Engineering PR draft preview route at
  `POST /workflow-runs/{run_id}/engineering-issue-to-pr/pr-draft/preview`.
- Dry-run PR preview evidence artifact with tool-call ID, approval ID, input hash verification,
  proposal summary, planned-change paths, PR body hash, and
  `dry_run_preview_created_no_write_execution`. No raw code or GitHub write is persisted.
- Generic workflow-run trace endpoint at `GET /workflow-runs/{run_id}/trace`, returning run
  status plus approval, tool-call, model-call, evidence, and audit metadata for UI readout.
- Web command-center trace readout wired to a configured real run id. It renders approved,
  blocked, and preview-created PR authorization outcomes, record counts, and recent metadata
  from `GET /workflow-runs/{run_id}/trace`; if no run id is configured, it shows only the
  configuration contract and no fake trace data.
- GitHub issue/file/PR draft tool contracts.
- Approved SQL read-only query tool contract.
- Document retrieval tool contract.
- Observability log search tool contract.
- Support ticket read, CRM customer profile read, and knowledge base search tool contracts.
- Supplier profile, sanctions screening, approved web research, invoice read, and purchase
  order read tool contracts for the supplier-risk and finance examples.
- Web command center now loads the live `/tools` registry and changes the React Flow agent
  graph per selected use case, showing distinct tool calls, guardrails, memory, model/eval,
  evidence, and approval stages from real contracts before any trace exists.
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

1. Keep branch and PR write adapters disabled until final review and live connector hardening
   are complete.
2. Capture a real sandbox run and point `DEMO_TRACE_RUN_ID` at it for public trace/eval display.

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
- Web trace readout for approval decisions, blocked/authorized PR draft tool calls, dry-run PR
  preview evidence, and compact audit/evidence metadata from a configured real run id.

Goal: Implement the first flagship production workflow against a real GitHub repository.

Tasks:

1. Done: create `services/api/src/aegisops_api/workflows/engineering_issue_to_pr/`.
2. Done: add typed state and contracts for issue context collection.
3. In progress: add graph nodes. Done for issue ingestion, repo context reads, optional
   planning, patch proposal contract, test plan contract, evaluator contract, approval review
   persistence, approve/reject decision route, PR draft authorization route, and dry-run PR
   preview UI state.
4. In progress: add GitHub tools. Done for issue read and file read; branch and PR draft write
   adapters remain disabled.
5. In progress: add policy rules for branch and PR approval. Done for approval decision
   fixtures, approved-approval-ID tool authorization, dry-run preview artifact, and UI state
   over persisted outcomes.
6. Add visual graph mapping for UI.
7. In progress: add tests for branch decisions and approval paths. Done for pending
   approval-review creation, approve/reject transitions, and approved write-tool authorization;
   done for dry-run preview creation and input-hash mismatch.
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
deployment events, and optional repository files. Source-grounded evidence validation and a
typed RCA draft contract are implemented without model generation or external writes. Pending
approval records and approve/reject decisions for rollback, paging, and incident-update
proposals are implemented, while production write actions remain future work. Captured-real-run
replay schema and loading are implemented without committing fabricated replay payloads. Live
observability/deployment reads use the HTTP JSON read adapters when connector env vars are
configured.

Tasks:

1. Done: add visual multi-agent orchestration contract for supervisor-worker incident
   investigation.
2. Done: add workflow module under
   `services/api/src/aegisops_api/workflows/incident_response_investigator/`.
3. Done: add connector/tool contracts for deployment events and logs/traces.
4. In progress: add graph nodes. Done for read-only log investigator, deployment investigator,
   code investigator, evidence auditor, source-grounded evidence validation, and RCA draft
   contract creation. Pending model-backed hypothesis generation and approval nodes.
5. In progress: add source-grounded evidence board. Done for backend validation summaries;
   pending richer UI visualization over persisted evidence records.
6. In progress: add policy rules for rollback and incident update actions. Done for structured
   approval decision fixtures and pending approval records covering rollback, paging, and
   incident updates, plus OPA-checked approve/reject decision handling with no write execution.
7. Done: add captured-real-run replay format and loader.
8. Done: add eval rubric for RCA quality.
9. Done: add real observability/deployment read adapter implementations for live evidence
   collection.

Acceptance criteria:

- Workflow uses real observability/deployment data when configured.
- RCA claims link to evidence.
- Rollback/update actions require approval.

## Phase 8: Customer Support Escalation Workflow

Goal: Add real support workflow with knowledge retrieval and human-approved response drafting.

Status note: the runtime slices are implemented at code/test level. The workflow is `ready` behind real
connector readiness and uses `support_ticket_read`, `crm_customer_profile_read`, and
`knowledge_base_search` tools through HTTP JSON adapters. The run-scoped context route persists
hash-only/redacted evidence metadata and can create an internal cited response draft with
`include_draft=true`. The approval-review route stores a pending external-message approval for
that draft, and the approval decision route records OPA-checked approve/reject decisions.
The context route also writes run-scoped redacted memory-policy records with 30-day retention.
The send-disabled authorization route verifies the approved draft hash and persists a blocked
`customer_message_send` tool-call record. Customer-visible messages, refunds, and account
changes remain disabled.

Tasks:

1. Done: add support connector abstraction.
2. Done: add CRM/account context abstraction.
3. Done: add knowledge base retrieval over real docs.
4. In progress: add graph nodes for triage, account lookup, KB search, policy check, response
   draft, evaluator, approval, and handoff. Done for read-only ticket, CRM, KB search, and
   redacted evidence persistence, plus cited internal response draft creation.
5. Done: add memory policy for customer preferences and prior incidents.
6. Done: add approval workflow for customer-visible messages, including pending approval review
   queue, OPA-checked approval decisions, and send-disabled authorization.

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
5. In progress: add trace evals for tool validity, policy compliance, cost, and grounding.
   Done for rubric contracts covering Engineering proposal quality, Incident RCA grounding, and
   Customer Support response drafts. Done for executable deterministic trace eval runners and
   UI eval-result display over real configured run ids.
6. Done: add admin-only live-run gate.
7. Done: add per-run budget enforcement.
8. Done: add demo reset and seed from captured real traces only.

Acceptance criteria:

- Public demo can run from captured real traces with no live API spend.
- Live runs require admin configuration.
- Runtime routes stop when persisted run usage exceeds the configured budget envelope.
- Eval results are visible in the UI.
- Replay mode is clearly labeled.

## Phase 10: Deployment and Portfolio Polish

Goal: Deploy a polished public demo with production-grade engineering posture.

Tasks:

1. Done: add Vercel deployment config for web.
2. Done: add API deployment config for selected free-tier/low-cost host candidate.
3. Done: add production env var documentation.
4. Done: add database migration deployment steps.
5. Done: add health, readiness, connector status, trace, and eval panels.
6. Done: add final visual polish for command center screens, including the autonomy taxonomy
   and peel-the-layers stack depth panels.
7. Done: add portfolio walkthrough script.
8. Done: add README deployment guide.
9. Done: deploy a Vercel Services read-only registry API and wire the web app to same-origin
   `/api` at request time.
10. Done: add an in-app Test Drive panel plus `/test-drive/probe` for safe read-only endpoint
    verification without live connector credentials.
11. Done: replace the registry-gateway run button with a real AI SDK UIMessage streaming route.
12. Done: add four real-source dual-lane use cases with live MCP calls and deterministic rules.
13. Done: implement and visualize the incident supervisor plus parallel specialist agents.
14. Done: add OPA/Rego WASM policy, unit economics, tool I/O, and automated web boundary tests.
15. Done: redeploy the live workbench and verify a production multi-agent run.
16. Pending: activate dedicated Postgres/pgvector checkpoints and durable Redis rate limiting.

Acceptance criteria:

- Public URL loads the visual command center.
- Public URL shows `API online` and `Live registry` from non-empty workflow, connector, and
  tool registry endpoints.
- Test Drive can verify `/api/health`, `/api/ready`, `/api/workflows`, `/api/connectors`, and
  `/api/tools` from the browser while showing live-run/write gates as closed.
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

Provision dedicated Postgres/pgvector and a Redis-compatible limiter, then validate durable
LangGraph checkpoints and cross-instance rate limits. Do not enable rollback, paging,
incident-update, customer-message, refund, account-change, branch, or pull-request write execution.
Continue real connector adapters only behind MCP schemas and OPA.
