import type { UIMessage } from "ai";
import { z } from "zod";

export const scenarioIdSchema = z.enum([
  "hassantuk_villa_response",
  "incident_response",
  "engineering_triage",
  "supplier_risk",
  "finance_evidence",
]);

export type ScenarioId = z.infer<typeof scenarioIdSchema>;

export const publicModelSchema = z.enum([
  "openai/gpt-4.1-mini",
  "openai/gpt-4o-mini",
]);

export const runRequestSchema = z.object({
  messages: z.array(z.unknown()).max(20).default([]),
  scenarioId: scenarioIdSchema,
  input: z.record(z.string(), z.string().max(500)).default({}),
  controls: z
    .object({
      maxToolCalls: z.number().int().min(1).max(8).default(4),
      maxCostUsd: z.number().positive().max(0.25).default(0.05),
      requireApproval: z.literal(true).default(true),
      model: publicModelSchema.default("openai/gpt-4.1-mini"),
    })
    .default({
      maxToolCalls: 4,
      maxCostUsd: 0.05,
      requireApproval: true,
      model: "openai/gpt-4.1-mini",
    }),
});

export type RunRequest = z.infer<typeof runRequestSchema>;

export const runLaneSchema = z.enum(["system", "agentic", "rules", "policy"]);
export type RunLane = z.infer<typeof runLaneSchema>;

export const eventStatusSchema = z.enum([
  "queued",
  "running",
  "passed",
  "completed",
  "blocked",
  "failed",
  "skipped",
]);

export const evidenceSchema = z.object({
  id: z.string(),
  title: z.string(),
  source: z.string(),
  sourceUrl: z.string().url(),
  capturedAt: z.string(),
  fields: z.record(z.string(), z.unknown()),
});

export type Evidence = z.infer<typeof evidenceSchema>;

export const runEventSchema = z.object({
  id: z.string(),
  runId: z.string(),
  sequence: z.number().int().nonnegative(),
  timestamp: z.string(),
  lane: runLaneSchema,
  type: z.enum([
    "run_started",
    "node_started",
    "node_completed",
    "tool_started",
    "tool_completed",
    "evidence_captured",
    "guardrail_decision",
    "policy_decision",
    "rule_evaluated",
    "model_step",
    "agent_handoff",
    "lane_completed",
    "run_completed",
    "error",
  ]),
  nodeId: z.string(),
  label: z.string(),
  summary: z.string(),
  status: eventStatusSchema,
  actor: z.string(),
  durationMs: z.number().nonnegative().optional(),
  traceId: z.string().optional(),
  data: z.record(z.string(), z.unknown()).optional(),
  evidence: evidenceSchema.optional(),
});

export type RunEvent = z.infer<typeof runEventSchema>;

export type AegisUIMessage = UIMessage<
  { runId?: string },
  { "run-event": RunEvent }
>;

export type EventEmitter = (
  event: Omit<RunEvent, "id" | "sequence" | "timestamp" | "runId">,
) => void;

export const publicToolResultSchema = z.object({
  tool: z.string(),
  source: z.string(),
  sourceUrl: z.string().url(),
  capturedAt: z.string(),
  data: z.record(z.string(), z.unknown()),
});

export type PublicToolResult = z.infer<typeof publicToolResultSchema>;
