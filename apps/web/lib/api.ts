import { z } from "zod";

import {
  localWorkflowCatalog,
  type WorkflowCatalog,
  type WorkflowDetail,
} from "@/lib/workflows";

export type ApiHealth = {
  status: string;
  service: string;
};

const apiReadinessSchema = z.object({
  status: z.string(),
  environment: z.string(),
  policy_configured: z.boolean(),
  database_configured: z.boolean(),
  live_runs_require_approval: z.boolean(),
  engineering_issue_to_pr_planner_configured: z.boolean(),
  openai_planner_model: z.string().nullable(),
});

export type ApiReadiness = z.infer<typeof apiReadinessSchema>;

export type ApiStatus =
  | {
      configured: false;
      label: "not_configured";
      message: string;
    }
  | {
      configured: true;
      label: "online";
      message: string;
      health: ApiHealth;
      readiness: ApiReadiness;
    }
  | {
      configured: true;
      label: "unreachable";
      message: string;
    };

export async function getApiStatus(): Promise<ApiStatus> {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

  if (!baseUrl) {
    return {
      configured: false,
      label: "not_configured",
      message: "API URL is not configured for this deployment.",
    };
  }

  try {
    const normalizedBaseUrl = baseUrl.replace(/\/$/, "");
    const response = await fetch(`${normalizedBaseUrl}/health`, {
      cache: "no-store",
      headers: {
        accept: "application/json",
      },
    });

    if (!response.ok) {
      return {
        configured: true,
        label: "unreachable",
        message: `API health check returned HTTP ${response.status}.`,
      };
    }

    const health = (await response.json()) as ApiHealth;
    const readinessResponse = await fetch(`${normalizedBaseUrl}/ready`, {
      cache: "no-store",
      headers: {
        accept: "application/json",
      },
    });

    if (!readinessResponse.ok) {
      return {
        configured: true,
        label: "unreachable",
        message: `API readiness check returned HTTP ${readinessResponse.status}.`,
      };
    }

    const readiness = apiReadinessSchema.parse(await readinessResponse.json());

    return {
      configured: true,
      label: "online",
      message: "API health endpoint is reachable.",
      health,
      readiness,
    };
  } catch {
    return {
      configured: true,
      label: "unreachable",
      message: "API health endpoint could not be reached.",
    };
  }
}

const workflowStatusSchema = z.enum(["planned", "ready", "gated", "disabled"]);
const autonomyLevelSchema = z.enum([
  "read_only",
  "draft_only",
  "approval_required",
  "autonomous",
]);

const workflowSummarySchema = z.object({
  id: z.string(),
  name: z.string(),
  domain: z.string(),
  status: workflowStatusSchema,
  enabled: z.boolean(),
  disabled_reason: z.string().nullable(),
  required_connectors: z.array(z.string()),
  missing_connectors: z.array(z.string()),
  required_scopes: z.array(z.string()),
  default_autonomy: autonomyLevelSchema,
  patterns: z.array(z.string()),
});

const workflowDetailSchema = workflowSummarySchema.extend({
  data_policy: z.object({
    fake_data_allowed: z.boolean(),
    replay_allowed_from_real_runs: z.boolean(),
    regex_business_extraction_allowed: z.boolean(),
  }),
  approval_required_for: z.array(z.string()),
  visual_surfaces: z.array(z.string()),
  source_path: z.string(),
});

const workflowSummaryListSchema = z.array(workflowSummarySchema);

export async function getWorkflowCatalog(): Promise<WorkflowCatalog> {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

  if (!baseUrl) {
    return repositoryMirrorCatalog(
      "API URL is not configured for this deployment.",
    );
  }

  const normalizedBaseUrl = baseUrl.replace(/\/$/, "");

  try {
    const summaryResponse = await fetch(`${normalizedBaseUrl}/workflows`, {
      cache: "no-store",
      headers: {
        accept: "application/json",
      },
    });

    if (!summaryResponse.ok) {
      return repositoryMirrorCatalog(
        `Workflow registry returned HTTP ${summaryResponse.status}.`,
      );
    }

    const summaries = workflowSummaryListSchema.parse(
      await summaryResponse.json(),
    );
    const details = await Promise.all(
      summaries.map(async (workflow) => {
        const detailResponse = await fetch(
          `${normalizedBaseUrl}/workflows/${workflow.id}`,
          {
            cache: "no-store",
            headers: {
              accept: "application/json",
            },
          },
        );

        if (!detailResponse.ok) {
          throw new Error(
            `Workflow detail returned HTTP ${detailResponse.status}.`,
          );
        }

        return workflowDetailSchema.parse(await detailResponse.json());
      }),
    );

    return {
      source: "api",
      live: true,
      message: "Workflow registry API is the active catalog source.",
      workflows: details,
    };
  } catch {
    return repositoryMirrorCatalog(
      "Workflow registry API could not be reached.",
    );
  }
}

function repositoryMirrorCatalog(message: string): WorkflowCatalog {
  return {
    source: "repository_mirror",
    live: false,
    message,
    workflows: localWorkflowCatalog satisfies WorkflowDetail[],
  };
}
