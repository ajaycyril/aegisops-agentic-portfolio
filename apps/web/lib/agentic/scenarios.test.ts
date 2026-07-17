import { describe, expect, it } from "vitest";

import { scenarios } from "@/lib/agentic/scenarios";

describe("live scenario registry", () => {
  it("keeps four distinct real-source enterprise workflows", () => {
    expect(scenarios).toHaveLength(4);
    expect(new Set(scenarios.map((scenario) => scenario.id)).size).toBe(4);
    expect(scenarios.every((scenario) => scenario.requiredTools.length > 0)).toBe(true);
  });

  it("uses multi-agent orchestration only where specialist reconciliation is justified", () => {
    const multiAgentScenarios = scenarios.filter(
      (scenario) => scenario.orchestration === "multi_agent",
    );

    expect(multiAgentScenarios.map((scenario) => scenario.id)).toEqual([
      "incident_response",
    ]);
    expect(multiAgentScenarios[0].requiredTools).toEqual([
      "github_status",
      "github_incidents",
    ]);
  });
});
