# ADR 0001: Monorepo and Runtime Boundaries

## Status

Accepted.

## Context

The project needs a full-stack visual command center, a Python agent runtime, shared schemas,
workflow configs, policies, and deployment infrastructure.

## Decision

Use a monorepo with:

- `apps/web` for the Next.js visual control plane.
- `services/api` for FastAPI, LangGraph, OpenAI, MCP, OPA, memory, and evals.
- `packages/shared-contracts` for TypeScript-facing contracts.
- `configs` for workflow and policy registries.
- `docs` for architecture and use-case documentation.
- `infra` for local/deployment infrastructure.

## Consequences

This keeps the platform understandable and demoable as one system while preserving strong
runtime boundaries.
