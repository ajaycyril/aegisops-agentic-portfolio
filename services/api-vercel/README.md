# AegisOps Vercel Read-Only API

This service is the public Vercel Services API gateway for the portfolio demo.

It is intentionally smaller than `services/api`:

- exposes `/health`, `/ready`, `/version`, `/workflows`, `/connectors`, `/tools`, and a
  guarded `/workflow-runs` control-plane gate;
- reads the real workflow, connector, and tool registry contracts from `configs/`;
- reports registry counts in readiness and fails readiness if the snapshot is missing;
- does not connect to Postgres, OPA, OpenAI, LangGraph, or live enterprise systems;
- does not execute workflow runs, approvals, tools, model calls, memory writes, or external
  write routes.

`POST /workflow-runs` is intentionally present so the UI never falls through to a raw 404. It
returns a typed `full_runtime_not_configured` gate unless `FULL_RUNTIME_API_BASE_URL` and
`PUBLIC_LIVE_RUN_PROXY_ENABLED` are configured after the full runtime has database, OPA,
connector secrets, approval gates, and spend controls.

The full stateful agent runtime remains in `services/api` and should be deployed as a cloud API
service with managed Postgres, hosted OPA-compatible policy, connector secrets, approval gates,
spend controls, and migrations. Local Docker is not required for the live path.

## Config Snapshot

Vercel packages each service from its own root, so this service keeps a committed snapshot of
the canonical public registry config:

```text
services/api-vercel/configs/connectors
services/api-vercel/configs/tools
services/api-vercel/configs/workflows
```

After editing the canonical registry under the repo-level `configs/` directory, run:

```bash
pnpm vercel-api:sync-config
pnpm vercel-api:check-config
```

The snapshot must stay byte-for-byte aligned with the canonical workflow, connector, and tool
YAML files before deploying the public Vercel API.
