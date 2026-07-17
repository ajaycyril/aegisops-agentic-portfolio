# Stack Decisions

## Final Stack

| Layer | Selected Tooling | Reason |
| --- | --- | --- |
| Frontend | Next.js, React, shadcn/ui, Tailwind | Enterprise-grade visual control plane |
| Visual graphs | React Flow / XYFlow | Interactive workflow and dependency maps |
| Code/policy viewer | Monaco Editor | Inspect graph code, schemas, JSON, and Rego |
| Backend | FastAPI, Pydantic, SQLAlchemy | Typed Python API with mature async ecosystem |
| Core orchestration | LangGraph | Durable, stateful, inspectable agent graphs |
| OpenAI-native agents | OpenAI Agents SDK | Handoffs, sessions, guardrails, managed agent turns |
| Model API | OpenAI Responses API | Low-level control over structured outputs and tool loops |
| Tool protocol | MCP | Standard agent tool and resource contract |
| Policy | OPA/Rego | Policy-as-code outside the model |
| Database | Postgres | System of record for app state and audit |
| Vector search | pgvector | Demo-friendly retrieval without extra infrastructure |
| Cache | Redis / Upstash Redis | Rate limits, locks, run counters, budget caps |
| Observability | OpenTelemetry, LangSmith, Langfuse | Native agent traces plus open telemetry |
| Evaluation | pytest, promptfoo, Ragas, custom trace evals | Regression and quality gates |
| Deployment | Vercel, Render/Fly/Railway, Neon/Supabase | Free-tier demo with production upgrade path |

## July 2026 Implementation Audit

The live workbench uses one standard library per ownership boundary instead of reimplementing
agent loops, graph execution, policy evaluation, rules evaluation, tool protocol, or graph UI.
Repository popularity was checked on 2026-07-17 and is evidence of ecosystem adoption, not the
sole selection criterion.

| Boundary | Active package | Version | GitHub stars checked | Why it owns this boundary |
| --- | --- | ---: | ---: | --- |
| Agent graph | `@langchain/langgraph` | 1.4.8 | 3,120 | Stateful nodes, parallel fan-out, fan-in, checkpoints, streamed updates |
| Model/tool loop | `ai` | 6.0.225 | 25,604 | Provider-neutral `ToolLoopAgent`, typed tools, streaming, usage |
| Tool protocol | `@modelcontextprotocol/sdk` | 1.29.0 | 12,870 | Standard client/server schemas and portable connector boundary |
| Dynamic policy | OPA/Rego + `opa-wasm` | OPA 1.18.2 | 11,989 | Deterministic authorization outside model control |
| Fixed rules | `json-rules-engine` | 7.3.1 | 3,107 | Versioned, inspectable business conditions |
| Workflow UI | `@xyflow/react` | 12.11.2 | 37,673 | Production graph rendering, custom nodes, animated execution edges |
| Runtime contracts | Zod | 4.4.3 | 43,277 | Input, event, source response, and evidence validation |
| Cloud data target | Supabase Postgres | adapter-ready | 106,436 | Postgres, pgvector, audit, and LangGraph checkpoint target |

`@openai/agents` is installed as an evaluated OpenAI-native option, but it is not falsely shown as
active in the public free-tier path. LangGraph owns the incident supervisor-worker graph and AI SDK
owns each specialist tool loop. OpenAI Agents SDK becomes appropriate when an OpenAI-native
deployment needs its sessions, hosted tracing, or handoff semantics more than provider portability.

## Why LangGraph Is Primary

LangGraph is the core runtime because this platform needs explicit state, branching,
checkpointing, retries, interrupts, human approvals, and visualizable graph execution.

Alternative frameworks can be discussed in the product, but the implementation should not split
core orchestration across too many runtimes.

## Where OpenAI Agents SDK Fits

Use the OpenAI Agents SDK for specialist agents when managed handoffs, sessions, tracing, and
guardrails are more valuable than custom graph control.

The platform still owns:

- Run lifecycle.
- Policy context.
- Human approvals.
- Audit log.
- Tool authorization.
- Cost budget.
- Visual trace mapping.

## Enterprise Alternatives To Acknowledge

| Alternative | How To Position |
| --- | --- |
| Microsoft Agent Framework / Semantic Kernel | Strong for Microsoft-centric enterprise stacks |
| AWS Bedrock Agents / AgentCore | Strong for AWS-native organizations |
| Google Vertex AI Agent Builder | Strong for Google Cloud-native teams |
| CrewAI | Useful for role-based multi-agent automation, not primary runtime here |
| AutoGen | Useful for multi-agent research and conversation patterns |
| LlamaIndex | Strong for RAG/data agents, can be integrated as retrieval layer |
| Haystack | Strong for search/RAG pipelines |
| PydanticAI | Strong for lightweight typed agents |

The expert move is to show awareness of these options while selecting one coherent production
runtime.

## Cost Posture

The demo should be free-tier first:

- Real API calls are budget-capped.
- Public demo can use captured real-run replay.
- Live workflows require configured credentials and admin approval.
- Unit economics are shown in the UI as an architectural capability, not as a cost burden.
- Actual GitHub Models free-tier charge and direct OpenAI API equivalent are displayed separately.

## Dependency Policy

- Pin major versions in manifests.
- Generate lockfiles when implementation starts.
- Keep dependency ownership clear by layer.
- Prefer SDKs and parsers over ad hoc string parsing.
- Avoid adding framework overlap unless it demonstrates a real capability.
