# Web Command Center

The web app is the visual control plane for AegisOps.

It is intentionally scaffolded before implementation so the product surface is clear:

- Executive workflow map.
- Agent graph explorer.
- Evidence board.
- Policy studio.
- Memory explorer.
- Tool registry.
- Trace timeline.
- Eval dashboard.
- Cost and risk controls.
- Code lens for schemas, graph nodes, and policies.

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
