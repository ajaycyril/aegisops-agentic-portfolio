package aegisops.budget

import rego.v1

default allow := false
default requires_approval := false

allow if {
	input.estimated_cost_usd <= input.budget.max_estimated_usd
	input.tool_call_count <= input.budget.max_tool_calls
	input.elapsed_seconds <= input.budget.max_run_seconds
}

requires_approval if {
	input.estimated_cost_usd > input.budget.max_estimated_usd
}

requires_approval if {
	input.tool_call_count > input.budget.max_tool_calls
}

requires_approval if {
	input.elapsed_seconds > input.budget.max_run_seconds
}

reason_codes contains "estimated_cost_exceeded" if {
	input.estimated_cost_usd > input.budget.max_estimated_usd
}

reason_codes contains "tool_call_limit_exceeded" if {
	input.tool_call_count > input.budget.max_tool_calls
}

reason_codes contains "run_time_limit_exceeded" if {
	input.elapsed_seconds > input.budget.max_run_seconds
}

decision := {
	"allow": allow,
	"requires_approval": requires_approval,
	"reason_codes": reason_codes,
}
