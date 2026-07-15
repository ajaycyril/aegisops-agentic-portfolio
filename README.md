# AegisOps Agentic Workflow Portfolio

A production-grade, visual-first agentic AI platform blueprint for enterprise workflows.

The purpose of this repo is to demonstrate expertise across the full agentic stack:
orchestration, tools, memory, policy, guardrails, human approval, observability, evals,
deployment, and cost governance.

This is not a chatbot demo. It is an agentic workflow platform.

## Current Phase

Foundation runtime, governance scaffolding, workflow registry, policy-gated run-start
scaffolding, and the registry-aware visual command center are in place.

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
- Typed connector auth/readiness catalog covering all enterprise systems referenced by the
  workflow and tool registries.
- Typed workflow registry loader and read-only workflow catalog endpoints.
- Typed `POST /workflow-runs` start gate with connector readiness, replay/live mode, budget
  envelope, OPA run eligibility, durable run records, registry snapshots, and audit events.
- Registry-aware visual command center with portfolio selection, execution segmentation,
  React Flow graph, evidence board, policy lens, trace timeline, code lens, and safe disabled
  run-start controls.
- Typed tool contract registry with GitHub, SQL read, document retrieval, and observability
  tool definitions exposed through read-only API endpoints.
- MCP tool contract server skeleton and `POST /tool-calls/authorize` boundary for
  schema-validated, OPA-checked, audit-logged tool calls without live connector execution.
- `POST /tool-calls/{tool_call_id}/execute` for executing a previously authorized stored tool
  call, with input-hash revalidation, output schema validation, status transitions, latency,
  output hash, and audit events.
- Read-only GitHub App adapter for real issue and file reads through installation-token REST
  calls. Write adapters remain intentionally unavailable.
- Read-only HTTP JSON adapters for observability log search and deployment event search,
  configured through explicit connection IDs, base URLs, optional endpoint paths, and optional
  bearer tokens.
- Engineering Issue-to-PR LangGraph module with typed input, issue read node, context file read
  node, evidence assembly node, and policy-backed tool runtime integration.
- Controlled Engineering Issue-to-PR evidence collection route at
  `POST /workflow-runs/{run_id}/engineering-issue-to-pr/evidence`, gated by a stored live
  workflow run, typed input, tool policy authorization, GitHub adapter execution, persisted
  evidence metadata, and audit events.
- Captured-real-run replay fixture schema and loader for the same Engineering evidence route.
  The repo documents fixture placement but does not ship fabricated replay payloads.
- Optional Engineering Issue-to-PR proposal/evaluator graph nodes with typed patch-plan,
  test-plan, and evaluation contracts. They require an injected planner and do not enable
  branch or pull-request writes.
- OpenAI Responses API planner adapter for those proposal/evaluator contracts, with
  `model_calls` audit records for model, prompt version, token counts, latency, trace ID, and
  failure status.
- `include_proposal=true` support on the Engineering evidence route when `OPENAI_API_KEY` and
  an explicit OpenAI model are configured. Proposal/evaluation output remains non-writing and
  approval-required.
- Run-scoped Engineering approval-review route that persists pending `approvals` rows for
  proposed branch and pull-request actions, validates evidence URIs against the proposal, moves
  the run to `waiting_for_approval`, and records audit events without executing GitHub writes.
- Run-scoped Engineering approval decision route that approves or rejects pending branch/PR
  approval records through OPA, captures decision metadata, enforces four-eyes review input, and
  still returns a no-write execution state.
- Run-scoped Engineering PR draft authorization route that accepts approved approval IDs and
  creates policy-checked `github_pull_request_draft` tool calls as authorized-but-not-executed
  records, or blocked records when approval is missing. It still does not execute GitHub writes.
- Run-scoped Engineering PR draft preview route that verifies the approved authorization and
  input hash, then persists a dry-run evidence artifact with PR metadata and hashes only.
- Generic workflow-run trace endpoint returning run, approval, tool-call, model-call, evidence,
  and audit metadata for UI readouts.
- Server-rendered web trace reader keyed by `DEMO_WORKFLOW_RUN_ID`/`DEMO_TRACE_RUN_ID`, with
  no fake fallback data. It visualizes approval decisions, PR authorization blocks, dry-run
  preview evidence, record counts, and recent trace metadata from `GET /workflow-runs/{run_id}/trace`.
- Visual Proposal Review cockpit showing the route contract, planner readiness, typed
  proposal/evaluation output, model-call audit path, approval persistence contract, and approval
  stop-points.
- Visual multi-agent orchestration cockpit for the Production Incident Investigator, using
  React Flow to show supervisor-worker fan-out, specialist evidence gathering, evaluator
  reconciliation, and approval-gated production actions without fake incident data.
- Production Incident Investigator LangGraph runtime slice with read-only log, deployment,
  and code evidence collection through policy-authorized tool calls plus captured-real-run
  replay loading. Live observability/deployment reads use the generic HTTP JSON adapters when
  connector env vars are configured. The route returns source-grounded evidence validation and
  can create a typed, hash-only RCA draft contract when `include_rca=true`; rollback, paging,
  incident updates, and external writes remain disabled.
- Run-scoped Incident approval-review route that creates pending `approvals` rows for rollback,
  paging, and incident-update proposals from a grounded RCA draft without executing those
  actions.
- Run-scoped Incident approval decision route that approves or rejects those records through
  OPA policy, audits the decision, and still returns a no-write execution state.
- Rubric-only eval contracts for Engineering patch proposals and Incident RCA drafts, plus
  structured incident approval policy fixtures for rollback, paging, and incident updates.

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

| Domain            | Workflow                            | Production Value                                               |
| ----------------- | ----------------------------------- | -------------------------------------------------------------- |
| Engineering       | GitHub Issue-to-PR Agent            | Turns real issues into reviewed PR drafts                      |
| Security          | Vulnerability Remediation Agent     | Triage CVEs and generate safe remediation plans                |
| Customer Support  | Escalation Resolution Agent         | Resolve real support escalations with context and approval     |
| Supply Chain      | Supplier Risk Agent                 | Investigate supplier risk from real systems and sources        |
| Finance Ops       | Invoice Exception Agent             | Triage invoices, policies, approvals, and audit evidence       |
| Incident Response | Production Incident Investigator    | Multi-agent log, trace, deploy, and code investigation for RCA |
| Sales / RFP       | Account Research and Proposal Agent | Build source-grounded RFP and account briefs                   |
| Compliance        | Audit Evidence Agent                | Collect evidence from systems and map to controls              |
| Data / BI         | Executive Analyst Agent             | Query real operational data and explain drivers                |
| HR / IT Ops       | Onboarding and Access Agent         | Coordinate access, docs, tasks, and approvals                  |

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
│   ├── connectors/           # Connector auth, scope, and data-boundary contracts
│   ├── policies/             # Policy routing and approval metadata
│   ├── tools/                # Typed tool contract definitions
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

| Layer                     | Choice                                                     |
| ------------------------- | ---------------------------------------------------------- |
| Frontend                  | Next.js, React, shadcn/ui, Tailwind, React Flow            |
| Backend                   | FastAPI, Pydantic, SQLAlchemy                              |
| Agent orchestration       | LangGraph                                                  |
| OpenAI-native specialists | OpenAI Agents SDK                                          |
| Model API                 | OpenAI Responses API                                       |
| Tool protocol             | MCP                                                        |
| Policy engine             | OPA/Rego                                                   |
| Data layer                | Postgres, pgvector                                         |
| Cache/rate limits         | Redis or Upstash Redis                                     |
| Observability             | OpenTelemetry, LangSmith, Langfuse                         |
| Evals                     | pytest, promptfoo, Ragas, trace evaluators                 |
| Deployment                | Vercel web, Render/Fly/Railway API, Neon/Supabase Postgres |

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

1. Verify Phase 2/3 live infrastructure on a machine with Docker.
2. Run Alembic against local Postgres/pgvector and confirm OPA loads the Rego modules.
3. Continue Phase 8 by adding the customer support connector and knowledge-retrieval
   abstractions.
4. Continue Phase 9 by adding executable trace eval runners and UI eval-result display.

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
