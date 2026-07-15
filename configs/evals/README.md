# Evaluation Contracts

This directory contains eval configuration that can run without fabricated business data.

The first layer is rubric-only: it defines what must be measured before live demos can expose
model-generated proposals or RCA drafts. Runtime tests validate the rubric schema, weights,
workflow IDs, and no-fake-data constraints without making model calls.

## Rubric Rules

- Every artifact must cite real evidence URIs.
- Every rubric must set `fake_data_allowed: false`.
- Dimension weights must sum to `1.0`.
- Required dimensions must be enforceable by schema, deterministic checks, human review, or an
  explicitly configured model judge.
- Write-action recommendations must remain approval-gated.
