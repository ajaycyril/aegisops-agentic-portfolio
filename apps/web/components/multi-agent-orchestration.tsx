"use client";

import {
  AlertTriangle,
  BrainCircuit,
  CheckCircle2,
  Code2,
  Database,
  FileText,
  GitBranch,
  LineChart,
  Network,
  RadioTower,
  ShieldCheck,
  Workflow,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useMemo, useState } from "react";
import {
  Background,
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
  type NodeTypes,
} from "@xyflow/react";

import type { WorkflowDetail } from "@/lib/workflows";

type MultiAgentOrchestrationProps = {
  workflows: WorkflowDetail[];
  selectedWorkflowId: string;
  shouldReduceMotion: boolean | null;
  onSelectWorkflow: (workflowId: string) => void;
};

type AgentState = "supervisor" | "parallel" | "evaluator" | "approval" | "gate";

type AgentNodeData = Record<string, unknown> & {
  title: string;
  role: string;
  layer: string;
  state: AgentState;
  icon: LucideIcon;
  tools: string[];
  output: string;
  policy: string;
  whyAgentic: string;
};

type AgentNode = Node<AgentNodeData, "agent">;

const incidentWorkflowId = "incident_response_investigator";

const agentNodes: AgentNode[] = [
  agentNode("intake", 0, 190, {
    title: "Incident Intake",
    role: "deterministic gate",
    layer: "rule-based",
    state: "gate",
    icon: RadioTower,
    tools: ["incident payload", "severity policy", "service catalog"],
    output: "typed incident envelope",
    policy:
      "Validates required fields, tenant, severity, and live-run budget before graph start.",
    whyAgentic:
      "This step is intentionally not agentic; deterministic gates keep bad or expensive runs out.",
  }),
  agentNode("commander", 180, 190, {
    title: "Incident Commander",
    role: "supervisor agent",
    layer: "LangGraph supervisor",
    state: "supervisor",
    icon: BrainCircuit,
    tools: ["run checkpoint", "worker routing", "budget ledger"],
    output: "parallel investigation plan",
    policy:
      "Can assign read-only workers but cannot approve rollback, paging, or incident updates.",
    whyAgentic:
      "The incident scope is ambiguous, so the commander decomposes work and changes the plan as evidence arrives.",
  }),
  agentNode("logs", 360, 30, {
    title: "Log Investigator",
    role: "specialist worker",
    layer: "OpenAI agent + MCP",
    state: "parallel",
    icon: Database,
    tools: ["observability_log_search", "traces:read"],
    output: "source-linked log and trace evidence",
    policy:
      "Read-only observability scopes; retrieved records must carry source metadata.",
    whyAgentic:
      "Logs and traces need iterative narrowing, time-window changes, and exception-pattern follow-up.",
  }),
  agentNode("deploys", 360, 190, {
    title: "Deploy Investigator",
    role: "specialist worker",
    layer: "OpenAI agent + MCP",
    state: "parallel",
    icon: GitBranch,
    tools: ["deployments:read", "checks:read"],
    output: "release and CI correlation",
    policy:
      "Read-only deployment and check access; rollback remains approval-gated.",
    whyAgentic:
      "Deploy history must be correlated with symptoms, checks, ownership, and blast radius.",
  }),
  agentNode("code", 360, 350, {
    title: "Code Investigator",
    role: "specialist worker",
    layer: "OpenAI agent + MCP",
    state: "parallel",
    icon: Code2,
    tools: ["github_file_read", "contents:read"],
    output: "suspect code paths and config evidence",
    policy:
      "Read-only repository access; branch and pull-request writes stay unavailable.",
    whyAgentic:
      "The worker follows evidence into relevant files instead of scanning the repository blindly.",
  }),
  agentNode("slo", 540, 190, {
    title: "SLO Analyst",
    role: "metric specialist",
    layer: "guarded data agent",
    state: "parallel",
    icon: LineChart,
    tools: ["metrics:read", "traces:read"],
    output: "impact window and affected service map",
    policy:
      "Read-only telemetry, bounded time windows, and no customer data export.",
    whyAgentic:
      "Impact analysis changes as evidence identifies services, regions, dependencies, and cohorts.",
  }),
  agentNode("auditor", 720, 190, {
    title: "Evidence Auditor",
    role: "evaluator agent",
    layer: "evaluator-optimizer",
    state: "evaluator",
    icon: ShieldCheck,
    tools: ["evidence_records", "trace timeline", "source verifier"],
    output: "grounding verdict and blocking gaps",
    policy:
      "RCA claims must cite evidence records; ungrounded claims are blocked from approval.",
    whyAgentic:
      "Independent findings can conflict, so an evaluator reconciles confidence and asks for more context.",
  }),
  agentNode("rca", 900, 110, {
    title: "RCA Drafter",
    role: "communications agent",
    layer: "structured output",
    state: "evaluator",
    icon: FileText,
    tools: ["RCA schema", "remediation rubric", "incident template"],
    output: "RCA draft and remediation plan",
    policy:
      "Can draft summaries only; external updates and rollback requests require review.",
    whyAgentic:
      "The draft must preserve nuance from multiple evidence streams and produce action-ready remediation.",
  }),
  agentNode("approval", 900, 280, {
    title: "Human Approval",
    role: "governance stop",
    layer: "OPA + approvals",
    state: "approval",
    icon: AlertTriangle,
    tools: ["approval_requests", "policy decision", "audit event"],
    output: "approved rollback, update, or paging action",
    policy:
      "Rollback, incident update, and paging action are blocked until approval records exist.",
    whyAgentic:
      "This step is deliberately human-governed because production write actions carry operational risk.",
  }),
];

function agentNode(
  id: string,
  x: number,
  y: number,
  data: AgentNodeData,
): AgentNode {
  return {
    id,
    type: "agent",
    position: { x, y },
    data,
  };
}

function createEdges(shouldReduceMotion: boolean | null): Edge[] {
  const animated = !shouldReduceMotion;
  return [
    orchestrationEdge("intake", "commander", "eligible run", animated),
    orchestrationEdge("commander", "logs", "fan-out", animated),
    orchestrationEdge("commander", "deploys", "fan-out", animated),
    orchestrationEdge("commander", "code", "fan-out", animated),
    orchestrationEdge("commander", "slo", "fan-out", animated),
    orchestrationEdge("logs", "auditor", "evidence", animated),
    orchestrationEdge("deploys", "auditor", "evidence", animated),
    orchestrationEdge("code", "auditor", "evidence", animated),
    orchestrationEdge("slo", "auditor", "impact", animated),
    orchestrationEdge("auditor", "rca", "grounded brief", animated),
    orchestrationEdge("rca", "approval", "write gate", animated, true),
  ];
}

function orchestrationEdge(
  source: string,
  target: string,
  label: string,
  animated: boolean,
  blocked = false,
): Edge {
  return {
    id: `${source}-${target}`,
    source,
    target,
    label,
    type: "smoothstep",
    animated,
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color: blocked ? "#ff7a90" : "#7f8da4",
    },
    style: {
      stroke: blocked ? "#ff7a90" : "#7f8da4",
      strokeDasharray: blocked ? "7 5" : undefined,
      strokeWidth: blocked ? 2 : 1.6,
    },
    labelStyle: {
      fill: "#dce4f0",
      fontSize: 11,
      fontWeight: 700,
    },
    labelBgStyle: {
      fill: "rgba(13, 17, 24, 0.88)",
      stroke: "rgba(255, 255, 255, 0.12)",
      strokeWidth: 1,
    },
    labelBgPadding: [6, 4],
    labelBgBorderRadius: 6,
  };
}

const agentNodeTypes = {
  agent: AgentNodeCard,
} satisfies NodeTypes;

const agentStateCopy: Record<AgentState, string> = {
  approval: "approval",
  evaluator: "evaluator",
  gate: "gate",
  parallel: "parallel",
  supervisor: "supervisor",
};

export function MultiAgentOrchestration({
  workflows,
  selectedWorkflowId,
  shouldReduceMotion,
  onSelectWorkflow,
}: MultiAgentOrchestrationProps) {
  const [selectedAgentId, setSelectedAgentId] = useState("commander");
  const incidentWorkflow = workflows.find(
    (workflow) => workflow.id === incidentWorkflowId,
  );
  const selectedAgent =
    agentNodes.find((node) => node.id === selectedAgentId) ?? agentNodes[1];
  const edges = useMemo(
    () => createEdges(shouldReduceMotion),
    [shouldReduceMotion],
  );
  const active = selectedWorkflowId === incidentWorkflowId;

  if (!incidentWorkflow) {
    return null;
  }

  return (
    <section className="panel multi-agent-panel">
      <div className="multi-agent-heading">
        <div className="panel-title">
          <Network size={18} />
          Multi-Agent Orchestration
        </div>
        <div className="multi-agent-actions">
          <span className="badge">incident response demo</span>
          <button
            className="focus-workflow-button"
            disabled={active}
            type="button"
            onClick={() => onSelectWorkflow(incidentWorkflowId)}
          >
            {active ? "Workflow focused" : "Focus workflow"}
          </button>
        </div>
      </div>

      <div className="multi-agent-brief">
        <div>
          <span className="eyebrow">Production Incident Investigator</span>
          <h2>
            Supervisor-led parallel specialists for real incident evidence.
          </h2>
        </div>
        <div className="multi-agent-patterns">
          {incidentWorkflow.patterns.map((pattern) => (
            <span key={pattern}>{humanize(pattern)}</span>
          ))}
        </div>
      </div>

      <div className="multi-agent-shell">
        <div className="multi-agent-canvas" aria-label="Multi-agent graph">
          <div className="lane-overlay">
            <span>gate</span>
            <span>supervisor</span>
            <span>parallel workers</span>
            <span>review</span>
            <span>approval</span>
          </div>
          <HandoffOverlay />
          <ReactFlow
            nodes={agentNodes}
            edges={edges}
            nodeTypes={agentNodeTypes}
            fitView
            fitViewOptions={{ padding: 0.18 }}
            minZoom={0.25}
            maxZoom={1.35}
            nodesDraggable={false}
            nodesConnectable={false}
            elementsSelectable
            panOnScroll
            proOptions={{ hideAttribution: true }}
            onInit={(instance) => {
              window.requestAnimationFrame(() => {
                instance.fitView({ padding: 0.18 });
              });
            }}
            onNodeClick={(_, node) => setSelectedAgentId(node.id)}
          >
            <Background color="rgba(255,255,255,0.13)" gap={24} />
            <Controls showInteractive={false} />
          </ReactFlow>
        </div>

        <div
          className="mobile-agent-sequence"
          aria-label="Multi-agent sequence"
        >
          {agentNodes.map((node, index) => {
            const Icon = node.data.icon;
            return (
              <button
                className={`mobile-agent-card ${node.id === selectedAgent.id ? "active" : ""}`}
                key={node.id}
                type="button"
                onClick={() => setSelectedAgentId(node.id)}
              >
                <span>{String(index + 1).padStart(2, "0")}</span>
                <Icon size={17} />
                <strong>{node.data.title}</strong>
                <em>{node.data.role}</em>
              </button>
            );
          })}
        </div>

        <aside className="agent-inspector">
          <div className="inspector-kicker">
            {agentStateCopy[selectedAgent.data.state]}
          </div>
          <h2>{selectedAgent.data.title}</h2>
          <p>{selectedAgent.data.whyAgentic}</p>
          <div className="agent-lens-list">
            <AgentLensRow label="Role" value={selectedAgent.data.role} />
            <AgentLensRow label="Layer" value={selectedAgent.data.layer} />
            <AgentLensRow
              label="Tools"
              value={selectedAgent.data.tools.join(", ")}
            />
            <AgentLensRow label="Output" value={selectedAgent.data.output} />
            <AgentLensRow label="Policy" value={selectedAgent.data.policy} />
          </div>
        </aside>
      </div>

      <div className="multi-agent-readiness">
        <ReadinessChip
          icon={Workflow}
          label="Workflow status"
          value={humanize(incidentWorkflow.status)}
          blocked={incidentWorkflow.status !== "ready"}
        />
        <ReadinessChip
          icon={Database}
          label="Connectors"
          value={incidentWorkflow.required_connectors.join(", ")}
          blocked={incidentWorkflow.missing_connectors.length > 0}
        />
        <ReadinessChip
          icon={ShieldCheck}
          label="Approval stops"
          value={incidentWorkflow.approval_required_for
            .map(humanize)
            .join(", ")}
          blocked
        />
        <ReadinessChip
          icon={CheckCircle2}
          label="Replay policy"
          value={
            incidentWorkflow.data_policy.replay_allowed_from_real_runs
              ? "captured real runs only"
              : "replay disabled"
          }
          blocked={!incidentWorkflow.data_policy.replay_allowed_from_real_runs}
        />
      </div>
    </section>
  );
}

function HandoffOverlay() {
  return (
    <svg aria-hidden="true" className="handoff-lines" viewBox="0 0 1080 500">
      <defs>
        <marker
          id="handoff-arrow"
          markerHeight="8"
          markerWidth="8"
          orient="auto"
          refX="7"
          refY="4"
          viewBox="0 0 8 8"
        >
          <path d="M0,0 L8,4 L0,8 Z" />
        </marker>
        <marker
          id="handoff-arrow-blocked"
          markerHeight="8"
          markerWidth="8"
          orient="auto"
          refX="7"
          refY="4"
          viewBox="0 0 8 8"
        >
          <path d="M0,0 L8,4 L0,8 Z" />
        </marker>
      </defs>
      <path className="handoff-line gate-line" d="M170 234 L180 234" />
      <path className="handoff-line" d="M350 234 C356 234 356 74 360 74" />
      <path className="handoff-line" d="M350 234 L360 234" />
      <path className="handoff-line" d="M350 234 C356 234 356 394 360 394" />
      <path className="handoff-line" d="M530 234 L540 234" />
      <path className="handoff-line" d="M530 74 C620 74 620 234 720 234" />
      <path className="handoff-line" d="M530 234 L720 234" />
      <path className="handoff-line" d="M530 394 C620 394 620 234 720 234" />
      <path className="handoff-line" d="M710 234 L720 234" />
      <path className="handoff-line" d="M890 234 C900 234 900 154 900 154" />
      <path
        className="handoff-line blocked-line"
        d="M985 198 C1035 224 1035 286 985 324"
      />
      <g className="handoff-labels">
        <text x="390" y="156">
          fan-out
        </text>
        <text x="610" y="164">
          evidence
        </text>
        <text x="720" y="128">
          grounded brief
        </text>
        <text x="930" y="252">
          write gate
        </text>
      </g>
    </svg>
  );
}

function AgentNodeCard({ data }: NodeProps<AgentNode>) {
  const Icon = data.icon;
  return (
    <div className={`agent-node agent-node-${data.state}`}>
      <Handle className="agent-handle" type="target" position={Position.Left} />
      <div className="agent-node-icon">
        <Icon size={18} />
      </div>
      <div>
        <strong>{data.title}</strong>
        <span>{data.role}</span>
        <em>{data.layer}</em>
      </div>
      <Handle
        className="agent-handle"
        type="source"
        position={Position.Right}
      />
    </div>
  );
}

function AgentLensRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="agent-lens-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function ReadinessChip({
  icon: Icon,
  label,
  value,
  blocked,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  blocked: boolean;
}) {
  return (
    <div className={`readiness-chip ${blocked ? "blocked" : ""}`}>
      <Icon size={16} />
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function humanize(value: string) {
  return value
    .split("_")
    .map((word) =>
      word.length > 0 ? `${word[0].toUpperCase()}${word.slice(1)}` : word,
    )
    .join(" ");
}
