# Contributing

AegisOps accepts focused improvements that preserve the production contracts described in
`AGENTS.md` and `PROJECT_PLAN.md`.

## Before Opening A Pull Request

1. Create a branch from `main`.
2. Keep business decisions in typed rules, OPA policy, or graph code, never regular expressions.
3. Use real connectors or clearly labeled captured-real-run replay data. Do not add synthetic
   business records.
4. Keep all tool calls typed and read/write classified.
5. Require policy evaluation and human approval for sensitive side effects.
6. Add tests for changed contracts, routing, policy, tools, memory, or evaluation behavior.
7. Never commit `.env` files, tokens, credentials, customer data, or raw sensitive traces.

## Validation

```bash
pnpm install --frozen-lockfile
pnpm --filter @aegisops/web lint
pnpm --filter @aegisops/web typecheck
pnpm --filter @aegisops/web test
pnpm --filter @aegisops/web build
node scripts/check-docs-placeholders.mjs
```

API changes should also run the Python test, Ruff, and mypy checks defined in
`.github/workflows/ci.yml`.
