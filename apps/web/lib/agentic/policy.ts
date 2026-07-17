import { readFile } from "node:fs/promises";
import path from "node:path";

import { loadPolicy, type LoadedPolicy } from "@open-policy-agent/opa-wasm";
import { z } from "zod";

const policyDecisionSchema = z.object({
  allow: z.boolean(),
  require_approval: z.boolean(),
  reason: z.string(),
  controls: z.array(z.string()),
});

export type PolicyDecision = z.infer<typeof policyDecisionSchema>;

let policyPromise: Promise<LoadedPolicy> | undefined;

async function getPolicy() {
  policyPromise ??= readFile(
    path.join(process.cwd(), "lib/agentic/policies/public-demo.wasm"),
  ).then((wasm) => loadPolicy(wasm));
  return policyPromise;
}

export async function evaluatePublicDemoPolicy(input: {
  action: "read" | "write" | "external_message";
  max_tool_calls: number;
  max_cost_usd: number;
  tools: string[];
}): Promise<PolicyDecision> {
  const policy = await getPolicy();
  const result = z
    .array(z.object({ result: policyDecisionSchema }))
    .min(1)
    .parse(policy.evaluate(input));
  return result[0].result;
}
