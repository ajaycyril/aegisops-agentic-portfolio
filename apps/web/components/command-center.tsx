"use client";

import {
  Activity,
  AlertTriangle,
  BrainCircuit,
  CheckCircle2,
  ClipboardCheck,
  Database,
  FileText,
  Gauge,
  GitPullRequest,
  LockKeyhole,
  MessageSquare,
  Network,
  Pause,
  Play,
  RefreshCw,
  Route,
  Scale,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Timer,
  Workflow,
  XCircle,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useReducedMotion } from "framer-motion";
import { useEffect, useMemo, useState, type CSSProperties, type ReactNode } from "react";
import {
  Background,
  Controls,
  MarkerType,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";

import type {
  ApiStatus,
  ToolCatalog,
  ToolDetail,
  WorkflowRunTrace,
  WorkflowRunTraceEvalStatus,
  WorkflowRunTraceStatus,
} from "@/lib/api";
import type { WorkflowCatalog, WorkflowDetail } from "@/lib/workflows";

type CommandCenterProps = {
  apiBaseUrl: string | null;
  apiStatus: ApiStatus;
  toolCatalog: ToolCatalog;
  workflowCatalog: WorkflowCatalog;
  workflowRunTrace: WorkflowRunTraceStatus;
  workflowRunTraceEval: WorkflowRunTraceEvalStatus;
};

type UseCaseDefinition = {
  workflowId: string;
  shortName: string;
  icon: LucideIcon;
  accent: string;
  liveInputTemplate: Record<string, string>;
  whyAgentic: string;
  traditionalLimit: string;
  agenticLoop: string[];
  rulePath: string[];
};

type RuntimeStepKind =
  | "contract"
  | "readiness"
  | "run"
  | "tool"
  | "evidence"
  | "model"
  | "policy"
  | "approval"
  | "memory"
  | "eval"
  | "output";

type RuntimeStepState = "complete" | "running" | "blocked" | "pending" | "not_configured";

type RuntimeStep = {
  id: string;
  title: string;
  kind: RuntimeStepKind;
  state: RuntimeStepState;
  actor: string;
  summary: string;
  data: string[];
  reasoning: string[];
  controls: string[];
  source: "live_trace" | "live_api" | "workflow_contract";
  timestamp?: string | null;
};

type TuneState = {
  autonomy: "read_only" | "draft_only" | "approval_required";
  maxToolCalls: number;
  maxUsd: number;
  requireApproval: boolean;
  includeModelPlanning: boolean;
};

type StartAttempt =
  | { state: "idle"; message: string }
  | { state: "running"; message: string }
  | { state: "success"; message: string; body: unknown }
  | { state: "blocked"; message: string; body: unknown }
  | { state: "error"; message: string; body: unknown };

type FlowNodeData = Record<string, unknown> & {
  label: ReactNode;
  title: string;
};

type Gate = {
  label: string;
  value: string;
  state: "open" | "closed" | "neutral";
};

const preferredUseCases: UseCaseDefinition[] = [
  {
    workflowId: "incident_response_investigator",
    shortName: "Incident",
    icon: Activity,
    accent: "#35c2a7",
    liveInputTemplate: {
      incident_id: "",
      service: "",
      severity: "sev2",
      time_window: "",
    },
    whyAgentic:
      "Incident diagnosis needs adaptive investigation across logs, deployments, code ownership, hypotheses, policy, and approvals.",
    traditionalLimit:
      "A rule engine can page on thresholds, but it cannot decide which evidence is missing or reconcile competing causes.",
    agenticLoop: [
      "Supervisor plans investigation branches.",
      "Specialist tools read logs, deployments, and code.",
      "Evidence is reconciled into hypotheses.",
      "OPA blocks rollback, paging, and updates until approval.",
    ],
    rulePath: [
      "Metric crosses threshold.",
      "Static alert fires.",
      "Ticket or page is created.",
      "Human manually opens every system.",
    ],
  },
  {
    workflowId: "customer_support_escalation",
    shortName: "Support",
    icon: MessageSquare,
    accent: "#78a6ff",
    liveInputTemplate: {
      ticket_id: "",
      customer_id: "",
      requested_action: "draft_response",
    },
    whyAgentic:
      "Support escalation needs ticket context, CRM state, knowledge retrieval, redacted memory, and approval before customer-visible output.",
    traditionalLimit:
      "Rules can route by priority or keyword, but cannot produce a grounded response with citations and risk-aware stop points.",
    agenticLoop: [
      "Read ticket and customer context.",
      "Retrieve approved knowledge citations.",
      "Draft a structured response with unsupported claims marked.",
      "Block customer send until approval.",
    ],
    rulePath: [
      "Match keyword or priority.",
      "Apply queue routing rule.",
      "Offer a canned macro.",
      "Human manually checks CRM and KB.",
    ],
  },
  {
    workflowId: "engineering_issue_to_pr",
    shortName: "Engineering",
    icon: GitPullRequest,
    accent: "#f4c95d",
    liveInputTemplate: {
      issue_url: "",
      repository: "",
      include_proposal: "false",
    },
    whyAgentic:
      "Issue-to-PR work requires reading issue context, inspecting code, planning a patch, evaluating test coverage, and stopping before writes.",
    traditionalLimit:
      "Rules can label or assign an issue, but cannot inspect a repo and produce an evaluated implementation plan.",
    agenticLoop: [
      "Read issue and repo files through GitHub tools.",
      "Plan a patch and tests with structured outputs.",
      "Evaluate grounding and blast radius.",
      "Require approval before branch or PR creation.",
    ],
    rulePath: [
      "Match label or owner rule.",
      "Assign the issue.",
      "Maybe post a canned comment.",
      "Human reads files and writes the fix.",
    ],
  },
  {
    workflowId: "supply_chain_supplier_risk",
    shortName: "Supplier Risk",
    icon: Network,
    accent: "#ff7a90",
    liveInputTemplate: {
      supplier_id: "",
      renewal_id: "",
      geography: "",
    },
    whyAgentic:
      "Supplier risk needs source-grounded research, sanctions context, procurement impact, and policy-gated status changes.",
    traditionalLimit:
      "Rules can flag a score, but they cannot collect new evidence and explain tradeoffs for a renewal decision.",
    agenticLoop: [
      "Read supplier and procurement context.",
      "Collect sanctions and approved research sources.",
      "Separate confirmed signals from weak signals.",
      "Route supplier status changes through policy approval.",
    ],
    rulePath: [
      "Supplier risk score crosses threshold.",
      "Flag renewal.",
      "Notify procurement queue.",
      "Human researches sources manually.",
    ],
  },
  {
    workflowId: "finance_invoice_exception",
    shortName: "Finance",
    icon: Scale,
    accent: "#b79cff",
    liveInputTemplate: {
      invoice_id: "",
      purchase_order_id: "",
      vendor_id: "",
    },
    whyAgentic:
      "Invoice exceptions need document evidence, policy routing, audit packets, and approval before payment or vendor communication.",
    traditionalLimit:
      "Rules can block amount mismatches, but they cannot classify the cause with document-backed reasoning.",
    agenticLoop: [
      "Read invoice, PO, vendor, and delivery evidence.",
      "Classify exception type with cited documents.",
      "Route approval by amount and vendor risk.",
      "Block payment or vendor message until approval.",
    ],
    rulePath: [
      "Compare invoice amount with PO tolerance.",
      "Flag mismatch.",
      "Hold payment.",
      "Human reads documents and asks vendor.",
    ],
  },
];

const stepIcons: Record<RuntimeStepKind, LucideIcon> = {
  contract: Workflow,
  readiness: ShieldCheck,
  run: Play,
  tool: Search,
  evidence: FileText,
  model: BrainCircuit,
  policy: LockKeyhole,
  approval: ClipboardCheck,
  memory: Database,
  eval: Gauge,
  output: Sparkles,
};

const defaultTuneState: TuneState = {
  autonomy: "read_only",
  maxToolCalls: 12,
  maxUsd: 0.25,
  requireApproval: true,
  includeModelPlanning: false,
};

export function CommandCenter({
  apiBaseUrl,
  apiStatus,
  toolCatalog,
  workflowCatalog,
  workflowRunTrace,
  workflowRunTraceEval,
}: CommandCenterProps) {
  const shouldReduceMotion = useReducedMotion();
  const availableUseCases = useMemo(
    () => preferredUseCases.filter((useCase) => workflowCatalog.workflows.some((workflow) => workflow.id === useCase.workflowId)),
    [workflowCatalog.workflows],
  );
  const useCases = availableUseCases.length > 0 ? availableUseCases : preferredUseCases;
  const [selectedWorkflowId, setSelectedWorkflowId] = useState(useCases[0]?.workflowId ?? "");
  const [activeStepIndex, setActiveStepIndex] = useState(0);
  const [selectedStepId, setSelectedStepId] = useState("");
  const [isPlaying, setIsPlaying] = useState(false);
  const [tuneState, setTuneState] = useState<TuneState>(defaultTuneState);
  const [liveInput, setLiveInput] = useState<Record<string, string>>(useCases[0]?.liveInputTemplate ?? {});
  const [startAttempt, setStartAttempt] = useState<StartAttempt>({
    state: "idle",
    message: "No live run request has been sent in this browser session.",
  });

  const selectedUseCase =
    useCases.find((useCase) => useCase.workflowId === selectedWorkflowId) ?? useCases[0];
  const workflow =
    workflowCatalog.workflows.find((item) => item.id === selectedUseCase.workflowId) ??
    workflowCatalog.workflows[0];
  const workflowTools = useMemo(
    () =>
      toolCatalog.tools.filter((tool) =>
        tool.allowed_workflows.includes(workflow.id),
      ),
    [toolCatalog.tools, workflow.id],
  );
  const matchingTrace =
    workflowRunTrace.label === "loaded" && workflowRunTrace.trace.run.workflow_id === workflow.id
      ? workflowRunTrace.trace
      : null;

  const steps = useMemo(
    () =>
      buildRuntimeSteps({
        apiStatus,
        selectedUseCase,
        toolCatalog,
        tools: workflowTools,
        workflowCatalog,
        workflow,
        trace: matchingTrace,
        traceStatus: workflowRunTrace,
        evalStatus: workflowRunTraceEval,
        startAttempt,
      }),
    [
      apiStatus,
      selectedUseCase,
      toolCatalog,
      workflowTools,
      workflowCatalog,
      workflow,
      matchingTrace,
      workflowRunTrace,
      workflowRunTraceEval,
      startAttempt,
    ],
  );

  const activeStep = steps[activeStepIndex] ?? steps[0];
  const selectedStep = isPlaying
    ? activeStep
    : steps.find((step) => step.id === selectedStepId) ?? activeStep;
  const flow = useMemo(
    () => buildFlow(steps, activeStepIndex, selectedStep.id, selectedUseCase.accent),
    [steps, activeStepIndex, selectedStep.id, selectedUseCase.accent],
  );
  const gates = buildGates(apiStatus, workflowCatalog, workflow, workflowRunTrace, matchingTrace);
  const canAttemptLiveStart = Boolean(apiBaseUrl && workflow);
  const canPlayTrace = steps.some((step) => step.source === "live_trace" || step.state === "complete");

  useEffect(() => {
    if (!isPlaying || !canPlayTrace) {
      return;
    }

    if (activeStepIndex >= steps.length - 1) {
      const stopTimer = window.setTimeout(() => setIsPlaying(false), 0);
      return () => window.clearTimeout(stopTimer);
    }

    const timer = window.setTimeout(
      () => {
        setActiveStepIndex((current) => {
          const next = Math.min(current + 1, steps.length - 1);
          setSelectedStepId(steps[next]?.id ?? "");
          return next;
        });
      },
      shouldReduceMotion ? 900 : 1500,
    );

    return () => window.clearTimeout(timer);
  }, [activeStepIndex, canPlayTrace, isPlaying, shouldReduceMotion, steps]);

  async function startLiveRun() {
    if (!apiBaseUrl) {
      setStartAttempt({
        state: "blocked",
        message: "No API base URL is configured, so a real workflow-run request cannot be sent.",
        body: null,
      });
      return;
    }

    setStartAttempt({
      state: "running",
      message: "Sending real workflow-run request to the configured API.",
    });

    const payload = {
      workflow_id: workflow.id,
      execution_mode: "live",
      autonomy_level: tuneState.autonomy,
      input_payload: compactInput(liveInput),
      budget: {
        max_tool_calls: tuneState.maxToolCalls,
        max_estimated_usd: tuneState.maxUsd.toFixed(2),
      },
      require_human_approval: tuneState.requireApproval,
      include_proposal: tuneState.includeModelPlanning,
    };

    try {
      const response = await fetch("/live-run/start", {
        method: "POST",
        headers: {
          accept: "application/json",
          "content-type": "application/json",
        },
        body: JSON.stringify({
          api_base_url: apiBaseUrl,
          payload,
        }),
      });
      const body = await readResponseBody(response);
      const upstreamResult = readUpstreamResult(body);

      if (response.ok && upstreamResult?.upstream_ok === true) {
        setStartAttempt({
          state: "success",
          message: `Live workflow-run request succeeded with upstream HTTP ${upstreamResult.upstream_status}.`,
          body,
        });
      } else if (response.ok && upstreamResult) {
        setStartAttempt({
          state: "blocked",
          message: `Live workflow-run request returned upstream HTTP ${upstreamResult.upstream_status}. This is the actual response from the configured API gate.`,
          body,
        });
      } else {
        setStartAttempt({
          state: "blocked",
          message: `Live workflow-run request returned HTTP ${response.status}. This is the actual response from the configured API gate.`,
          body,
        });
      }
    } catch (error) {
      setStartAttempt({
        state: "error",
        message: error instanceof Error ? error.message : "Live workflow-run request failed.",
        body: null,
      });
    }
  }

  function toggleTracePlayback() {
    if (activeStepIndex >= steps.length - 1) {
      setActiveStepIndex(0);
      setSelectedStepId(steps[0]?.id ?? "");
      setIsPlaying(true);
      return;
    }

    setIsPlaying((current) => !current);
  }

  return (
    <main className="agent-lab" style={{ "--accent": selectedUseCase.accent } as CSSProperties}>
      <header className="lab-topbar">
        <div className="brand-lockup">
          <div className="brand-glyph">
            <Workflow size={20} />
          </div>
          <div>
            <strong>AegisOps Live Agent Lab</strong>
            <span>Real contracts, real API gates, real traces only</span>
          </div>
        </div>
        <div className="topbar-gates">
          {gates.slice(0, 3).map((gate) => (
            <GatePill gate={gate} key={gate.label} />
          ))}
        </div>
      </header>

      <section className="live-cockpit" aria-label="Live agentic workflow cockpit">
        <div className="operator-panel">
          <p className="eyebrow">Use case</p>
          <h1>{workflow.name}</h1>
          <p className="workflow-purpose">{selectedUseCase.whyAgentic}</p>

          <div className="use-case-grid" aria-label="Select workflow use case">
            {useCases.map((useCase) => {
              const Icon = useCase.icon;
              const contract = workflowCatalog.workflows.find(
                (item) => item.id === useCase.workflowId,
              );
              return (
                <button
                  className={
                    useCase.workflowId === selectedWorkflowId
                      ? "use-case-button active"
                      : "use-case-button"
                  }
                  key={useCase.workflowId}
                  onClick={() => {
                    const nextWorkflow = workflowCatalog.workflows.find(
                      (item) => item.id === useCase.workflowId,
                    );
                    setSelectedWorkflowId(useCase.workflowId);
                    setActiveStepIndex(0);
                    setSelectedStepId("");
                    setIsPlaying(false);
                    setLiveInput(useCase.liveInputTemplate);
                    setTuneState((current) => ({
                      ...current,
                      autonomy:
                        nextWorkflow?.default_autonomy === "autonomous"
                          ? "approval_required"
                          : nextWorkflow?.default_autonomy ?? "read_only",
                    }));
                    setStartAttempt({
                      state: "idle",
                      message: "No live run request has been sent in this browser session.",
                    });
                  }}
                  type="button"
                >
                  <Icon size={17} />
                  <span>
                    <strong>{useCase.shortName}</strong>
                    <small>{contract?.status ?? "contract"}</small>
                  </span>
                </button>
              );
            })}
          </div>

          <div className="run-control-row">
            <button
              className="primary-run-button"
              disabled={!canAttemptLiveStart || startAttempt.state === "running"}
              onClick={startLiveRun}
              type="button"
            >
              {startAttempt.state === "running" ? <RefreshCw size={18} /> : <Play size={18} />}
              Start real run
            </button>
            <button
              className="secondary-run-button"
              disabled={!canPlayTrace}
              onClick={toggleTracePlayback}
              type="button"
            >
              {isPlaying ? <Pause size={16} /> : <Activity size={16} />}
              {matchingTrace ? "Play trace" : "Play contract"}
            </button>
          </div>

          <LiveAttempt attempt={startAttempt} />
        </div>

        <div className="visualizer-panel">
          <div className="visualizer-head">
            <div>
              <p className="eyebrow">{matchingTrace ? "Live trace player" : "Configured agent path"}</p>
              <h2>{activeStep?.title ?? "No runtime steps available"}</h2>
            </div>
            <div className="step-counter">
              <Timer size={15} />
              {Math.min(activeStepIndex + 1, steps.length)} / {steps.length}
            </div>
          </div>
          <div className="flow-shell">
            <ReactFlow
              nodes={flow.nodes}
              edges={flow.edges}
              fitView
              fitViewOptions={{ padding: 0.18 }}
              minZoom={0.45}
              maxZoom={1.55}
              nodesDraggable={false}
              nodesConnectable={false}
              onNodeClick={(_, node) => {
                setSelectedStepId(node.id);
                setActiveStepIndex(Math.max(0, steps.findIndex((step) => step.id === node.id)));
                setIsPlaying(false);
              }}
              proOptions={{ hideAttribution: true }}
            >
              <Background color="rgba(255,255,255,0.13)" gap={22} />
              <Controls position="bottom-right" showInteractive={false} />
            </ReactFlow>
          </div>
        </div>

        <aside className="step-inspector">
          <div className="inspector-top">
            <div>
              <p className="eyebrow">Current step</p>
              <h2>{selectedStep.title}</h2>
            </div>
            <StateBadge state={selectedStep.state} />
          </div>
          <p className="step-summary">{selectedStep.summary}</p>
          <InspectorBlock icon={Database} title="Data and context">
            {selectedStep.data.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </InspectorBlock>
          <InspectorBlock icon={BrainCircuit} title="Reasoning and control">
            {selectedStep.reasoning.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </InspectorBlock>
          <InspectorBlock icon={ShieldCheck} title="Guardrails">
            {selectedStep.controls.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </InspectorBlock>
          <div className="source-stamp">
            Source: <strong>{formatSource(selectedStep.source)}</strong>
            {selectedStep.timestamp ? <span>{selectedStep.timestamp}</span> : null}
          </div>
        </aside>
      </section>

      <section className="tuning-and-comparison" aria-label="Workflow tuning and comparison">
        <div className="tuning-panel">
          <div className="section-head">
            <SlidersHorizontal size={18} />
            <div>
              <p className="eyebrow">Tune this workflow</p>
              <h2>Controls sent to the real run request</h2>
            </div>
          </div>
          <div className="tuning-grid">
            <label>
              Autonomy
              <select
                value={tuneState.autonomy}
                onChange={(event) =>
                  setTuneState((current) => ({
                    ...current,
                    autonomy: event.target.value as TuneState["autonomy"],
                  }))
                }
              >
                <option value="read_only">Read only</option>
                <option value="draft_only">Draft only</option>
                <option value="approval_required">Approval required</option>
              </select>
            </label>
            <label>
              Max tool calls
              <input
                max={25}
                min={1}
                type="number"
                value={tuneState.maxToolCalls}
                onChange={(event) =>
                  setTuneState((current) => ({
                    ...current,
                    maxToolCalls: Number(event.target.value),
                  }))
                }
              />
            </label>
            <label>
              Max USD
              <input
                max={1}
                min={0}
                step={0.05}
                type="number"
                value={tuneState.maxUsd}
                onChange={(event) =>
                  setTuneState((current) => ({
                    ...current,
                    maxUsd: Number(event.target.value),
                  }))
                }
              />
            </label>
            <label className="toggle-row">
              <input
                checked={tuneState.requireApproval}
                onChange={(event) =>
                  setTuneState((current) => ({
                    ...current,
                    requireApproval: event.target.checked,
                  }))
                }
                type="checkbox"
              />
              Require approval for external actions
            </label>
            <label className="toggle-row">
              <input
                checked={tuneState.includeModelPlanning}
                onChange={(event) =>
                  setTuneState((current) => ({
                    ...current,
                    includeModelPlanning: event.target.checked,
                  }))
                }
                type="checkbox"
              />
              Include model planning where supported
            </label>
          </div>

          <div className="live-inputs">
            {Object.entries(liveInput).map(([key, value]) => (
              <label key={key}>
                {key}
                <input
                  value={value}
                  onChange={(event) =>
                    setLiveInput((current) => ({
                      ...current,
                      [key]: event.target.value,
                    }))
                  }
                  placeholder={`real ${key}`}
                />
              </label>
            ))}
          </div>
        </div>

        <div className="comparison-card">
          <div className="section-head">
            <Route size={18} />
            <div>
              <p className="eyebrow">Traditional system below the agent</p>
              <h2>Why a rule engine is not enough here</h2>
            </div>
          </div>
          <div className="comparison-split">
            <article>
              <h3>Rule-based path</h3>
              <p>{selectedUseCase.traditionalLimit}</p>
              <ul>
                {selectedUseCase.rulePath.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </article>
            <article>
              <h3>Agentic path</h3>
              <p>{selectedUseCase.whyAgentic}</p>
              <ul>
                {selectedUseCase.agenticLoop.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </article>
          </div>
        </div>
      </section>

      <section className="contract-depth" aria-label="Production stack depth">
        <DepthCard
          icon={Workflow}
          title="Workflow contract"
          rows={[
            ["Status", workflow.status],
            ["Autonomy", workflow.default_autonomy],
            ["Source", workflow.source_path],
          ]}
        />
        <DepthCard
          icon={Search}
          title="Tool calls"
          rows={[
            ["Registered", workflowTools.map((tool) => tool.id).join(", ") || "none yet"],
            ["Connectors", workflow.required_connectors.join(", ") || "none"],
            ["Missing", workflow.missing_connectors.join(", ") || "none"],
          ]}
        />
        <DepthCard
          icon={ShieldCheck}
          title="Guardrails"
          rows={[
            ["Fake data", workflow.data_policy.fake_data_allowed ? "allowed" : "blocked"],
            [
              "Replay",
              workflow.data_policy.replay_allowed_from_real_runs
                ? "captured real runs only"
                : "disabled",
            ],
            [
              "Regex extraction",
              workflow.data_policy.regex_business_extraction_allowed ? "allowed" : "blocked",
            ],
          ]}
        />
        <DepthCard
          icon={ClipboardCheck}
          title="Approvals"
          rows={workflow.approval_required_for.map((approval) => ["Required", approval])}
        />
      </section>

      <section className="trace-strip" aria-label="Live gates">
        {gates.map((gate) => (
          <GatePill gate={gate} key={gate.label} />
        ))}
      </section>
    </main>
  );
}

function buildRuntimeSteps({
  apiStatus,
  selectedUseCase,
  toolCatalog,
  tools,
  workflowCatalog,
  workflow,
  trace,
  traceStatus,
  evalStatus,
  startAttempt,
}: {
  apiStatus: ApiStatus;
  selectedUseCase: UseCaseDefinition;
  toolCatalog: ToolCatalog;
  tools: ToolDetail[];
  workflowCatalog: WorkflowCatalog;
  workflow: WorkflowDetail;
  trace: WorkflowRunTrace | null;
  traceStatus: WorkflowRunTraceStatus;
  evalStatus: WorkflowRunTraceEvalStatus;
  startAttempt: StartAttempt;
}): RuntimeStep[] {
  const steps: RuntimeStep[] = [
    {
      id: "contract",
      title: "Workflow Contract",
      kind: "contract",
      state: workflowCatalog.source === "api" ? "complete" : "not_configured",
      actor: "Registry API",
      summary: "The UI is reading the real workflow contract before any run can start.",
      data: [
        `workflow_id=${workflow.id}`,
        `status=${workflow.status}`,
        `source=${workflow.source_path}`,
      ],
      reasoning: [
        "The workflow contract defines required connectors, scopes, autonomy, approvals, and data policy.",
        "The UI does not infer business rules from free text.",
      ],
      controls: [
        workflow.data_policy.fake_data_allowed ? "Fake data allowed by contract" : "Fake data blocked by contract",
        workflow.data_policy.regex_business_extraction_allowed
          ? "Regex extraction allowed by contract"
          : "Regex business extraction blocked by contract",
      ],
      source: workflowCatalog.source === "api" ? "live_api" : "workflow_contract",
    },
    {
      id: "readiness",
      title: "Runtime Readiness",
      kind: "readiness",
      state: isFullRuntimeReady(apiStatus) ? "complete" : "blocked",
      actor: "FastAPI /ready",
      summary: "The runtime gate checks database, policy, admin live-run key, and registry readiness.",
      data: readinessData(apiStatus),
      reasoning: [
        "Agentic execution needs durable state, OPA, audit, and budget controls before it can run.",
        "If any runtime gate is closed, the app must show the block instead of simulating a run.",
      ],
      controls: [
        "Managed Postgres/pgvector required for live workflow state.",
        "Hosted OPA-compatible policy endpoint required for run and tool authorization.",
        "Admin live-run key required before live execution.",
      ],
      source: apiStatus.label === "online" ? "live_api" : "workflow_contract",
    },
    {
      id: "start",
      title: "Start Real Run",
      kind: "run",
      state: startAttemptState(startAttempt),
      actor: "POST /workflow-runs",
      summary: startAttempt.message,
      data: [
        `attempt_state=${startAttempt.state}`,
        `workflow_id=${workflow.id}`,
        `required_connectors=${workflow.required_connectors.join(", ") || "none"}`,
      ],
      reasoning: [
        "The start button sends a real request to the configured API.",
        "HTTP errors and policy rejects are displayed as live production gates.",
      ],
      controls: [
        "Live runs use the selected autonomy, budget, approval, and input controls.",
        "No external write action is available without policy and approval.",
      ],
      source: "live_api",
    },
  ];

  if (!trace) {
    steps.push(
      ...contractAgentSteps({
        apiStatus,
        selectedUseCase,
        toolCatalog,
        tools,
        workflow,
        traceStatus,
      }),
    );
    return steps;
  }

  steps.push({
    id: `run-${trace.run.id}`,
    title: "Run Record",
    kind: "run",
    state: trace.run.status === "failed" ? "blocked" : "complete",
    actor: "Workflow runtime",
    summary: `Stored ${trace.run.execution_mode} run is ${trace.run.status}.`,
    data: [
      `run_id=${trace.run.id}`,
      `autonomy=${trace.run.autonomy_level}`,
      `started_at=${trace.run.started_at}`,
    ],
    reasoning: [
      "This run record is the anchor for the graph, tools, memory, approvals, and evals.",
      "Every following card comes from persisted trace metadata.",
    ],
    controls: [
      trace.run.failure_reason ?? "No failure reason recorded.",
      "Run state is persisted before graph execution continues.",
    ],
    source: "live_trace",
    timestamp: trace.run.updated_at,
  });

  trace.tool_calls.forEach((toolCall) => {
    steps.push({
      id: `tool-${toolCall.id}`,
      title: toolCall.tool_name,
      kind: "tool",
      state: toolCall.status.includes("blocked") ? "blocked" : "complete",
      actor: "Typed tool adapter",
      summary: `Tool call ${toolCall.status}; risk class ${toolCall.risk_class}.`,
      data: [
        `tool_call_id=${toolCall.id}`,
        `execution_state=${toolCall.execution_state ?? "not recorded"}`,
        `output_hash=${toolCall.output_hash ?? "not recorded"}`,
      ],
      reasoning: [
        "Tool execution is separate from tool authorization.",
        "The stored input hash must match before execution is allowed.",
      ],
      controls: [
        `policy_decision_id=${toolCall.policy_decision_id ?? "not recorded"}`,
        `approval_id=${toolCall.approval_id ?? "none"}`,
        `latency_ms=${toolCall.latency_ms ?? "not recorded"}`,
      ],
      source: "live_trace",
      timestamp: toolCall.completed_at ?? toolCall.started_at,
    });
  });

  trace.evidence_records.forEach((evidence) => {
    steps.push({
      id: `evidence-${evidence.id}`,
      title: evidence.title,
      kind: "evidence",
      state: "complete",
      actor: evidence.source_system,
      summary: `Evidence record captured from ${evidence.source_system}.`,
      data: [
        `kind=${evidence.kind}`,
        `source_uri=${evidence.source_uri ?? "not recorded"}`,
        `content_hash=${evidence.content_hash}`,
      ],
      reasoning: [
        "Claims in the workflow must point back to evidence records.",
        "The UI exposes source metadata without inventing source content.",
      ],
      controls: [
        "Evidence metadata is persisted.",
        "Sensitive content is referenced by hash and source metadata.",
      ],
      source: "live_trace",
      timestamp: evidence.created_at,
    });
  });

  trace.model_calls.forEach((modelCall) => {
    steps.push({
      id: `model-${modelCall.id}`,
      title: modelCall.purpose,
      kind: "model",
      state: modelCall.status === "completed" ? "complete" : "blocked",
      actor: `${modelCall.provider} ${modelCall.model}`,
      summary: `Structured model call ${modelCall.status}.`,
      data: [
        `prompt_version=${modelCall.prompt_version}`,
        `input_tokens=${modelCall.input_token_count}`,
        `output_tokens=${modelCall.output_token_count}`,
      ],
      reasoning: [
        "Model calls are ledgered; the model never decides policy.",
        "Generated artifacts need evals and approval before external writes.",
      ],
      controls: [
        `estimated_cost_usd=${modelCall.estimated_cost_usd}`,
        `trace_id=${modelCall.trace_id ?? "not recorded"}`,
        `latency_ms=${modelCall.latency_ms ?? "not recorded"}`,
      ],
      source: "live_trace",
      timestamp: modelCall.completed_at ?? modelCall.started_at,
    });
  });

  trace.memory_records.forEach((memory) => {
    steps.push({
      id: `memory-${memory.id}`,
      title: memory.memory_key,
      kind: "memory",
      state: "complete",
      actor: "Memory store",
      summary: `Memory record stored with ${memory.retention_class} retention.`,
      data: [
        `scope=${memory.scope}`,
        `subject_id=${memory.subject_id ?? "none"}`,
        `sensitivity=${memory.data_sensitivity}`,
      ],
      reasoning: [
        "Memory is explicit and inspectable.",
        "Retention and sensitivity are policy-visible metadata.",
      ],
      controls: [
        `source_evidence_id=${memory.source_evidence_id ?? "none"}`,
        `expires_at=${memory.expires_at ?? "not set"}`,
      ],
      source: "live_trace",
      timestamp: memory.created_at,
    });
  });

  trace.approvals.forEach((approval) => {
    steps.push({
      id: `approval-${approval.id}`,
      title: approval.requested_action,
      kind: "approval",
      state: approval.status === "approved" ? "complete" : "blocked",
      actor: "Approval service",
      summary: `Approval is ${approval.status}; risk class ${approval.risk_class}.`,
      data: [
        `approval_id=${approval.id}`,
        `requested_by=${approval.requested_by}`,
        `approver_id=${approval.approver_id ?? "not decided"}`,
      ],
      reasoning: [
        "External writes require accountable review.",
        "Four-eyes and reviewer separation are enforced outside the model.",
      ],
      controls: [
        `policy_decision_id=${approval.policy_decision_id ?? "not recorded"}`,
        `expires_at=${approval.expires_at ?? "not set"}`,
      ],
      source: "live_trace",
      timestamp: approval.decided_at ?? approval.requested_at,
    });
  });

  if (evalStatus.label === "loaded") {
    evalStatus.evals.checks.forEach((check) => {
      steps.push({
        id: `eval-${check.id}`,
        title: check.label,
        kind: "eval",
        state: check.status === "fail" ? "blocked" : "complete",
        actor: "Trace evaluator",
        summary: check.details,
        data: [`score=${check.score}`, `status=${check.status}`],
        reasoning: [
          "Evals verify the trace after execution.",
          "Grounding, safety, and policy coverage are checked from persisted metadata.",
        ],
        controls: check.evidence_refs.length > 0 ? check.evidence_refs : ["No evidence refs recorded."],
        source: "live_trace",
        timestamp: evalStatus.evals.evaluated_at,
      });
    });
  }

  return steps;
}

function contractAgentSteps({
  apiStatus,
  selectedUseCase,
  toolCatalog,
  tools,
  workflow,
  traceStatus,
}: {
  apiStatus: ApiStatus;
  selectedUseCase: UseCaseDefinition;
  toolCatalog: ToolCatalog;
  tools: ToolDetail[];
  workflow: WorkflowDetail;
  traceStatus: WorkflowRunTraceStatus;
}): RuntimeStep[] {
  const source: RuntimeStep["source"] =
    toolCatalog.source === "api" ? "live_api" : "workflow_contract";
  const runtimeReady = isFullRuntimeReady(apiStatus);
  const graphSteps: RuntimeStep[] = [
    {
      id: `${workflow.id}-langgraph-plan`,
      title: "LangGraph Plan",
      kind: "run",
      state: "complete",
      actor: "LangGraph StateGraph",
      summary: "The workflow is modeled as a stateful graph, not a linear script.",
      data: [
        `patterns=${workflow.patterns.join(", ")}`,
        `default_autonomy=${workflow.default_autonomy}`,
        "execution_library=langgraph",
        "visualization_library=@xyflow/react",
      ],
      reasoning: selectedUseCase.agenticLoop,
      controls: [
        "Pydantic runtime contracts define node inputs and outputs.",
        "Graph execution is checkpoint-ready through Postgres/pgvector storage.",
        "The graph can pause at approval nodes instead of autonomously writing.",
      ],
      source,
    },
  ];

  if (tools.length > 0) {
    graphSteps.push(
      ...tools.map((tool) => ({
        id: `${workflow.id}-tool-${tool.id}`,
        title: tool.name,
        kind: "tool" as const,
        state: tool.enabled ? "complete" as const : "not_configured" as const,
        actor: tool.mcp_server,
        summary: tool.description,
        data: [
          `tool_id=${tool.id}`,
          `connector=${tool.connector}`,
          `risk_class=${tool.risk_class}`,
          `scopes=${tool.required_scopes.join(", ")}`,
          `source=${tool.source_path}`,
        ],
        reasoning: [
          "This is a registered MCP-shaped tool contract for the selected workflow.",
          "The agent can choose this tool only after workflow, connector, schema, and policy checks pass.",
          `Input schema: ${schemaSummary(tool.input_schema)}`,
          `Output schema: ${schemaSummary(tool.output_schema)}`,
        ],
        controls: [
          tool.requires_approval
            ? "Approval required before execution."
            : "Read or draft tool; still policy-authorized before execution.",
          tool.disabled_reason ?? "Tool is contract-ready for this workflow.",
          "OPA tool_access must allow the call before the adapter executes.",
        ],
        source,
      })),
    );
  } else {
    graphSteps.push({
      id: `${workflow.id}-tool-gap`,
      title: "Tool Contract Gap",
      kind: "tool",
      state: "blocked",
      actor: "Tool registry",
      summary: "No registered tool contract is currently mapped to this workflow.",
      data: [
        `required_connectors=${workflow.required_connectors.join(", ")}`,
        `tool_registry=${toolCatalog.message}`,
      ],
      reasoning: [
        "The UI will not invent tool calls just to make the graph look busy.",
        "This workflow needs typed tool contracts before it can execute agentically.",
      ],
      controls: [
        "Add MCP tool contracts under configs/tools.",
        "Map each tool to allowed_workflows and connector scopes.",
      ],
      source,
    });
  }

  graphSteps.push(
    {
      id: `${workflow.id}-evidence`,
      title: "Evidence Board",
      kind: "evidence",
      state: tools.length > 0 ? "pending" : "blocked",
      actor: "Evidence store",
      summary: "Tool outputs become evidence records with source metadata and hashes.",
      data: [
        `visual_surfaces=${workflow.visual_surfaces.join(", ") || "none"}`,
        "evidence_records require source_system, source_uri, content_hash, and metadata.",
      ],
      reasoning: [
        "The agent cannot make claims from memory alone.",
        "Every final recommendation must point to tool output or persisted evidence.",
      ],
      controls: [
        "No fabricated evidence rows.",
        "Sensitive content is retained by policy and exposed through metadata.",
      ],
      source: "workflow_contract",
    },
    {
      id: `${workflow.id}-model-eval`,
      title: "Structured Reasoning + Eval",
      kind: "model",
      state: "pending",
      actor: "OpenAI Responses + eval runner",
      summary: "Model calls are bounded structured transformations, then evaluated from trace metadata.",
      data: [
        "model_api=OpenAI Responses API",
        `model_planning_supported=${workflow.patterns.some((pattern) => pattern.includes("rag") || pattern.includes("rca") || pattern.includes("evaluator") || pattern.includes("plan"))}`,
        "evals=trace grounding, policy coverage, blocked writes, evidence completeness",
      ],
      reasoning: [
        "The model can reason over evidence and produce typed drafts.",
        "The model cannot approve policy, bypass schema validation, or execute write actions.",
      ],
      controls: [
        "Prompt version, model, token counts, cost, latency, and trace id must be recorded.",
        "Rubric/eval checks run against persisted trace metadata.",
      ],
      source: "workflow_contract",
    },
    {
      id: `${workflow.id}-memory`,
      title: "Memory + Checkpoints",
      kind: "memory",
      state: apiStatus.label === "online" && apiStatus.readiness.database_configured ? "pending" : "blocked",
      actor: "Supabase/Postgres + pgvector",
      summary: "Durable state, checkpoints, evidence, approvals, memory, and retrieval live in managed Postgres with pgvector.",
      data: [
        "provider_target=Supabase Postgres or equivalent managed Postgres",
        "tables=workflow_runs, tool_calls, model_calls, evidence_records, memory_records, approvals, audit_events",
        "vector_extension=pgvector",
      ],
      reasoning: [
        "A production agent needs persistent graph state and memory; browser state is not execution.",
        "Supabase/Postgres is the cloud storage boundary for live runs.",
      ],
      controls: [
        "DATABASE_URL must be configured on the full runtime.",
        "Alembic migrations must run before live workflow execution.",
        "Memory writes carry retention class and data sensitivity.",
      ],
      source: apiStatus.label === "online" ? "live_api" : "workflow_contract",
    },
    {
      id: `${workflow.id}-policy`,
      title: "Guardrails + OPA",
      kind: "policy",
      state: apiStatus.label === "online" && apiStatus.readiness.policy_configured ? "pending" : "blocked",
      actor: "OPA/Rego",
      summary: "Dynamic policy decides run eligibility, tool access, budgets, approvals, and data sensitivity outside the model.",
      data: [
        `fake_data_allowed=${workflow.data_policy.fake_data_allowed}`,
        `regex_business_extraction_allowed=${workflow.data_policy.regex_business_extraction_allowed}`,
        `approval_required_for=${workflow.approval_required_for.join(", ") || "none"}`,
      ],
      reasoning: [
        "Rule-based checks still matter, but policy is separate from model reasoning.",
        "The agent can propose actions; OPA decides whether they are allowed, blocked, or approval-required.",
      ],
      controls: [
        "aegisops.run_eligibility",
        "aegisops.tool_access",
        "aegisops.approvals",
        "aegisops.budget",
        "aegisops.data_sensitivity",
      ],
      source: apiStatus.label === "online" ? "live_api" : "workflow_contract",
    },
    {
      id: `${workflow.id}-approval-output`,
      title: "Approval + Output",
      kind: "approval",
      state: runtimeReady && workflow.enabled ? "pending" : "blocked",
      actor: "Approval service",
      summary: "The workflow ends in an inspectable decision packet, not an uncontrolled autonomous action.",
      data: [
        `workflow_enabled=${workflow.enabled}`,
        `missing_connectors=${workflow.missing_connectors.join(", ") || "none"}`,
        `trace_status=${traceStatus.label}`,
      ],
      reasoning: [
        "Executives see outcome, risk, confidence, and next action.",
        "Architects see policy, tools, memory, and observability.",
        "Engineers see schemas, source paths, hashes, and trace ids.",
      ],
      controls: [
        "External writes remain blocked without approval records.",
        "Captured real trace is required before public outcome playback.",
      ],
      source: "workflow_contract",
    },
  );

  return graphSteps;
}

function buildFlow(
  steps: RuntimeStep[],
  activeStepIndex: number,
  selectedStepId: string,
  accent: string,
): { nodes: Array<Node<FlowNodeData>>; edges: Edge[] } {
  const nodes = steps.map((step, index) => {
    const Icon = stepIcons[step.kind];
    const column = index % 2;
    const row = Math.floor(index / 2);
    return {
      id: step.id,
      type: "default",
      position: { x: column * 285, y: row * 162 },
      data: {
        title: step.title,
        label: (
          <div
            className={[
              "flow-node",
              `flow-node-${step.state}`,
              index === activeStepIndex ? "flow-node-active" : "",
              selectedStepId === step.id ? "flow-node-selected" : "",
            ].join(" ")}
          >
            <div className="flow-node-icon">
              <Icon size={16} />
            </div>
            <div>
              <strong>{step.title}</strong>
              <span>{step.actor}</span>
              <small>{formatSource(step.source)}</small>
            </div>
          </div>
        ),
      },
      draggable: false,
      selectable: true,
      style: {
        background: "transparent",
        border: 0,
        padding: 0,
        width: 210,
      },
    } satisfies Node<FlowNodeData>;
  });

  const edges: Edge[] = steps.slice(0, -1).map((step, index) => ({
    id: `${step.id}-${steps[index + 1]?.id}`,
    source: step.id,
    target: steps[index + 1]?.id ?? step.id,
    animated: index < activeStepIndex,
    markerEnd: { type: MarkerType.ArrowClosed },
    style: {
      stroke: index < activeStepIndex ? accent : "rgba(255,255,255,0.22)",
      strokeWidth: index < activeStepIndex ? 2.5 : 1.5,
    },
  }));

  return { nodes, edges };
}

function buildGates(
  apiStatus: ApiStatus,
  workflowCatalog: WorkflowCatalog,
  workflow: WorkflowDetail,
  traceStatus: WorkflowRunTraceStatus,
  matchingTrace: WorkflowRunTrace | null,
): Gate[] {
  const readiness = apiStatus.label === "online" ? apiStatus.readiness : null;

  return [
    {
      label: "Catalog",
      value: workflowCatalog.source === "api" ? `${workflowCatalog.workflows.length} live` : "mirror",
      state: workflowCatalog.source === "api" ? "open" : "neutral",
    },
    {
      label: "Connectors",
      value: workflow.enabled ? "ready" : workflow.missing_connectors.join(", ") || "not ready",
      state: workflow.enabled ? "open" : "closed",
    },
    {
      label: "Database",
      value: readiness?.database_configured ? "configured" : "pending",
      state: readiness?.database_configured ? "open" : "closed",
    },
    {
      label: "Policy",
      value: readiness?.policy_configured ? "OPA ready" : "OPA pending",
      state: readiness?.policy_configured ? "open" : "closed",
    },
    {
      label: "Live key",
      value: readiness?.live_run_admin_gate_configured ? "configured" : "blocked",
      state: readiness?.live_run_admin_gate_configured ? "neutral" : "closed",
    },
    {
      label: "Trace",
      value: matchingTrace ? matchingTrace.run.status : traceStatus.message,
      state: matchingTrace ? "open" : "neutral",
    },
  ];
}

function isFullRuntimeReady(apiStatus: ApiStatus) {
  return (
    apiStatus.label === "online" &&
    apiStatus.readiness.database_configured &&
    apiStatus.readiness.policy_configured &&
    apiStatus.readiness.live_run_admin_gate_configured
  );
}

function readinessData(apiStatus: ApiStatus) {
  if (apiStatus.label !== "online") {
    return [apiStatus.message];
  }

  return [
    `mode=${apiStatus.readiness.mode}`,
    `database_configured=${apiStatus.readiness.database_configured}`,
    `policy_configured=${apiStatus.readiness.policy_configured}`,
    `live_run_admin_gate_configured=${apiStatus.readiness.live_run_admin_gate_configured}`,
    `registry_counts=${JSON.stringify(apiStatus.readiness.registry_counts)}`,
  ];
}

function startAttemptState(startAttempt: StartAttempt): RuntimeStepState {
  if (startAttempt.state === "success") {
    return "complete";
  }

  if (startAttempt.state === "running") {
    return "running";
  }

  if (startAttempt.state === "blocked" || startAttempt.state === "error") {
    return "blocked";
  }

  return "pending";
}

function LiveAttempt({ attempt }: { attempt: StartAttempt }) {
  const body =
    attempt.state === "success" ||
    attempt.state === "blocked" ||
    attempt.state === "error"
      ? attempt.body
      : undefined;

  return (
    <div className={`live-attempt live-attempt-${attempt.state}`}>
      <strong>{attempt.state === "idle" ? "Live run status" : attempt.state}</strong>
      <p>{attempt.message}</p>
      {body !== undefined ? (
        <pre>{formatUnknown(body)}</pre>
      ) : null}
    </div>
  );
}

function InspectorBlock({
  icon: Icon,
  title,
  children,
}: {
  icon: LucideIcon;
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="inspector-block">
      <div className="inspector-block-title">
        <Icon size={15} />
        <strong>{title}</strong>
      </div>
      <ul>{children}</ul>
    </div>
  );
}

function StateBadge({ state }: { state: RuntimeStepState }) {
  const Icon =
    state === "complete" ? CheckCircle2 : state === "blocked" ? XCircle : state === "running" ? Activity : AlertTriangle;
  return (
    <span className={`state-badge state-${state}`}>
      <Icon size={14} />
      {state.replace("_", " ")}
    </span>
  );
}

function DepthCard({
  icon: Icon,
  title,
  rows,
}: {
  icon: LucideIcon;
  title: string;
  rows: Array<[string, string]>;
}) {
  return (
    <article className="depth-card">
      <div className="depth-card-head">
        <Icon size={18} />
        <h3>{title}</h3>
      </div>
      {rows.length > 0 ? (
        <div className="depth-rows">
          {rows.map(([label, value], index) => (
            <div className="depth-row" key={`${label}-${value}-${index}`}>
              <span>{label}</span>
              <strong>{value}</strong>
            </div>
          ))}
        </div>
      ) : (
        <p>No contract rows defined.</p>
      )}
    </article>
  );
}

function GatePill({ gate }: { gate: Gate }) {
  const Icon =
    gate.state === "open" ? CheckCircle2 : gate.state === "closed" ? AlertTriangle : Activity;

  return (
    <span className={`gate-pill gate-${gate.state}`}>
      <Icon size={14} />
      <strong>{gate.label}</strong>
      <span>{gate.value}</span>
    </span>
  );
}

function compactInput(input: Record<string, string>) {
  return Object.fromEntries(
    Object.entries(input).filter(([, value]) => value.trim().length > 0),
  );
}

async function readResponseBody(response: Response) {
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return response.json();
  }

  return response.text();
}

function formatSource(source: RuntimeStep["source"]) {
  if (source === "live_trace") {
    return "live trace";
  }

  if (source === "live_api") {
    return "live API";
  }

  return "workflow contract";
}

function formatUnknown(value: unknown) {
  if (typeof value === "string") {
    return value;
  }

  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function schemaSummary(schema: Record<string, unknown>) {
  const required = Array.isArray(schema.required)
    ? schema.required.filter((item): item is string => typeof item === "string")
    : [];
  const properties =
    schema.properties && typeof schema.properties === "object"
      ? Object.keys(schema.properties)
      : [];

  if (required.length > 0) {
    return `required=${required.join(", ")}`;
  }

  if (properties.length > 0) {
    return `properties=${properties.join(", ")}`;
  }

  return "object schema";
}

function readUpstreamResult(
  value: unknown,
): { upstream_ok: boolean; upstream_status: number } | null {
  if (!value || typeof value !== "object") {
    return null;
  }

  const record = value as Record<string, unknown>;
  if (
    typeof record.upstream_ok === "boolean" &&
    typeof record.upstream_status === "number"
  ) {
    return {
      upstream_ok: record.upstream_ok,
      upstream_status: record.upstream_status,
    };
  }

  return null;
}
