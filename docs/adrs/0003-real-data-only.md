# ADR 0003: Real Data Only

## Status

Accepted.

## Context

The project is intended to demonstrate production-grade agentic workflows. Fake data and toy
fixtures would weaken credibility.

## Decision

Workflows are disabled until real connectors are configured. Replay mode is allowed only for
captured real runs and must be labeled as replay.

Business extraction, parsing, routing, and policy decisions cannot rely on regex.

## Consequences

Development may take longer because connectors and permissions must be configured properly.
The resulting demo is substantially more credible.
