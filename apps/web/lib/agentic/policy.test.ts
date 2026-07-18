import { describe, expect, it } from "vitest";

import { evaluatePublicDemoPolicy } from "@/lib/agentic/policy";

describe("public demo OPA policy", () => {
  it("allows bounded read-only tools", async () => {
    const decision = await evaluatePublicDemoPolicy({
      action: "read",
      max_tool_calls: 4,
      max_cost_usd: 0.05,
      tools: ["github_status", "github_incidents"],
    });

    expect(decision.allow).toBe(true);
    expect(decision.require_approval).toBe(false);
    expect(decision.controls).toContain("approved_tool_allowlist");
  });

  it("allows the Hassantuk public evidence tools", async () => {
    const decision = await evaluatePublicDemoPolicy({
      action: "read",
      max_tool_calls: 4,
      max_cost_usd: 0.05,
      tools: [
        "hassantuk_home_protocol",
        "open_meteo_villa_conditions",
        "enterprise_policy_search",
      ],
    });

    expect(decision.allow).toBe(true);
    expect(decision.controls).toContain("approved_tool_allowlist");
  });

  it("blocks unapproved tools", async () => {
    const decision = await evaluatePublicDemoPolicy({
      action: "read",
      max_tool_calls: 2,
      max_cost_usd: 0.05,
      tools: ["unregistered_write_tool"],
    });

    expect(decision.allow).toBe(false);
    expect(decision.controls).toEqual(["deny_by_default"]);
  });

  it("requires approval for side effects", async () => {
    const decision = await evaluatePublicDemoPolicy({
      action: "write",
      max_tool_calls: 2,
      max_cost_usd: 0.05,
      tools: ["github_issue"],
    });

    expect(decision.allow).toBe(false);
    expect(decision.require_approval).toBe(true);
    expect(decision.controls).toContain("human_approval");
  });

  it("blocks reads above the configured spend ceiling", async () => {
    const decision = await evaluatePublicDemoPolicy({
      action: "read",
      max_tool_calls: 2,
      max_cost_usd: 0.26,
      tools: ["github_status"],
    });

    expect(decision.allow).toBe(false);
  });
});
