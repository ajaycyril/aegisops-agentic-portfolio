import { Engine, type RuleProperties } from "json-rules-engine";

import type {
  EventEmitter,
  PublicToolResult,
  RunRequest,
  ScenarioId,
} from "@/lib/agentic/contracts";
import { callPublicMcpTool } from "@/lib/agentic/mcp-tools";
import { scenarioById } from "@/lib/agentic/scenarios";

type Facts = Record<string, string | number | boolean>;

const rulesByScenario: Record<ScenarioId, RuleProperties[]> = {
  incident_response: [
    {
      name: "active-incident-escalation",
      priority: 100,
      conditions: { all: [{ fact: "unresolvedCount", operator: "greaterThan", value: 0 }] },
      event: {
        type: "page-incident-commander",
        params: { outcome: "Escalate because at least one unresolved incident exists." },
      },
    },
    {
      name: "degraded-component-review",
      priority: 90,
      conditions: {
        all: [{ fact: "degradedComponentCount", operator: "greaterThan", value: 0 }],
      },
      event: {
        type: "open-operations-review",
        params: { outcome: "Route degraded components to the operations queue." },
      },
    },
    {
      name: "all-operational",
      priority: 10,
      conditions: {
        all: [
          { fact: "unresolvedCount", operator: "equal", value: 0 },
          { fact: "degradedComponentCount", operator: "equal", value: 0 },
        ],
      },
      event: {
        type: "no-static-alert",
        params: { outcome: "No threshold-based alert is generated." },
      },
    },
  ],
  engineering_triage: [
    {
      name: "high-discussion-issue",
      priority: 80,
      conditions: { all: [{ fact: "comments", operator: "greaterThanInclusive", value: 5 }] },
      event: {
        type: "senior-maintainer-review",
        params: { outcome: "Route issues with five or more comments to senior review." },
      },
    },
    {
      name: "unlabelled-issue",
      priority: 60,
      conditions: { all: [{ fact: "labelCount", operator: "equal", value: 0 }] },
      event: {
        type: "needs-manual-labelling",
        params: { outcome: "Place an unlabelled issue in the manual triage queue." },
      },
    },
    {
      name: "active-repository",
      priority: 20,
      conditions: { all: [{ fact: "archived", operator: "equal", value: false }] },
      event: {
        type: "standard-engineering-queue",
        params: { outcome: "Repository is active; continue standard queue routing." },
      },
    },
  ],
  supplier_risk: [
    {
      name: "entity-not-resolved",
      priority: 100,
      conditions: { all: [{ fact: "matchCount", operator: "equal", value: 0 }] },
      event: {
        type: "block-onboarding",
        params: { outcome: "Block automatic onboarding when no LEI entity is resolved." },
      },
    },
    {
      name: "inactive-registration",
      priority: 90,
      conditions: {
        any: [
          { fact: "entityStatus", operator: "notEqual", value: "ACTIVE" },
          { fact: "registrationStatus", operator: "notEqual", value: "ISSUED" },
        ],
      },
      event: {
        type: "enhanced-due-diligence",
        params: { outcome: "Route inactive entity or registration status to due diligence." },
      },
    },
    {
      name: "resolved-active-entity",
      priority: 20,
      conditions: {
        all: [
          { fact: "matchCount", operator: "greaterThan", value: 0 },
          { fact: "entityStatus", operator: "equal", value: "ACTIVE" },
          { fact: "registrationStatus", operator: "equal", value: "ISSUED" },
        ],
      },
      event: {
        type: "standard-procurement-review",
        params: { outcome: "Entity evidence passes fixed status checks." },
      },
    },
  ],
  finance_evidence: [
    {
      name: "filing-evidence-present",
      priority: 50,
      conditions: { all: [{ fact: "observationCount", operator: "greaterThan", value: 0 }] },
      event: {
        type: "route-finance-review",
        params: { outcome: "Current filing evidence is available for analyst review." },
      },
    },
    {
      name: "stale-filing-review",
      priority: 70,
      conditions: { all: [{ fact: "latestFilingAgeDays", operator: "greaterThan", value: 180 }] },
      event: {
        type: "stale-evidence-warning",
        params: { outcome: "Latest observation was filed more than 180 days ago." },
      },
    },
  ],
};

function toolArguments(tool: string, request: RunRequest): Record<string, unknown> {
  if (tool === "github_issue") {
    return {
      owner: request.input.owner,
      repository: request.input.repository,
      issueNumber: Number(request.input.issueNumber),
    };
  }
  if (tool === "github_repository") {
    return { owner: request.input.owner, repository: request.input.repository };
  }
  if (tool === "gleif_entity") {
    return { legalName: request.input.legalName };
  }
  if (tool === "sec_company_facts") {
    return { cik: request.input.cik, metric: request.input.metric };
  }
  return {};
}

function numberField(result: PublicToolResult, field: string) {
  const value = result.data[field];
  return typeof value === "number" ? value : 0;
}

function stringField(result: PublicToolResult, field: string) {
  const value = result.data[field];
  return typeof value === "string" ? value : "";
}

function factsFromResults(results: PublicToolResult[]): Facts {
  const byTool = Object.fromEntries(results.map((result) => [result.tool, result]));
  const status = byTool.github_status;
  const incidents = byTool.github_incidents;
  const issue = byTool.github_issue;
  const repository = byTool.github_repository;
  const gleif = byTool.gleif_entity;
  const sec = byTool.sec_company_facts;
  const matches = Array.isArray(gleif?.data.matches) ? gleif.data.matches : [];
  const firstMatch =
    matches.length > 0 && typeof matches[0] === "object" && matches[0] !== null
      ? (matches[0] as Record<string, unknown>)
      : {};
  const observations = Array.isArray(sec?.data.observations) ? sec.data.observations : [];
  const latestObservation =
    observations.length > 0 && typeof observations[0] === "object" && observations[0] !== null
      ? (observations[0] as Record<string, unknown>)
      : {};
  const filed = typeof latestObservation.filed === "string" ? latestObservation.filed : null;

  return {
    degradedComponentCount: status ? numberField(status, "degradedComponentCount") : 0,
    unresolvedCount: incidents ? numberField(incidents, "unresolvedCount") : 0,
    comments: issue ? numberField(issue, "comments") : 0,
    labelCount: issue && Array.isArray(issue.data.labels) ? issue.data.labels.length : 0,
    archived: repository?.data.archived === true,
    matchCount: gleif ? numberField(gleif, "matchCount") : 0,
    entityStatus: typeof firstMatch.entityStatus === "string" ? firstMatch.entityStatus : "UNRESOLVED",
    registrationStatus:
      typeof firstMatch.registrationStatus === "string"
        ? firstMatch.registrationStatus
        : "UNRESOLVED",
    observationCount: observations.length,
    latestFilingAgeDays: filed
      ? Math.max(0, Math.floor((Date.now() - Date.parse(filed)) / 86_400_000))
      : 99999,
    metric: sec ? stringField(sec, "metric") : "",
  };
}

export async function runRulesLane(request: RunRequest, emit: EventEmitter) {
  const scenario = scenarioById[request.scenarioId];
  const startedAt = performance.now();
  emit({
    lane: "rules",
    type: "node_started",
    nodeId: "rules-fetch",
    label: "Fetch fixed inputs",
    summary: `Calling ${scenario.requiredTools.length} typed MCP source${scenario.requiredTools.length === 1 ? "" : "s"} without model planning.`,
    status: "running",
    actor: "MCP client",
  });

  const results = await Promise.all(
    scenario.requiredTools.map(async (toolName) => {
      const toolStart = performance.now();
      emit({
        lane: "rules",
        type: "tool_started",
        nodeId: `rules-${toolName}`,
        label: toolName,
        summary: "Deterministic lane requested the configured data source.",
        status: "running",
        actor: "MCP SDK v1",
        data: { arguments: toolArguments(toolName, request) },
      });
      const result = await callPublicMcpTool(toolName, toolArguments(toolName, request));
      emit({
        lane: "rules",
        type: "tool_completed",
        nodeId: `rules-${toolName}`,
        label: toolName,
        summary: `Structured evidence returned by ${result.source}.`,
        status: "completed",
        actor: "MCP SDK v1",
        durationMs: Math.round(performance.now() - toolStart),
        data: { sourceUrl: result.sourceUrl, fields: Object.keys(result.data) },
      });
      return result;
    }),
  );

  emit({
    lane: "rules",
    type: "node_completed",
    nodeId: "rules-fetch",
    label: "Inputs normalized",
    summary: "Source responses were validated against Zod contracts and converted to rule facts.",
    status: "completed",
    actor: "Zod",
    data: { sourceCount: results.length },
  });

  const facts = factsFromResults(results);
  const engine = new Engine(rulesByScenario[request.scenarioId]);
  const evaluationStart = performance.now();
  emit({
    lane: "rules",
    type: "node_started",
    nodeId: "rules-evaluate",
    label: "Evaluate deterministic rules",
    summary: `${rulesByScenario[request.scenarioId].length} versioned rules are evaluating the live facts.`,
    status: "running",
    actor: "json-rules-engine 7",
    data: { facts },
  });
  const evaluation = await engine.run(facts);
  const successfulNames = new Set(evaluation.results.map((result) => result.name));

  for (const rule of rulesByScenario[request.scenarioId]) {
    const passed = rule.name ? successfulNames.has(rule.name) : false;
    emit({
      lane: "rules",
      type: "rule_evaluated",
      nodeId: `rule-${rule.name ?? "unnamed"}`,
      label: rule.name ?? "unnamed-rule",
      summary: passed
        ? String(rule.event.params?.outcome ?? rule.event.type)
        : "Condition did not match the current facts.",
      status: passed ? "passed" : "skipped",
      actor: "json-rules-engine 7",
      data: { eventType: rule.event.type, conditions: rule.conditions },
    });
  }

  emit({
    lane: "rules",
    type: "node_completed",
    nodeId: "rules-evaluate",
    label: "Deterministic evaluation complete",
    summary: `${evaluation.events.length} of ${rulesByScenario[request.scenarioId].length} configured outcomes matched the live facts.`,
    status: "completed",
    actor: "json-rules-engine 7",
    durationMs: Math.round(performance.now() - evaluationStart),
    data: { matchedEvents: evaluation.events.map((event) => event.type) },
  });

  emit({
    lane: "rules",
    type: "lane_completed",
    nodeId: "rules-output",
    label: "Fixed workflow complete",
    summary:
      evaluation.events.length > 0
        ? `${evaluation.events.length} predefined outcome${evaluation.events.length === 1 ? "" : "s"} matched. The lane cannot investigate beyond its configured facts.`
        : "No predefined outcome matched. The lane stops without adapting its plan.",
    status: "completed",
    actor: "json-rules-engine 7",
    durationMs: Math.round(performance.now() - startedAt),
    data: {
      matchedEvents: evaluation.events.map((event) => event.type),
      evaluationMs: Math.round(performance.now() - evaluationStart),
    },
  });

  return { results, facts, matchedEvents: evaluation.events };
}
