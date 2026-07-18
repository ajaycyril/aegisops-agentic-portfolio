import type { LucideIcon } from "lucide-react";
import {
  Activity,
  Building2,
  Flame,
  GitPullRequest,
  ReceiptText,
} from "lucide-react";

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
  businessOutcome: string;
  enterpriseSystems: string;
  agenticAdvantage: string;
  ruleBoundary: string;
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
    id: "hassantuk_villa_response",
    name: "Hassantuk Villa Fire Response Copilot",
    shortName: "Villa fire",
    domain: "UAE physical AI / public safety",
    description:
      "Assess an operator-supplied villa alarm envelope against the live official Hassantuk operating protocol and current local conditions, then prepare an approval-held response recommendation.",
    sourceLabel: "UAE MoI Hassantuk + Open-Meteo",
    icon: Flame,
    accent: "red",
    orchestration: "multi_agent",
    agentPattern:
      "Parallel protocol and conditions specialists + response supervisor",
    businessOutcome:
      "Faster, evidence-grounded villa alarm verification and response preparation",
    enterpriseSystems:
      "Hassantuk alarm panel · ARC · ICCC/I999 · Civil Defence dispatch · weather context",
    agenticAdvantage:
      "The copilot can reconcile the alarm envelope, current official protocol, local conditions, missing evidence, and safety constraints into a case-specific response plan while holding dispatch for authorized human verification.",
    ruleBoundary:
      "A mature decision engine can execute the known MoI verification and escalation protocol exactly; it cannot seek unmodeled context, interpret conflicting multi-sensor evidence, or create a new response plan for an unfamiliar villa state.",
    agentNodes: [
      "guardrail",
      "protocol-specialist",
      "conditions-specialist",
      "response-supervisor",
      "dispatch-policy",
      "evaluate",
    ],
    ruleNodes: [
      "validate-envelope",
      "fetch-protocol",
      "derive-risk-facts",
      "evaluate-response-table",
      "approval-route",
    ],
    requiredTools: ["hassantuk_home_protocol", "open_meteo_villa_conditions"],
    defaultInput: {
      alarmType: "smoke and heat",
      sensorCount: "2",
      detectorZone: "ground-floor kitchen",
      occupantsStatus: "telephone verification pending",
      latitude: "24.4539",
      longitude: "54.3773",
    },
    inputFields: [
      {
        key: "alarmType",
        label: "Operator alarm",
        placeholder: "smoke and heat",
      },
      { key: "sensorCount", label: "Triggered sensors", placeholder: "2" },
      {
        key: "detectorZone",
        label: "Detector zone",
        placeholder: "ground-floor kitchen",
      },
      {
        key: "occupantsStatus",
        label: "Verification state",
        placeholder: "telephone verification pending",
      },
      { key: "latitude", label: "Area latitude", placeholder: "24.4539" },
      { key: "longitude", label: "Area longitude", placeholder: "54.3773" },
    ],
    prompt: (input) =>
      `Act as a read-only UAE villa fire response team for an operator-supplied ${input.alarmType} alarm in ${input.detectorZone}. Occupant verification is ${input.occupantsStatus}. Reconcile the current official Hassantuk operating protocol with current conditions at ${input.latitude}, ${input.longitude}. Clearly label operator-supplied claims versus live external observations and inference. Identify missing sensor or visual evidence, propose the safest next verification and response actions, and state whether authenticated drone or thermal overwatch would add useful situational awareness. Hold any drone launch, Civil Defence, or physical dispatch action behind authorized human approval. Never claim access to Hassantuk sensors, ARC, ICCC/I999, drone control, or dispatch systems.`,
  },
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
    businessOutcome: "Faster, evidence-backed incident command",
    enterpriseSystems: "Datadog · PagerDuty · deployment telemetry · GitHub",
    agenticAdvantage:
      "Parallel specialists reconcile independent evidence and adapt the operational brief to what they observe.",
    ruleBoundary:
      "Thresholds route known severity states; they cannot investigate conflicting or novel evidence combinations.",
    agentNodes: [
      "guardrail",
      "status-specialist",
      "incident-specialist",
      "supervisor",
      "policy",
      "evaluate",
    ],
    ruleNodes: [
      "fetch-status",
      "normalize-facts",
      "evaluate-rules",
      "route-alert",
    ],
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
    businessOutcome:
      "Higher-quality triage before engineering time is committed",
    enterpriseSystems: "GitHub Enterprise · Jira · CI/CD · code search",
    agenticAdvantage:
      "The agent selects evidence, resolves issue ambiguity, and changes its investigation path as repository context arrives.",
    ruleBoundary:
      "Rules can label by state, age, or comment count; they cannot determine an evidence-grounded implementation path.",
    agentNodes: [
      "guardrail",
      "plan",
      "issue-tool",
      "repo-tool",
      "assess",
      "policy",
      "evaluate",
    ],
    ruleNodes: [
      "fetch-issue",
      "normalize-facts",
      "evaluate-rules",
      "assign-queue",
    ],
    requiredTools: ["github_issue", "github_repository"],
    defaultInput: {
      owner: "langchain-ai",
      repository: "langgraphjs",
      issueNumber: "2570",
    },
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
    businessOutcome: "Defensible supplier onboarding and renewal decisions",
    enterpriseSystems: "ERP supplier master · GLEIF · sanctions · procurement",
    agenticAdvantage:
      "The agent resolves entity ambiguity, weighs registration evidence, and explains why a candidate needs review.",
    ruleBoundary:
      "Rules can block known status codes; they cannot disambiguate legal entities or reconcile incomplete evidence.",
    agentNodes: [
      "guardrail",
      "plan",
      "gleif-tool",
      "entity-resolution",
      "risk-review",
      "policy",
      "evaluate",
    ],
    ruleNodes: [
      "fetch-entity",
      "normalize-facts",
      "evaluate-rules",
      "route-review",
    ],
    requiredTools: ["gleif_entity"],
    defaultInput: { legalName: "Microsoft Corporation" },
    inputFields: [
      {
        key: "legalName",
        label: "Legal entity name",
        placeholder: "Microsoft Corporation",
      },
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
    businessOutcome: "Faster exception review with an auditable evidence trail",
    enterpriseSystems: "ERP subledger · filings · policy service · approvals",
    agenticAdvantage:
      "The agent finds relevant filing evidence, interprets periods and caveats, and separates facts from judgment.",
    ruleBoundary:
      "Rules can flag dates and thresholds; they cannot produce a grounded materiality narrative from changing evidence.",
    agentNodes: [
      "guardrail",
      "plan",
      "sec-tool",
      "evidence-analysis",
      "materiality-review",
      "policy",
      "evaluate",
    ],
    ruleNodes: [
      "fetch-facts",
      "normalize-facts",
      "evaluate-rules",
      "route-review",
    ],
    requiredTools: ["sec_company_facts"],
    defaultInput: { cik: "0000789019", metric: "AccountsPayableCurrent" },
    inputFields: [
      { key: "cik", label: "SEC CIK", placeholder: "0000789019" },
      {
        key: "metric",
        label: "US-GAAP metric",
        placeholder: "AccountsPayableCurrent",
      },
    ],
    prompt: (input) =>
      `Analyze live SEC company facts for CIK ${input.cik}, focusing on ${input.metric}. Use the SEC tool, cite the filing evidence returned, explain the latest reported value and period, avoid unsupported accounting conclusions, and require approval before any financial action.`,
  },
];

export const scenarioById = Object.fromEntries(
  scenarios.map((scenario) => [scenario.id, scenario]),
) as Record<ScenarioId, ScenarioDefinition>;
