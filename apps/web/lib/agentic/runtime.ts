import { createOpenAI } from "@ai-sdk/openai";
import { gateway } from "@ai-sdk/gateway";
import { Annotation, END, START, StateGraph } from "@langchain/langgraph";
import {
  ToolLoopAgent,
  stepCountIs,
  tool,
  type UIMessageStreamWriter,
} from "ai";
import { z } from "zod";

import type {
  AegisUIMessage,
  EventEmitter,
  PublicToolResult,
  RunRequest,
} from "@/lib/agentic/contracts";
import { getCheckpointer } from "@/lib/agentic/checkpointer";
import { callPublicMcpTool } from "@/lib/agentic/mcp-tools";
import { evaluatePublicDemoPolicy } from "@/lib/agentic/policy";
import { scenarioById } from "@/lib/agentic/scenarios";

const AgentState = Annotation.Root({
  request: Annotation<RunRequest>(),
  specialistReports: Annotation<SpecialistReport[]>({
    reducer: (current, update) => [...current, ...update],
    default: () => [],
  }),
  finalText: Annotation<string>({
    reducer: (_, next) => next,
    default: () => "",
  }),
  evidenceCount: Annotation<number>({
    reducer: (_, next) => next,
    default: () => 0,
  }),
  policyAllowed: Annotation<boolean>({
    reducer: (_, next) => next,
    default: () => false,
  }),
});

type SpecialistReport = {
  agentId: string;
  label: string;
  toolName: string;
  report: string;
};

function toolArguments(name: string, request: RunRequest): Record<string, unknown> {
  if (name === "github_issue") {
    return {
      owner: request.input.owner,
      repository: request.input.repository,
      issueNumber: Number(request.input.issueNumber),
    };
  }
  if (name === "github_repository") {
    return { owner: request.input.owner, repository: request.input.repository };
  }
  if (name === "gleif_entity") {
    return { legalName: request.input.legalName };
  }
  if (name === "sec_company_facts") {
    return { cik: request.input.cik, metric: request.input.metric };
  }
  return {};
}

function languageModel(request: RunRequest) {
  if (process.env.GITHUB_MODELS_TOKEN) {
    const githubModels = createOpenAI({
      apiKey: process.env.GITHUB_MODELS_TOKEN,
      baseURL: "https://models.github.ai/inference",
      headers: {
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2026-03-10",
      },
    });
    return githubModels.chat(request.controls.model);
  }
  if (process.env.OPENAI_API_KEY) {
    const openai = createOpenAI({ apiKey: process.env.OPENAI_API_KEY });
    return openai(request.controls.model.replace("openai/", ""));
  }
  return gateway(request.controls.model);
}

function createTools(
  request: RunRequest,
  emit: EventEmitter,
  evidence: PublicToolResult[],
) {
  const execute = async (name: string, args: Record<string, unknown>) => {
    const startedAt = performance.now();
    emit({
      lane: "agentic",
      type: "tool_started",
      nodeId: `agent-${name}`,
      label: name,
      summary: "The model selected this typed tool from the policy-approved MCP registry.",
      status: "running",
      actor: "AI SDK ToolLoopAgent -> MCP SDK v1",
      data: { arguments: args },
    });
    const result = await callPublicMcpTool(name, args);
    evidence.push(result);
    const evidenceRecord = {
      id: crypto.randomUUID(),
      title: `${result.source}: ${name}`,
      source: result.source,
      sourceUrl: result.sourceUrl,
      capturedAt: result.capturedAt,
      fields: result.data,
    };
    emit({
      lane: "agentic",
      type: "evidence_captured",
      nodeId: `evidence-${name}`,
      label: "Evidence captured",
      summary: `Validated structured evidence from ${result.source}.`,
      status: "completed",
      actor: "Zod evidence contract",
      evidence: evidenceRecord,
    });
    emit({
      lane: "agentic",
      type: "tool_completed",
      nodeId: `agent-${name}`,
      label: name,
      summary: `Tool completed with ${Object.keys(result.data).length} structured fields.`,
      status: "completed",
      actor: "MCP SDK v1",
      durationMs: Math.round(performance.now() - startedAt),
      data: { sourceUrl: result.sourceUrl, fields: Object.keys(result.data) },
    });
    return result;
  };

  return {
    github_status: tool({
      description: "Read current GitHub platform component health from the official status API.",
      inputSchema: z.object({}),
      strict: true,
      execute: (args) => execute("github_status", args),
    }),
    github_incidents: tool({
      description: "Read current unresolved GitHub platform incidents from the official status API.",
      inputSchema: z.object({}),
      strict: true,
      execute: (args) => execute("github_incidents", args),
    }),
    github_issue: tool({
      description: "Read a public GitHub issue through the official REST API.",
      inputSchema: z.object({
        owner: z.string(),
        repository: z.string(),
        issueNumber: z.number().int().positive(),
      }),
      strict: true,
      execute: (args) => execute("github_issue", args),
    }),
    github_repository: tool({
      description: "Read public GitHub repository metadata through the official REST API.",
      inputSchema: z.object({ owner: z.string(), repository: z.string() }),
      strict: true,
      execute: (args) => execute("github_repository", args),
    }),
    gleif_entity: tool({
      description: "Resolve a legal entity through the official GLEIF LEI API.",
      inputSchema: z.object({ legalName: z.string() }),
      strict: true,
      execute: (args) => execute("gleif_entity", args),
    }),
    sec_company_facts: tool({
      description: "Read one US-GAAP company fact from the official SEC EDGAR Data API.",
      inputSchema: z.object({ cik: z.string(), metric: z.string() }),
      strict: true,
      execute: (args) => execute("sec_company_facts", args),
    }),
  };
}

function providerOptions(request: RunRequest, runId: string) {
  if (process.env.GITHUB_MODELS_TOKEN || process.env.OPENAI_API_KEY) {
    return undefined;
  }
  return {
    gateway: {
      models: ["openai/gpt-4.1-mini", "openai/gpt-4o-mini"],
      tags: ["aegisops", request.scenarioId, "public-demo"],
      user: `public-demo-${runId}`,
      zeroDataRetention: true,
      disallowPromptTraining: true,
    },
  };
}

function emitModelStep(
  emit: EventEmitter,
  agentId: string,
  agentLabel: string,
  decisionContext: {
    availableTools: string[];
    initialToolRequired: boolean;
    role: "adaptive_agent" | "specialist" | "supervisor";
  },
) {
  return (step: {
    stepNumber: number;
    toolCalls: Array<{ toolName: string }>;
    finishReason: string;
    model: { provider: string; modelId: string };
    usage: { inputTokens?: number; outputTokens?: number };
    response: { id?: string };
  }) => {
    const selectedTools = step.toolCalls.map((call) => call.toolName);
    const requiredByGraph = decisionContext.initialToolRequired && step.stepNumber === 0;
    const decisionKind =
      selectedTools.length > 0 ? "tool_selection" : "synthesize_or_stop";
    const controller =
      selectedTools.length > 0 && requiredByGraph
        ? "model_within_graph_constraint"
        : "model";
    emit({
      lane: "agentic",
      type: "model_step",
      nodeId: `${agentId}-model-step-${step.stepNumber + 1}`,
      label: `${agentLabel} step ${step.stepNumber + 1}`,
      summary:
        selectedTools.length > 0
          ? decisionContext.role === "specialist"
            ? `LangGraph assigned ${selectedTools.join(", ")}; the specialist issued the typed call.`
            : `A tool call was required; the model selected ${selectedTools.join(", ")} from ${decisionContext.availableTools.length} approved tools.`
          : decisionContext.role === "supervisor"
            ? "The supervisor synthesized the specialist handoffs and stopped without requesting new evidence."
            : `The agent used the returned observations and completed with ${step.finishReason}.`,
      status: "completed",
      actor: `${step.model.provider}/${step.model.modelId}`,
      data: {
        agentId,
        inputTokens: step.usage.inputTokens ?? 0,
        outputTokens: step.usage.outputTokens ?? 0,
        finishReason: step.finishReason,
        toolCalls: selectedTools,
        generationId: step.response.id,
        observableDecision: {
          kind: decisionKind,
          controller,
          role: decisionContext.role,
          availableTools: decisionContext.availableTools,
          selectedTools,
          graphConstraint: requiredByGraph ? "at_least_one_tool_call_required" : "none",
          visibility: "execution_summary_not_private_chain_of_thought",
        },
      },
    });
  };
}

async function runSpecialistAgent({
  request,
  runId,
  emit,
  evidence,
  agentId,
  label,
  toolName,
  assignment,
}: {
  request: RunRequest;
  runId: string;
  emit: EventEmitter;
  evidence: PublicToolResult[];
  agentId: string;
  label: string;
  toolName: "github_status" | "github_incidents";
  assignment: string;
}): Promise<SpecialistReport> {
  const startedAt = performance.now();
  emit({
    lane: "agentic",
    type: "node_started",
    nodeId: agentId,
    label,
    summary: assignment,
    status: "running",
    actor: "LangGraph specialist + AI SDK ToolLoopAgent",
    data: { model: request.controls.model, activeTool: toolName },
  });

  const tools = createTools(request, emit, evidence);
  const agent = new ToolLoopAgent({
    id: agentId,
    model: languageModel(request),
    instructions:
      "You are one read-only specialist in a supervised incident team. Call your assigned tool exactly as required, analyze only its returned evidence, cite the source URL, distinguish observation from inference, and return a compact structured handoff for the supervisor. Do not make or claim side effects.",
    tools,
    activeTools: [toolName],
    stopWhen: stepCountIs(3),
    maxOutputTokens: 450,
    maxRetries: 2,
    prepareStep: ({ stepNumber }) => ({
      activeTools: [toolName],
      toolChoice: stepNumber === 0 ? "required" : "auto",
    }),
    providerOptions: providerOptions(request, runId),
    experimental_telemetry: {
      isEnabled: true,
      functionId: `aegisops.incident.${agentId}`,
      metadata: { runId, scenarioId: request.scenarioId, agentId },
    },
  });

  const result = await agent.generate({
    prompt: `${assignment}\n\nApproved tool arguments: ${JSON.stringify(
      toolArguments(toolName, request),
    )}`,
    onStepFinish: emitModelStep(emit, agentId, label, {
      availableTools: [toolName],
      initialToolRequired: true,
      role: "specialist",
    }),
  });

  emit({
    lane: "agentic",
    type: "node_completed",
    nodeId: agentId,
    label: `${label} handoff ready`,
    summary: `Completed ${result.steps.length} model step${result.steps.length === 1 ? "" : "s"} and returned grounded findings to the supervisor.`,
    status: "completed",
    actor: "AI SDK ToolLoopAgent",
    durationMs: Math.round(performance.now() - startedAt),
    data: {
      toolName,
      inputTokens: result.totalUsage.inputTokens ?? 0,
      outputTokens: result.totalUsage.outputTokens ?? 0,
    },
  });

  return { agentId, label, toolName, report: result.text };
}

export async function runAgenticLane(
  request: RunRequest,
  runId: string,
  writer: UIMessageStreamWriter<AegisUIMessage>,
  emit: EventEmitter,
) {
  const scenario = scenarioById[request.scenarioId];
  const evidence: PublicToolResult[] = [];
  const checkpointer = await getCheckpointer();
  const laneStartedAt = performance.now();

  const graphBuilder = new StateGraph(AgentState)
    .addNode("guardrail", async (state) => {
      const startedAt = performance.now();
      emit({
        lane: "agentic",
        type: "node_started",
        nodeId: "agent-guardrail",
        label: "Input guardrail",
        summary: "Validating scope, tool budget, spend ceiling, and read-only action class.",
        status: "running",
        actor: "LangGraph + Zod",
      });
      const decision = await evaluatePublicDemoPolicy({
        action: "read",
        max_tool_calls: state.request.controls.maxToolCalls,
        max_cost_usd: state.request.controls.maxCostUsd,
        tools: scenario.requiredTools,
      });
      emit({
        lane: "policy",
        type: "guardrail_decision",
        nodeId: "agent-guardrail",
        label: decision.allow ? "Execution allowed" : "Execution blocked",
        summary: decision.reason,
        status: decision.allow ? "passed" : "blocked",
        actor: "OPA 1.18 / Rego WASM",
        durationMs: Math.round(performance.now() - startedAt),
        data: { controls: decision.controls, tools: scenario.requiredTools },
      });
      if (!decision.allow) {
        throw new Error(decision.reason);
      }
      return { policyAllowed: true };
    })
    .addNode("agent", async (state) => {
      const tools = createTools(state.request, emit, evidence);
      emit({
        lane: "agentic",
        type: "node_started",
        nodeId: "agent-plan",
        label: "Adaptive plan and tool loop",
        summary: `${scenario.agentPattern}. The model must call live evidence tools before answering.`,
        status: "running",
        actor: "LangGraph + AI SDK ToolLoopAgent",
        data: {
          model: state.request.controls.model,
          activeTools: scenario.requiredTools,
          checkpoint: checkpointer.mode,
        },
      });
      const agent = new ToolLoopAgent({
        id: `${scenario.id}-evidence-agent`,
        model: languageModel(state.request),
        instructions:
          "You are a read-only enterprise evidence agent. You must call every active tool at least once before reaching a conclusion. Use only returned evidence, cite source URLs, explicitly separate observations from inferences, never invent identifiers or values, and never propose that a side effect already happened. Keep the final brief under 350 words with sections: Decision, Evidence, Adaptive work, Guardrails, Next action.",
        tools,
        activeTools: scenario.requiredTools as Array<keyof typeof tools>,
        stopWhen: stepCountIs(state.request.controls.maxToolCalls + 2),
        maxOutputTokens: 900,
        maxRetries: 2,
        prepareStep: ({ stepNumber }) => ({
          activeTools: scenario.requiredTools as Array<keyof typeof tools>,
          toolChoice: stepNumber === 0 ? "required" : "auto",
        }),
        providerOptions: providerOptions(state.request, runId),
        experimental_telemetry: {
          isEnabled: true,
          functionId: `aegisops.${scenario.id}`,
          metadata: { runId, scenarioId: scenario.id },
        },
      });

      const result = await agent.stream({
        prompt: `${scenario.prompt(state.request.input)}\n\nExact approved tool arguments: ${JSON.stringify(
          Object.fromEntries(
            scenario.requiredTools.map((name) => [name, toolArguments(name, state.request)]),
          ),
        )}`,
        onStepFinish: emitModelStep(emit, "agent-plan", "Evidence agent", {
          availableTools: scenario.requiredTools,
          initialToolRequired: true,
          role: "adaptive_agent",
        }),
      });
      writer.merge(result.toUIMessageStream<AegisUIMessage>());
      const finalText = await result.text;
      emit({
        lane: "agentic",
        type: "node_completed",
        nodeId: "agent-plan",
        label: "Adaptive synthesis complete",
        summary: `${evidence.length} live evidence record${evidence.length === 1 ? "" : "s"} informed the answer.`,
        status: "completed",
        actor: "AI SDK ToolLoopAgent",
        data: { evidenceCount: evidence.length },
      });
      return { finalText, evidenceCount: evidence.length };
    })
    .addNode("status_specialist", async (state) => ({
      specialistReports: [
        await runSpecialistAgent({
          request: state.request,
          runId,
          emit,
          evidence,
          agentId: "agent-status-specialist",
          label: "Platform health specialist",
          toolName: "github_status",
          assignment:
            "Inspect current GitHub component health, identify degraded surfaces, and prepare a source-grounded operational handoff.",
        }),
      ],
    }))
    .addNode("incident_specialist", async (state) => ({
      specialistReports: [
        await runSpecialistAgent({
          request: state.request,
          runId,
          emit,
          evidence,
          agentId: "agent-incident-specialist",
          label: "Incident evidence specialist",
          toolName: "github_incidents",
          assignment:
            "Inspect unresolved GitHub incidents, extract current impact and chronology, and prepare a source-grounded operational handoff.",
        }),
      ],
    }))
    .addNode("supervisor", async (state) => {
      const startedAt = performance.now();
      emit({
        lane: "agentic",
        type: "agent_handoff",
        nodeId: "agent-supervisor",
        label: "Specialist handoff",
        summary: `${state.specialistReports.length} independent specialist reports reached the supervisor for reconciliation.`,
        status: "running",
        actor: "LangGraph fan-in",
        data: {
          from: state.specialistReports.map((report) => report.agentId),
          evidenceCount: evidence.length,
        },
      });

      const supervisor = new ToolLoopAgent({
        id: "incident-supervisor",
        model: languageModel(state.request),
        instructions:
          "You are the supervising incident agent. Reconcile the two specialist handoffs without adding unsupported facts. Resolve conflicts explicitly, cite every supplied source URL, separate observations from inferences, explain why parallel specialists improved coverage, and keep all production side effects behind policy and human approval. Return sections: Decision, Reconciled evidence, Multi-agent work, Guardrails, Next action.",
        tools: {},
        stopWhen: stepCountIs(1),
        maxOutputTokens: 900,
        maxRetries: 2,
        providerOptions: providerOptions(state.request, runId),
        experimental_telemetry: {
          isEnabled: true,
          functionId: "aegisops.incident.supervisor",
          metadata: { runId, scenarioId: state.request.scenarioId },
        },
      });
      const result = await supervisor.stream({
        prompt: `${scenario.prompt(state.request.input)}\n\nSpecialist handoffs:\n${JSON.stringify(
          state.specialistReports,
          null,
          2,
        )}`,
        onStepFinish: emitModelStep(emit, "agent-supervisor", "Supervisor", {
          availableTools: [],
          initialToolRequired: false,
          role: "supervisor",
        }),
      });
      writer.merge(result.toUIMessageStream<AegisUIMessage>());
      const finalText = await result.text;
      emit({
        lane: "agentic",
        type: "node_completed",
        nodeId: "agent-supervisor",
        label: "Supervisor synthesis complete",
        summary: `Reconciled ${state.specialistReports.length} specialist handoffs and ${evidence.length} validated evidence records.`,
        status: "completed",
        actor: "LangGraph supervisor + AI SDK ToolLoopAgent",
        durationMs: Math.round(performance.now() - startedAt),
        data: {
          specialists: state.specialistReports.map((report) => report.label),
          evidenceCount: evidence.length,
        },
      });
      return { finalText, evidenceCount: evidence.length };
    })
    .addNode("policy", async (state) => {
      const decision = await evaluatePublicDemoPolicy({
        action: state.request.controls.requireApproval ? "write" : "read",
        max_tool_calls: state.request.controls.maxToolCalls,
        max_cost_usd: state.request.controls.maxCostUsd,
        tools: scenario.requiredTools,
      });
      emit({
        lane: "policy",
        type: "policy_decision",
        nodeId: "output-policy",
        label: decision.require_approval ? "Side effects held" : "Read-only output allowed",
        summary: decision.reason,
        status: decision.allow ? "passed" : "blocked",
        actor: "OPA 1.18 / Rego WASM",
        data: { controls: decision.controls, requestedAction: decision.require_approval ? "write" : "read" },
      });
      return {};
    })
    .addNode("evaluate", async (state) => {
      const grounded = state.evidenceCount >= scenario.requiredTools.length;
      emit({
        lane: "agentic",
        type: "node_completed",
        nodeId: "agent-evaluate",
        label: grounded ? "Grounding check passed" : "Grounding check failed",
        summary: grounded
          ? "Every required live source produced a validated evidence record."
          : "The agent did not collect all evidence required by the workflow contract.",
        status: grounded ? "passed" : "failed",
        actor: "LangGraph evaluator",
        data: {
          requiredEvidence: scenario.requiredTools.length,
          capturedEvidence: state.evidenceCount,
        },
      });
      if (!grounded) {
        throw new Error("Grounding evaluator rejected an incomplete evidence set");
      }
      emit({
        lane: "agentic",
        type: "lane_completed",
        nodeId: "agent-output",
        label: "Agentic workflow complete",
        summary:
          scenario.orchestration === "multi_agent"
            ? "Parallel specialist agents, supervisor reconciliation, policy, and grounding checks completed."
            : "Adaptive evidence collection, synthesis, policy, and grounding checks completed.",
        status: "completed",
        actor:
          scenario.orchestration === "multi_agent"
            ? "LangGraph multi-agent runtime"
            : "LangGraph single-agent runtime",
        durationMs: Math.round(performance.now() - laneStartedAt),
        data: { checkpoint: checkpointer.mode, graph: scenario.agentNodes },
      });
      return {};
    });

  graphBuilder
    .addEdge(START, "guardrail")
    .addConditionalEdges(
      "guardrail",
      (state) =>
        state.request.scenarioId === "incident_response"
          ? ["status_specialist", "incident_specialist"]
          : "agent",
      ["agent", "status_specialist", "incident_specialist"],
    )
    .addEdge(["status_specialist", "incident_specialist"], "supervisor")
    .addEdge("supervisor", "policy")
    .addEdge("agent", "policy");
  const graph = graphBuilder
    .addEdge("policy", "evaluate")
    .addEdge("evaluate", END)
    .compile({ checkpointer: checkpointer.saver });

  const stream = await graph.stream(
    { request, specialistReports: [] },
    {
      configurable: { thread_id: runId },
      recursionLimit: 20,
      tags: ["aegisops", scenario.id],
      metadata: { runId, scenarioId: scenario.id },
      streamMode: "updates",
    },
  );
  for await (const update of stream) {
    // Consuming LangGraph's update stream keeps node execution and UI events live.
    void update;
  }
}
