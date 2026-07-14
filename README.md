# AegisOps Agentic Workflow Portfolio

A production-grade, visual-first agentic AI platform blueprint for enterprise workflows.

The purpose of this repo is to demonstrate expertise across the full agentic stack:
orchestration, tools, memory, policy, guardrails, human approval, observability, evals,
deployment, and cost governance.

This is not a chatbot demo. It is an agentic workflow platform.

## Current Phase

Foundation runtime and governance scaffolding are in place.

This repository currently defines:

- Durable agent execution instructions.
- Full incremental project plan.
- Monorepo structure.
- Production stack decisions.
- Workflow portfolio and use-case library.
- Visual product architecture.
- Real-data-only operating rules.
- Free-tier deployment target with production-grade upgrade path.
- Dependency manifests for web, API, and shared contracts.
- Local infrastructure plan for Postgres, pgvector, Redis, and OPA.
- Deployed visual command-center shell.
- SQLAlchemy governance data model and Alembic migration.
- OPA/Rego policy baseline and structured policy fixtures.
- Typed OPA client and audit event writer.

## Core Principle

Every workflow must be real-system ready.

- No fake data.
- No regex-driven extraction for business logic.
- No opaque agent runs.
- No unrestricted autonomy.
- No model call without trace, budget, and policy context.

If a real connector is not configured, the workflow remains disabled. Replay mode is allowed
only for captured real runs and must be labeled as replay.

## Portfolio Workflows

| Domain | Workflow | Production Value |
| --- | --- | --- |
| Engineering | GitHub Issue-to-PR Agent | Turns real issues into reviewed PR drafts |
| Security | Vulnerability Remediation Agent | Triage CVEs and generate safe remediation plans |
| Customer Support | Escalation Resolution Agent | Resolve real support escalations with context and approval |
| Supply Chain | Supplier Risk Agent | Investigate supplier risk from real systems and sources |
| Finance Ops | Invoice Exception Agent | Triage invoices, policies, approvals, and audit evidence |
| Incident Response | Production Incident Investigator | Correlate logs, traces, deploys, and CI to produce RCA |
| Sales / RFP | Account Research and Proposal Agent | Build source-grounded RFP and account briefs |
| Compliance | Audit Evidence Agent | Collect evidence from systems and map to controls |
| Data / BI | Executive Analyst Agent | Query real operational data and explain drivers |
| HR / IT Ops | Onboarding and Access Agent | Coordinate access, docs, tasks, and approvals |

## Repository Layout

```text
.
├── apps/
│   └── web/                  # Visual command center
├── services/
│   └── api/                  # FastAPI, LangGraph, OpenAI, policy, tools
├── packages/
│   └── shared-contracts/     # Shared TypeScript contracts and generated schemas
├── configs/
│   ├── policies/             # Policy routing and approval metadata
│   └── workflows/            # Workflow registry definitions
├── docs/
│   ├── architecture/          # System design and stack decisions
│   ├── adrs/                  # Architecture decision records
│   ├── use-cases/             # Enterprise workflow portfolio
│   └── workflows/             # Workflow design contracts
├── infra/                    # Local and deployment infrastructure
├── mcp/                      # MCP server design and tool contracts
└── policies/                 # OPA/Rego policy home
```

## Stack Summary

| Layer | Choice |
| --- | --- |
| Frontend | Next.js, React, shadcn/ui, Tailwind, React Flow |
| Backend | FastAPI, Pydantic, SQLAlchemy |
| Agent orchestration | LangGraph |
| OpenAI-native specialists | OpenAI Agents SDK |
| Model API | OpenAI Responses API |
| Tool protocol | MCP |
| Policy engine | OPA/Rego |
| Data layer | Postgres, pgvector |
| Cache/rate limits | Redis or Upstash Redis |
| Observability | OpenTelemetry, LangSmith, Langfuse |
| Evals | pytest, promptfoo, Ragas, trace evaluators |
| Deployment | Vercel web, Render/Fly/Railway API, Neon/Supabase Postgres |

## Start Here

Read these documents in order:

1. [Agent Operating Guide](./AGENTS.md)
2. [Incremental Project Plan](./PROJECT_PLAN.md)
3. [Executive Overview](./docs/architecture/00-executive-overview.md)
4. [System Architecture](./docs/architecture/01-system-architecture.md)
5. [Stack Decisions](./docs/architecture/02-stack-decisions.md)
6. [Workflow Taxonomy](./docs/architecture/03-agentic-workflow-taxonomy.md)
7. [Visual Product Blueprint](./docs/architecture/04-visual-product-blueprint.md)
8. [Use-Case Portfolio](./docs/use-cases/README.md)
9. [Workflow Contracts](./docs/workflows/README.md)
10. [Local Development Setup](./docs/development/local-setup.md)

## Execution Plan

`PROJECT_PLAN.md` is the canonical execution plan. Future agents should use it to select the
next incomplete task without relying on chat history.

Current next task:

1. Verify Phase 2 live infrastructure on a machine with Docker.
2. Run Alembic against local Postgres/pgvector.
3. Start Phase 3 by loading and validating workflow YAML configs into a typed registry.

## Local Development Target

The first implementation milestone will support:

- `pnpm` workspace for frontend and shared TypeScript contracts.
- Python virtual environment for the API and agent runtime.
- Local Postgres with pgvector.
- Local Redis-compatible cache.
- Local OPA policy service.
- Environment variables validated at startup.

## Free-Tier Constraint

The public demo should run on free tiers where possible, but the architecture must remain
deployment-grade. Free hosting is a demo constraint, not a production SLA.

## Current Deployment

The visual command center is deployed on Vercel:

- Production URL: https://aegisops-agentic-portfolio.vercel.app
- Vercel project: `aegisops-agentic-portfolio`

The deployed web shell is the visual foundation. Live workflow execution remains disabled until
real connectors, live policy checks, backend deployment, and spend controls are wired.

## License

Private project scaffold. Choose a license before public release.
