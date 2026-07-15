"use client";

import {
  Activity,
  AlertTriangle,
  Boxes,
  BrainCircuit,
  CheckCircle2,
  CircleDot,
  Code2,
  Database,
  FileCode2,
  FileText,
  Gauge,
  GitPullRequest,
  KeyRound,
  Layers3,
  LockKeyhole,
  MessageSquare,
  Network,
  PlayCircle,
  Send,
  Server,
  ShieldCheck,
  Sparkles,
  TimerReset,
  UserRound,
  Workflow,
  XCircle,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { motion, useReducedMotion } from "framer-motion";
import { useMemo, useState, type ReactNode } from "react";
import {
  Background,
  Controls,
  MarkerType,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type {
  ApiReadiness,
  ApiStatus,
  WorkflowRunTrace,
  WorkflowRunTraceEvalStatus,
  WorkflowRunTraceStatus,
} from "@/lib/api";
import { MultiAgentOrchestration } from "@/components/multi-agent-orchestration";
import type {
  WorkflowCatalog,
  WorkflowDetail,
  WorkflowStatus,
} from "@/lib/workflows";

type CommandCenterProps = {
  apiStatus: ApiStatus;
  workflowCatalog: WorkflowCatalog;
  workflowRunTrace: WorkflowRunTraceStatus;
  workflowRunTraceEval: WorkflowRunTraceEvalStatus;
};

type NavItem = {
  label: string;
  icon: LucideIcon;
};

type GraphNodeData = Record<string, unknown> & {
  label: ReactNode;
  title: string;
  layer: string;
  state: string;
  evidence: string[];
  policy: string;
};

type WorkflowNode = Node<GraphNodeData>;
type WorkflowEdge = Edge;

type GraphInspector = {
  id: string;
  title: string;
  layer: string;
  state: string;
  evidence: string[];
  policy: string;
};

type GateState = "open" | "closed" | "neutral";

type ProposalReviewModel = {
  badge: string;
  route: string;
  routeState: GateState;
  routeNote: string;
  readiness: Array<{
    label: string;
    value: string;
    state: GateState;
  }>;
  requestContract: Array<{
    label: string;
    value: string;
  }>;
  outputContract: Array<{
    label: string;
    value: string;
  }>;
  approvalRoute: string;
  approvalPersistence: Array<{
    label: string;
    value: string;
  }>;
  approvalStops: string[];
  traceReadout: TraceReadoutModel;
};

type TraceReadoutModel = {
  badge: string;
  route: string;
  state: GateState;
  runId: string;
  message: string;
  outcomes: Array<{
    label: string;
    value: string;
    state: GateState;
  }>;
  records: Array<{
    label: string;
    value: string;
  }>;
  events: Array<{
    label: string;
    value: string;
    state: GateState;
  }>;
};

type SupportRuntimeStage = {
  title: string;
  icon: LucideIcon;
  layer: string;
  tool: string;
  artifact: string;
  policy: string;
  state: GateState;
};

const navItems: NavItem[] = [
  { label: "Portfolio", icon: Boxes },
  { label: "Command", icon: Gauge },
  { label: "Agents", icon: Network },
  { label: "Graph", icon: Workflow },
  { label: "Review", icon: BrainCircuit },
  { label: "Evidence", icon: Database },
  { label: "Policy", icon: LockKeyhole },
  { label: "Trace", icon: Activity },
  { label: "Code", icon: Code2 },
];

const statusCopy: Record<WorkflowStatus, string> = {
  planned: "Planned",
  ready: "Ready",
  gated: "Gated",
  disabled: "Disabled",
};

const statusIcon: Record<WorkflowStatus, LucideIcon> = {
  planned: CircleDot,
  ready: CheckCircle2,
  gated: AlertTriangle,
  disabled: XCircle,
};

const apiStatusLabel = {
  not_configured: "API not deployed",
  online: "API online",
  unreachable: "API unreachable",
} satisfies Record<ApiStatus["label"], string>;

const runtimeModes = [
  {
    title: "Rule-based",
    engine: "Typed deterministic gates",
    cost: "$0 model cost",
    scope: "Schema validation, status checks, connector readiness",
  },
  {
    title: "Dynamic policy",
    engine: "OPA/Rego",
    cost: "$0 model cost",
    scope: "Run eligibility, budget, tool access, approval routing",
  },
  {
    title: "AI workflow",
    engine: "Responses API",
    cost: "metered",
    scope: "Structured model calls, retrieval summaries, evaluator passes",
  },
  {
    title: "Agentic",
    engine: "LangGraph + MCP",
    cost: "bounded",
    scope: "Stateful planning, typed tools, interrupts, memory, replay",
  },
];

export function CommandCenter({
  apiStatus,
  workflowCatalog,
  workflowRunTrace,
  workflowRunTraceEval,
}: CommandCenterProps) {
  const shouldReduceMotion = useReducedMotion();
  const workflows = workflowCatalog.workflows;
  const [activeNav, setActiveNav] = useState(navItems[0].label);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState(
    workflows[0]?.id ?? "",
  );
  const [selectedNodeId, setSelectedNodeId] = useState("source");

  const selectedWorkflow = useMemo(
    () =>
      workflows.find((workflow) => workflow.id === selectedWorkflowId) ??
      workflows[0],
    [selectedWorkflowId, workflows],
  );

  const graph = useMemo(
    () => createWorkflowGraph(selectedWorkflow),
    [selectedWorkflow],
  );
  const activeNodeId = graph.inspectors.some(
    (node) => node.id === selectedNodeId,
  )
    ? selectedNodeId
    : "source";
  const selectedNode =
    graph.inspectors.find((node) => node.id === activeNodeId) ??
    graph.inspectors[0];
  const domainData = useMemo(() => createDomainChart(workflows), [workflows]);
  const connectorData = useMemo(
    () => createConnectorChart(workflows),
    [workflows],
  );
  const apiBacked =
    workflowCatalog.source === "api" && apiStatus.label === "online";
  const readiness = apiStatus.label === "online" ? apiStatus.readiness : null;
  const proposalReview = useMemo(
    () =>
      createProposalReview(
        selectedWorkflow,
        apiBacked,
        readiness,
        workflowRunTrace,
      ),
    [apiBacked, readiness, selectedWorkflow, workflowRunTrace],
  );
  const enabledCount = workflows.filter((workflow) => workflow.enabled).length;
  const connectorCount = new Set(
    workflows.flatMap((workflow) => workflow.required_connectors),
  ).size;
  const approvalCount = workflows.reduce(
    (total, workflow) => total + workflow.approval_required_for.length,
    0,
  );
  const canAttemptReplay = apiBacked && selectedWorkflow.enabled;

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">
            <BrainCircuit size={22} />
          </div>
          <div>
            <div>AegisOps</div>
            <div className="topbar-meta">Agentic Workflow Command Center</div>
          </div>
        </div>
        <div className="topbar-meta">
          <span className="status-pill status-live">
            <span className="dot" />
            Phase 4 cockpit
          </span>
          <span className="status-pill status-muted">
            <Server size={14} />
            {apiStatusLabel[apiStatus.label]}
          </span>
          <span className="status-pill status-muted">
            <Database size={14} />
            {workflowCatalog.source === "api"
              ? "Live registry"
              : "Repository registry"}
          </span>
        </div>
      </header>

      <div className="command-layout">
        <aside className="sidebar">
          <section className="nav-section">
            <div className="nav-title">Surfaces</div>
            {navItems.map(({ label, icon: Icon }) => (
              <button
                className={`nav-item ${activeNav === label ? "active" : ""}`}
                key={label}
                type="button"
                onClick={() => setActiveNav(label)}
              >
                <Icon size={17} />
                <span>{label}</span>
              </button>
            ))}
          </section>

          <section className="nav-section">
            <div className="nav-title">Execution Modes</div>
            <div className="mode-stack">
              {runtimeModes.map((mode) => (
                <div className="mode-row" key={mode.title}>
                  <span>{mode.title}</span>
                  <strong>{mode.cost}</strong>
                </div>
              ))}
            </div>
          </section>
        </aside>

        <section className="main cockpit">
          <section className="mission-strip">
            <div className="mission-copy">
              <div className="eyebrow">Production-grade agentic AI</div>
              <h1>Every workflow layer visible, gated, and inspectable.</h1>
              <p>
                The command center separates deterministic rules, dynamic
                policy, AI workflow calls, and agentic tool loops before any
                live action is allowed.
              </p>
            </div>
            <div className="mission-metrics" aria-label="Architecture metrics">
              <Metric
                value={String(workflows.length)}
                label="workflow configs"
              />
              <Metric value={String(enabledCount)} label="connector-ready" />
              <Metric
                value={String(connectorCount)}
                label="connector classes"
              />
              <Metric value={String(approvalCount)} label="approval gates" />
            </div>
          </section>

          <section className="ops-grid">
            <section className="panel portfolio-panel">
              <PanelHeader
                icon={Sparkles}
                title="Enterprise Workflow Portfolio"
                badge={workflowCatalog.message}
              />
              <div className="portfolio">
                {workflows.map((workflow, index) => (
                  <WorkflowCard
                    key={workflow.id}
                    workflow={workflow}
                    index={index}
                    selected={workflow.id === selectedWorkflow.id}
                    shouldReduceMotion={shouldReduceMotion}
                    onSelect={() => setSelectedWorkflowId(workflow.id)}
                  />
                ))}
              </div>
            </section>

            <section className="panel workflow-inspector">
              <PanelHeader
                icon={GitPullRequest}
                title={selectedWorkflow.name}
                badge={statusCopy[selectedWorkflow.status]}
              />
              <div className="workflow-detail">
                <ReadinessBlock
                  workflow={selectedWorkflow}
                  apiBacked={apiBacked}
                />
                <div className="run-control-grid">
                  <RunButton
                    icon={PlayCircle}
                    label="Replay run"
                    enabled={false}
                    reason={
                      canAttemptReplay
                        ? "Captured real-run source id required"
                        : (selectedWorkflow.disabled_reason ??
                          "Registry or connector gate is closed")
                    }
                  />
                  <RunButton
                    icon={ShieldCheck}
                    label="Live run"
                    enabled={false}
                    reason="Disabled until OPA, database, connectors, and approval queue are live"
                  />
                </div>
              </div>
            </section>
          </section>

          <section className="panel runtime-panel">
            <PanelHeader
              icon={Layers3}
              title="Execution Segmentation"
              badge="clear boundaries"
            />
            <div className="runtime-grid">
              {runtimeModes.map((mode, index) => (
                <motion.article
                  className="runtime-card"
                  key={mode.title}
                  initial={shouldReduceMotion ? false : { opacity: 0, y: 16 }}
                  animate={
                    shouldReduceMotion ? undefined : { opacity: 1, y: 0 }
                  }
                  transition={{ delay: 0.04 * index, duration: 0.3 }}
                >
                  <div className="runtime-index">
                    {String(index + 1).padStart(2, "0")}
                  </div>
                  <div>
                    <h2>{mode.title}</h2>
                    <strong>{mode.engine}</strong>
                    <span>{mode.scope}</span>
                  </div>
                  <em>{mode.cost}</em>
                </motion.article>
              ))}
            </div>
          </section>

          <MultiAgentOrchestration
            workflows={workflows}
            selectedWorkflowId={selectedWorkflow.id}
            shouldReduceMotion={shouldReduceMotion}
            onSelectWorkflow={setSelectedWorkflowId}
          />

          <SupportEscalationPanel
            workflow={workflows.find(
              (workflow) => workflow.id === "customer_support_escalation",
            )}
            selected={selectedWorkflow.id === "customer_support_escalation"}
            shouldReduceMotion={shouldReduceMotion}
            onSelectWorkflow={setSelectedWorkflowId}
          />

          <section className="panel graph-panel">
            <PanelHeader
              icon={Network}
              title="Agent Graph"
              badge={selectedWorkflow.id}
            />
            <div className="graph-shell">
              <div className="graph-frame">
                <ReactFlow
                  nodes={graph.nodes}
                  edges={graph.edges}
                  fitView
                  fitViewOptions={{ padding: 0.24 }}
                  nodesDraggable={false}
                  nodesConnectable={false}
                  elementsSelectable
                  panOnScroll
                  proOptions={{ hideAttribution: true }}
                  onNodeClick={(_, node) => setSelectedNodeId(node.id)}
                >
                  <Background color="rgba(255,255,255,0.16)" gap={22} />
                  <Controls showInteractive={false} />
                </ReactFlow>
              </div>
              <aside className="node-inspector">
                <div className="inspector-kicker">{selectedNode.layer}</div>
                <h2>{selectedNode.title}</h2>
                <p>{selectedNode.state}</p>
                <div className="lens-list compact">
                  <LensRow label="Policy" value={selectedNode.policy} />
                  <LensRow
                    label="Evidence"
                    value={selectedNode.evidence.join(", ")}
                  />
                </div>
              </aside>
            </div>
          </section>

          <ProposalReviewPanel
            review={proposalReview}
            traceEval={workflowRunTraceEval}
          />

          <section className="telemetry-grid">
            <section className="panel chart-panel">
              <PanelHeader
                icon={Gauge}
                title="Portfolio Distribution"
                badge="from configs"
              />
              <div className="chart-frame">
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={domainData}>
                    <CartesianGrid
                      stroke="rgba(255,255,255,0.08)"
                      vertical={false}
                    />
                    <XAxis
                      dataKey="name"
                      tickLine={false}
                      axisLine={false}
                      stroke="#9aa5b8"
                    />
                    <YAxis
                      allowDecimals={false}
                      tickLine={false}
                      axisLine={false}
                      stroke="#9aa5b8"
                    />
                    <Tooltip
                      content={<ChartTooltip />}
                      cursor={{ fill: "rgba(255,255,255,0.04)" }}
                    />
                    <Bar
                      dataKey="workflows"
                      fill="#35c2a7"
                      radius={[6, 6, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </section>

            <section className="panel chart-panel">
              <PanelHeader
                icon={KeyRound}
                title="Connector Demand"
                badge="real integrations"
              />
              <div className="chart-frame">
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={connectorData}>
                    <CartesianGrid
                      stroke="rgba(255,255,255,0.08)"
                      vertical={false}
                    />
                    <XAxis
                      dataKey="name"
                      tickLine={false}
                      axisLine={false}
                      stroke="#9aa5b8"
                    />
                    <YAxis
                      allowDecimals={false}
                      tickLine={false}
                      axisLine={false}
                      stroke="#9aa5b8"
                    />
                    <Tooltip
                      content={<ChartTooltip />}
                      cursor={{ fill: "rgba(255,255,255,0.04)" }}
                    />
                    <Bar
                      dataKey="workflows"
                      fill="#78a6ff"
                      radius={[6, 6, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </section>

            <section className="panel evidence-panel">
              <PanelHeader
                icon={Database}
                title="Evidence Board"
                badge="empty until real runs"
              />
              <div className="evidence-table">
                {selectedWorkflow.required_connectors.map((connector) => (
                  <div className="evidence-row" key={connector}>
                    <span>{connector}</span>
                    <strong>
                      {selectedWorkflow.missing_connectors.includes(connector)
                        ? "Connector gated"
                        : "Connector ready"}
                    </strong>
                    <em>
                      {matchingScopes(selectedWorkflow, connector).join(", ") ||
                        "Scope mapping pending"}
                    </em>
                  </div>
                ))}
              </div>
            </section>
          </section>

          <section className="bottom-grid">
            <section className="panel">
              <PanelHeader
                icon={LockKeyhole}
                title="Policy Lens"
                badge="OPA first"
              />
              <div className="lens-list">
                <LensRow
                  label="Run eligibility"
                  value="workflow status, connector readiness, replay source, budget envelope"
                />
                <LensRow
                  label="Replay allowed"
                  value={String(
                    selectedWorkflow.data_policy.replay_allowed_from_real_runs,
                  )}
                />
                <LensRow
                  label="Fake data"
                  value={String(selectedWorkflow.data_policy.fake_data_allowed)}
                />
                <LensRow
                  label="Regex extraction"
                  value={String(
                    selectedWorkflow.data_policy
                      .regex_business_extraction_allowed,
                  )}
                />
                <LensRow
                  label="Approval actions"
                  value={selectedWorkflow.approval_required_for
                    .map(humanize)
                    .join(", ")}
                />
              </div>
            </section>

            <section className="panel">
              <PanelHeader
                icon={TimerReset}
                title="Trace Timeline"
                badge="not executed"
              />
              <div className="timeline">
                {[
                  "run_start",
                  "policy_decision",
                  "graph_checkpoint",
                  "tool_call",
                  "approval_request",
                ].map((event, index) => (
                  <div className="timeline-row" key={event}>
                    <span>{String(index + 1).padStart(2, "0")}</span>
                    <strong>{humanize(event)}</strong>
                    <em>
                      {index < 2 ? "implemented gate" : "waiting for runtime"}
                    </em>
                  </div>
                ))}
              </div>
            </section>

            <section className="panel code-panel">
              <PanelHeader
                icon={FileCode2}
                title="Code Lens"
                badge="workflow yaml"
              />
              <pre>{formatWorkflowConfig(selectedWorkflow)}</pre>
            </section>
          </section>
        </section>
      </div>
    </main>
  );
}

function SupportEscalationPanel({
  workflow,
  selected,
  shouldReduceMotion,
  onSelectWorkflow,
}: {
  workflow: WorkflowDetail | undefined;
  selected: boolean;
  shouldReduceMotion: boolean | null;
  onSelectWorkflow: (workflowId: string) => void;
}) {
  const stages: SupportRuntimeStage[] = [
    {
      title: "Ticket Read",
      icon: MessageSquare,
      layer: "read tool",
      tool: "support_ticket_read",
      artifact: "support ticket hash",
      policy: "tickets:read only",
      state: "open",
    },
    {
      title: "Customer Context",
      icon: UserRound,
      layer: "read tool",
      tool: "crm_customer_profile_read",
      artifact: "redacted CRM metadata",
      policy: "customers:read only",
      state: "open",
    },
    {
      title: "Knowledge Search",
      icon: FileText,
      layer: "RAG retrieval",
      tool: "knowledge_base_search",
      artifact: "cited KB documents",
      policy: "knowledge:read only",
      state: "open",
    },
    {
      title: "Draft Contract",
      icon: BrainCircuit,
      layer: "structured output",
      tool: "include_draft=true",
      artifact: "response_draft.v1",
      policy: "citations required",
      state: "neutral",
    },
    {
      title: "Memory Policy",
      icon: Database,
      layer: "memory guardrail",
      tool: "memory_records",
      artifact: "redacted run memory",
      policy: "30d run scope",
      state: "open",
    },
    {
      title: "Approval Decision",
      icon: ShieldCheck,
      layer: "OPA + human",
      tool: "approval decision route",
      artifact: "approved or rejected row",
      policy: "no self approval",
      state: "neutral",
    },
    {
      title: "Send Authorization",
      icon: KeyRound,
      layer: "disabled contract",
      tool: "customer_message_send",
      artifact: "blocked tool call",
      policy: "approved draft hash",
      state: "closed",
    },
    {
      title: "Send Gate",
      icon: Send,
      layer: "blocked write",
      tool: "send adapter unavailable",
      artifact: "no customer message",
      policy: "external action disabled",
      state: "closed",
    },
  ];
  const missingConnectors = workflow?.missing_connectors ?? [
    "support_system",
    "crm",
    "knowledge_base",
  ];

  return (
    <section className="panel support-panel">
      <PanelHeader
        icon={MessageSquare}
        title="Support Escalation Runtime"
        badge={workflow ? statusCopy[workflow.status] : "Not in registry"}
      />
      <div className="support-runtime">
        <div className="support-runtime-brief">
          <div>
            <div className="contract-title">Route Stack</div>
            <code>
              POST /workflow-runs/{"{run_id}"}/customer-support-escalation/context
            </code>
            <code>
              POST /workflow-runs/{"{run_id}"}
              /customer-support-escalation/approval-review
            </code>
            <code>
              POST /workflow-runs/{"{run_id}"}
              /customer-support-escalation/approvals/{"{approval_id}"}/decision
            </code>
            <code>
              POST /workflow-runs/{"{run_id}"}
              /customer-support-escalation/message-send/authorize
            </code>
            <code>GET /workflow-runs/{"{run_id}"}/evals/trace</code>
          </div>
          <button
            className="focus-workflow-button"
            type="button"
            disabled={!workflow || selected}
            onClick={() => workflow && onSelectWorkflow(workflow.id)}
          >
            {selected ? "Support selected" : "Focus support workflow"}
          </button>
        </div>

        <div className="support-stage-grid">
          {stages.map((stage, index) => {
            const Icon = stage.icon;
            return (
              <motion.div
                className={`support-stage support-stage-${stage.state}`}
                key={stage.title}
                initial={shouldReduceMotion ? false : { opacity: 0, y: 12 }}
                animate={
                  shouldReduceMotion ? undefined : { opacity: 1, y: 0 }
                }
                transition={{ delay: index * 0.03, duration: 0.24 }}
              >
                <div className="support-stage-icon">
                  <Icon size={18} />
                </div>
                <div>
                  <strong>{stage.title}</strong>
                  <span>{stage.layer}</span>
                </div>
                <em>{stage.tool}</em>
                <small>{stage.artifact}</small>
                <small>{stage.policy}</small>
              </motion.div>
            );
          })}
        </div>

        <div className="support-contract-grid">
          <div className="support-contract-card">
            <span>Connector Gate</span>
            <strong>
              {missingConnectors.length === 0
                ? "support, CRM, and KB configured"
                : missingConnectors.join(", ")}
            </strong>
          </div>
          <div className="support-contract-card">
            <span>Evidence Storage</span>
            <strong>hash-only records with redacted support and CRM metadata</strong>
          </div>
          <div className="support-contract-card">
            <span>Memory Policy</span>
            <strong>run-scoped, 30-day retention, no raw customer payloads</strong>
          </div>
          <div className="support-contract-card">
            <span>Draft Grounding</span>
            <strong>response citations must come from KB source URIs</strong>
          </div>
          <div className="support-contract-card">
            <span>Trace Evals</span>
            <strong>deterministic grounding, redaction, memory, send, and cost checks</strong>
          </div>
          <div className="support-contract-card blocked">
            <span>External Action</span>
            <strong>customer message, refund, and account change remain disabled</strong>
          </div>
        </div>
      </div>
    </section>
  );
}

function ProposalReviewPanel({
  review,
  traceEval,
}: {
  review: ProposalReviewModel;
  traceEval: WorkflowRunTraceEvalStatus;
}) {
  return (
    <section className="panel proposal-panel">
      <PanelHeader
        icon={BrainCircuit}
        title="Proposal Review"
        badge={review.badge}
      />
      <div className="proposal-review">
        <div className={`proposal-route route-${review.routeState}`}>
          <span>Run-scoped route</span>
          <code>{review.route}</code>
          <p>{review.routeNote}</p>
        </div>

        <div className="proposal-readiness">
          {review.readiness.map((item) => (
            <div className="review-check" key={item.label}>
              <span className={`review-state ${item.state}`} />
              <div>
                <strong>{item.label}</strong>
                <em>{item.value}</em>
              </div>
            </div>
          ))}
        </div>

        <div className="proposal-contract">
          <div className="contract-title">Request Contract</div>
          {review.requestContract.map((item) => (
            <ContractRow
              key={item.label}
              label={item.label}
              value={item.value}
            />
          ))}
        </div>

        <div className="proposal-contract output-contract">
          <div className="contract-title">Planner and Evaluator Output</div>
          {review.outputContract.map((item) => (
            <ContractRow
              key={item.label}
              label={item.label}
              value={item.value}
            />
          ))}
        </div>

        <div className="approval-persistence">
          <div className="contract-title">Approval Review Persistence</div>
          <code>{review.approvalRoute}</code>
          {review.approvalPersistence.map((item) => (
            <ContractRow
              key={item.label}
              label={item.label}
              value={item.value}
            />
          ))}
        </div>

        <TraceReadout readout={review.traceReadout} />

        <TraceEvalPanel traceEval={traceEval} />

        <div className="approval-review">
          <div className="contract-title">Approval Stops</div>
          <div className="approval-stop-list">
            {review.approvalStops.map((stop, index) => (
              <div className="approval-stop" key={stop}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <strong>{humanize(stop)}</strong>
                <em>
                  write action blocked until policy and review records approve
                  it
                </em>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function TraceEvalPanel({
  traceEval,
}: {
  traceEval: WorkflowRunTraceEvalStatus;
}) {
  if (traceEval.label !== "loaded") {
    return (
      <div className="trace-eval trace-eval-neutral">
        <div className="trace-readout-header">
          <div>
            <div className="contract-title">Executable Eval Results</div>
            <code>GET /workflow-runs/{"{run_id}"}/evals/trace</code>
          </div>
          <span className="trace-badge trace-badge-neutral">
            {traceEval.label === "not_configured" ? "run id required" : traceEval.label}
          </span>
        </div>
        <p>{traceEval.message}</p>
      </div>
    );
  }

  const statusState = evalStatusToGateState(traceEval.evals.overall_status);

  return (
    <div className={`trace-eval trace-eval-${statusState}`}>
      <div className="trace-readout-header">
        <div>
          <div className="contract-title">Executable Eval Results</div>
          <code>GET /workflow-runs/{"{run_id}"}/evals/trace</code>
        </div>
        <span className={`trace-badge trace-badge-${statusState}`}>
          {traceEval.evals.overall_status} / {Math.round(traceEval.evals.score * 100)}%
        </span>
      </div>
      <p>{traceEval.message}</p>
      <div className="trace-eval-grid">
        {traceEval.evals.checks.map((check) => {
          const state = evalStatusToGateState(check.status);
          return (
            <div className={`trace-eval-check eval-${state}`} key={check.id}>
              <span className={`review-state ${state}`} />
              <strong>{check.label}</strong>
              <em>{check.details}</em>
              <small>{Math.round(check.score * 100)}% score</small>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function TraceReadout({ readout }: { readout: TraceReadoutModel }) {
  return (
    <div className={`trace-readout trace-${readout.state}`}>
      <div className="trace-readout-header">
        <div>
          <div className="contract-title">Live Trace State</div>
          <code>{readout.route}</code>
        </div>
        <span className={`trace-badge trace-badge-${readout.state}`}>
          {readout.badge}
        </span>
      </div>
      <p>{readout.message}</p>

      <div className="trace-outcome-grid">
        {readout.outcomes.map((outcome) => (
          <div className={`trace-outcome outcome-${outcome.state}`} key={outcome.label}>
            <span className={`review-state ${outcome.state}`} />
            <strong>{outcome.label}</strong>
            <em>{outcome.value}</em>
          </div>
        ))}
      </div>

      <div className="trace-record-strip">
        {readout.records.map((record) => (
          <div className="trace-record" key={record.label}>
            <span>{record.label}</span>
            <strong>{record.value}</strong>
          </div>
        ))}
      </div>

      <div className="trace-events">
        {readout.events.map((event) => (
          <div className={`trace-event event-${event.state}`} key={`${event.label}-${event.value}`}>
            <span>{event.label}</span>
            <strong>{event.value}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}

function ContractRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="contract-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function WorkflowCard({
  workflow,
  index,
  selected,
  shouldReduceMotion,
  onSelect,
}: {
  workflow: WorkflowDetail;
  index: number;
  selected: boolean;
  shouldReduceMotion: boolean | null;
  onSelect: () => void;
}) {
  const Icon = statusIcon[workflow.status];
  return (
    <motion.button
      className={`workflow-card ${selected ? "selected" : ""}`}
      type="button"
      onClick={onSelect}
      initial={shouldReduceMotion ? false : { opacity: 0, y: 16 }}
      animate={shouldReduceMotion ? undefined : { opacity: 1, y: 0 }}
      transition={{ delay: 0.03 * index, duration: 0.28 }}
      whileHover={shouldReduceMotion ? undefined : { y: -3 }}
    >
      <div className="workflow-title">
        <Icon size={18} />
        <span>{workflow.name}</span>
      </div>
      <div className="workflow-copy">
        {humanize(workflow.domain)} ·{" "}
        {workflow.patterns.map(humanize).join(" / ")}
      </div>
      <div className={`workflow-stage stage-${workflow.status}`}>
        {workflow.enabled ? "enabled" : statusCopy[workflow.status]}
      </div>
    </motion.button>
  );
}

function ReadinessBlock({
  workflow,
  apiBacked,
}: {
  workflow: WorkflowDetail;
  apiBacked: boolean;
}) {
  return (
    <div className="readiness-grid">
      <ReadinessItem
        label="Registry"
        value={apiBacked ? "API backed" : "Repository backed"}
        state={apiBacked}
      />
      <ReadinessItem
        label="Workflow"
        value={statusCopy[workflow.status]}
        state={workflow.status === "ready"}
      />
      <ReadinessItem
        label="Connectors"
        value={
          workflow.missing_connectors.length === 0
            ? "Configured"
            : workflow.missing_connectors.join(", ")
        }
        state={workflow.missing_connectors.length === 0}
      />
      <ReadinessItem
        label="Autonomy"
        value={humanize(workflow.default_autonomy)}
        state={workflow.default_autonomy !== "autonomous"}
      />
    </div>
  );
}

function ReadinessItem({
  label,
  value,
  state,
}: {
  label: string;
  value: string;
  state: boolean;
}) {
  return (
    <div className="readiness-item">
      <span>{label}</span>
      <strong>{value}</strong>
      <em className={state ? "gate-open" : "gate-closed"}>
        {state ? "open" : "closed"}
      </em>
    </div>
  );
}

function RunButton({
  icon: Icon,
  label,
  enabled,
  reason,
}: {
  icon: LucideIcon;
  label: string;
  enabled: boolean;
  reason: string;
}) {
  return (
    <button className="run-button" type="button" disabled={!enabled}>
      <span>
        <Icon size={17} />
        {label}
      </span>
      <em>{reason}</em>
    </button>
  );
}

function Metric({ value, label }: { value: string; label: string }) {
  return (
    <motion.div className="metric" whileHover={{ y: -3 }}>
      <div className="metric-value">{value}</div>
      <div className="metric-label">{label}</div>
    </motion.div>
  );
}

function PanelHeader({
  icon: Icon,
  title,
  badge,
}: {
  icon: LucideIcon;
  title: string;
  badge: string;
}) {
  return (
    <div className="panel-header">
      <div className="panel-title">
        <Icon size={18} />
        {title}
      </div>
      <span className="badge">{badge}</span>
    </div>
  );
}

function LensRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="lens-row">
      <span className="lens-label">{label}</span>
      <span className="lens-value">{value}</span>
    </div>
  );
}

function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ value?: number; name?: string }>;
  label?: string;
}) {
  if (!active || !payload?.length) {
    return null;
  }

  return (
    <div className="chart-tooltip">
      <strong>{label}</strong>
      {payload.map((item) => (
        <span key={item.name}>
          {item.name}: {item.value}
        </span>
      ))}
    </div>
  );
}

function createWorkflowGraph(workflow: WorkflowDetail): {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  inspectors: GraphInspector[];
} {
  const inspectors: GraphInspector[] = [
    {
      id: "source",
      title: "Real Source Intake",
      layer: "deterministic",
      state: `Requires ${workflow.required_connectors.join(", ")} before any run can start.`,
      evidence: workflow.required_scopes,
      policy:
        "Connector readiness is checked before OPA and before persistence.",
    },
    {
      id: "policy",
      title: "Run Eligibility",
      layer: "dynamic policy",
      state:
        "OPA decides allow, deny, or approval-required for the run-start gate.",
      evidence: [
        "aegisops.run_eligibility",
        "budget envelope",
        "replay source",
      ],
      policy: "No model decides whether the run is allowed.",
    },
    {
      id: "graph",
      title: "LangGraph Runtime",
      layer: "AI workflow",
      state: `Configured patterns: ${workflow.patterns.map(humanize).join(", ")}.`,
      evidence: workflow.visual_surfaces,
      policy: "Graph execution waits until durable run creation succeeds.",
    },
    {
      id: "proposal",
      title: "Proposal and Evaluator",
      layer: "structured AI review",
      state:
        workflow.id === "engineering_issue_to_pr"
          ? "OpenAI Responses emits typed patch-plan and evaluation contracts when include_proposal=true."
          : "Workflow-specific proposal and evaluator contracts are planned from the registry patterns.",
      evidence:
        workflow.id === "engineering_issue_to_pr"
          ? ["IssueToPrProposal", "IssueToPrEvaluation", "model_calls"]
          : workflow.patterns,
      policy:
        "Planner output cannot enable writes; approval_required remains true.",
    },
    {
      id: "tools",
      title: "Typed Tool Plane",
      layer: "agentic",
      state:
        "MCP contracts will bind every tool call to schemas, scopes, and risk classes.",
      evidence: workflow.required_connectors,
      policy:
        "Each tool call will require tool-access policy before execution.",
    },
    {
      id: "memory",
      title: "Memory and Evidence",
      layer: "data plane",
      state:
        "Postgres and pgvector store checkpoints, evidence, memory records, and trace links.",
      evidence: ["workflow_runs", "evidence_records", "memory_records"],
      policy: "Memory writes require sensitivity and retention checks.",
    },
    {
      id: "approval",
      title: "Human Approval",
      layer: "governance",
      state: `${workflow.approval_required_for.length} workflow actions require approval.`,
      evidence: workflow.approval_required_for,
      policy: "Sensitive writes are approval-gated by default.",
    },
  ];

  const nodePositions = [
    ["source", 0, 158],
    ["policy", 170, 80],
    ["graph", 340, 158],
    ["proposal", 520, 80],
    ["tools", 700, 80],
    ["memory", 520, 236],
    ["approval", 880, 158],
  ] as const;

  return {
    inspectors,
    nodes: nodePositions.map(([id, x, y]) => {
      const inspector = inspectors.find((item) => item.id === id);
      return {
        id,
        type: "default",
        position: { x, y },
        data: {
          label: (
            <GraphNodeLabel
              active={workflow.enabled}
              title={inspector?.title ?? id}
              layer={inspector?.layer ?? ""}
            />
          ),
          title: inspector?.title ?? id,
          layer: inspector?.layer ?? "",
          state: inspector?.state ?? "",
          evidence: inspector?.evidence ?? [],
          policy: inspector?.policy ?? "",
        },
        className: `flow-node flow-${id}`,
      };
    }),
    edges: [
      edge("source", "policy"),
      edge("policy", "graph"),
      edge("graph", "proposal"),
      edge("graph", "memory"),
      edge("proposal", "tools"),
      edge("proposal", "approval"),
      edge("tools", "approval"),
      edge("memory", "approval"),
    ],
  };
}

function GraphNodeLabel({
  active,
  title,
  layer,
}: {
  active: boolean;
  title: string;
  layer: string;
}) {
  return (
    <div className="graph-node-label">
      <span className={active ? "node-dot node-open" : "node-dot"} />
      <strong>{title}</strong>
      <em>{layer}</em>
    </div>
  );
}

function edge(source: string, target: string): WorkflowEdge {
  return {
    id: `${source}-${target}`,
    source,
    target,
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color: "#7f8da4",
    },
    style: {
      stroke: "#7f8da4",
      strokeWidth: 1.5,
    },
  };
}

function createDomainChart(workflows: WorkflowDetail[]) {
  return [
    ...countBy(
      workflows.map((workflow) => humanize(workflow.domain)),
    ).entries(),
  ]
    .map(([name, workflowsCount]) => ({ name, workflows: workflowsCount }))
    .sort((a, b) => b.workflows - a.workflows)
    .slice(0, 6);
}

function createConnectorChart(workflows: WorkflowDetail[]) {
  return [
    ...countBy(
      workflows.flatMap((workflow) => workflow.required_connectors),
    ).entries(),
  ]
    .map(([name, workflowsCount]) => ({ name, workflows: workflowsCount }))
    .sort((a, b) => b.workflows - a.workflows)
    .slice(0, 6);
}

function createProposalReview(
  workflow: WorkflowDetail,
  apiBacked: boolean,
  readiness: ApiReadiness | null,
  workflowRunTrace: WorkflowRunTraceStatus,
): ProposalReviewModel {
  const traceReadout = createTraceReadout(workflow, workflowRunTrace);

  if (workflow.id !== "engineering_issue_to_pr") {
    return {
      badge: "workflow contract planned",
      route: "workflow-specific run route pending",
      routeState: "neutral",
      routeNote: `${workflow.name} is present in the production registry, with runtime implementation still gated by the build plan.`,
      readiness: [
        {
          label: "Registry source",
          value: apiBacked ? "live API registry" : "repository mirror",
          state: apiBacked ? "open" : "neutral",
        },
        {
          label: "Workflow status",
          value: statusCopy[workflow.status],
          state: workflow.status === "ready" ? "open" : "neutral",
        },
        {
          label: "Connector readiness",
          value:
            workflow.missing_connectors.length === 0
              ? "all configured"
              : workflow.missing_connectors.join(", "),
          state: workflow.missing_connectors.length === 0 ? "open" : "closed",
        },
        {
          label: "Autonomy ceiling",
          value: humanize(workflow.default_autonomy),
          state: workflow.default_autonomy === "autonomous" ? "closed" : "open",
        },
      ],
      requestContract: [
        {
          label: "Required connectors",
          value: workflow.required_connectors.join(", "),
        },
        {
          label: "Required scopes",
          value: workflow.required_scopes.join(", "),
        },
        {
          label: "Patterns",
          value: workflow.patterns.map(humanize).join(", "),
        },
        {
          label: "Replay policy",
          value: String(workflow.data_policy.replay_allowed_from_real_runs),
        },
      ],
      outputContract: [
        {
          label: "Visual surfaces",
          value: workflow.visual_surfaces.map(humanize).join(", "),
        },
        {
          label: "Fake data allowed",
          value: String(workflow.data_policy.fake_data_allowed),
        },
        {
          label: "Regex business extraction",
          value: String(workflow.data_policy.regex_business_extraction_allowed),
        },
        {
          label: "Approval actions",
          value: workflow.approval_required_for.map(humanize).join(", "),
        },
      ],
      approvalRoute: "workflow-specific approval route pending",
      approvalPersistence: [
        {
          label: "Approval table",
          value: "approvals",
        },
        {
          label: "Decision route",
          value: "workflow-specific decision route pending",
        },
        {
          label: "Status",
          value: "pending until reviewer decision is implemented",
        },
        {
          label: "Write behavior",
          value: "tool execution remains disabled",
        },
      ],
      approvalStops: workflow.approval_required_for,
      traceReadout,
    };
  }

  const plannerConfigured =
    readiness?.engineering_issue_to_pr_planner_configured ?? false;
  const plannerModel =
    readiness?.openai_planner_model ??
    "OPENAI_REASONING_MODEL or OPENAI_DEFAULT_MODEL";

  return {
    badge: plannerConfigured ? "planner configured" : "planner gated",
    route: "POST /workflow-runs/{run_id}/engineering-issue-to-pr/evidence",
    routeState: apiBacked ? "open" : "neutral",
    routeNote:
      "Set include_proposal=true after a stored workflow run exists; the route returns typed proposal and evaluation payloads, not branch or PR writes.",
    readiness: [
      {
        label: "Registry source",
        value: apiBacked ? "live API registry" : "repository mirror",
        state: apiBacked ? "open" : "neutral",
      },
      {
        label: "OPA policy",
        value: readiness
          ? readiness.policy_configured
            ? "configured"
            : "not configured"
          : "ready check unavailable",
        state: readiness
          ? readiness.policy_configured
            ? "open"
            : "closed"
          : "neutral",
      },
      {
        label: "Database",
        value: readiness
          ? readiness.database_configured
            ? "configured"
            : "not configured"
          : "ready check unavailable",
        state: readiness
          ? readiness.database_configured
            ? "open"
            : "closed"
          : "neutral",
      },
      {
        label: "OpenAI planner",
        value: plannerConfigured
          ? plannerModel
          : "OPENAI_API_KEY plus explicit model required",
        state: plannerConfigured ? "open" : "closed",
      },
      {
        label: "Write actions",
        value: "disabled; approval-review route only creates pending records",
        state: "closed",
      },
    ],
    requestContract: [
      {
        label: "Issue locator",
        value: "issue_url or repository plus issue_number",
      },
      { label: "Context paths", value: "up to 10 relative repository paths" },
      { label: "Planner switch", value: "include_proposal: true" },
      {
        label: "Audit context",
        value: "actor_id and trace_id optional but persisted when supplied",
      },
    ],
    outputContract: [
      {
        label: "Patch proposal",
        value:
          "summary, problem_statement, planned_changes[], source_evidence_uris[]",
      },
      {
        label: "Test plan",
        value: "command, purpose, risk_covered for each step",
      },
      {
        label: "Evaluator",
        value:
          "grounded, requires_more_context, risk_level, findings[], blocking_issues[]",
      },
      {
        label: "Model audit",
        value: "model_calls rows for patch plan and plan evaluation",
      },
      {
        label: "Write guard",
        value: "approval_required=true and write_actions_enabled=false",
      },
    ],
    approvalRoute:
      "POST /workflow-runs/{run_id}/engineering-issue-to-pr/approval-review",
    approvalPersistence: [
      {
        label: "Storage",
        value: "approvals rows with pending status and write risk class",
      },
      {
        label: "Payload",
        value: "proposal, evaluation, action metadata, evidence URIs",
      },
      {
        label: "Audit",
        value: "approval.requested, approval.approved, approval.rejected",
      },
      {
        label: "Decision route",
        value:
          "POST /workflow-runs/{run_id}/engineering-issue-to-pr/approvals/{approval_id}/decision",
      },
      {
        label: "PR gate",
        value:
          "POST /workflow-runs/{run_id}/engineering-issue-to-pr/pr-draft/authorize",
      },
      {
        label: "Preview",
        value:
          "POST /workflow-runs/{run_id}/engineering-issue-to-pr/pr-draft/preview",
      },
      {
        label: "Trace readout",
        value: "GET /workflow-runs/{run_id}/trace",
      },
      {
        label: "Execution",
        value: "dry_run_preview_created_no_write_execution",
      },
    ],
    approvalStops: workflow.approval_required_for,
    traceReadout,
  };
}

function createTraceReadout(
  workflow: WorkflowDetail,
  workflowRunTrace: WorkflowRunTraceStatus,
): TraceReadoutModel {
  const route = "GET /workflow-runs/{run_id}/trace";

  if (workflowRunTrace.label === "not_configured") {
    return {
      badge: "run id required",
      route,
      state: "neutral",
      runId: "not configured",
      message: workflowRunTrace.message,
      outcomes: [
        {
          label: "Approval decision",
          value: "waiting for a real stored run id",
          state: "neutral",
        },
        {
          label: "PR authorization",
          value: "no tool authorization read without a trace",
          state: "neutral",
        },
        {
          label: "Preview evidence",
          value: "no dry-run preview read without a trace",
          state: "neutral",
        },
      ],
      records: emptyTraceRecords(),
      events: [
        {
          label: "Configuration",
          value: "DEMO_WORKFLOW_RUN_ID or DEMO_TRACE_RUN_ID",
          state: "neutral",
        },
      ],
    };
  }

  if (workflowRunTrace.label !== "loaded") {
    return {
      badge:
        workflowRunTrace.label === "not_found" ? "run not found" : "offline",
      route,
      state: "closed",
      runId: workflowRunTrace.configuredRunId,
      message: workflowRunTrace.message,
      outcomes: [
        {
          label: "Approval decision",
          value: "trace endpoint did not return records",
          state: "closed",
        },
        {
          label: "PR authorization",
          value: "authorization state unavailable",
          state: "closed",
        },
        {
          label: "Preview evidence",
          value: "preview evidence unavailable",
          state: "closed",
        },
      ],
      records: emptyTraceRecords(),
      events: [
        {
          label: "Trace fetch",
          value: workflowRunTrace.message,
          state: "closed",
        },
      ],
    };
  }

  const trace = workflowRunTrace.trace;
  const records = createTraceRecordSummary(trace);

  if (trace.run.workflow_id !== workflow.id) {
    return {
      badge: "different workflow",
      route,
      state: "neutral",
      runId: workflowRunTrace.configuredRunId,
      message: `Configured run belongs to ${humanize(trace.run.workflow_id)}. Select that workflow or configure a run for ${workflow.name}.`,
      outcomes: [
        {
          label: "Approval decision",
          value: "loaded for another workflow",
          state: "neutral",
        },
        {
          label: "PR authorization",
          value: "loaded for another workflow",
          state: "neutral",
        },
        {
          label: "Preview evidence",
          value: "loaded for another workflow",
          state: "neutral",
        },
      ],
      records,
      events: createTraceEvents(trace),
    };
  }

  const outcomes = [
    summarizeApprovalOutcome(trace),
    summarizePrAuthorizationOutcome(trace),
    summarizePreviewOutcome(trace),
  ];

  return {
    badge: "live metadata",
    route,
    state: "open",
    runId: workflowRunTrace.configuredRunId,
    message: `${humanize(trace.run.workflow_id)} run ${shortId(trace.run.id)} is ${humanize(trace.run.status)} in ${humanize(trace.run.execution_mode)} mode.`,
    outcomes,
    records,
    events: createTraceEvents(trace),
  };
}

function summarizeApprovalOutcome(trace: WorkflowRunTrace) {
  const approved = trace.approvals.filter((approval) => approval.status === "approved");
  const rejected = trace.approvals.filter((approval) => approval.status === "rejected");
  const pending = trace.approvals.filter((approval) => approval.status === "pending");

  if (rejected.length > 0) {
    return {
      label: "Approval decision",
      value: `${rejected.length} rejected approval record${pluralize(rejected.length)}`,
      state: "closed" as const,
    };
  }

  if (approved.length > 0) {
    return {
      label: "Approval decision",
      value: `${approved.length} approved approval record${pluralize(approved.length)}`,
      state: "open" as const,
    };
  }

  if (pending.length > 0) {
    return {
      label: "Approval decision",
      value: `${pending.length} pending approval record${pluralize(pending.length)}`,
      state: "neutral" as const,
    };
  }

  return {
    label: "Approval decision",
    value: "no approval records in this run",
    state: "neutral" as const,
  };
}

function summarizePrAuthorizationOutcome(trace: WorkflowRunTrace) {
  const prToolCalls = trace.tool_calls.filter(
    (toolCall) => toolCall.tool_name === "github_pull_request_draft",
  );
  const blocked = prToolCalls.filter(
    (toolCall) =>
      toolCall.status.includes("blocked") ||
      toolCall.execution_state?.includes("blocked") ||
      Boolean(toolCall.error_message),
  );
  const authorized = prToolCalls.filter(
    (toolCall) => toolCall.execution_state === "authorized_not_executed",
  );

  if (blocked.length > 0) {
    return {
      label: "PR authorization",
      value: `${blocked.length} blocked before execution`,
      state: "closed" as const,
    };
  }

  if (authorized.length > 0) {
    return {
      label: "PR authorization",
      value: `${authorized.length} authorized, not executed`,
      state: "open" as const,
    };
  }

  if (prToolCalls.length > 0) {
    return {
      label: "PR authorization",
      value: prToolCalls.map((toolCall) => humanize(toolCall.status)).join(", "),
      state: "neutral" as const,
    };
  }

  return {
    label: "PR authorization",
    value: "no PR draft authorization calls",
    state: "neutral" as const,
  };
}

function summarizePreviewOutcome(trace: WorkflowRunTrace) {
  const previewEvidence = trace.evidence_records.filter(
    (record) =>
      record.metadata.schema_version === "engineering_issue_to_pr.pr_preview.v1",
  );
  const previewAuditEvents = trace.audit_events.filter(
    (event) => event.event_type === "pr_draft.preview_created",
  );
  const previewCount = previewEvidence.length + previewAuditEvents.length;

  if (previewCount > 0) {
    return {
      label: "Preview evidence",
      value: `${previewEvidence.length} hash-only preview evidence record${pluralize(previewEvidence.length)}`,
      state: "open" as const,
    };
  }

  return {
    label: "Preview evidence",
    value: "no dry-run preview evidence in this run",
    state: "neutral" as const,
  };
}

function createTraceRecordSummary(trace: WorkflowRunTrace) {
  return [
    {
      label: "Run",
      value: `${humanize(trace.run.status)} / ${humanize(trace.run.autonomy_level)}`,
    },
    { label: "Approvals", value: String(trace.approvals.length) },
    { label: "Tool calls", value: String(trace.tool_calls.length) },
    {
      label: "Model calls",
      value: `${trace.model_calls.length} / ${formatEstimatedCost(trace)}`,
    },
    { label: "Evidence", value: String(trace.evidence_records.length) },
    { label: "Memory", value: String(trace.memory_records.length) },
    { label: "Audit events", value: String(trace.audit_events.length) },
  ];
}

function emptyTraceRecords() {
  return [
    { label: "Run", value: "not loaded" },
    { label: "Approvals", value: "0" },
    { label: "Tool calls", value: "0" },
    { label: "Model calls", value: "0 / $0.0000" },
    { label: "Evidence", value: "0" },
    { label: "Memory", value: "0" },
    { label: "Audit events", value: "0" },
  ];
}

function createTraceEvents(trace: WorkflowRunTrace) {
  const approvalEvents = trace.approvals.slice(-2).map((approval) => ({
    label: humanize(approval.requested_action),
    value: `${humanize(approval.status)} approval ${shortId(approval.id)}`,
    state: traceStateFromStatus(approval.status),
  }));
  const toolEvents = trace.tool_calls.slice(-2).map((toolCall) => ({
    label: humanize(toolCall.tool_name),
    value: humanize(toolCall.execution_state ?? toolCall.status),
    state: traceStateFromStatus(toolCall.execution_state ?? toolCall.status),
  }));
  const evidenceEvents = trace.evidence_records.slice(-2).map((record) => ({
    label: record.title,
    value: `${humanize(record.kind)} ${shortHash(record.content_hash)}`,
    state: "open" as const,
  }));
  const auditEvents = trace.audit_events.slice(-2).map((event) => ({
    label: humanize(event.event_type),
    value: humanize(event.action),
    state: traceStateFromStatus(event.event_type),
  }));

  const events = [
    ...approvalEvents,
    ...toolEvents,
    ...evidenceEvents,
    ...auditEvents,
  ].slice(-6);

  if (events.length === 0) {
    return [
      {
        label: "No trace records",
        value: "stored run has no approval, tool, evidence, or audit metadata yet",
        state: "neutral" as const,
      },
    ];
  }

  return events;
}

function traceStateFromStatus(value: string): GateState {
  if (
    value.includes("approved") ||
    value.includes("authorized") ||
    value.includes("created") ||
    value.includes("succeeded")
  ) {
    return "open";
  }

  if (
    value.includes("blocked") ||
    value.includes("rejected") ||
    value.includes("failed") ||
    value.includes("error")
  ) {
    return "closed";
  }

  return "neutral";
}

function evalStatusToGateState(value: "pass" | "warn" | "fail"): GateState {
  if (value === "pass") {
    return "open";
  }

  if (value === "fail") {
    return "closed";
  }

  return "neutral";
}

function formatEstimatedCost(trace: WorkflowRunTrace) {
  const total = trace.model_calls.reduce((sum, call) => {
    const value = Number(call.estimated_cost_usd);
    return Number.isFinite(value) ? sum + value : sum;
  }, 0);
  return `$${total.toFixed(4)}`;
}

function shortId(value: string) {
  return value.slice(0, 8);
}

function shortHash(value: string) {
  return value ? value.slice(0, 10) : "no hash";
}

function pluralize(count: number) {
  return count === 1 ? "" : "s";
}

function countBy(values: string[]) {
  const counts = new Map<string, number>();
  for (const value of values) {
    counts.set(value, (counts.get(value) ?? 0) + 1);
  }
  return counts;
}

function matchingScopes(workflow: WorkflowDetail, connector: string) {
  const prefix = connector.split("_")[0] ?? connector;
  return workflow.required_scopes.filter((scope) => scope.startsWith(prefix));
}

function formatWorkflowConfig(workflow: WorkflowDetail) {
  return [
    `id: ${workflow.id}`,
    `name: ${workflow.name}`,
    `domain: ${workflow.domain}`,
    `status: ${workflow.status}`,
    "enabled_when:",
    "  connectors:",
    ...workflow.required_connectors.map((connector) => `    - ${connector}`),
    "  required_scopes:",
    ...workflow.required_scopes.map((scope) => `    - ${scope}`),
    "patterns:",
    ...workflow.patterns.map((pattern) => `  - ${pattern}`),
    "data_policy:",
    `  fake_data_allowed: ${workflow.data_policy.fake_data_allowed}`,
    `  replay_allowed_from_real_runs: ${workflow.data_policy.replay_allowed_from_real_runs}`,
    `  regex_business_extraction_allowed: ${workflow.data_policy.regex_business_extraction_allowed}`,
    `default_autonomy: ${workflow.default_autonomy}`,
    "approval_required_for:",
    ...workflow.approval_required_for.map((action) => `  - ${action}`),
    "visual_surfaces:",
    ...workflow.visual_surfaces.map((surface) => `  - ${surface}`),
  ].join("\n");
}

function humanize(value: string) {
  return value
    .split("_")
    .map((word) =>
      word.length > 0 ? `${word[0].toUpperCase()}${word.slice(1)}` : word,
    )
    .join(" ");
}
