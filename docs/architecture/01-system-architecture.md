# System Architecture

## High-Level Architecture

```mermaid
flowchart TB
  subgraph UI["Visual Command Center"]
    Exec["Executive View"]
    GraphUI["Agent Graph"]
    Evidence["Evidence Board"]
    PolicyUI["Policy Studio"]
    TraceUI["Trace Timeline"]
    CodeLens["Code Lens"]
  end

  subgraph API["API and Runtime"]
    Gateway["FastAPI Gateway"]
    Registry["Workflow Registry"]
    Orchestrator["LangGraph Runtime"]
    OpenAINative["OpenAI Agents SDK Specialists"]
    Approval["Human Approval Service"]
    EvalRunner["Eval Runner"]
  end

  subgraph Governance["Governance"]
    OPA["OPA Policy Engine"]
    Guardrails["Validation and Guardrails"]
    Budget["Budget Controls"]
  end

  subgraph Data["Data Plane"]
    Postgres["Postgres"]
    PgVector["pgvector"]
    Redis["Redis / Upstash"]
    Memory["Memory Store"]
    Checkpoints["LangGraph Checkpoints"]
  end

  subgraph Tools["Tool Plane"]
    MCP["MCP Server"]
    GitHub["GitHub"]
    Support["Support / CRM"]
    Observability["Logs / Traces"]
    Docs["Docs / Knowledge"]
    Finance["Finance Systems"]
    Web["Approved Web Research"]
  end

  UI --> Gateway
  Gateway --> Registry
  Registry --> Orchestrator
  Orchestrator --> OpenAINative
  Orchestrator --> Approval
  Orchestrator --> OPA
  Orchestrator --> Guardrails
  Orchestrator --> Budget
  Orchestrator --> Postgres
  Orchestrator --> PgVector
  Orchestrator --> Redis
  Orchestrator --> Memory
  Orchestrator --> Checkpoints
  Orchestrator --> MCP
  MCP --> GitHub
  MCP --> Support
  MCP --> Observability
  MCP --> Docs
  MCP --> Finance
  MCP --> Web
  EvalRunner --> Orchestrator
```

## Runtime Flow

```mermaid
sequenceDiagram
  actor User
  participant UI as Visual Command Center
  participant API as FastAPI
  participant Policy as OPA
  participant Graph as LangGraph
  participant Model as OpenAI
  participant Tools as MCP Tools
  participant DB as Postgres

  User->>UI: Start workflow
  UI->>API: POST /workflow-runs
  API->>Policy: Check run eligibility
  Policy-->>API: Allow / block / require approval
  API->>DB: Persist workflow run, registry snapshot, audit event
  API->>Graph: Start graph with policy context
  Graph->>DB: Persist checkpoint
  Graph->>Model: Structured planning or reasoning call
  Graph->>Policy: Check tool permission
  Graph->>DB: Persist authorized or blocked tool call
  Graph->>Tools: Execute typed tool call after authorization
  Tools-->>Graph: Structured result
  Graph->>DB: Persist trace, memory, audit event
  Graph-->>UI: Stream node events and evidence
  Graph->>Policy: Check final action
  Policy-->>Graph: Approval required
  Graph-->>UI: Human approval request
```

## Primary Boundaries

| Boundary | Responsibility |
| --- | --- |
| Web app | Visualization, workflow control, approvals, inspection |
| API gateway | Auth, rate limits, workflow control, streaming |
| Public registry API | Vercel read-only workflow, connector, and tool contract endpoints |
| LangGraph runtime | Stateful orchestration and durable graph execution |
| OpenAI layer | Model calls, structured outputs, specialist managed agents |
| MCP layer | Tool contracts and external system access |
| OPA layer | Dynamic policy decisions outside the model |
| Postgres | App state, audit, memory, checkpoints, retrieval |
| Observability | Traces, evals, model/tool telemetry, cost accounting |

## Public Deployment Split

The public Vercel deployment serves three bounded surfaces:

- `apps/web`: the visual command center.
- `apps/web/app/api/agent-runs`: a Node.js streaming runtime for read-only public-source
  workflows. It enforces typed input, OPA policy, tool and spend ceilings, per-session rate
  limits, and no external writes.
- `services/api-vercel`: a slim read-only FastAPI service mounted at `/api` that exposes
  workflow, connector, and tool registry contracts.

The browser's live demo route is deliberately narrower than the full enterprise runtime. It can
read only the approved public MCP tools and cannot mutate memory or external systems. The full
stateful runtime remains in `services/api` for authenticated enterprise connectors, durable audit,
approval records, and writes. `DATABASE_URL` upgrades the public LangGraph checkpointer from
`MemorySaver` to `PostgresSaver`; a durable Redis-compatible limiter is still required before
raising public traffic limits.

## Production Constraints

- All tool calls must be typed.
- All write actions must be policy-checked.
- Sensitive write actions must require human approval by default.
- All model calls must record model, prompt version, cost estimate, latency, and trace ID.
- All retrieval results must carry source metadata.
- All long-running workflows must checkpoint state.
- All workflow runs must be replayable from trace records.
