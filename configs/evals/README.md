# Evaluation Contracts

This directory contains eval configuration that can run without fabricated business data.

The first layer is rubric plus deterministic trace checks: it defines what must be measured
before live demos can expose model-generated proposals, RCA drafts, or support response drafts.
Runtime tests validate the rubric schema, weights, workflow IDs, and no-fake-data constraints
without making model calls. The API also exposes `GET /workflow-runs/{run_id}/evals/trace` for
executable checks over persisted trace metadata.

## Rubric Rules

- Every artifact must cite real evidence URIs.
- Every rubric must set `fake_data_allowed: false`.
- Dimension weights must sum to `1.0`.
- Required dimensions must be enforceable by schema, deterministic checks, human review, or an
  explicitly configured model judge.
- Write-action recommendations must remain approval-gated.
- Customer-visible support messages must have a blocked send-authorization trace while the send
  adapter is disabled.
