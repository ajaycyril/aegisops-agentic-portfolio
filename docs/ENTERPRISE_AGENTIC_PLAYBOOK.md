# Enterprise Agentic AI Playbook

This playbook explains how AegisOps decides whether a workflow should be deterministic, model-backed,
agentic, or multi-agent, and what must exist before that workflow can be trusted in production.

## Start With The Control Problem

Agentic AI is justified when observations can change the next action. A workflow becomes a stronger
candidate as more of these conditions are true:

- The goal is stable but the path cannot be fully enumerated in advance.
- Evidence comes from multiple tools or systems.
- Inputs are incomplete, ambiguous, or contradictory.
- Tool selection depends on earlier observations.
- The workflow must recover, retry, ask for approval, or stop conditionally.
- A source-grounded narrative or recommendation is required.
- Specialists can collect independent evidence in parallel.

Use deterministic automation when the required facts, thresholds, and outcomes are known. Use OPA
or another policy engine when the decision is authorization rather than interpretation. Use a
bounded AI workflow when one model transformation is enough and no tool-planning loop is needed.

## The Value Test

Before adding an agent, write down four things:

1. **Business decision:** the operational outcome the workflow supports.
2. **Deterministic ceiling:** what rules can decide reliably with known facts.
3. **Adaptive work:** what must change after evidence is observed.
4. **Autonomy boundary:** which actions remain read-only, policy-controlled, or approval-gated.

If the adaptive work cannot be stated concretely, the workflow probably does not need an agent.

## Pattern Selection

| Pattern | Use when | AegisOps example |
| --- | --- | --- |
| Deterministic pipeline | Known data and outcomes | Fixed comparison lane in every scenario |
| Policy decision point | Context changes authorization | OPA allow, block, and approval decisions |
| Bounded model step | One structured interpretation or evaluation | Grounding and rubric evaluation |
| Tool-using agent | Evidence changes tool use or stopping | Engineering, supplier, and finance workflows |
| Supervisor and specialists | Independent evidence can be collected concurrently and reconciled | Incident investigation |
| Human-in-the-loop graph | Sensitive action requires accountable review | PR, customer message, rollback, and access contracts |

Multi-agent orchestration should be chosen for topology, isolation, or parallelism, not because more
agents appear more sophisticated. Every specialist needs a distinct assignment, scoped tools, a
typed handoff, and a reason the supervisor cannot perform the same work more simply.

## Production Stack Boundaries

### Orchestration

LangGraph owns state transitions, retries, fan-out/fan-in, checkpoints, and approval pauses. The
model does not own the workflow state machine.

### Model Runtime

AI SDK `ToolLoopAgent`, OpenAI-compatible provider adapters, and optional OpenAI Agents SDK
specialists own model invocation, typed tool calls, usage, and provider telemetry. Model identifiers
are allowlisted per deployment.

### Tools

MCP is the typed boundary between agent logic and connectors. Tools declare schemas, read/write
classification, scopes, rate behavior, and approval requirements. The public runtime exposes only
read tools.

### Policy

OPA/Rego owns contextual authorization. Policy decisions are versioned, tested, and audited outside
the prompt. The model may provide evidence to policy but cannot approve its own action.

### State And Memory

Postgres stores workflow state, checkpoints, approvals, audit events, model calls, tool calls, and
evidence metadata. pgvector supports retrieval where policy permits it. Memory has explicit scope,
retention, provenance, redaction, and write approval; it is not an unbounded transcript dump.

### Observability And Evaluation

Every model and tool operation needs a trace identity, latency, usage, actor, and structured status.
Evals cover grounding, policy metadata, sensitive writes, redaction, memory behavior, cost, and
workflow-specific quality. A trace without evaluation is debugging data, not production assurance.

## Enterprise Use-Case Library

| Domain | Agentic value | Deterministic responsibility | Sensitive action boundary |
| --- | --- | --- | --- |
| Incident response | Correlate logs, deployments, incidents, and code; reconcile hypotheses | Severity thresholds, paging rules, SLO calculations | Rollback, page, incident update |
| Engineering | Resolve issue ambiguity, inspect code context, propose and evaluate a change | Repository eligibility, CI status, branch policy | Branch and pull-request creation |
| Customer support | Assemble ticket, account, and knowledge context; draft a cited resolution | Entitlement, SLA, refund, and routing rules | Customer message, refund, account change |
| Supplier risk | Resolve entities and reconcile internal/external risk evidence | Sanctions hit, registration status, spend threshold | Onboard, suspend, change supplier status |
| Finance operations | Investigate invoice or filing exceptions and assemble audit evidence | Matching tolerances, close calendar, approval matrix | Post journal, release payment, change vendor |
| Security | Assess exploitability and plan remediation from code and advisory evidence | CVSS thresholds, blocked packages, required controls | Patch merge, production deployment, exception |
| Compliance | Collect evidence and map it to controls with cited gaps | Control applicability and evidence freshness | Attestation or exception approval |
| Sales/RFP | Research accounts and draft source-grounded responses | Pricing, discount, legal clause, export rules | Proposal export or customer commitment |
| Data/BI | Select guarded queries and explain drivers with caveats | Row-level access, query cost, metric definitions | Data export or scheduled distribution |
| HR/IT | Coordinate onboarding context and access requests | Role mappings, segregation of duties, expiry | Account or privileged access creation |

## Unit Economics

Evaluate the complete workflow, not only token price:

- Model input and output tokens.
- Tool/API calls and connector limits.
- Retrieval, storage, checkpoint, and trace volume.
- Retries, evaluator calls, and approval wait time.
- Human review saved or added.
- Error cost and the value of prevented unsafe actions.

A rule engine is usually cheaper when the path is known. An agent earns its cost only when adaptive
evidence work materially reduces handling time, improves decision quality, or expands the class of
cases that can be handled safely.

## Production Readiness Gate

Do not enable sensitive writes until all of the following exist:

- Authenticated user and organization identity.
- Least-privilege connector credentials and scoped MCP tools.
- Durable Postgres checkpoints, approvals, audit, and evidence metadata.
- Shared rate limiting, concurrency control, and budget enforcement.
- OPA policy tests for allow, block, and approval outcomes.
- Four-eyes rules for high-risk actions.
- Prompt-injection and untrusted-content boundaries.
- Redaction, retention, and memory-scope policy.
- Grounding, regression, safety, and cost evals.
- Replayable traces and operational dashboards.
- Idempotency, retry, timeout, and compensation behavior.
- Kill switch, incident runbook, and connector revocation path.

The public AegisOps workbench demonstrates these boundaries with live read-only evidence. The
stateful FastAPI runtime and registry contracts show the upgrade path for authenticated enterprise
connectors, durable approvals, and audited side effects.
