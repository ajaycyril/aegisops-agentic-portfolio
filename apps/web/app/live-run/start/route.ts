import { NextResponse, type NextRequest } from "next/server";
import { z } from "zod";

const requestSchema = z.object({
  api_base_url: z.string().url(),
  payload: z.record(z.string(), z.unknown()),
});

export async function POST(request: NextRequest) {
  const parsed = requestSchema.safeParse(await request.json().catch(() => null));

  if (!parsed.success) {
    return NextResponse.json(
      {
        error: "invalid_live_run_request",
        detail: parsed.error.flatten(),
      },
      { status: 400 },
    );
  }

  const baseUrl = stripTrailingSlash(parsed.data.api_base_url);

  try {
    const response = await fetch(`${baseUrl}/workflow-runs`, {
      method: "POST",
      headers: {
        accept: "application/json",
        "content-type": "application/json",
      },
      body: JSON.stringify(parsed.data.payload),
    });
    const contentType = response.headers.get("content-type") ?? "";
    const body = contentType.includes("application/json")
      ? await response.json()
      : await response.text();

    return NextResponse.json(
      {
        upstream_status: response.status,
        upstream_ok: response.ok,
        body,
      },
      { status: 200 },
    );
  } catch (error) {
    return NextResponse.json(
      {
        error: "live_run_upstream_unreachable",
        detail: error instanceof Error ? error.message : "Unknown upstream error.",
      },
      { status: 502 },
    );
  }
}

function stripTrailingSlash(value: string) {
  return value.endsWith("/") ? value.slice(0, -1) : value;
}
