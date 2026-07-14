package aegisops.tool_access

import rego.v1

write_risk_classes := {"write", "external_message", "financial", "access_change"}
allowed_autonomy_levels := {"read_only", "draft_only", "approval_required", "autonomous"}

default allow := false
default requires_approval := false

allow if {
	input.connector_ready == true
	input.autonomy_level in allowed_autonomy_levels
	input.tool.risk_class in {"read", "draft"}
}

allow if {
	input.connector_ready == true
	input.autonomy_level in {"approval_required", "autonomous"}
	input.tool.risk_class in write_risk_classes
	input.approval.status == "approved"
}

requires_approval if {
	input.tool.risk_class in write_risk_classes
}

reason_codes contains "connector_not_ready" if {
	not input.connector_ready
}

reason_codes contains "approval_required" if {
	requires_approval
	not input.approval.status == "approved"
}

reason_codes contains "unsupported_autonomy_level" if {
	not input.autonomy_level in allowed_autonomy_levels
}

decision := {
	"allow": allow,
	"requires_approval": requires_approval,
	"reason_codes": reason_codes,
}
