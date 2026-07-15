# Web Command Center

The web app is the visual control plane for AegisOps.

The current command center includes:

- Executive workflow map.
- Agent graph explorer.
- Evidence board.
- Policy studio.
- Trace timeline.
- Live workflow trace readout when `DEMO_WORKFLOW_RUN_ID` or `DEMO_TRACE_RUN_ID` points to a
  real stored API run.
- Cost and risk controls.
- Code lens for schemas, graph nodes, and policies.
- Safe disabled run-start controls.
- Repository workflow catalog mirror when the live API is not configured.

## Technology

- Next.js
- React
- TypeScript
- Tailwind
- shadcn/ui
- React Flow / XYFlow
- Monaco Editor
- TanStack Query
- TanStack Table
- Recharts
- Framer Motion

## Implementation Rule

The UI must make every layer inspectable. A non-technical viewer should understand the
business flow, and an engineer should be able to inspect the graph, tools, policy decisions,
schemas, traces, and deployment metadata.
