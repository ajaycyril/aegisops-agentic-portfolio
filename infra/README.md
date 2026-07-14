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
