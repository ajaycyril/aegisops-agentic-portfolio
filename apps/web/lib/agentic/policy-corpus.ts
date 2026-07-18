import { createHash } from "node:crypto";

import MiniSearch from "minisearch";

import type { ScenarioId } from "@/lib/agentic/contracts";

export type PolicyChunk = {
  id: string;
  scenarioId: ScenarioId;
  documentId: string;
  authority: string;
  title: string;
  sourceUrl: string;
  version: string;
  effectiveDate: string;
  capturedAt: string;
  topics: string[];
  text: string;
};

const capturedAt = "2026-07-18T00:00:00.000Z";

export const policyCorpus: PolicyChunk[] = [
  {
    id: "nist-ir-lifecycle",
    scenarioId: "incident_response",
    documentId: "nist-sp-800-61r2",
    authority: "NIST",
    title: "Computer Security Incident Handling Guide",
    sourceUrl:
      "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-61r2.pdf",
    version: "SP 800-61 Rev. 2",
    effectiveDate: "2012-08-06",
    capturedAt,
    topics: ["incident", "analysis", "containment", "recovery", "evidence"],
    text: "Incident response should follow preparation, detection and analysis, containment, eradication and recovery, and post-incident activity. Evidence collection and incident prioritization should be repeatable and documented.",
  },
  {
    id: "nist-ir-communication",
    scenarioId: "incident_response",
    documentId: "nist-csf-respond",
    authority: "NIST",
    title: "Cybersecurity Framework - Respond",
    sourceUrl: "https://www.nist.gov/cyberframework/respond",
    version: "CSF Respond guidance",
    effectiveDate: "2025-02-03",
    capturedAt,
    topics: ["coordination", "communication", "analysis", "mitigation"],
    text: "Response activities should be coordinated with internal and external stakeholders. Analysis supports effective response and recovery, while mitigation limits expansion and resolves the incident.",
  },
  {
    id: "nist-ssdf-practices",
    scenarioId: "engineering_triage",
    documentId: "nist-sp-800-218",
    authority: "NIST",
    title: "Secure Software Development Framework",
    sourceUrl: "https://csrc.nist.gov/projects/ssdf",
    version: "SSDF 1.1 / SP 800-218",
    effectiveDate: "2022-02-03",
    capturedAt,
    topics: ["software", "triage", "secure development", "vulnerability"],
    text: "Secure development practices are grouped into preparing the organization, protecting software, producing well-secured software, and responding to vulnerabilities. Practices should align with mission needs and risk tolerance.",
  },
  {
    id: "nist-ssdf-response",
    scenarioId: "engineering_triage",
    documentId: "nist-sp-800-218",
    authority: "NIST",
    title: "SSDF Respond to Vulnerabilities",
    sourceUrl: "https://csrc.nist.gov/projects/ssdf",
    version: "SSDF 1.1 / SP 800-218",
    effectiveDate: "2022-02-03",
    capturedAt,
    topics: ["issue", "root cause", "remediation", "prevention"],
    text: "Organizations should identify residual vulnerabilities, respond appropriately, and prevent similar vulnerabilities from recurring. Triage should preserve evidence and connect remediation to a defined secure-development outcome.",
  },
  {
    id: "uae-home-response",
    scenarioId: "hassantuk_villa_response",
    documentId: "moi-hassantuk-homes",
    authority: "UAE Ministry of Interior",
    title: "Hassantuk for Homes operating process",
    sourceUrl: "https://home.moi.gov.ae/en/index.html",
    version: "Public service page",
    effectiveDate: "2026-07-15",
    capturedAt,
    topics: ["smoke", "heat", "verification", "resident call", "dispatch"],
    text: "Connected smoke and heat alarms notify the command centre. The command centre contacts the customer to verify an alert, and verified alerts are sent to Civil Defence with location and incident details.",
  },
  {
    id: "uae-home-obligations",
    scenarioId: "hassantuk_villa_response",
    documentId: "uae-cabinet-resolution-90-2020",
    authority: "UAE Legislation",
    title: "Requirements for Fire Detectors in Residential Homes",
    sourceUrl: "https://uaelegislation.gov.ae/en/legislations/1484",
    version: "Cabinet Resolution No. 90 of 2020",
    effectiveDate: "2021-01-03",
    capturedAt,
    topics: ["residential", "fire detector", "maintenance", "civil defence"],
    text: "Residential owners must use approved installation and maintenance establishments, participate in the Civil Defence electronic protection system, keep resident data current, and cooperate with operations-room calls.",
  },
  {
    id: "oecd-rbc-risk",
    scenarioId: "supplier_risk",
    documentId: "oecd-rbc-due-diligence",
    authority: "OECD",
    title: "Due Diligence for Responsible Business Conduct",
    sourceUrl:
      "https://www.oecd.org/en/topics/sub-issues/due-diligence-guidance-for-responsible-business-conduct.html",
    version: "OECD RBC guidance",
    effectiveDate: "2023-06-08",
    capturedAt,
    topics: ["supplier", "due diligence", "risk", "business relationship"],
    text: "Risk-based due diligence should identify and address actual and potential adverse impacts in operations, supply chains, and business relationships. The operating context determines how risks are identified and addressed.",
  },
  {
    id: "oecd-rbc-priority",
    scenarioId: "supplier_risk",
    documentId: "oecd-rbc-due-diligence",
    authority: "OECD",
    title: "Risk prioritization in supply-chain due diligence",
    sourceUrl:
      "https://www.oecd.org/en/topics/sub-issues/due-diligence-guidance-for-responsible-business-conduct.html",
    version: "OECD RBC guidance",
    effectiveDate: "2023-06-08",
    capturedAt,
    topics: ["prioritization", "monitoring", "stakeholder", "mitigation"],
    text: "Enterprises should prioritize their most significant impacts, engage business partners and stakeholders, track mitigation, and revisit decisions as supply-chain circumstances change.",
  },
  {
    id: "sec-sab99-materiality",
    scenarioId: "finance_evidence",
    documentId: "sec-sab-99",
    authority: "US Securities and Exchange Commission",
    title: "Staff Accounting Bulletin No. 99 - Materiality",
    sourceUrl: "https://www.sec.gov/interps/account/sab99.htm",
    version: "SAB 99",
    effectiveDate: "1999-08-12",
    capturedAt,
    topics: ["materiality", "qualitative", "quantitative", "misstatement"],
    text: "Materiality cannot be decided exclusively through a numerical threshold. Both quantitative magnitude and surrounding qualitative circumstances should be considered before reaching a financial-reporting conclusion.",
  },
  {
    id: "sec-sab108-errors",
    scenarioId: "finance_evidence",
    documentId: "sec-sab-108",
    authority: "US Securities and Exchange Commission",
    title: "Staff Accounting Bulletin No. 108",
    sourceUrl:
      "https://www.sec.gov/rules-regulations/staff-guidance/staff-accounting-bulletins/staff-accounting-bulletin-no-108",
    version: "SAB 108",
    effectiveDate: "2006-09-13",
    capturedAt,
    topics: ["misstatement", "prior year", "rollover", "iron curtain"],
    text: "Materiality analysis should consider current-period effects and accumulated balance-sheet effects of prior-year misstatements. Evidence should be reviewed under both relevant quantification perspectives.",
  },
];

const index = new MiniSearch<PolicyChunk>({
  fields: ["title", "authority", "topics", "text"],
  storeFields: [
    "scenarioId",
    "documentId",
    "authority",
    "title",
    "sourceUrl",
    "version",
    "effectiveDate",
    "capturedAt",
    "topics",
    "text",
  ],
  searchOptions: {
    boost: { title: 3, topics: 2 },
    fuzzy: 0.2,
    prefix: true,
  },
});

index.addAll(policyCorpus);

export function searchPolicyCorpus(
  scenarioId: ScenarioId,
  query: string,
  limit = 3,
) {
  const ranked = index.search(query, {
    filter: (result) => result.scenarioId === scenarioId,
  });
  const selected = (
    ranked.length > 0
      ? ranked
      : policyCorpus.filter((chunk) => chunk.scenarioId === scenarioId)
  ).slice(0, limit);

  return selected.map((result) => {
    const chunk = result as unknown as PolicyChunk;
    return {
      ...chunk,
      contentHash: createHash("sha256").update(chunk.text).digest("hex"),
    };
  });
}
