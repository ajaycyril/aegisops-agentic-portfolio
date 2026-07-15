# Production Deployment Runbook

This runbook keeps the public demo free-tier friendly while preserving production controls.
Provider free-tier availability changes over time; verify current quotas before deploying.

## Targets

| Layer | Demo Target | Required Before Live Runs |
| --- | --- | --- |
| Web | Vercel project `aegisops-agentic-portfolio` | `NEXT_PUBLIC_API_BASE_URL` only when API is deployed |
| API | Docker web service from `services/api/Dockerfile` | database, OPA, budgets, connector env vars |
| Database | Managed Postgres with pgvector | Alembic head applied |
| Policy | OPA service or sidecar | `policies/aegisops/*.rego` loaded |
| Connectors | Read-only HTTP JSON gateways or GitHub App | connector env vars and scopes configured |

## Web Deployment

The web app deploys from `apps/web`.

Required production variables:

```text
NEXT_PUBLIC_API_BASE_URL=https://<api-host>
DEMO_TRACE_RUN_ID=<captured-real-run-id>
```

Leave both unset for a static visual-only public demo. The command center will show repository
contracts, disabled live controls, and no fake trace data.

## API Deployment

The API container is defined in `services/api/Dockerfile`. `render.yaml` is a deploy-ready
blueprint for a Docker web service candidate.

Safe defaults:

```text
APP_ENV=production
LIVE_WORKFLOW_RUNS_ENABLED=false
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
```

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
   validating a live sandbox.
3. Execute the read-only context/evidence route.
4. Run approval-review and decision routes where required.
5. For support demos, call `message-send/authorize` to record the blocked send gate.
6. Set `DEMO_TRACE_RUN_ID` in Vercel to the stored run id.
7. Redeploy the web app and verify the trace/eval panels show live metadata.

## Deployment Gates

- `GET /health` returns `200`.
- `GET /ready` reports database and policy configured before live runs.
- `GET /connectors` shows required connectors configured.
- `GET /workflow-runs/{run_id}/trace` returns stored metadata.
- `GET /workflow-runs/{run_id}/evals/trace` returns pass/warn/fail checks.
- No branch, PR, rollback, paging, customer-message, refund, or account-change write adapter is
  enabled for the public demo.
