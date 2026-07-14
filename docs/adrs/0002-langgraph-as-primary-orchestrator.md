# ADR 0002: LangGraph As Primary Orchestrator

## Status

Accepted.

## Context

The platform needs production-grade stateful orchestration, graph execution, persistence,
human approval pauses, retries, and inspectable execution paths.

## Decision

Use LangGraph as the primary orchestration runtime.

Use OpenAI Agents SDK for specialist OpenAI-native agents where managed sessions, handoffs,
tracing, and guardrails are advantageous.

## Consequences

The platform has one primary graph runtime, avoiding fragmented orchestration. Other agent
frameworks can be discussed or adapted later, but they do not own core control flow.
