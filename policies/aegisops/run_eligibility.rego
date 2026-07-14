package aegisops.run_eligibility

import rego.v1

default allow := false
default requires_approval := false

workflow_ready if {
	input.workflow.status == "ready"
}

connector_ready if {
	count(input.missing_connectors) == 0
}

budget_valid if {
	input.estimated_cost_usd <= input.budget.max_estimated_usd
	input.tool_call_count <= input.budget.max_tool_calls
	input.elapsed_seconds <= input.budget.max_run_seconds
}

replay_source_present if {
	input.replay_source_run_id != null
	input.replay_source_run_id != ""
}

replay_allowed if {
	input.execution_mode == "replay"
	input.workflow.data_policy.replay_allowed_from_real_runs == true
	replay_source_present
}

live_run_can_request_approval if {
	input.execution_mode == "live"
	input.live_workflow_runs_enabled == true
	input.require_human_approval == true
}

allow if {
	workflow_ready
	connector_ready
	budget_valid
	replay_allowed
}

requires_approval if {
	workflow_ready
	connector_ready
	budget_valid
	live_run_can_request_approval
}

reason_codes contains "workflow_not_ready" if {
	not workflow_ready
}

reason_codes contains "connectors_not_configured" if {
	not connector_ready
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

reason_codes contains "replay_source_required" if {
	input.execution_mode == "replay"
	not replay_source_present
}

reason_codes contains "replay_not_allowed" if {
	input.execution_mode == "replay"
	input.workflow.data_policy.replay_allowed_from_real_runs != true
}

reason_codes contains "live_runs_disabled" if {
	input.execution_mode == "live"
	input.live_workflow_runs_enabled != true
}

reason_codes contains "human_approval_not_required" if {
	input.execution_mode == "live"
	input.require_human_approval != true
}

decision := {
	"allow": allow,
	"requires_approval": requires_approval,
	"reason_codes": reason_codes,
}
