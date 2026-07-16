# Agent Operating Guide

This file is the durable handoff context for coding agents working in this repository.

## Mission

Build AegisOps: a production-grade, visual-first agentic workflow portfolio that demonstrates
enterprise-ready agentic AI across engineering, security, customer support, supply chain,
finance, incident response, sales, compliance, data, and HR/IT operations.

The product must communicate at three levels:

- Executive: outcome, value, risk, cost, decision.
- Architect: workflow graph, governance, tools, memory, observability.
- Engineer: code, schemas, policies, traces, tests, deployment config.

## Start Every Session Here

Before making changes, read:

1. `PROJECT_PLAN.md`
2. `README.md`
3. `docs/architecture/01-system-architecture.md`
4. `docs/architecture/04-visual-product-blueprint.md`
5. Relevant workflow config under `configs/workflows/`

Use `PROJECT_PLAN.md` to pick the next incomplete task. Do not rely on chat history.

## Non-Negotiables

- No fake business data.
- No regex-driven business extraction, routing, parsing, or policy decisions.
- No opaque agent behavior.
- No untyped tool calls.
- No autonomous write action without policy evaluation and approval rules.
- No public live-run path without spend controls.
- No UI that hides the stack depth.

Replay mode is allowed only for captured real runs and must be labeled as replay.

## Architecture Commitments

- Use LangGraph as the primary orchestration runtime.
- Use OpenAI Responses API for low-level model/tool control.
- Use OpenAI Agents SDK for OpenAI-native specialist agents where it improves handoffs,
  sessions, tracing, or guardrails.
- Use MCP as the typed tool boundary.
- Use OPA/Rego for dynamic policy decisions.
- Use Postgres plus pgvector for app state, memory, checkpoints, audit, and retrieval.
- Use OpenTelemetry plus LangSmith/Langfuse-compatible tracing.
- Use Pydantic models as source-of-truth API/runtime contracts.
- Keep optional heavy eval/observability stacks out of the default install path unless needed.
- Treat the runtime as cloud-only for verification and demos. Local Docker is not a project
  prerequisite; any container file is only a cloud build artifact or optional emulator.

## Execution Protocol

1. Check `git status --short --branch`.
2. Read the current phase in `PROJECT_PLAN.md`.
3. Select the first incomplete task that is not blocked.
4. Make the smallest coherent change that completes that task.
5. Update `PROJECT_PLAN.md` status notes if the task state changed.
6. Run relevant validation.
7. Summarize changed files and remaining next step.

## Coding Standards

- Prefer existing repo patterns over new abstractions.
- Keep backend contracts typed with Pydantic.
- Keep frontend contracts typed with TypeScript and generated/shared schemas where possible.
- Use SDKs, parsers, ASTs, structured APIs, or schemas instead of ad hoc string parsing.
- Keep workflow modules self-contained and registry-driven.
- Write docs alongside architecture-affecting code.
- Add tests/evals for behavior that affects policy, tools, memory, graph routing, or approvals.

## Visual Product Standards

The web app is the product, not a marketing page.

Every workflow run should support:

- Executive summary.
- Interactive graph.
- Evidence board.
- Policy lens.
- Memory lens.
- Tool registry view.
- Trace timeline.
- Eval result view.
- Code/config lens.

Every graph node should expose input, output, policy decision, tool schema, trace ID, cost,
latency, memory access, evidence sources, and approval status when applicable.

## Current Priority

The repository has completed the architecture baseline, foundation runtime, governance/data
layer, workflow registry/run-start gate, and visual command center shell.

Next major milestone: complete the cloud-only runtime path with managed Postgres/pgvector,
a hosted OPA-compatible policy endpoint, deployed full API runtime, connector secrets, and
admin-gated real-run validation. Then continue the typed tool and connector substrate behind
the policy-checked authorization boundary. See `PROJECT_PLAN.md`.
