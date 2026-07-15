# Portfolio Walkthrough Script

Use this as a five-minute executive demo path.

## 1. Open With The Stack

Show the top command center and say:

> AegisOps separates deterministic rules, dynamic policy, AI workflow execution, and agentic
> tool use. Every layer is visible before any live action is allowed.

Point out:

- 10 workflow configs,
- connector readiness,
- approval-gated actions,
- API status and registry source.

## 2. Explain The Portfolio

Select these three flagship workflows:

- GitHub Issue-to-PR Agent for engineering operations,
- Production Incident Investigator for multi-agent orchestration,
- Customer Support Escalation Agent for customer operations.

Explain that the other workflows are configured modules, not fake demos. They remain planned
until real connectors are added.

## 3. Show The Multi-Agent Case

Open the Production Incident Investigator orchestration.

Use this framing:

> Multi-agent orchestration is justified here because logs, deployments, code, impact, and RCA
> review are separate specialist tasks. The supervisor coordinates parallel evidence gathering,
> the evaluator reconciles conflicts, and approval gates block production actions.

## 4. Show Support Guardrails

Open Customer Support Escalation.

Point out:

- support ticket, CRM, and KB read tools,
- cited draft contract,
- memory policy with run scope and 30-day retention,
- human approval decision,
- blocked send authorization,
- executable trace eval endpoint.

Say:

> Even when a human approves the draft, the public demo cannot send a customer message. It
> records a blocked send tool-call instead, which is safer and more auditable.

## 5. Peel Into Trace And Evals

If `DEMO_TRACE_RUN_ID` is configured, show:

- `GET /workflow-runs/{run_id}/trace`,
- `GET /workflow-runs/{run_id}/evals/trace`,
- approval records,
- tool-call states,
- evidence hashes,
- memory records,
- eval pass/warn/fail checks.

If not configured, say:

> The public deployment does not invent trace data. It shows the exact route and required run id
> until a captured real sandbox run is connected.

## 6. Close With The Production Posture

Summarize:

- no fake business data,
- no regex business extraction,
- no hidden model calls,
- real connector readiness,
- OPA policy gates,
- human approval,
- trace/eval visibility,
- write adapters disabled until final hardening.
