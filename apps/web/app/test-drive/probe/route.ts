import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

type ProbeEndpoint = {
  id: string;
  label: string;
  path: string;
};

type ProbeResult = ProbeEndpoint & {
  ok: boolean;
  status: number | null;
  latency_ms: number | null;
  count: number | null;
  summary: string;
  error: string | null;
};

const probeEndpoints: ProbeEndpoint[] = [
  { id: "health", label: "Health", path: "/health" },
  { id: "ready", label: "Readiness", path: "/ready" },
  { id: "workflows", label: "Workflows", path: "/workflows" },
  { id: "connectors", label: "Connectors", path: "/connectors" },
  { id: "tools", label: "Tools", path: "/tools" },
];

export async function GET(request: NextRequest) {
  const baseUrl = getRegistryApiBaseUrl(request);
  const endpointResults = await Promise.all(
    probeEndpoints.map((endpoint) => probeEndpoint(baseUrl, endpoint)),
  );
  const readiness = endpointResults.find((endpoint) => endpoint.id === "ready");
  const workflows = endpointResults.find((endpoint) => endpoint.id === "workflows");
  const connectors = endpointResults.find((endpoint) => endpoint.id === "connectors");
  const tools = endpointResults.find((endpoint) => endpoint.id === "tools");
  const allRegistryChecksPassed = endpointResults.every((endpoint) => endpoint.ok);

  return NextResponse.json(
    {
      checked_at: new Date().toISOString(),
      base_url: baseUrl,
      endpoints: endpointResults,
      gates: [
        {
          id: "public_registry",
          label: "Public registry",
          state: allRegistryChecksPassed ? "open" : "closed",
          detail: allRegistryChecksPassed
            ? "Read-only registry endpoints are reachable."
            : "One or more read-only registry endpoints failed.",
        },
        {
          id: "runtime_writes",
          label: "Live writes",
          state: "closed",
          detail:
            "Branch, PR, customer message, rollback, paging, and account-change writes are not exposed by the public API.",
        },
        {
          id: "trace_demo",
          label: "Captured trace",
          state: "neutral",
          detail:
            "A real captured run can be attached through DEMO_TRACE_RUN_ID after live connector verification.",
        },
      ],
      counts: {
        workflows: extractCount(workflows),
        connectors: extractCount(connectors),
        tools: extractCount(tools),
      },
      readiness: readiness?.summary ?? "readiness unavailable",
      next_steps: [
        "Inspect workflow and tool contracts in the live portal.",
        "Configure real sandbox connectors only in the guarded full API runtime.",
        "Capture a real replay trace before enabling a public run demo.",
      ],
    },
    {
      headers: {
        "Cache-Control": "no-store",
      },
    },
  );
}

async function probeEndpoint(
  baseUrl: string,
  endpoint: ProbeEndpoint,
): Promise<ProbeResult> {
  const startedAt = performance.now();

  try {
    const response = await fetch(`${baseUrl}${endpoint.path}`, {
      cache: "no-store",
      headers: {
        accept: "application/json",
      },
    });
    const latencyMs = Math.round(performance.now() - startedAt);
    const payload: unknown = await response.json();
    const summary = summarizePayload(endpoint.id, payload);

    return {
      ...endpoint,
      ok: response.ok,
      status: response.status,
      latency_ms: latencyMs,
      count: summary.count,
      summary: summary.value,
      error: null,
    };
  } catch (error) {
    return {
      ...endpoint,
      ok: false,
      status: null,
      latency_ms: null,
      count: null,
      summary: "unavailable",
      error: error instanceof Error ? error.message : "unknown probe failure",
    };
  }
}

function getRegistryApiBaseUrl(request: NextRequest) {
  const configuredBaseUrl =
    process.env.API_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? null;

  if (configuredBaseUrl) {
    return configuredBaseUrl.endsWith("/")
      ? configuredBaseUrl.slice(0, -1)
      : configuredBaseUrl;
  }

  return `${request.nextUrl.origin}/api`;
}

function summarizePayload(endpointId: string, payload: unknown) {
  if (Array.isArray(payload)) {
    return {
      count: payload.length,
      value: `${payload.length} ${endpointId}`,
    };
  }

  if (!isObject(payload)) {
    return {
      count: null,
      value: "unexpected response",
    };
  }

  if (endpointId === "ready" && isObject(payload.registry_counts)) {
    const counts = payload.registry_counts;
    return {
      count: null,
      value: [
        `workflows=${readNumber(counts.workflows)}`,
        `connectors=${readNumber(counts.connectors)}`,
        `tools=${readNumber(counts.tools)}`,
      ].join(" / "),
    };
  }

  if (typeof payload.status === "string") {
    return {
      count: null,
      value: payload.status,
    };
  }

  return {
    count: null,
    value: "ok",
  };
}

function extractCount(result: ProbeResult | undefined) {
  return result?.ok ? (result.count ?? 0) : 0;
}

function readNumber(value: unknown) {
  return typeof value === "number" ? value : 0;
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
