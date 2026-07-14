package aegisops.data_sensitivity

import rego.v1

restricted_classes := {"restricted", "secret"}
allowed_memory_retention := {"ephemeral", "run", "short_term", "long_term"}

default allow := false
default requires_approval := false

external_blocked if {
	input.destination == "external"
	input.data_sensitivity in restricted_classes
}

memory_retention_valid if {
	input.operation != "memory_write"
}

memory_retention_valid if {
	input.operation == "memory_write"
	input.retention_class in allowed_memory_retention
}

allow if {
	not external_blocked
	memory_retention_valid
}

requires_approval if {
	external_blocked
}

reason_codes contains "restricted_external_output" if {
	external_blocked
}

reason_codes contains "invalid_memory_retention" if {
	not memory_retention_valid
}

decision := {
	"allow": allow,
	"requires_approval": requires_approval,
	"reason_codes": reason_codes,
}
