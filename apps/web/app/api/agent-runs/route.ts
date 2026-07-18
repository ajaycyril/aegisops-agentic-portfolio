import {
  createUIMessageStream,
  createUIMessageStreamResponse,
  type UIMessageStreamWriter,
} from "ai";
import { NextResponse } from "next/server";

import {
  runRequestSchema,
  type AegisUIMessage,
  type EventEmitter,
  type RunEvent,
} from "@/lib/agentic/contracts";
import { runRulesLane } from "@/lib/agentic/rules";
import { runAgenticLane } from "@/lib/agentic/runtime";
import { scenarioById } from "@/lib/agentic/scenarios";

export const runtime = "nodejs";
export const maxDuration = 60;

const RATE_WINDOW_MS = 15 * 60 * 1000;
const RATE_LIMIT = 6;
const MAX_REQUEST_BYTES = 24_000;
const MAX_CONCURRENT_RUNS = 2;
const requestWindows = new Map<string, { count: number; resetAt: number }>();
let activeRuns = 0;

function requestIdentity(request: Request) {
  return (
    request.headers.get("x-vercel-forwarded-for")?.split(",")[0]?.trim() ??
    request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ??
    "local"
  );
}

function consumeRateLimit(identity: string) {
  const now = Date.now();
  const current = requestWindows.get(identity);
  if (!current || current.resetAt <= now) {
    requestWindows.set(identity, { count: 1, resetAt: now + RATE_WINDOW_MS });
    return {
      allowed: true,
      remaining: RATE_LIMIT - 1,
      resetAt: now + RATE_WINDOW_MS,
    };
  }
  if (current.count >= RATE_LIMIT) {
    return { allowed: false, remaining: 0, resetAt: current.resetAt };
  }
  current.count += 1;
  return {
    allowed: true,
    remaining: RATE_LIMIT - current.count,
    resetAt: current.resetAt,
  };
}

function errorMessage(reason: unknown) {
  return reason instanceof Error
    ? reason.message.slice(0, 400)
    : "Unknown runtime error";
}

async function readBoundedJson(request: Request) {
  const declaredLength = Number(request.headers.get("content-length") ?? 0);
  if (Number.isFinite(declaredLength) && declaredLength > MAX_REQUEST_BYTES) {
    return { ok: false as const, status: 413, reason: "request_too_large" };
  }

  const body = await request.text();
  if (new TextEncoder().encode(body).byteLength > MAX_REQUEST_BYTES) {
    return { ok: false as const, status: 413, reason: "request_too_large" };
  }

  try {
    return { ok: true as const, value: JSON.parse(body) as unknown };
  } catch {
    return { ok: false as const, status: 400, reason: "invalid_json" };
  }
}

export async function POST(request: Request) {
  const rate = consumeRateLimit(requestIdentity(request));
  if (!rate.allowed) {
    return NextResponse.json(
      {
        status: "blocked",
        reason_code: "public_demo_rate_limit",
        detail:
          "This public browser session has reached its live-run limit. Try again after the window resets.",
      },
      {
        status: 429,
        headers: {
          "Retry-After": String(Math.ceil((rate.resetAt - Date.now()) / 1000)),
        },
      },
    );
  }

  const body = await readBoundedJson(request);
  if (!body.ok) {
    return NextResponse.json(
      {
        status: "blocked",
        reason_code: body.reason,
        detail:
          body.reason === "request_too_large"
            ? "The live-run request exceeds the public payload limit."
            : "The live-run request body is not valid JSON.",
      },
      { status: body.status },
    );
  }

  const parsed = runRequestSchema.safeParse(body.value);
  if (!parsed.success) {
    return NextResponse.json(
      {
        status: "blocked",
        reason_code: "invalid_run_contract",
        detail: "The live-run request failed its typed input contract.",
        issues: parsed.error.issues,
      },
      { status: 400 },
    );
  }

  const runRequest = parsed.data;
  if (activeRuns >= MAX_CONCURRENT_RUNS) {
    return NextResponse.json(
      {
        status: "blocked",
        reason_code: "public_demo_capacity",
        detail:
          "The bounded public runtime is at capacity. Retry after an active run completes.",
      },
      { status: 429, headers: { "Retry-After": "15" } },
    );
  }

  const runId = crypto.randomUUID();
  const traceId = crypto.randomUUID().replaceAll("-", "");
  const scenario = scenarioById[runRequest.scenarioId];
  let sequence = 0;
  activeRuns += 1;

  const stream = createUIMessageStream<AegisUIMessage>({
    execute: async ({ writer }) => {
      try {
        const emit: EventEmitter = (event) => {
          const runEvent: RunEvent = {
            ...event,
            id: crypto.randomUUID(),
            runId,
            traceId,
            sequence: sequence++,
            timestamp: new Date().toISOString(),
          };
          writer.write({ type: "data-run-event", data: runEvent });
        };

        emit({
          lane: "system",
          type: "run_started",
          nodeId: "run-start",
          label: scenario.name,
          summary:
            "Agentic and deterministic decision lanes started concurrently against the same live public sources.",
          status: "running",
          actor: "AegisOps runtime",
          data: {
            scenarioId: scenario.id,
            orchestration: "LangGraph 1",
            streaming: "AI SDK 6 UIMessage stream",
            policy: "OPA/Rego WASM",
            ruleEngine: "json-rules-engine 7",
            toolBoundary: "MCP TypeScript SDK v1",
          },
        });

        const [agenticResult, rulesResult] = await Promise.allSettled([
          runAgenticLane(
            runRequest,
            runId,
            writer as UIMessageStreamWriter<AegisUIMessage>,
            emit,
          ),
          runRulesLane(runRequest, emit),
        ]);

        if (agenticResult.status === "rejected") {
          emit({
            lane: "agentic",
            type: "error",
            nodeId: "agent-error",
            label: "Agentic lane failed",
            summary: errorMessage(agenticResult.reason),
            status: "failed",
            actor: "LangGraph runtime",
          });
        }
        if (rulesResult.status === "rejected") {
          emit({
            lane: "rules",
            type: "error",
            nodeId: "rules-error",
            label: "Rules lane failed",
            summary: errorMessage(rulesResult.reason),
            status: "failed",
            actor: "json-rules-engine runtime",
          });
        }

        const completed =
          agenticResult.status === "fulfilled" &&
          rulesResult.status === "fulfilled";
        emit({
          lane: "system",
          type: "run_completed",
          nodeId: "run-complete",
          label: completed
            ? "Parallel comparison complete"
            : "Run completed with errors",
          summary: completed
            ? "Both lanes completed against the same live-source scenario."
            : "At least one lane failed; inspect the event and policy lenses for the exact runtime reason.",
          status: completed ? "completed" : "failed",
          actor: "AegisOps runtime",
          data: {
            agentic: agenticResult.status,
            rules: rulesResult.status,
            eventCount: sequence,
          },
        });
      } finally {
        activeRuns = Math.max(0, activeRuns - 1);
      }
    },
    onError: (error) => `Live runtime error: ${errorMessage(error)}`,
  });

  return createUIMessageStreamResponse({
    stream,
    headers: {
      "Cache-Control": "no-store",
      "X-AegisOps-Run-Id": runId,
      "X-AegisOps-Trace-Id": traceId,
      "X-RateLimit-Limit": String(RATE_LIMIT),
      "X-RateLimit-Remaining": String(rate.remaining),
    },
  });
}
