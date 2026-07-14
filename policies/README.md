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

Implementation will add Rego modules after the architecture baseline is approved.
