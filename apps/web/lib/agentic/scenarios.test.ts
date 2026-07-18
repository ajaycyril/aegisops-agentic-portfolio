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
      "incident_response",
      "hassantuk_villa_response",
    ]);
    expect(multiAgentScenarios[0].requiredTools).toEqual([
      "github_status",
      "github_incidents",
      "enterprise_policy_search",
    ]);
    expect(multiAgentScenarios[1].requiredTools).toEqual([
      "hassantuk_home_protocol",
      "open_meteo_villa_conditions",
      "enterprise_policy_search",
    ]);
  });

  it("places Hassantuk third and requires governed policy retrieval", () => {
    expect(scenarios[2].id).toBe("hassantuk_villa_response");
    expect(
      scenarios.every((scenario) =>
        scenario.requiredTools.includes("enterprise_policy_search"),
      ),
    ).toBe(true);
  });
});
