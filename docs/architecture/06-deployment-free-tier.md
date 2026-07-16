# Deployment and Free-Tier Strategy

The demo must be free-tier friendly while remaining production-shaped.

## Demo Deployment

| Component | Free-Tier Target | Notes |
| --- | --- | --- |
| Web | Vercel Hobby | Visual command center |
| API | Render, Fly, Railway, Vercel service, or similar | Managed cloud FastAPI runtime |
| Postgres | Neon or Supabase free | App state, audit, checkpoints, pgvector |
| Cache | Upstash Redis free | Rate limits and run budget |
| Policy | Hosted OPA-compatible endpoint | Rego policy service with bundle deployment |
| Observability | LangSmith/Langfuse free | Trace and eval visibility |

## Production Upgrade

| Component | Upgrade Path |
| --- | --- |
| Web | Vercel Pro/Enterprise |
| API | Paid container service or cloud Kubernetes |
| Database | Managed Postgres with backups, PITR, private networking |
| Vector search | pgvector until scale; Qdrant/Pinecone/Weaviate if needed |
| Cache | Paid Redis or Upstash |
| Policy | Dedicated OPA service with bundle deployment |
| Workflow durability | LangGraph persistence first; Temporal for cross-service, long-running workflows |
| Observability | Paid LangSmith/Langfuse or self-hosted stack |

## Deployment Gates

Before public deployment:

- Environment validation.
- Health endpoint.
- Database migration check.
- Connector status check.
- OPA policy load check.
- Rate limit configured.
- Model budget configured.
- Admin-only live-run control.
- Replay mode clearly labeled.

## Repository Artifacts

- `services/api` packages the full FastAPI runtime, configs, and policy-aware routes.
- `services/api/Dockerfile` is an optional cloud build artifact for hosts that build container
  images; it is not a local Docker requirement.
- `render.yaml` provides a cloud web-service blueprint candidate with live runs disabled by
  default and `LIVE_RUN_ADMIN_KEY` secret-managed for explicit live-run sandboxes.
- `docs/deployment/production-runbook.md` is the operator checklist for API env vars,
  migrations, OPA, connector gates, and real-run trace/eval display.
- `docs/deployment/portfolio-walkthrough.md` is the executive demo script.

## Cost Controls

The public demo should default to safe modes:

- No live run without `LIVE_RUN_ADMIN_KEY` and a matching `x-aegisops-live-run-key` header.
- Per-run model budget.
- Per-run tool-call limit.
- Per-workflow autonomy limit.
- No write actions without approval.
- Replay mode from captured real runs.
