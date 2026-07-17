import { describe, expect, it } from "vitest";

import { runEventSchema, runRequestSchema } from "@/lib/agentic/contracts";

describe("agent run contracts", () => {
  it("applies bounded public-demo defaults", () => {
    const request = runRequestSchema.parse({
      scenarioId: "incident_response",
      input: { scope: "github-platform" },
    });

    expect(request.controls).toEqual({
      maxToolCalls: 4,
      maxCostUsd: 0.05,
      requireApproval: true,
      model: "openai/gpt-4.1-mini",
    });
  });

  it("rejects a tool budget outside the public envelope", () => {
    const result = runRequestSchema.safeParse({
      scenarioId: "incident_response",
      input: {},
      controls: {
        maxToolCalls: 9,
        maxCostUsd: 0.05,
        requireApproval: true,
        model: "openai/gpt-4.1-mini",
      },
    });

    expect(result.success).toBe(false);
  });

  it("accepts specialist handoff trace events", () => {
    const event = runEventSchema.parse({
      id: "event-1",
      runId: "run-1",
      sequence: 3,
      timestamp: "2026-07-17T00:00:00.000Z",
      lane: "agentic",
      type: "agent_handoff",
      nodeId: "agent-supervisor",
      label: "Specialist handoff",
      summary: "Two specialist reports reached the supervisor.",
      status: "running",
      actor: "LangGraph fan-in",
    });

    expect(event.type).toBe("agent_handoff");
  });
});
