# Workflow Design Contracts

Each workflow is a production module. It is not a prompt folder.

## Required Structure

```text
workflows/<workflow_id>/
├── graph.py              # LangGraph graph definition
├── contracts.py          # Pydantic input/output/state models
├── tools.py              # Typed tool bindings
├── policies.rego         # Workflow-specific policy rules
├── prompts/              # Versioned prompts, if needed
├── evals/                # Workflow eval datasets and rubrics
├── README.md             # Workflow operating guide
└── tests/                # Graph, policy, and tool-contract tests
```

Implementation has started with
`services/api/src/aegisops_api/workflows/engineering_issue_to_pr/`. The current module contains
the first typed LangGraph state/input contract and read-only GitHub issue/file evidence nodes.
It is exposed through a controlled run-scoped evidence collection route that requires a stored
workflow run. Live mode uses read-only GitHub tools; replay mode requires a captured real-run
fixture. Optional planner/evaluator nodes can produce typed patch-plan and test-plan artifacts
when a real planner implementation is injected. The OpenAI Responses API planner adapter
records `model_calls` and is available from the run route with `include_proposal=true` when
OpenAI credentials and a model are configured. The YAML files under `configs/workflows` remain
the portfolio registry.

## Workflow Contract

Every workflow must define:

- Workflow ID.
- Domain.
- Real connector requirements.
- Required scopes.
- Autonomy levels.
- Allowed tools.
- Approval requirements.
- Budget defaults.
- Memory policy.
- Retrieval policy.
- Eval gates.
- Visual surfaces.
- Deployment status.

## State Model

Every workflow graph must use typed state. State should include:

- Run metadata.
- User and organization context.
- Input artifact references.
- Policy context.
- Evidence collected.
- Tool results.
- Model outputs.
- Approval state.
- Cost state.
- Final artifact references.

## Tool Contract

Every tool must declare:

- Input schema.
- Output schema.
- Read/write classification.
- Auth scope.
- Rate limit.
- Cost behavior.
- Approval requirement.
- Observability fields.

## Completion Criteria

A workflow is production-ready only when it has:

- Real connector integration.
- Graph tests.
- Tool-contract tests.
- Policy tests.
- Eval harness.
- Trace view.
- Cost budget.
- Human approval path for sensitive actions.
- Deployment configuration.
