# Policy Layer

OPA/Rego policies live here.

The policy layer controls:

- Tool access by workflow, user, environment, and autonomy level.
- Human approval requirements.
- Budget thresholds.
- Data sensitivity constraints.
- Write-action permissions.
- Replay/live execution eligibility.

## Rule

Policy is not prompt text. Policy decisions must be made outside the model and included in the
run trace.

## Initial Policy Files

The baseline Rego modules live under `policies/aegisops/`:

- `tool_access.rego`
- `run_eligibility.rego`
- `approvals.rego`
- `budget.rego`
- `data_sensitivity.rego`

Structured policy fixture inputs live under `configs/policies/fixtures/`.

Current approval fixtures cover the Engineering branch/PR decision path, including allowed
approval, allowed rejection, missing approver rejection, and self-approval rejection.
They also cover Incident Investigator approval decisions for rollback approval, paging
rejection, and self-approval blocking for incident updates.
