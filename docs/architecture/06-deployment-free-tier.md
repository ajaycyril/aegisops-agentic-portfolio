# Deployment and Free-Tier Strategy

The demo must be free-tier friendly while remaining production-shaped.

## Demo Deployment

| Component | Free-Tier Target | Notes |
| --- | --- | --- |
| Web | Vercel Hobby | Visual command center |
| API | Render, Fly, Railway, or similar | Containerized FastAPI service |
| Postgres | Neon or Supabase free | App state, audit, checkpoints, pgvector |
| Cache | Upstash Redis free | Rate limits and run budget |
| Policy | OPA container | Local container or sidecar |
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

## Cost Controls

The public demo should default to safe modes:

- No live run without admin key.
- Per-run model budget.
- Per-run tool-call limit.
- Per-workflow autonomy limit.
- No write actions without approval.
- Replay mode from captured real runs.
