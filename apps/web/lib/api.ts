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

const workflowRunStatusSchema = z.enum([
  "queued",
  "running",
  "waiting_for_approval",
  "completed",
  "failed",
  "canceled",
]);

const jsonObjectSchema = z.record(z.string(), z.unknown());

const workflowRunTraceSchema = z.object({
  run: z.object({
    id: z.string(),
    workflow_id: z.string(),
    status: workflowRunStatusSchema,
    execution_mode: z.enum(["replay", "live"]),
    autonomy_level: z.enum([
      "read_only",
      "draft_only",
      "approval_required",
      "autonomous",
    ]),
    org_id: z.string().nullable(),
    user_id: z.string().nullable(),
    started_at: z.string(),
    updated_at: z.string(),
    completed_at: z.string().nullable(),
    failure_reason: z.string().nullable(),
  }),
  approvals: z.array(
    z.object({
      id: z.string(),
      status: z.string(),
      risk_class: z.string(),
      requested_action: z.string(),
      requested_by: z.string(),
      approver_id: z.string().nullable(),
      policy_decision_id: z.string().nullable(),
      requested_at: z.string(),
      decided_at: z.string().nullable(),
      expires_at: z.string().nullable(),
    }),
  ),
  tool_calls: z.array(
    z.object({
      id: z.string(),
      approval_id: z.string().nullable(),
      tool_name: z.string(),
      risk_class: z.string(),
      status: z.string(),
      policy_decision_id: z.string().nullable(),
      trace_id: z.string().nullable(),
      output_hash: z.string().nullable(),
      latency_ms: z.number().int().nullable(),
      started_at: z.string(),
      completed_at: z.string().nullable(),
      error_message: z.string().nullable(),
      execution_state: z.string().nullable(),
    }),
  ),
  model_calls: z.array(
    z.object({
      id: z.string(),
      provider: z.string(),
      model: z.string(),
      purpose: z.string(),
      prompt_version: z.string(),
      input_token_count: z.number().int(),
      output_token_count: z.number().int(),
      estimated_cost_usd: z.string(),
      latency_ms: z.number().int().nullable(),
      trace_id: z.string().nullable(),
      status: z.string(),
      started_at: z.string(),
      completed_at: z.string().nullable(),
      error_message: z.string().nullable(),
    }),
  ),
  evidence_records: z.array(
    z.object({
      id: z.string(),
      kind: z.string(),
      source_system: z.string(),
      source_uri: z.string().nullable(),
      title: z.string(),
      content_hash: z.string(),
      metadata: jsonObjectSchema,
      captured_at: z.string(),
      created_at: z.string(),
    }),
  ),
  audit_events: z.array(
    z.object({
      id: z.string(),
      event_type: z.string(),
      actor_type: z.string(),
      actor_id: z.string().nullable(),
      action: z.string(),
      resource_type: z.string().nullable(),
      resource_id: z.string().nullable(),
      policy_decision_id: z.string().nullable(),
      trace_id: z.string().nullable(),
      data_sensitivity: z.string(),
      payload: jsonObjectSchema,
      created_at: z.string(),
    }),
  ),
});

export type WorkflowRunTrace = z.infer<typeof workflowRunTraceSchema>;

export type WorkflowRunTraceStatus =
  | {
      label: "not_configured";
      configuredRunId: null;
      message: string;
    }
  | {
      label: "unreachable";
      configuredRunId: string;
      message: string;
    }
  | {
      label: "not_found";
      configuredRunId: string;
      message: string;
    }
  | {
      label: "loaded";
      configuredRunId: string;
      message: string;
      trace: WorkflowRunTrace;
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

export async function getDemoWorkflowRunTrace(): Promise<WorkflowRunTraceStatus> {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
  const configuredRunId =
    process.env.DEMO_WORKFLOW_RUN_ID ??
    process.env.DEMO_TRACE_RUN_ID ??
    process.env.NEXT_PUBLIC_DEMO_WORKFLOW_RUN_ID ??
    null;

  if (!configuredRunId) {
    return {
      label: "not_configured",
      configuredRunId: null,
      message:
        "Set DEMO_WORKFLOW_RUN_ID to a real stored run id to render live trace outcomes.",
    };
  }

  if (!baseUrl) {
    return {
      label: "unreachable",
      configuredRunId,
      message:
        "NEXT_PUBLIC_API_BASE_URL is required before a configured run trace can be fetched.",
    };
  }

  const normalizedBaseUrl = baseUrl.replace(/\/$/, "");

  try {
    const response = await fetch(
      `${normalizedBaseUrl}/workflow-runs/${encodeURIComponent(configuredRunId)}/trace`,
      {
        cache: "no-store",
        headers: {
          accept: "application/json",
        },
      },
    );

    if (response.status === 404) {
      return {
        label: "not_found",
        configuredRunId,
        message: "The configured run id was not found by the workflow API.",
      };
    }

    if (!response.ok) {
      return {
        label: "unreachable",
        configuredRunId,
        message: `Workflow trace endpoint returned HTTP ${response.status}.`,
      };
    }

    return {
      label: "loaded",
      configuredRunId,
      message: "Workflow trace endpoint returned live metadata.",
      trace: workflowRunTraceSchema.parse(await response.json()),
    };
  } catch {
    return {
      label: "unreachable",
      configuredRunId,
      message: "Workflow trace endpoint could not be reached.",
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
