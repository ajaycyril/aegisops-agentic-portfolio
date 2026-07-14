# Local Development Setup

This guide covers the foundation runtime, governance/data scaffolding, workflow registry, and
policy-gated run-start API.

## Prerequisites

- Node.js 24 or newer.
- pnpm 10.15.1 or compatible.
- Python 3.12 or newer.
- Docker Desktop for local Postgres, Redis, and OPA.

## Install

```bash
make install
```

This installs:

- pnpm workspace dependencies.
- API service dependencies with the `dev` extra.

Optional heavyweight extras are separate:

```bash
make install-evals
make install-observability
```

## Environment

```bash
cp .env.example .env
```

For local frontend-to-backend health checks, keep:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

OpenAI keys are not required for health checks, workflow registry reads, or run-start
eligibility tests. Live agent execution will require model credentials in a later phase.

Run-start safety controls:

```bash
CONFIGURED_CONNECTORS=github,observability
MAX_AGENT_RUN_SECONDS=300
MAX_AGENT_TOOL_CALLS=25
MAX_AGENT_ESTIMATED_USD=1.00
REQUIRE_HUMAN_APPROVAL=true
LIVE_WORKFLOW_RUNS_ENABLED=false
```

Connector readiness has two layers:

- `CONFIGURED_CONNECTORS` is the coarse deployment toggle used by workflow/tool readiness.
- `configs/connectors/*.yaml` declares auth type, scopes, data boundaries, and required env var
  names for each connector. `GET /connectors` reports missing env var names only and never
  returns secret values.

`LIVE_WORKFLOW_RUNS_ENABLED=false` keeps live execution disabled by default. Replay mode still
requires a captured real-run source id.

## Run Local Infrastructure

```bash
make infra-up
```

This starts:

- Postgres with pgvector.
- Redis.
- OPA.

Stop it with:

```bash
make infra-down
```

## Run Migrations

After `make infra-up`, apply the governance schema:

```bash
cd services/api
.venv/bin/alembic upgrade head
```

To inspect migration SQL without a running database:

```bash
cd services/api
.venv/bin/alembic upgrade head --sql
```

## Run API

```bash
make api-dev
```

Health endpoints:

- `GET http://localhost:8000/health`
- `GET http://localhost:8000/ready`
- `GET http://localhost:8000/version`

Workflow registry endpoints:

- `GET http://localhost:8000/workflows`
- `GET http://localhost:8000/workflows/{workflow_id}`
- `POST http://localhost:8000/workflow-runs`

Tool registry endpoints:

- `GET http://localhost:8000/connectors`
- `GET http://localhost:8000/connectors/{connector_id}`
- `GET http://localhost:8000/tools`
- `GET http://localhost:8000/tools/{tool_id}`
- `POST http://localhost:8000/tool-calls/authorize`
- `POST http://localhost:8000/tool-calls/{tool_call_id}/execute`
- `POST http://localhost:8000/workflow-runs/{run_id}/engineering-issue-to-pr/evidence`

By default, workflows are visible but disabled because no real connectors are configured. For
local readiness experiments, set `CONFIGURED_CONNECTORS` to a comma-separated list such as
`github,observability`.

Example replay run-start request:

```bash
curl -X POST http://localhost:8000/workflow-runs \
  -H 'content-type: application/json' \
  -d '{
    "workflow_id": "engineering_issue_to_pr",
    "execution_mode": "replay",
    "replay_source_run_id": "captured-real-run-id",
    "input_payload": {
      "issue_url": "https://github.com/owner/repo/issues/1"
    }
  }'
```

The request is rejected unless the workflow is ready, required connectors are configured, OPA
is reachable, and the budget/replay policy permits the start.

Tool authorization validates the selected workflow/tool contract, JSON input schema, connector
readiness, OPA `tool_access`, and approval status before a non-executed `tool_calls` record is
created. Tool execution is a separate step: it requires that stored authorized record, rechecks
the input hash, validates output against the tool schema, and then records status, latency,
output hash, and audit events.

The first live adapter is read-only GitHub App REST access for:

- `github_issue_read`
- `github_file_read`

The Engineering Issue-to-PR graph can be invoked through the run-scoped evidence route only
after a stored workflow run exists. Live mode collects GitHub issue/file evidence through the
read-only GitHub adapter. Replay mode loads a captured real-run fixture by
`replay_source_run_id`, persists the same evidence metadata, and never calls GitHub.

Replay fixtures resolve from `configs/replays/engineering_issue_to_pr/` by default, or from
`REPLAY_FIXTURE_DIR` when set. Do not add invented fixture data; fixtures must declare
`provenance: captured_real_run`.

Set `include_proposal=true` on the evidence route to run the OpenAI-backed proposal/evaluator
planner. This requires `OPENAI_API_KEY` plus `OPENAI_REASONING_MODEL` or
`OPENAI_DEFAULT_MODEL`. The planner writes `model_calls` audit records and returns typed
proposal/evaluation payloads; it does not create branches, commits, comments, or pull
requests.

`GET /ready` exposes `engineering_issue_to_pr_planner_configured` and `openai_planner_model`
so the web cockpit can show planner readiness without exposing `OPENAI_API_KEY`.

`github_pull_request_draft` remains contract-only until the approval UI and write-action
review path are wired.

## Run Web

```bash
make web-dev
```

Open:

- `http://localhost:3000`

If the API is running and `NEXT_PUBLIC_API_BASE_URL` is set, the web app shows backend runtime
status. If not, it shows that the API is not configured for the deployment.

The Phase 1 web shell uses Framer Motion for command-center motion and Recharts for telemetry
visuals. Keep future UI work inside the operational cockpit pattern rather than turning the
homepage into a marketing page.

## Validation

```bash
pnpm -r lint
pnpm -r typecheck
pnpm -r build
services/api/.venv/bin/pytest services/api/tests
services/api/.venv/bin/ruff check services/api
cd services/api && .venv/bin/mypy .
node scripts/check-docs-placeholders.mjs
```
