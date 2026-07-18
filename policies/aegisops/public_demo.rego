package aegisops.public_demo

import rego.v1

approved_tools := {
  "github_status",
  "github_incidents",
  "github_issue",
  "github_repository",
  "gleif_entity",
  "sec_company_facts",
  "hassantuk_home_protocol",
  "open_meteo_villa_conditions",
  "enterprise_policy_search",
}

default decision := {
  "allow": false,
  "require_approval": true,
  "reason": "request does not satisfy the public demo policy",
  "controls": ["deny_by_default"],
}

decision := {
  "allow": true,
  "require_approval": false,
  "reason": "read-only tools, bounded tool count, and bounded spend are permitted",
  "controls": [
    "approved_tool_allowlist",
    "read_only_execution",
    "max_tool_calls",
    "max_cost_usd",
  ],
} if {
  input.action == "read"
  input.max_tool_calls <= 8
  input.max_cost_usd <= 0.25
  every tool in input.tools {
    tool in approved_tools
  }
}

decision := {
  "allow": false,
  "require_approval": true,
  "reason": "write and external side-effect actions require a human approval record",
  "controls": ["human_approval", "audit_record"],
} if {
  input.action != "read"
}
