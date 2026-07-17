import type { LucideIcon } from "lucide-react";
import { Activity, Building2, GitPullRequest, ReceiptText } from "lucide-react";

import type { ScenarioId } from "@/lib/agentic/contracts";

export type ScenarioDefinition = {
  id: ScenarioId;
  name: string;
  shortName: string;
  domain: string;
  description: string;
  sourceLabel: string;
  icon: LucideIcon;
  accent: "teal" | "blue" | "amber" | "red";
  orchestration: "multi_agent" | "single_agent";
  agentPattern: string;
  agentNodes: string[];
  ruleNodes: string[];
  requiredTools: string[];
  defaultInput: Record<string, string>;
  inputFields: Array<{
    key: string;
    label: string;
    placeholder: string;
  }>;
  prompt: (input: Record<string, string>) => string;
};

export const scenarios: ScenarioDefinition[] = [
  {
    id: "incident_response",
    name: "Production Incident Investigator",
    shortName: "Incident",
    domain: "SRE / incident response",
    description:
      "Investigate the live GitHub platform status, reconcile component health and active incidents, then produce an evidence-grounded operational brief.",
    sourceLabel: "GitHub Status API",
    icon: Activity,
    accent: "teal",
    orchestration: "multi_agent",
    agentPattern: "Supervisor + parallel evidence specialists",
    agentNodes: ["guardrail", "status-specialist", "incident-specialist", "supervisor", "policy", "evaluate"],
    ruleNodes: ["fetch-status", "normalize-facts", "evaluate-rules", "route-alert"],
    requiredTools: ["github_status", "github_incidents"],
    defaultInput: { scope: "github-platform", timeWindow: "current" },
    inputFields: [
      { key: "scope", label: "Service scope", placeholder: "github-platform" },
      { key: "timeWindow", label: "Time window", placeholder: "current" },
    ],
    prompt: (input) =>
      `Investigate the current operational state for ${input.scope ?? "github-platform"}. Use both status tools, reconcile component state and unresolved incidents, cite every source, and distinguish observed evidence from inference. The requested time window is ${input.timeWindow ?? "current"}.`,
  },
  {
    id: "engineering_triage",
    name: "Engineering Issue Triage Agent",
    shortName: "Engineering",
    domain: "Software engineering",
    description:
      "Read a real open-source issue and repository metadata, assess impact and ambiguity, and draft a grounded implementation triage without making writes.",
    sourceLabel: "GitHub REST API",
    icon: GitPullRequest,
    accent: "blue",
    orchestration: "single_agent",
    agentPattern: "Plan-and-execute + evaluator",
    agentNodes: ["guardrail", "plan", "issue-tool", "repo-tool", "assess", "policy", "evaluate"],
    ruleNodes: ["fetch-issue", "normalize-facts", "evaluate-rules", "assign-queue"],
    requiredTools: ["github_issue", "github_repository"],
    defaultInput: { owner: "langchain-ai", repository: "langgraphjs", issueNumber: "2570" },
    inputFields: [
      { key: "owner", label: "GitHub owner", placeholder: "langchain-ai" },
      { key: "repository", label: "Repository", placeholder: "langgraphjs" },
      { key: "issueNumber", label: "Issue number", placeholder: "2570" },
    ],
    prompt: (input) =>
      `Triage GitHub issue ${input.owner}/${input.repository}#${input.issueNumber}. Read the issue and repository metadata through tools. Identify evidence, affected surface, missing context, a safe investigation plan, and whether human approval is needed before any write action.`,
  },
  {
    id: "supplier_risk",
    name: "Supplier Entity Risk Agent",
    shortName: "Supplier",
    domain: "Supply chain / procurement",
    description:
      "Resolve a real legal entity against GLEIF, inspect registration evidence, and produce an explainable onboarding or renewal risk brief.",
    sourceLabel: "GLEIF LEI API",
    icon: Building2,
    accent: "red",
    orchestration: "single_agent",
    agentPattern: "Research agent + policy gate",
    agentNodes: ["guardrail", "plan", "gleif-tool", "entity-resolution", "risk-review", "policy", "evaluate"],
    ruleNodes: ["fetch-entity", "normalize-facts", "evaluate-rules", "route-review"],
    requiredTools: ["gleif_entity"],
    defaultInput: { legalName: "Microsoft Corporation" },
    inputFields: [
      { key: "legalName", label: "Legal entity name", placeholder: "Microsoft Corporation" },
    ],
    prompt: (input) =>
      `Assess legal-entity evidence for supplier candidate ${input.legalName}. Resolve the entity with GLEIF, report match confidence using returned structured fields, flag registration or entity-status concerns, cite the source, and require approval for any supplier status change.`,
  },
  {
    id: "finance_evidence",
    name: "Finance Evidence Analyst",
    shortName: "Finance",
    domain: "Finance operations",
    description:
      "Read live SEC company facts for a public company, extract current filing evidence, and explain what a deterministic threshold can and cannot conclude.",
    sourceLabel: "SEC EDGAR Data API",
    icon: ReceiptText,
    accent: "amber",
    orchestration: "single_agent",
    agentPattern: "Evidence analyst + grounded evaluator",
    agentNodes: ["guardrail", "plan", "sec-tool", "evidence-analysis", "materiality-review", "policy", "evaluate"],
    ruleNodes: ["fetch-facts", "normalize-facts", "evaluate-rules", "route-review"],
    requiredTools: ["sec_company_facts"],
    defaultInput: { cik: "0000789019", metric: "AccountsPayableCurrent" },
    inputFields: [
      { key: "cik", label: "SEC CIK", placeholder: "0000789019" },
      { key: "metric", label: "US-GAAP metric", placeholder: "AccountsPayableCurrent" },
    ],
    prompt: (input) =>
      `Analyze live SEC company facts for CIK ${input.cik}, focusing on ${input.metric}. Use the SEC tool, cite the filing evidence returned, explain the latest reported value and period, avoid unsupported accounting conclusions, and require approval before any financial action.`,
  },
];

export const scenarioById = Object.fromEntries(
  scenarios.map((scenario) => [scenario.id, scenario]),
) as Record<ScenarioId, ScenarioDefinition>;
