# Enterprise Use-Case Portfolio

The product should feel like an enterprise portfolio, not a single narrow agent.

## Flagship Use Cases

### 1. Engineering Issue-to-PR Agent

Turns a real GitHub issue into a reviewed PR draft.

Real systems:

- GitHub issues.
- Repository files.
- CI checks.
- Test logs.
- Pull request API.

Agentic depth:

- Plan-and-execute.
- Repo-aware tool use.
- Test/eval loop.
- Human approval before PR creation.

### 2. Security Vulnerability Remediation Agent

Investigates real dependency or code security alerts and proposes remediation.

Real systems:

- OSV.
- GitHub security advisories.
- Dependency manifests.
- Static analysis outputs.
- Pull request API.

Agentic depth:

- Risk triage.
- Exploitability reasoning.
- Patch planning.
- Regression gate.

### 3. Customer Support Escalation Agent

Resolves real customer escalations with account, product, and policy context.

Real systems:

- Support system or email.
- CRM.
- Knowledge base.
- Product docs.
- Order or account system.

Agentic depth:

- Routing.
- Retrieval-grounded response.
- Memory of prior interactions.
- Human approval before customer message.

### 4. Supply Chain Supplier Risk Agent

Evaluates supplier risk using internal vendor data and external sources.

Real systems:

- Supplier master data.
- Procurement records.
- Sanctions or compliance source.
- Web research.
- Logistics or weather APIs if available.

Agentic depth:

- Parallel research.
- Source credibility evaluation.
- Risk classification.
- Mitigation recommendation.

### 5. Finance Invoice Exception Agent

Investigates invoices that violate policy or fail matching checks.

Real systems:

- Accounting API.
- Email invoices.
- Document store.
- Vendor records.
- Approval system.

Agentic depth:

- Document understanding.
- Policy comparison.
- Approval routing.
- Audit packet generation.

### 6. Production Incident Investigator

Correlates observability, deployments, and code changes to produce RCA.

Real systems:

- Logs.
- Traces.
- Deployment events.
- GitHub Actions.
- Incident system.

Agentic depth:

- Supervisor-worker orchestration.
- ReAct tool loop.
- Parallel investigation.
- Specialist handoffs for logs, traces, deploys, code, and impact.
- Evaluator reconciliation when evidence conflicts.
- Hypothesis generation.
- Evidence-backed RCA.
- Human approval before rollback, paging, or incident updates.

### 7. Sales / RFP Agent

Creates source-grounded account briefs and proposal drafts.

Real systems:

- CRM.
- Document repository.
- Company websites.
- Public filings where relevant.
- Prior proposal repository.

Agentic depth:

- Source-grounded research.
- Retrieval.
- Evaluator-optimizer.
- Approval before export.

### 8. Compliance Audit Evidence Agent

Collects evidence for an audit request and maps it to controls.

Real systems:

- GitHub.
- Deployment platform.
- Identity provider.
- Document store.
- Security policies.

Agentic depth:

- Evidence collection.
- Control mapping.
- Gap analysis.
- Audit packet generation.

### 9. Data / BI Executive Analyst Agent

Answers executive questions from real operational databases.

Real systems:

- Postgres analytics tables.
- Product metrics.
- Trace and cost records.
- CRM or finance metrics if connected.

Agentic depth:

- Guarded text-to-SQL.
- Chart generation.
- Explanation with caveats.
- Query review and cost limits.

### 10. HR / IT Onboarding and Access Agent

Coordinates onboarding tasks and access approvals.

Real systems:

- Identity provider.
- Ticketing system.
- Document repository.
- HRIS if connected.

Agentic depth:

- Checklist orchestration.
- Policy-gated access.
- Approval routing.
- Audit trail.

## Prioritization

V1 should fully implement:

1. Engineering Issue-to-PR.
2. Customer Support Escalation.
3. Production Incident Investigator.

These three cover code, customer operations, and production operations. They also exercise most
of the platform layers.
