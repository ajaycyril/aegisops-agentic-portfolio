package aegisops.approvals

import rego.v1

approval_risk_classes := {"write", "external_message", "financial", "access_change"}

default allow := false
default requires_approval := false

requires_approval if {
	input.risk_class in approval_risk_classes
}

requires_approval if {
	input.autonomy_level == "approval_required"
}

allow if {
	not requires_approval
}

allow if {
	requires_approval
	input.approval.status == "approved"
}

reason_codes contains "approval_required" if {
	requires_approval
	not input.approval.status == "approved"
}

decision := {
	"allow": allow,
	"requires_approval": requires_approval,
	"reason_codes": reason_codes,
}
