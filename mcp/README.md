# MCP Tool Layer

The MCP layer exposes tools and resources to agents through typed contracts.

## Tool Families

- GitHub tools: issues, PRs, commits, checks, files.
- Security tools: dependency graph, OSV, advisories, scanner output.
- Support tools: email/ticketing/CRM connectors.
- Observability tools: logs, traces, deployments, CI.
- Data tools: approved SQL query execution and chart generation.
- Document tools: Drive/Notion/Confluence/knowledge base retrieval.
- Policy tools: explain allowed, blocked, and approval-required actions.

## Contract Requirements

Every tool must define:

- Name and description.
- Input schema.
- Output schema.
- Required auth scope.
- Read/write classification.
- Approval requirement.
- Rate limit.
- Cost estimate behavior.
- Observability metadata.

No untyped tool calls are allowed.
