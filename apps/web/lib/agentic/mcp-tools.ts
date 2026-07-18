import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { load } from "cheerio";
import { z } from "zod";

import {
  publicToolResultSchema,
  scenarioIdSchema,
  type PublicToolResult,
} from "@/lib/agentic/contracts";
import { searchPolicyCorpus } from "@/lib/agentic/policy-corpus";

const githubStatusSchema = z.object({
  status: z.object({ indicator: z.string(), description: z.string() }),
  components: z.array(
    z.object({
      id: z.string(),
      name: z.string(),
      status: z.string(),
      updated_at: z.string(),
    }),
  ),
});

const githubIncidentsSchema = z.object({
  incidents: z.array(
    z.object({
      id: z.string(),
      name: z.string(),
      status: z.string(),
      impact: z.string(),
      shortlink: z.string(),
      updated_at: z.string(),
    }),
  ),
});

const githubIssueSchema = z.object({
  number: z.number().int(),
  title: z.string(),
  state: z.string(),
  html_url: z.string().url(),
  body: z.string().nullable(),
  comments: z.number().int(),
  labels: z.array(z.object({ name: z.string() })),
  user: z.object({ login: z.string() }),
  created_at: z.string(),
  updated_at: z.string(),
});

const githubRepositorySchema = z.object({
  full_name: z.string(),
  html_url: z.string().url(),
  description: z.string().nullable(),
  default_branch: z.string(),
  language: z.string().nullable(),
  stargazers_count: z.number().int(),
  open_issues_count: z.number().int(),
  archived: z.boolean(),
  updated_at: z.string(),
});

const gleifSchema = z.object({
  data: z.array(
    z.object({
      id: z.string(),
      attributes: z.object({
        lei: z.string(),
        entity: z.object({
          legalName: z.object({ name: z.string() }),
          status: z.string(),
          legalAddress: z.object({
            city: z.string().optional(),
            country: z.string().optional(),
          }),
        }),
        registration: z.object({
          status: z.string(),
          lastUpdateDate: z.string(),
          nextRenewalDate: z.string().optional(),
        }),
      }),
    }),
  ),
});

const secCompanyFactsSchema = z.object({
  cik: z.number(),
  entityName: z.string(),
  facts: z.record(
    z.string(),
    z.record(
      z.string(),
      z.object({
        label: z.string().nullable(),
        description: z.string().nullable(),
        units: z.record(
          z.string(),
          z.array(
            z.object({
              val: z.number(),
              accn: z.string(),
              fy: z.number().nullable().optional(),
              fp: z.string().nullable().optional(),
              form: z.string(),
              filed: z.string(),
              frame: z.string().nullable().optional(),
              start: z.string().nullable().optional(),
              end: z.string().nullable().optional(),
            }),
          ),
        ),
      }),
    ),
  ),
});

const openMeteoCurrentSchema = z.object({
  latitude: z.number(),
  longitude: z.number(),
  timezone: z.string(),
  current: z.object({
    time: z.string(),
    temperature_2m: z.number(),
    relative_humidity_2m: z.number(),
    precipitation: z.number(),
    weather_code: z.number(),
    wind_speed_10m: z.number(),
    wind_direction_10m: z.number(),
    wind_gusts_10m: z.number(),
  }),
  current_units: z.record(z.string(), z.string()),
});

const capturedAt = () => new Date().toISOString();

async function fetchJson(url: string, schema: z.ZodType) {
  const response = await fetch(url, {
    headers: {
      Accept: "application/json",
      "User-Agent": "AegisOps Agentic Portfolio contact@aegisops.dev",
    },
    signal: AbortSignal.timeout(12_000),
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Public source returned HTTP ${response.status}`);
  }

  return schema.parse(await response.json());
}

async function fetchHtml(url: string) {
  const response = await fetch(url, {
    headers: {
      Accept: "text/html",
      "User-Agent": "AegisOps Agentic Portfolio contact@aegisops.dev",
    },
    signal: AbortSignal.timeout(12_000),
    cache: "no-store",
  });
  if (!response.ok)
    throw new Error(`Public source returned HTTP ${response.status}`);
  return response.text();
}

function asToolResponse(result: PublicToolResult) {
  return {
    content: [{ type: "text" as const, text: JSON.stringify(result) }],
    structuredContent: result,
  };
}

async function buildMcpClient() {
  const server = new McpServer(
    { name: "aegisops-public-evidence", version: "1.0.0" },
    { capabilities: { tools: {} } },
  );

  server.registerTool(
    "enterprise_policy_search",
    {
      title: "Governed enterprise policy retrieval",
      description:
        "Retrieve ranked, versioned policy chunks from the authoritative corpus approved for a workflow.",
      inputSchema: z.object({
        scenarioId: scenarioIdSchema,
        query: z.string().min(3).max(500),
        limit: z.number().int().min(1).max(5).default(3),
      }),
      annotations: { readOnlyHint: true, openWorldHint: false },
    },
    async ({ scenarioId, query, limit }) => {
      const chunks = searchPolicyCorpus(scenarioId, query, limit);
      return asToolResponse({
        tool: "enterprise_policy_search",
        source: "AegisOps governed policy corpus",
        sourceUrl: chunks[0].sourceUrl,
        capturedAt: capturedAt(),
        data: {
          retrievalMode:
            "MiniSearch lexical fallback; pgvector production target",
          scenarioId,
          query,
          resultCount: chunks.length,
          chunks,
        },
      });
    },
  );

  server.registerTool(
    "hassantuk_home_protocol",
    {
      title: "Official Hassantuk operating protocol",
      description:
        "Read the current public Ministry of Interior Hassantuk operating protocol.",
      inputSchema: z.object({}),
      annotations: { readOnlyHint: true, openWorldHint: true },
    },
    async () => {
      const sourceUrl = "https://building.moi.gov.ae/en-US/faqs/";
      const $ = load(await fetchHtml(sourceUrl));
      const pageText = $("main").text().trim() || $("body").text().trim();
      const headings = $("h1, h2, h3, h4, h5")
        .map((_, element) => $(element).text().trim())
        .get()
        .filter(Boolean)
        .slice(0, 24);
      return asToolResponse({
        tool: "hassantuk_home_protocol",
        source: "UAE Ministry of Interior - Hassantuk",
        sourceUrl,
        capturedAt: capturedAt(),
        data: {
          pageTitle: $("title").text().trim(),
          headings,
          publishedProtocolExcerpt: pageText.slice(0, 8_000),
          homesProgramUrl: "https://home.moi.gov.ae/en/index.html",
        },
      });
    },
  );

  server.registerTool(
    "open_meteo_villa_conditions",
    {
      title: "Current villa-area weather conditions",
      description:
        "Read current weather at operator-supplied UAE coordinates from Open-Meteo.",
      inputSchema: z.object({
        latitude: z.number().min(22).max(27),
        longitude: z.number().min(51).max(57),
      }),
      annotations: { readOnlyHint: true, openWorldHint: true },
    },
    async ({ latitude, longitude }) => {
      const url = new URL("https://api.open-meteo.com/v1/forecast");
      url.searchParams.set("latitude", String(latitude));
      url.searchParams.set("longitude", String(longitude));
      url.searchParams.set(
        "current",
        "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m,wind_direction_10m,wind_gusts_10m",
      );
      url.searchParams.set("timezone", "Asia/Dubai");
      const payload = openMeteoCurrentSchema.parse(
        await fetchJson(url.toString(), openMeteoCurrentSchema),
      );
      return asToolResponse({
        tool: "open_meteo_villa_conditions",
        source: "Open-Meteo Forecast API",
        sourceUrl: url.toString(),
        capturedAt: capturedAt(),
        data: {
          latitude: payload.latitude,
          longitude: payload.longitude,
          timezone: payload.timezone,
          observedAt: payload.current.time,
          temperatureC: payload.current.temperature_2m,
          relativeHumidityPct: payload.current.relative_humidity_2m,
          precipitationMm: payload.current.precipitation,
          weatherCode: payload.current.weather_code,
          windSpeedKmh: payload.current.wind_speed_10m,
          windDirectionDegrees: payload.current.wind_direction_10m,
          windGustsKmh: payload.current.wind_gusts_10m,
        },
      });
    },
  );

  server.registerTool(
    "github_status",
    {
      title: "GitHub platform status",
      description:
        "Read current component status from the official GitHub Status API.",
      inputSchema: z.object({}),
      annotations: { readOnlyHint: true, openWorldHint: true },
    },
    async () => {
      const sourceUrl = "https://www.githubstatus.com/api/v2/summary.json";
      const payload = githubStatusSchema.parse(
        await fetchJson(sourceUrl, githubStatusSchema),
      );
      const degradedComponents = payload.components
        .filter((component) => component.status !== "operational")
        .map((component) => ({
          name: component.name,
          status: component.status,
        }));

      return asToolResponse({
        tool: "github_status",
        source: "GitHub Status API",
        sourceUrl,
        capturedAt: capturedAt(),
        data: {
          indicator: payload.status.indicator,
          description: payload.status.description,
          componentCount: payload.components.length,
          degradedComponentCount: degradedComponents.length,
          degradedComponents,
        },
      });
    },
  );

  server.registerTool(
    "github_incidents",
    {
      title: "GitHub unresolved incidents",
      description:
        "Read unresolved incidents from the official GitHub Status API.",
      inputSchema: z.object({}),
      annotations: { readOnlyHint: true, openWorldHint: true },
    },
    async () => {
      const sourceUrl =
        "https://www.githubstatus.com/api/v2/incidents/unresolved.json";
      const payload = githubIncidentsSchema.parse(
        await fetchJson(sourceUrl, githubIncidentsSchema),
      );
      return asToolResponse({
        tool: "github_incidents",
        source: "GitHub Status API",
        sourceUrl,
        capturedAt: capturedAt(),
        data: {
          unresolvedCount: payload.incidents.length,
          incidents: payload.incidents,
        },
      });
    },
  );

  const githubEntityInput = z.object({
    owner: z.string().min(1).max(100),
    repository: z.string().min(1).max(100),
  });

  server.registerTool(
    "github_issue",
    {
      title: "GitHub issue evidence",
      description: "Read one public GitHub issue from the official REST API.",
      inputSchema: githubEntityInput.extend({
        issueNumber: z.number().int().positive(),
      }),
      annotations: { readOnlyHint: true, openWorldHint: true },
    },
    async ({ owner, repository, issueNumber }) => {
      const sourceUrl = `https://api.github.com/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repository)}/issues/${issueNumber}`;
      const issue = githubIssueSchema.parse(
        await fetchJson(sourceUrl, githubIssueSchema),
      );
      return asToolResponse({
        tool: "github_issue",
        source: "GitHub REST API",
        sourceUrl: issue.html_url,
        capturedAt: capturedAt(),
        data: {
          number: issue.number,
          title: issue.title,
          state: issue.state,
          author: issue.user.login,
          body: issue.body?.slice(0, 6_000) ?? null,
          comments: issue.comments,
          labels: issue.labels.map((label) => label.name),
          createdAt: issue.created_at,
          updatedAt: issue.updated_at,
        },
      });
    },
  );

  server.registerTool(
    "github_repository",
    {
      title: "GitHub repository evidence",
      description:
        "Read public repository metadata from the official GitHub REST API.",
      inputSchema: githubEntityInput,
      annotations: { readOnlyHint: true, openWorldHint: true },
    },
    async ({ owner, repository }) => {
      const sourceUrl = `https://api.github.com/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repository)}`;
      const repo = githubRepositorySchema.parse(
        await fetchJson(sourceUrl, githubRepositorySchema),
      );
      return asToolResponse({
        tool: "github_repository",
        source: "GitHub REST API",
        sourceUrl: repo.html_url,
        capturedAt: capturedAt(),
        data: {
          fullName: repo.full_name,
          description: repo.description,
          defaultBranch: repo.default_branch,
          language: repo.language,
          stars: repo.stargazers_count,
          openIssues: repo.open_issues_count,
          archived: repo.archived,
          updatedAt: repo.updated_at,
        },
      });
    },
  );

  server.registerTool(
    "gleif_entity",
    {
      title: "GLEIF legal-entity search",
      description: "Resolve a legal entity through the official GLEIF LEI API.",
      inputSchema: z.object({ legalName: z.string().min(2).max(200) }),
      annotations: { readOnlyHint: true, openWorldHint: true },
    },
    async ({ legalName }) => {
      const url = new URL("https://api.gleif.org/api/v1/lei-records");
      url.searchParams.set("filter[entity.legalName]", legalName);
      url.searchParams.set("page[size]", "5");
      const payload = gleifSchema.parse(
        await fetchJson(url.toString(), gleifSchema),
      );
      const matches = payload.data.map(({ attributes }) => ({
        lei: attributes.lei,
        legalName: attributes.entity.legalName.name,
        entityStatus: attributes.entity.status,
        registrationStatus: attributes.registration.status,
        city: attributes.entity.legalAddress.city ?? null,
        country: attributes.entity.legalAddress.country ?? null,
        lastUpdated: attributes.registration.lastUpdateDate,
        nextRenewal: attributes.registration.nextRenewalDate ?? null,
      }));
      return asToolResponse({
        tool: "gleif_entity",
        source: "GLEIF LEI API",
        sourceUrl: url.toString(),
        capturedAt: capturedAt(),
        data: { query: legalName, matchCount: matches.length, matches },
      });
    },
  );

  server.registerTool(
    "sec_company_facts",
    {
      title: "SEC company facts",
      description:
        "Read one US-GAAP metric from the official SEC EDGAR Data API.",
      inputSchema: z.object({
        cik: z.string().min(1).max(10),
        metric: z.string().min(1).max(100),
      }),
      annotations: { readOnlyHint: true, openWorldHint: true },
    },
    async ({ cik, metric }) => {
      const normalizedCik = cik.padStart(10, "0");
      const sourceUrl = `https://data.sec.gov/api/xbrl/companyfacts/CIK${encodeURIComponent(normalizedCik)}.json`;
      const payload = secCompanyFactsSchema.parse(
        await fetchJson(sourceUrl, secCompanyFactsSchema),
      );
      const fact = payload.facts["us-gaap"]?.[metric];
      if (!fact) {
        throw new Error(`US-GAAP metric ${metric} is not present for this CIK`);
      }
      const [unit, observations] = Object.entries(fact.units)[0] ?? [];
      if (!unit || !observations) {
        throw new Error(
          `US-GAAP metric ${metric} has no reported observations`,
        );
      }
      const latest = [...observations]
        .sort((left, right) => Date.parse(right.filed) - Date.parse(left.filed))
        .slice(0, 5);
      return asToolResponse({
        tool: "sec_company_facts",
        source: "SEC EDGAR Data API",
        sourceUrl,
        capturedAt: capturedAt(),
        data: {
          cik: normalizedCik,
          entityName: payload.entityName,
          metric,
          label: fact.label,
          description: fact.description,
          unit,
          observations: latest,
        },
      });
    },
  );

  const client = new Client({ name: "aegisops-runtime", version: "1.0.0" });
  const [clientTransport, serverTransport] =
    InMemoryTransport.createLinkedPair();
  await Promise.all([
    server.connect(serverTransport),
    client.connect(clientTransport),
  ]);
  return client;
}

let mcpClientPromise: ReturnType<typeof buildMcpClient> | undefined;

export async function callPublicMcpTool(
  name: string,
  args: Record<string, unknown>,
): Promise<PublicToolResult> {
  mcpClientPromise ??= buildMcpClient();
  const client = await mcpClientPromise;
  const result = await client.callTool({ name, arguments: args });
  if (result.isError || !result.structuredContent) {
    const content = Array.isArray(result.content) ? result.content : [];
    const detail = content
      .filter(
        (item): item is { type: "text"; text: string } =>
          typeof item === "object" &&
          item !== null &&
          "type" in item &&
          item.type === "text" &&
          "text" in item &&
          typeof item.text === "string",
      )
      .map((item) => item.text)
      .join(" ");
    throw new Error(
      detail || `MCP tool ${name} returned no structured content`,
    );
  }
  return publicToolResultSchema.parse(result.structuredContent);
}
