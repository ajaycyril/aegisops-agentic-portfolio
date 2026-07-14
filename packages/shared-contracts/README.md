# Shared Contracts

Shared TypeScript contracts live here.

This package will hold:

- Workflow registry schemas.
- Tool metadata schemas.
- Trace event schemas.
- Approval request schemas.
- Cost/risk metadata schemas.
- Generated OpenAPI client types.

The API owns source-of-truth Pydantic models. TypeScript contracts should be generated or
kept in explicit lockstep to prevent UI/API drift.
