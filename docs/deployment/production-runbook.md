# Production Deployment Runbook

This runbook keeps the public demo free-tier friendly while preserving production controls.
Provider free-tier availability changes over time; verify current quotas before deploying.

## Targets

| Layer | Demo Target | Required Before Live Runs |
| --- | --- | --- |
| Web | Vercel project `aegisops-agentic-portfolio` | `DEMO_TRACE_RUN_ID` only after a captured real run exists |
| Public registry API | Vercel Services app at `/api` from `services/api-vercel` | Not used for live runs |
| API | Docker web service from `services/api/Dockerfile` | database, OPA, budgets, connector env vars |
| Database | Managed Postgres with pgvector | Alembic head applied |
| Policy | OPA service or sidecar | `policies/aegisops/*.rego` loaded |
| Connectors | Read-only HTTP JSON gateways or GitHub App | connector env vars and scopes configured |

## Web Deployment

The web app deploys from `apps/web`.

Required production variables:

```text
DEMO_TRACE_RUN_ID=<captured-real-run-id>
```

`NEXT_PUBLIC_API_BASE_URL` is optional when the Vercel Services `/api` gateway is deployed in
the same project. Leave `DEMO_TRACE_RUN_ID` unset until a captured real run exists; the command
center will show registry contracts, disabled live controls, and no fake trace data.

## Public Registry API

The production Vercel deployment also includes `services/api-vercel`, a slim read-only FastAPI
service mounted at `/api`.

Safe public endpoints:

```text
GET /api/health
GET /api/ready
GET /api/version
GET /api/workflows
GET /api/workflows/{workflow_id}
GET /api/connectors
GET /api/connectors/{connector_id}
GET /api/tools
GET /api/tools/{tool_id}
```

This service reads a committed config snapshot from `services/api-vercel/configs` and reports
workflow, connector, and tool counts in `/api/ready`. It must not expose live run creation,
tool execution, model calls, memory, approval decisions, or connector write actions.

After editing canonical registry YAML under the repo-level `configs/` directory, run:

```bash
pnpm vercel-api:sync-config
pnpm vercel-api:check-config
```

## Test Drive

The web app exposes `GET /test-drive/probe` and an in-app Test Drive panel. The probe calls the
safe public registry API, records endpoint status and latency, and returns workflow, connector,
and tool counts. It also reports live workflow execution and external write gates as closed.

Safe test target:

```text
GET /test-drive/probe
```

Local test command using the deployed read-only registry:

```bash
NEXT_PUBLIC_API_BASE_URL=https://aegisops-agentic-portfolio.vercel.app/api pnpm --filter @aegisops/web dev --hostname 127.0.0.1 --port 3000
```

## API Deployment

The API container is defined in `services/api/Dockerfile`. `render.yaml` is a deploy-ready
blueprint for a Docker web service candidate.

Safe defaults:

```text
APP_ENV=production
LIVE_WORKFLOW_RUNS_ENABLED=false
LIVE_RUN_ADMIN_KEY=<required-only-when-live-runs-are-enabled>
REQUIRE_HUMAN_APPROVAL=true
MAX_AGENT_RUN_SECONDS=300
MAX_AGENT_TOOL_CALLS=25
MAX_AGENT_ESTIMATED_USD=1.00
```

Required before starting real workflow runs:

```text
DATABASE_URL=<managed-postgres-url>
OPA_BASE_URL=<opa-service-url>
CONFIGURED_CONNECTORS=github,observability,deployments,support_system,crm,knowledge_base
LIVE_RUN_ADMIN_KEY=<secret-admin-run-start-key>
```

Live workflow-run start requests must include `x-aegisops-live-run-key` with that configured
secret. If live runs are enabled without the key, the API returns a configuration error before
workflow lookup, policy evaluation, or persistence.

Runtime graph and tool routes also evaluate `aegisops.budget` against persisted usage before
continuing. Keep `MAX_AGENT_RUN_SECONDS`, `MAX_AGENT_TOOL_CALLS`, and
`MAX_AGENT_ESTIMATED_USD` low for the public demo; exceeded budgets fail the run and emit a
`budget.blocked` audit event instead of continuing spend.

Optional model configuration for Engineering proposal/evaluator runs:

```text
OPENAI_API_KEY=<secret>
OPENAI_DEFAULT_MODEL=<explicit-model>
OPENAI_REASONING_MODEL=<optional-explicit-model>
```

Connector gateway variables stay secret-managed by the host:

```text
SUPPORT_SYSTEM_API_BASE_URL=<read-only-support-gateway>
CRM_API_BASE_URL=<read-only-crm-gateway>
KNOWLEDGE_BASE_API_BASE_URL=<read-only-kb-gateway>
OBSERVABILITY_API_BASE_URL=<read-only-observability-gateway>
DEPLOYMENTS_API_BASE_URL=<read-only-deployments-gateway>
```

## Migrations

Run migrations against the production database before enabling the API for real runs:

```bash
cd services/api
.venv/bin/alembic upgrade head
```

For hosted jobs, run the same command from the API image or a one-off shell with
`DATABASE_URL` configured.

## Policy

OPA must load the repository policy packages:

```text
policies/aegisops/run_eligibility.rego
policies/aegisops/tool_access.rego
policies/aegisops/approvals.rego
policies/aegisops/budget.rego
policies/aegisops/data_sensitivity.rego
```

If `OPA_BASE_URL` is not configured, `/ready` reports `policy_configured=false` and mutating
runtime routes remain unavailable.

## Real-Run Trace Demo

Only use captured real runs. Do not seed invented business payloads.

1. Configure read-only connectors in the API host.
2. Start a workflow run with `LIVE_WORKFLOW_RUNS_ENABLED=false` unless an admin is explicitly
   validating a live sandbox with `LIVE_RUN_ADMIN_KEY` and `x-aegisops-live-run-key`.
3. Execute the read-only context/evidence route.
4. Run approval-review and decision routes where required.
5. For support demos, call `message-send/authorize` to record the blocked send gate.
6. Set `DEMO_TRACE_RUN_ID` in Vercel to the stored run id.
7. Redeploy the web app and verify the trace/eval panels show live metadata.

## Demo Reset And Seed

Use the API package CLI only with external captured replay fixtures:

```bash
cd services/api
.venv/bin/python -m aegisops_api.demo_seed /secure/path/demo-seed-manifest.json
```

Manifest shape:

```json
{
  "schema_version": "aegisops.demo_seed_manifest.v1",
  "provenance": "captured_real_run_manifest",
  "reset_existing_seeded_runs": true,
  "runs": [
    {
      "workflow_id": "engineering_issue_to_pr",
      "source_run_id": "captured-real-run-id"
    }
  ]
}
```

The CLI validates each replay fixture’s `provenance: captured_real_run`, resets only prior
demo-seeded replay runs for the same source ids, creates replay-labeled `workflow_runs`, and
persists trace/evidence metadata through the existing replay runtime. It does not create fake
business records and does not call live connectors.

## Deployment Gates

- `GET /health` returns `200`.
- `GET /ready` reports database, policy, and `live_run_admin_gate_configured=true` before live
  runs.
- `GET /connectors` shows required connectors configured.
- `GET /workflow-runs/{run_id}/trace` returns stored metadata.
- `GET /workflow-runs/{run_id}/evals/trace` returns pass/warn/fail checks.
- No branch, PR, rollback, paging, customer-message, refund, or account-change write adapter is
  enabled for the public demo.
