# AegisOps User Guide

AegisOps is an executable comparison between an agentic workflow and a traditional rule engine.
Both lanes receive the same scenario input and read the same live source data.

Production workbench: https://aegisops-agentic-portfolio.vercel.app

## Run A Workflow

1. Select Incident, Engineering, Supplier, or Finance.
2. Review the production integration pattern and the value boundary for that scenario.
3. Adjust the bounded inputs, tool limit, spend ceiling, or approved model route.
4. Select **Run both live**.
5. Watch the agentic and fixed-rule lanes execute concurrently.

Human approval is enforced in the public runtime and cannot be disabled. The public tools are
read-only; no production or external-system write is available.

## Read The Execution Canvas

The upper lane is agentic. Its graph can change by scenario and includes model agents, MCP tools,
policy, evidence, handoffs, and evaluation.

The lower lane is deterministic. It fetches predefined facts, evaluates versioned conditions, and
returns one of the outcomes configured before the run.

Select a graph node or trace event to inspect:

- Actor and runtime layer.
- Typed input and structured output.
- Evidence source and capture time.
- Policy or guardrail status.
- Trace ID, latency, and model usage.
- Approval state and requested action class.

## Read The Decision Ledger

The observable decision ledger answers **who controlled this step?**

| Phase | Controller | Meaning |
| --- | --- | --- |
| Bounded goal | Human + LangGraph | Scope, approved tools, spend, and graph topology were fixed before execution |
| Choose action | Model | The model selected from the tools allowed by the graph and policy |
| Execute tool | MCP | A typed read call crossed the connector boundary |
| Observe state | Source + Zod | Returned data passed the evidence contract |
| Adapt or reconcile | Model | The next action or synthesis depended on observed evidence |
| Verify boundary | OPA + evaluator | Policy and grounding requirements determined whether the run could complete |

This is operational decision telemetry, not private model chain-of-thought.

## Compare Agentic And Traditional Value

The value boundary changes with each scenario:

- **Incident:** rules route known severity; agents reconcile independent health and incident
  evidence before recommending the next operational step.
- **Engineering:** rules label known issue attributes; the agent resolves ambiguity and builds an
  investigation path from issue and repository evidence.
- **Supplier:** rules block known registration states; the agent resolves legal-entity ambiguity
  and explains why the evidence supports review.
- **Finance:** rules flag dates and thresholds; the agent grounds a narrative in filing periods,
  values, and caveats without turning an observation into an unsupported accounting conclusion.

## Inspect Tool I/O

Open **Tool I/O** after a run to see the actual model-initiated MCP calls. Each invocation displays
typed arguments, validated result fields, duration, and the official source link.

## Inspect The Live Stack

Open **Live stack map** to see the control and data path. Lit nodes have supporting events in the
current trace. Select a lit node to open its event in the inspector.

The map separates:

- Experience and streaming.
- Agent orchestration and model loops.
- Deterministic rules and dynamic policy.
- Contracts, state, and memory.
- MCP tools and external systems.
- Observability and evaluation.

## Understand Unit Economics

The workbench reports measured input and output tokens and a direct-provider cost equivalent. The
fixed-rule lane has no model cost. The public GitHub Models route can report a zero demo charge while
still showing the equivalent token economics for architecture comparison.

## Public Demo Limits

- Official public APIs are used instead of private enterprise records.
- The connector pattern is real; the public systems are safe analogues for enterprise sources.
- `MemorySaver` is used when managed Postgres is not configured.
- The public limiter is intentionally conservative.
- No write tools, external messages, refunds, rollbacks, pull requests, or account changes execute.

See the [enterprise playbook](./ENTERPRISE_AGENTIC_PLAYBOOK.md) for the authenticated, durable
production architecture.
