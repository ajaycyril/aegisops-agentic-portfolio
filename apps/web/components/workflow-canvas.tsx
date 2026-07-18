"use client";

import {
  BaseEdge,
  Background,
  BackgroundVariant,
  Controls,
  getSmoothStepPath,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  type Edge,
  type EdgeProps,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import {
  Bot,
  Braces,
  Check,
  CircleDashed,
  GitBranch,
  Scale,
  ShieldCheck,
  Wrench,
  X,
} from "lucide-react";
import { memo, useMemo } from "react";

import type { RunEvent } from "@/lib/agentic/contracts";
import type { ScenarioDefinition } from "@/lib/agentic/scenarios";

type VisualState =
  "queued" | "running" | "completed" | "blocked" | "failed" | "skipped";

type RuntimeNodeData = Record<string, unknown> & {
  title: string;
  subtitle: string;
  lane: "agentic" | "rules" | "policy";
  kind:
    | "guardrail"
    | "model"
    | "tool"
    | "policy"
    | "evaluator"
    | "rules"
    | "output";
  state: VisualState;
  durationMs?: number;
};

type RuntimeNode = Node<RuntimeNodeData, "runtime">;

const icons = {
  guardrail: ShieldCheck,
  model: Bot,
  tool: Wrench,
  policy: Scale,
  evaluator: Check,
  rules: Braces,
  output: GitBranch,
};

const RuntimeNodeView = memo(({ data }: NodeProps<RuntimeNode>) => {
  const Icon = icons[data.kind];
  const StateIcon =
    data.state === "failed" || data.state === "blocked"
      ? X
      : data.state === "completed"
        ? Check
        : CircleDashed;

  return (
    <div className={`runtime-node lane-${data.lane} state-${data.state}`}>
      <Handle type="target" position={Position.Left} />
      <div className="runtime-node-icon">
        <Icon size={15} strokeWidth={1.8} />
      </div>
      <div className="runtime-node-copy">
        <strong>{data.title}</strong>
        <span>{data.subtitle}</span>
      </div>
      <div className="runtime-node-state" aria-label={data.state}>
        <StateIcon size={13} />
        {data.durationMs !== undefined ? (
          <small>{data.durationMs}ms</small>
        ) : null}
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
});

RuntimeNodeView.displayName = "RuntimeNodeView";

const nodeTypes = { runtime: RuntimeNodeView };

function LiveEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  markerEnd,
  style,
  data,
}: EdgeProps) {
  const [edgePath] = getSmoothStepPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    borderRadius: 8,
  });
  const edgeData = data as
    { active?: boolean; lane?: "agentic" | "rules" } | undefined;
  const color = edgeData?.lane === "agentic" ? "#43d1b5" : "#8a97aa";

  return (
    <>
      <BaseEdge id={id} path={edgePath} markerEnd={markerEnd} style={style} />
      {edgeData?.active ? (
        <circle r="3.5" fill={color} className="execution-packet">
          <animateMotion dur="1.15s" repeatCount="indefinite" path={edgePath} />
        </circle>
      ) : null}
    </>
  );
}

const edgeTypes = { live: LiveEdge };

function stateForNode(nodeId: string, events: RunEvent[]): VisualState {
  const event = [...events]
    .reverse()
    .find((candidate) => candidate.nodeId === nodeId);
  if (!event) return "queued";
  if (event.status === "passed" || event.status === "completed")
    return "completed";
  if (event.status === "blocked") return "blocked";
  if (event.status === "failed") return "failed";
  if (event.status === "skipped") return "skipped";
  return "running";
}

function durationForNode(nodeId: string, events: RunEvent[]) {
  return [...events].reverse().find((candidate) => candidate.nodeId === nodeId)
    ?.durationMs;
}

function edge(
  source: string,
  target: string,
  lane: "agentic" | "rules",
  active: boolean,
): Edge {
  return {
    id: `${source}-${target}`,
    source,
    target,
    type: "live",
    data: { active, lane },
    style: {
      stroke: lane === "agentic" ? "#43d1b5" : "#8a97aa",
      strokeWidth: active ? 2.4 : 1.25,
      opacity: active ? 1 : 0.56,
    },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color: lane === "agentic" ? "#43d1b5" : "#8a97aa",
      width: 14,
      height: 14,
    },
  };
}

function makeNode(
  id: string,
  title: string,
  subtitle: string,
  lane: RuntimeNodeData["lane"],
  kind: RuntimeNodeData["kind"],
  x: number,
  y: number,
  events: RunEvent[],
): RuntimeNode {
  return {
    id,
    type: "runtime",
    position: { x, y },
    data: {
      title,
      subtitle,
      lane,
      kind,
      state: stateForNode(id, events),
      durationMs: durationForNode(id, events),
    },
  };
}

export function WorkflowCanvas({
  scenario,
  events,
  onSelectEvent,
}: {
  scenario: ScenarioDefinition;
  events: RunEvent[];
  onSelectEvent: (event: RunEvent) => void;
}) {
  const { nodes, edges } = useMemo(() => {
    const isActive = (source: string, target: string) =>
      stateForNode(source, events) === "running" ||
      stateForNode(target, events) === "running";

    if (scenario.orchestration === "multi_agent") {
      const agentY = 105;
      const ruleY = 400;
      const isHassantuk = scenario.id === "hassantuk_villa_response";
      const specialists = isHassantuk
        ? [
            {
              id: "agent-protocol-specialist",
              label: "Protocol specialist",
              tool: "hassantuk_home_protocol",
            },
            {
              id: "agent-conditions-specialist",
              label: "Conditions specialist",
              tool: "open_meteo_villa_conditions",
            },
            {
              id: "agent-policy-specialist",
              label: "Policy specialist",
              tool: "enterprise_policy_search",
            },
          ]
        : [
            {
              id: "agent-status-specialist",
              label: "Health specialist",
              tool: "github_status",
            },
            {
              id: "agent-incident-specialist",
              label: "Incident specialist",
              tool: "github_incidents",
            },
            {
              id: "agent-policy-specialist",
              label: "Policy specialist",
              tool: "enterprise_policy_search",
            },
          ];
      const visualNodes: RuntimeNode[] = [
        makeNode(
          "agent-guardrail",
          "Guardrail",
          "Typed intake + budget",
          "agentic",
          "guardrail",
          30,
          agentY,
          events,
        ),
        makeNode(
          specialists[0].id,
          specialists[0].label,
          "Independent model agent",
          "agentic",
          "model",
          310,
          45,
          events,
        ),
        makeNode(
          `agent-${specialists[0].tool}`,
          specialists[0].tool,
          "MCP read tool",
          "agentic",
          "tool",
          590,
          45,
          events,
        ),
        makeNode(
          specialists[1].id,
          specialists[1].label,
          "Independent model agent",
          "agentic",
          "model",
          310,
          175,
          events,
        ),
        makeNode(
          `agent-${specialists[1].tool}`,
          specialists[1].tool,
          "MCP read tool",
          "agentic",
          "tool",
          590,
          175,
          events,
        ),
        makeNode(
          specialists[2].id,
          specialists[2].label,
          "Independent retrieval agent",
          "agentic",
          "model",
          310,
          285,
          events,
        ),
        makeNode(
          `agent-${specialists[2].tool}`,
          specialists[2].tool,
          "Governed policy retrieval",
          "agentic",
          "tool",
          590,
          285,
          events,
        ),
        makeNode(
          "agent-supervisor",
          "Supervisor",
          "Reconcile agent handoffs",
          "agentic",
          "model",
          870,
          agentY,
          events,
        ),
        makeNode(
          "output-policy",
          "Dynamic policy",
          "OPA/Rego decision",
          "policy",
          "policy",
          1140,
          agentY,
          events,
        ),
        makeNode(
          "agent-evaluate",
          "Grounding eval",
          "Required evidence check",
          "agentic",
          "evaluator",
          1410,
          agentY,
          events,
        ),
        makeNode(
          "agent-output",
          "Agent output",
          "Reconciled conclusion",
          "agentic",
          "output",
          1680,
          agentY,
          events,
        ),
        makeNode(
          "rules-contract",
          "Decision contract",
          "Schema + outcome version",
          "rules",
          "rules",
          30,
          ruleY,
          events,
        ),
        makeNode(
          `rules-${scenario.requiredTools[0]}`,
          scenario.requiredTools[0],
          "Configured MCP evidence",
          "rules",
          "tool",
          320,
          ruleY,
          events,
        ),
        makeNode(
          `rules-${scenario.requiredTools[1]}`,
          scenario.requiredTools[1],
          "Configured MCP evidence",
          "rules",
          "tool",
          610,
          ruleY,
          events,
        ),
        makeNode(
          `rules-${scenario.requiredTools[2]}`,
          scenario.requiredTools[2],
          "Configured policy evidence",
          "rules",
          "tool",
          900,
          ruleY,
          events,
        ),
        makeNode(
          "rules-derive",
          "Typed derivation",
          "Reproducible decision facts",
          "rules",
          "rules",
          1190,
          ruleY,
          events,
        ),
        makeNode(
          "rules-evaluate",
          "Decision table",
          "Versioned conditions",
          "rules",
          "output",
          1480,
          ruleY,
          events,
        ),
        makeNode(
          "rules-output",
          "Governed outcome",
          "Known route or exception",
          "rules",
          "output",
          1770,
          ruleY,
          events,
        ),
      ];
      const paths: Array<[string, string, "agentic" | "rules"]> = [
        ["agent-guardrail", specialists[0].id, "agentic"],
        ["agent-guardrail", specialists[1].id, "agentic"],
        ["agent-guardrail", specialists[2].id, "agentic"],
        [specialists[0].id, `agent-${specialists[0].tool}`, "agentic"],
        [specialists[1].id, `agent-${specialists[1].tool}`, "agentic"],
        [specialists[2].id, `agent-${specialists[2].tool}`, "agentic"],
        [`agent-${specialists[0].tool}`, "agent-supervisor", "agentic"],
        [`agent-${specialists[1].tool}`, "agent-supervisor", "agentic"],
        [`agent-${specialists[2].tool}`, "agent-supervisor", "agentic"],
        ["agent-supervisor", "output-policy", "agentic"],
        ["output-policy", "agent-evaluate", "agentic"],
        ["agent-evaluate", "agent-output", "agentic"],
        ["rules-contract", `rules-${scenario.requiredTools[0]}`, "rules"],
        [
          `rules-${scenario.requiredTools[0]}`,
          `rules-${scenario.requiredTools[1]}`,
          "rules",
        ],
        [
          `rules-${scenario.requiredTools[1]}`,
          `rules-${scenario.requiredTools[2]}`,
          "rules",
        ],
        [`rules-${scenario.requiredTools[2]}`, "rules-derive", "rules"],
        ["rules-derive", "rules-evaluate", "rules"],
        ["rules-evaluate", "rules-output", "rules"],
      ];
      return {
        nodes: visualNodes,
        edges: paths.map(([source, target, lane]) =>
          edge(source, target, lane, isActive(source, target)),
        ),
      };
    }

    const agentY = 105;
    const ruleY = 400;
    const toolSpacing = 270;
    const agentTools = scenario.requiredTools.map((toolName, index) =>
      makeNode(
        `agent-${toolName}`,
        toolName,
        "MCP read tool",
        "agentic",
        "tool",
        600 + index * toolSpacing,
        agentY,
        events,
      ),
    );
    const ruleTools = scenario.requiredTools.map((toolName, index) =>
      makeNode(
        `rules-${toolName}`,
        toolName,
        "Configured MCP evidence",
        "rules",
        "tool",
        320 + index * toolSpacing,
        ruleY,
        events,
      ),
    );
    const afterAgentTools = 600 + scenario.requiredTools.length * toolSpacing;
    const afterRuleTools = 320 + scenario.requiredTools.length * toolSpacing;

    const visualNodes: RuntimeNode[] = [
      makeNode(
        "agent-guardrail",
        "Guardrail",
        "Typed intake + budget",
        "agentic",
        "guardrail",
        30,
        agentY,
        events,
      ),
      makeNode(
        "agent-plan",
        "Plan + act",
        scenario.agentPattern,
        "agentic",
        "model",
        310,
        agentY,
        events,
      ),
      ...agentTools,
      makeNode(
        "output-policy",
        "Dynamic policy",
        "OPA/Rego decision",
        "policy",
        "policy",
        afterAgentTools,
        agentY,
        events,
      ),
      makeNode(
        "agent-evaluate",
        "Grounding eval",
        "Required evidence check",
        "agentic",
        "evaluator",
        afterAgentTools + 270,
        agentY,
        events,
      ),
      makeNode(
        "agent-output",
        "Agent output",
        "Adaptive conclusion",
        "agentic",
        "output",
        afterAgentTools + 540,
        agentY,
        events,
      ),
      makeNode(
        "rules-fetch",
        "Decision contract",
        "Versioned fields and outcomes",
        "rules",
        "rules",
        30,
        ruleY,
        events,
      ),
      ...ruleTools,
      makeNode(
        "rules-evaluate",
        "Rule engine",
        "Configured conditions",
        "rules",
        "rules",
        afterRuleTools,
        ruleY,
        events,
      ),
      makeNode(
        "rules-output",
        "Rule output",
        "Predefined outcome",
        "rules",
        "output",
        afterRuleTools + 270,
        ruleY,
        events,
      ),
    ];

    const visualEdges: Edge[] = [];
    const agentIds = [
      "agent-guardrail",
      "agent-plan",
      ...scenario.requiredTools.map((toolName) => `agent-${toolName}`),
      "output-policy",
      "agent-evaluate",
      "agent-output",
    ];
    const ruleIds = [
      "rules-fetch",
      ...scenario.requiredTools.map((toolName) => `rules-${toolName}`),
      "rules-evaluate",
      "rules-output",
    ];
    for (let index = 0; index < agentIds.length - 1; index += 1) {
      const source = agentIds[index];
      const target = agentIds[index + 1];
      visualEdges.push(
        edge(source, target, "agentic", isActive(source, target)),
      );
    }
    for (let index = 0; index < ruleIds.length - 1; index += 1) {
      const source = ruleIds[index];
      const target = ruleIds[index + 1];
      visualEdges.push(edge(source, target, "rules", isActive(source, target)));
    }
    return { nodes: visualNodes, edges: visualEdges };
  }, [events, scenario]);

  return (
    <div
      className="workflow-canvas"
      aria-label="Live agent and rules execution graph"
    >
      <div className="lane-label lane-label-agent">
        <Bot size={14} />
        <span>Agentic lane</span>
        <small>adapts plan and tools</small>
      </div>
      <div className="lane-label lane-label-rules">
        <Braces size={14} />
        <span>Deterministic lane</span>
        <small>derives facts and evaluates decisions</small>
      </div>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        defaultViewport={{ x: 18, y: 28, zoom: 0.82 }}
        minZoom={0.45}
        maxZoom={1.4}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable
        onNodeClick={(_, node) => {
          const event = [...events]
            .reverse()
            .find((candidate) => candidate.nodeId === node.id);
          if (event) onSelectEvent(event);
        }}
        proOptions={{ hideAttribution: false }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={18}
          size={1}
          color="#27303d"
        />
        <Controls showInteractive={false} position="bottom-right" />
      </ReactFlow>
    </div>
  );
}
