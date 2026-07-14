# Local Development Setup

This guide covers the Phase 1 foundation runtime and Phase 2 governance/data scaffolding.

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

OpenAI keys are not required for Phase 1 health checks.

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
