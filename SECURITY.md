# Security Policy

## Supported Surface

Security fixes target the default branch and the current production deployment.

The public workbench is intentionally constrained:

- Only allowlisted read-only MCP tools are available.
- Public model identifiers are allowlisted server-side.
- OPA/Rego evaluates run eligibility and side-effect policy.
- Side-effect approval cannot be disabled by public callers.
- Request size, tool count, spend, rate, concurrency, and runtime are bounded.
- No connector credential is sent to the browser or committed to this repository.

The in-memory public limiter is a demo safety fallback. A deployment serving sustained or
untrusted traffic must configure shared Redis-compatible rate limiting and durable Postgres
checkpoints before raising public quotas.

## Reporting A Vulnerability

Do not open a public issue for a suspected vulnerability or exposed credential. Use the
[private security advisory form](https://github.com/ajaycyril/aegisops-agentic-portfolio/security/advisories/new)
with reproduction steps, affected surface, and impact.

Do not include active secrets, customer data, or exploit traffic in a report. Use redacted
examples and coordinate before testing against the production deployment.
