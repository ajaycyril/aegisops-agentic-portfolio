export type WorkflowStatus = "planned" | "ready" | "gated" | "disabled";

export type AutonomyLevel = "read_only" | "draft_only" | "approval_required" | "autonomous";

export type WorkflowDataPolicy = {
  fake_data_allowed: boolean;
  replay_allowed_from_real_runs: boolean;
  regex_business_extraction_allowed: boolean;
};

export type WorkflowDetail = {
  id: string;
  name: string;
  domain: string;
  status: WorkflowStatus;
  enabled: boolean;
  disabled_reason: string | null;
  required_connectors: string[];
  missing_connectors: string[];
  required_scopes: string[];
  default_autonomy: AutonomyLevel;
  patterns: string[];
  data_policy: WorkflowDataPolicy;
  approval_required_for: string[];
  visual_surfaces: string[];
  source_path: string;
};

export type WorkflowCatalog = {
  source: "api" | "repository_mirror";
  live: boolean;
  message: string;
  workflows: WorkflowDetail[];
};

type WorkflowSeed = Omit<
  WorkflowDetail,
  | "enabled"
  | "disabled_reason"
  | "missing_connectors"
  | "data_policy"
  | "source_path"
>;

const repositoryDataPolicy: WorkflowDataPolicy = {
  fake_data_allowed: false,
  replay_allowed_from_real_runs: true,
  regex_business_extraction_allowed: false,
};

const workflowSeeds: WorkflowSeed[] = [
  {
    id: "engineering_issue_to_pr",
    name: "GitHub Issue-to-PR Agent",
    domain: "engineering",
    status: "planned",
    required_connectors: ["github"],
    required_scopes: ["issues:read", "contents:read", "pull_requests:write", "checks:read"],
    default_autonomy: "draft_only",
    patterns: ["plan_execute", "code_agent", "evaluator_optimizer", "human_in_the_loop"],
    approval_required_for: ["branch_creation", "pull_request_creation", "external_comment"],
    visual_surfaces: [
      "executive_summary",
      "graph_view",
      "diff_viewer",
      "test_results",
      "trace_timeline",
      "policy_lens",
    ],
  },
  {
    id: "incident_response_investigator",
    name: "Production Incident Investigator",
    domain: "incident_response",
    status: "planned",
    required_connectors: ["observability", "deployments", "github"],
    required_scopes: ["logs:read", "traces:read", "deployments:read", "checks:read"],
    default_autonomy: "read_only",
    patterns: ["react_tool_use", "parallel_investigation", "supervisor_multi_agent", "rca_generation"],
    approval_required_for: ["rollback", "incident_update", "paging_action"],
    visual_surfaces: [
      "multi_agent_orchestration",
      "incident_timeline",
      "service_map",
      "evidence_board",
      "root_cause_hypotheses",
      "remediation_plan",
    ],
  },
  {
    id: "customer_support_escalation",
    name: "Customer Support Escalation Agent",
    domain: "customer_support",
    status: "ready",
    required_connectors: ["support_system", "knowledge_base", "crm"],
    required_scopes: ["tickets:read", "customers:read", "knowledge:read", "drafts:write"],
    default_autonomy: "draft_only",
    patterns: ["routing", "rag_agent", "supervisor_multi_agent", "human_in_the_loop"],
    approval_required_for: ["customer_message", "refund_request", "account_change"],
    visual_surfaces: [
      "customer_timeline",
      "evidence_board",
      "response_draft",
      "approval_queue",
      "memory_lens",
    ],
  },
  {
    id: "supply_chain_supplier_risk",
    name: "Supplier Risk Agent",
    domain: "supply_chain",
    status: "planned",
    required_connectors: ["supplier_system", "web_research", "sanctions_source"],
    required_scopes: ["suppliers:read", "procurement:read", "research:read"],
    default_autonomy: "read_only",
    patterns: ["web_research_agent", "parallel_investigation", "evaluator_optimizer", "policy_gate"],
    approval_required_for: ["supplier_status_change", "external_notification"],
    visual_surfaces: ["supplier_map", "risk_signals", "source_citations", "mitigation_brief", "policy_lens"],
  },
  {
    id: "finance_invoice_exception",
    name: "Invoice Exception Agent",
    domain: "finance_ops",
    status: "planned",
    required_connectors: ["accounting_system", "document_store", "email"],
    required_scopes: ["invoices:read", "vendors:read", "documents:read", "approvals:write"],
    default_autonomy: "approval_required",
    patterns: ["document_understanding", "policy_gate", "approval_routing", "audit_packet_generation"],
    approval_required_for: ["payment_approval", "vendor_message", "accounting_update"],
    visual_surfaces: ["invoice_viewer", "policy_comparison", "approval_route", "audit_trail"],
  },
  {
    id: "security_vulnerability_remediation",
    name: "Vulnerability Remediation Agent",
    domain: "security",
    status: "planned",
    required_connectors: ["github", "osv"],
    required_scopes: ["contents:read", "dependency_graph:read", "pull_requests:write"],
    default_autonomy: "approval_required",
    patterns: ["router", "risk_triage", "plan_execute", "evaluator_optimizer"],
    approval_required_for: ["dependency_change", "pull_request_creation", "risk_acceptance"],
    visual_surfaces: ["risk_matrix", "dependency_graph", "evidence_board", "remediation_plan", "policy_lens"],
  },
  {
    id: "sales_rfp_agent",
    name: "Account Research and RFP Agent",
    domain: "sales",
    status: "planned",
    required_connectors: ["crm", "document_store", "web_research"],
    required_scopes: ["accounts:read", "opportunities:read", "documents:read", "drafts:write"],
    default_autonomy: "draft_only",
    patterns: ["source_grounded_research", "rag_agent", "evaluator_optimizer", "human_in_the_loop"],
    approval_required_for: ["proposal_export", "customer_message"],
    visual_surfaces: ["account_brief", "citations", "proposal_draft", "scoring_rubric"],
  },
  {
    id: "compliance_audit_evidence",
    name: "Audit Evidence Agent",
    domain: "compliance",
    status: "planned",
    required_connectors: ["github", "document_store", "deployment_platform", "identity_provider"],
    required_scopes: ["controls:read", "documents:read", "deployments:read", "audit_exports:write"],
    default_autonomy: "draft_only",
    patterns: ["evidence_collection", "control_mapping", "policy_gate", "audit_packet_generation"],
    approval_required_for: ["evidence_export", "auditor_message"],
    visual_surfaces: ["control_matrix", "evidence_board", "gap_analysis", "audit_packet"],
  },
  {
    id: "data_bi_executive_analyst",
    name: "Executive Analyst Agent",
    domain: "data_bi",
    status: "planned",
    required_connectors: ["postgres", "observability"],
    required_scopes: ["analytics:read", "traces:read"],
    default_autonomy: "read_only",
    patterns: ["text_to_sql_guarded", "chart_generation", "evaluator_optimizer", "executive_summary"],
    approval_required_for: ["external_export", "saved_report"],
    visual_surfaces: ["metric_tree", "sql_lens", "charts", "insight_cards"],
  },
  {
    id: "hr_it_onboarding",
    name: "Onboarding and Access Agent",
    domain: "hr_it_ops",
    status: "planned",
    required_connectors: ["identity_provider", "ticketing", "document_store"],
    required_scopes: ["users:read", "access_requests:write", "documents:read"],
    default_autonomy: "approval_required",
    patterns: ["checklist_orchestration", "approval_routing", "policy_gate", "memory_workflow"],
    approval_required_for: ["access_grant", "manager_message", "identity_update"],
    visual_surfaces: ["onboarding_map", "access_matrix", "approval_queue", "audit_trail"],
  },
];

export const localWorkflowCatalog: WorkflowDetail[] = workflowSeeds.map((workflow) => ({
  ...workflow,
  enabled: false,
  disabled_reason:
    workflow.status === "ready" ? "required connectors are not configured" : `workflow status is ${workflow.status}`,
  missing_connectors: workflow.required_connectors,
  data_policy: repositoryDataPolicy,
  source_path: `configs/workflows/${workflow.id}.yaml`,
}));
