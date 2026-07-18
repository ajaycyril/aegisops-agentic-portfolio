import { describe, expect, it } from "vitest";

import { scenarios } from "@/lib/agentic/scenarios";

describe("live scenario registry", () => {
  it("keeps five distinct real-source enterprise workflows", () => {
    expect(scenarios).toHaveLength(5);
    expect(new Set(scenarios.map((scenario) => scenario.id)).size).toBe(5);
    expect(
      scenarios.every((scenario) => scenario.requiredTools.length > 0),
    ).toBe(true);
  });

  it("uses multi-agent orchestration only where specialist reconciliation is justified", () => {
    const multiAgentScenarios = scenarios.filter(
      (scenario) => scenario.orchestration === "multi_agent",
    );

    expect(multiAgentScenarios.map((scenario) => scenario.id)).toEqual([
      "hassantuk_villa_response",
      "incident_response",
    ]);
    expect(multiAgentScenarios[0].requiredTools).toEqual([
      "hassantuk_home_protocol",
      "open_meteo_villa_conditions",
    ]);
    expect(multiAgentScenarios[1].requiredTools).toEqual([
      "github_status",
      "github_incidents",
    ]);
  });
});
