package aegisops.approvals

import rego.v1

approval_risk_classes := {"write", "external_message", "financial", "access_change"}
approval_decision_actions := {"approve", "reject"}

default allow := false
default requires_approval := false

decision_action_present if {
	input.decision_action != ""
}

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

allow if {
	input.decision_action == "approve"
	input.approval.status == "pending"
	input.approver_id != ""
	input.approver_id != input.approval.requested_by
	input.risk_class in approval_risk_classes
	input.approval.write_actions_enabled == false
}

allow if {
	input.decision_action == "reject"
	input.approval.status == "pending"
	input.approver_id != ""
	input.approver_id != input.approval.requested_by
}

reason_codes contains "approval_required" if {
	requires_approval
	not input.approval.status == "approved"
	not decision_action_present
}

reason_codes contains "unsupported_decision_action" if {
	decision_action_present
	not input.decision_action in approval_decision_actions
}

reason_codes contains "approval_not_pending" if {
	input.decision_action in approval_decision_actions
	input.approval.status != "pending"
}

reason_codes contains "approver_required" if {
	input.decision_action in approval_decision_actions
	input.approver_id == ""
}

reason_codes contains "self_approval_not_allowed" if {
	input.decision_action in approval_decision_actions
	input.approver_id == input.approval.requested_by
}

reason_codes contains "write_actions_already_enabled" if {
	input.decision_action == "approve"
	input.approval.write_actions_enabled != false
}

decision := {
	"allow": allow,
	"requires_approval": requires_approval,
	"reason_codes": reason_codes,
}
