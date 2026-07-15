# Infrastructure

The infrastructure layer is designed for free-tier demo deployment with a production-grade
upgrade path.

## Local Components

- Postgres with pgvector for app data, checkpoints, audit logs, and retrieval.
- Redis-compatible cache for rate limits, locks, and budget counters.
- OPA policy service for dynamic authorization and approval decisions.

## Free-Tier Deployment Target

| Component | Demo Target | Production Upgrade |
| --- | --- | --- |
| Web | Vercel Hobby | Vercel Pro/Enterprise |
| API | Render/Fly/Railway free or low-cost service | Paid container service |
| Postgres | Neon/Supabase free | Paid Postgres with backups and PITR |
| Cache | Upstash Redis free | Paid Redis/Upstash |
| Policy | OPA sidecar/container | Dedicated policy service |
| Observability | LangSmith/Langfuse free tiers | Paid or self-hosted observability |

Free-tier hosting is acceptable for the public demo. It is not a production SLA.

## Deployment Artifacts

- `services/api/Dockerfile` builds the FastAPI runtime with workflow configs and Rego policy
  files included.
- `render.yaml` is a Docker web-service blueprint candidate with live runs disabled by default.
- `docs/deployment/production-runbook.md` documents production env vars, migrations, OPA, and
  trace/eval demo gates.
