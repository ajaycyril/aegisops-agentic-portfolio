import { describe, expect, it } from "vitest";

import { callPublicMcpTool } from "@/lib/agentic/mcp-tools";
import { policyCorpus, searchPolicyCorpus } from "@/lib/agentic/policy-corpus";
import { scenarios } from "@/lib/agentic/scenarios";

describe("governed policy corpus", () => {
  it("stores authoritative, versioned policy evidence for every scenario", () => {
    for (const scenario of scenarios) {
      const chunks = policyCorpus.filter(
        (chunk) => chunk.scenarioId === scenario.id,
      );
      expect(chunks.length).toBeGreaterThanOrEqual(2);
      expect(chunks.every((chunk) => new URL(chunk.sourceUrl))).toBe(true);
      expect(chunks.every((chunk) => chunk.version.length > 0)).toBe(true);
    }
  });

  it("ranks policy chunks inside the requested workflow boundary", () => {
    const results = searchPolicyCorpus(
      "finance_evidence",
      "qualitative materiality threshold",
      2,
    );

    expect(results).toHaveLength(2);
    expect(
      results.every((result) => result.scenarioId === "finance_evidence"),
    ).toBe(true);
    expect(results[0].contentHash).toMatch(/^[a-f0-9]{64}$/);
  });

  it("exposes retrieval through the typed MCP contract", async () => {
    const result = await callPublicMcpTool("enterprise_policy_search", {
      scenarioId: "supplier_risk",
      query: "supplier due diligence risk prioritization",
      limit: 2,
    });

    expect(result.tool).toBe("enterprise_policy_search");
    expect(result.data.resultCount).toBe(2);
    expect(result.data.retrievalMode).toContain("MiniSearch");
  });
});
