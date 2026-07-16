# Cloud-Only Runtime Plan

AegisOps does not wait for local Docker. The production demo path is cloud-first and keeps the
public portal safe while the stateful runtime is provisioned behind managed controls.

## Runtime Split

| Surface | Purpose | Status |
| --- | --- | --- |
| Vercel web | Visual command center and executive demo | Deployed |
| Vercel `/api` | Public read-only workflow, connector, and tool registry | Deployed |
| Full API runtime | Stateful workflow routes, traces, approvals, tool authorization, model ledger | Cloud provisioning pending |
| Managed Postgres/pgvector | Runs, audit events, approvals, memory, checkpoints, retrieval | Cloud provisioning pending |
| Hosted OPA-compatible policy | Run eligibility, tool access, approvals, budgets, data sensitivity | Cloud provisioning pending |

## Required Cloud Services

1. Managed Postgres with pgvector enabled.
2. Hosted OPA-compatible policy endpoint that loads `policies/aegisops/*.rego`.
3. Full API host for `services/api` with Python 3.12+, HTTPS, secret-managed env vars, and
   one-off migration support.
4. Optional Redis-compatible cache or Upstash Redis for rate limiting and runtime throttles.
5. Read-only connector gateways or GitHub App credentials for real sandbox runs.

## Environment Contract

```text
APP_ENV=production
DATABASE_URL=<managed-postgres-url>
OPA_BASE_URL=<policy-url>
CONFIGURED_CONNECTORS=github,observability,deployments,support_system,crm,knowledge_base
REQUIRE_HUMAN_APPROVAL=true
LIVE_WORKFLOW_RUNS_ENABLED=false
LIVE_RUN_ADMIN_KEY=<secret-admin-run-start-key>
MAX_AGENT_RUN_SECONDS=300
MAX_AGENT_TOOL_CALLS=25
MAX_AGENT_ESTIMATED_USD=1.00
```

Optional model variables stay disabled until a real sandbox workflow needs proposal or
evaluation generation:

```text
OPENAI_API_KEY=<secret>
OPENAI_DEFAULT_MODEL=<explicit-model>
OPENAI_REASONING_MODEL=<optional-explicit-model>
```

## Verification Steps

1. Run Alembic against the managed database:

   ```bash
   cd services/api
   DATABASE_URL=<managed-postgres-url> .venv/bin/alembic upgrade head
   ```

2. Verify policy loading by calling the hosted OPA-compatible endpoint for the
   `aegisops.run_eligibility`, `aegisops.tool_access`, `aegisops.approvals`,
   `aegisops.budget`, and `aegisops.data_sensitivity` packages.
3. Deploy `services/api` with live runs disabled and the admin live-run key configured.
4. Confirm `/ready` reports database and policy configured.
5. Confirm a live run without `x-aegisops-live-run-key` is rejected before persistence.
6. Capture a real sandbox run only through read-only connectors and approval-gated actions.
7. Set `DEMO_TRACE_RUN_ID` only after the trace exists in the managed database.

## Non-Negotiable Gates

- No invented business payloads.
- No regex-based business decisions.
- No live run without spend controls.
- No external write action without OPA and approval records.
- No public route that exposes model calls, memory mutation, connector writes, or approval
  decisions without the full admin-gated runtime.
