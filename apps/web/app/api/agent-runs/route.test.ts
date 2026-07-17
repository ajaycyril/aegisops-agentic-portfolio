import { describe, expect, it } from "vitest";

import { POST } from "@/app/api/agent-runs/route";

function request(body: string, headers?: HeadersInit) {
  return new Request("http://localhost/api/agent-runs", {
    method: "POST",
    body,
    headers: {
      "content-type": "application/json",
      "x-forwarded-for": crypto.randomUUID(),
      ...headers,
    },
  });
}

describe("public agent-run boundary", () => {
  it("rejects malformed JSON", async () => {
    const response = await POST(request("{"));
    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toMatchObject({ reason_code: "invalid_json" });
  });

  it("rejects oversized request bodies before execution", async () => {
    const response = await POST(request("{}", { "content-length": "24001" }));
    expect(response.status).toBe(413);
    await expect(response.json()).resolves.toMatchObject({ reason_code: "request_too_large" });
  });

  it("rejects a model outside the public allowlist", async () => {
    const response = await POST(
      request(JSON.stringify({
        scenarioId: "incident_response",
        controls: {
          maxToolCalls: 4,
          maxCostUsd: 0.05,
          requireApproval: true,
          model: "openai/unbounded-model",
        },
      })),
    );
    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toMatchObject({ reason_code: "invalid_run_contract" });
  });

  it("rejects attempts to disable side-effect approval", async () => {
    const response = await POST(
      request(JSON.stringify({
        scenarioId: "incident_response",
        controls: {
          maxToolCalls: 4,
          maxCostUsd: 0.05,
          requireApproval: false,
          model: "openai/gpt-4.1-mini",
        },
      })),
    );
    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toMatchObject({ reason_code: "invalid_run_contract" });
  });
});
