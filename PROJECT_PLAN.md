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

Phase 0 is complete.

The repo has architecture docs, dependency manifests, workflow registry configs, local infra
scaffolding, ADRs, and CI scaffolding. Feature implementation has not started.

## Milestone Map

| Phase | Name | Status | Outcome |
| --- | --- | --- | --- |
| 0 | Architecture baseline | Complete | Docs, stack decisions, workflow portfolio, scaffold |
| 1 | Foundation runtime | In progress | Installable web/API skeleton with health checks |
| 2 | Governance and data layer | Not started | Postgres, migrations, policy checks, audit model |
| 3 | Workflow registry and run lifecycle | Not started | Config-driven workflow catalog and run API |
| 4 | Visual command center shell | Not started | Portfolio UI, graph canvas, trace/evidence placeholders |
| 5 | Tool and connector substrate | Not started | MCP tool contracts, GitHub connector foundation |
| 6 | Engineering Issue-to-PR workflow | Not started | First real production workflow |
| 7 | Incident Investigator workflow | Not started | Real observability/deployment investigation workflow |
| 8 | Customer Support Escalation workflow | Not started | Real support/KB/CRM workflow path |
| 9 | Evals, replay, and demo hardening | Not started | Captured real-run replay and quality gates |
| 10 | Deployment and portfolio polish | Not started | Public free-tier deployment and executive-grade UI |

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

Status: In progress.

Completed in current phase:

- Minimal FastAPI app at `services/api/src/aegisops_api/main.py`.
- Environment settings with `pydantic-settings`.
- `/health`, `/ready`, and `/version` endpoints.
- Structured logging setup.
- Minimal Next.js visual command-center shell under `apps/web`.
- API health endpoint tests.

Goal: Make the repo installable and runnable with minimal skeleton services.

Tasks:

1. Done: add a minimal FastAPI app at `services/api/src/aegisops_api/main.py`.
2. Done: add environment settings with `pydantic-settings`.
3. Done: add `/health`, `/ready`, and `/version` endpoints.
4. Done: add structured logging setup.
5. Done: add a minimal Next.js app shell under `apps/web`.
6. Not started: add basic API client wiring from web to backend.
7. Not started: add local development docs for install/run commands.
8. Not started: update CI to install dependencies and run lightweight validation.

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

Goal: Add durable system state before agent behavior.

Tasks:

1. Add SQLAlchemy database module.
2. Add Alembic migration setup.
3. Create tables for workflow registry snapshots, workflow runs, audit events, approvals,
   tool calls, model calls, memory records, and evidence records.
4. Enable pgvector extension migration.
5. Add OPA client.
6. Add baseline Rego packages for tool access, approvals, budget, and data sensitivity.
7. Add policy test fixtures using structured JSON inputs.
8. Add audit event writer.

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
```

## Phase 3: Workflow Registry and Run Lifecycle

Goal: Convert YAML workflow configs into a typed runtime registry and run lifecycle.

Tasks:

1. Add Pydantic models for workflow config files.
2. Load and validate `configs/workflows/*.yaml`.
3. Expose `GET /workflows`.
4. Expose `GET /workflows/{workflow_id}`.
5. Add `POST /workflow-runs` with run eligibility checks.
6. Add run status states: queued, running, waiting_for_approval, completed, failed, canceled.
7. Add budget envelope model.
8. Add replay/live execution mode model.
9. Add connector readiness checks.

Acceptance criteria:

- Invalid workflow YAML fails fast.
- Workflows are disabled until connector requirements are satisfied.
- Starting a workflow creates a durable run record.
- Run creation calls OPA before execution.

## Phase 4: Visual Command Center Shell

Goal: Build the UI surface before deep workflow implementation.

Tasks:

1. Add app layout and navigation.
2. Add Portfolio page listing workflow modules from the API.
3. Add Command Center page for a selected workflow.
4. Add React Flow graph canvas with static config-driven nodes.
5. Add Evidence Board empty state.
6. Add Policy Lens empty state.
7. Add Trace Timeline empty state.
8. Add Code Lens read-only panes for YAML config and policy metadata.
9. Add visual status for connector readiness, replay availability, and live-run eligibility.

Acceptance criteria:

- A CEO can understand what each workflow does.
- A CTO can see the platform layers.
- An engineer can inspect the config and contracts.
- The UI does not imply fake data is available.

## Phase 5: Tool and Connector Substrate

Goal: Add typed tool infrastructure before workflow-specific tool usage.

Tasks:

1. Define tool contract Pydantic models.
2. Define tool risk classes: read, draft, write, external_message, financial, access_change.
3. Add MCP server skeleton.
4. Add tool registry endpoint.
5. Add GitHub connector config and auth placeholder.
6. Add approved SQL read-only tool contract.
7. Add document retrieval tool contract.
8. Add observability/log retrieval tool contract.
9. Add per-tool OPA authorization before execution.

Acceptance criteria:

- Every tool has input/output schemas.
- Every tool has required auth scopes.
- Every tool call produces an audit event.
- Write-class tools require approval by default.

## Phase 6: Engineering Issue-to-PR Workflow

Goal: Implement the first flagship production workflow against a real GitHub repository.

Tasks:

1. Create `services/api/src/aegisops_api/workflows/engineering_issue_to_pr/`.
2. Add typed state and contracts.
3. Add graph nodes: eligibility, issue ingestion, repo context, plan, patch proposal,
   test plan, evaluator, approval request, PR draft.
4. Add GitHub tools for issue read, file read, branch draft, PR draft.
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

Tasks:

1. Add workflow module.
2. Add connector contracts for deployment events and logs/traces.
3. Add graph nodes for incident intake, timeline construction, parallel investigation,
   hypothesis generation, evidence validation, RCA draft, and approval.
4. Add source-grounded evidence board.
5. Add policy rules for rollback and incident update actions.
6. Add eval rubric for RCA quality.

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

Start Phase 1.

First concrete task: validate the foundation runtime build, then add basic API client wiring
from the web app to the backend.
