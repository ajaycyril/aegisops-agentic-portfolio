# AegisOps Vercel Read-Only API

This service is the public Vercel Services API gateway for the portfolio demo.

It is intentionally smaller than `services/api`:

- exposes `/health`, `/ready`, `/version`, `/workflows`, `/connectors`, and `/tools`;
- reads the real workflow, connector, and tool registry contracts from `configs/`;
- reports registry counts in readiness and fails readiness if the snapshot is missing;
- does not connect to Postgres, OPA, OpenAI, LangGraph, or live enterprise systems;
- does not expose workflow-run, approval, tool execution, model, memory, or write routes.

The full stateful agent runtime remains in `services/api` and should be deployed as a Docker
service with Postgres, OPA, connector secrets, approval gates, spend controls, and migrations.

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
