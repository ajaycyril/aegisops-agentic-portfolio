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

type VisualState = "queued" | "running" | "completed" | "blocked" | "failed" | "skipped";

type RuntimeNodeData = Record<string, unknown> & {
  title: string;
  subtitle: string;
  lane: "agentic" | "rules" | "policy";
  kind: "guardrail" | "model" | "tool" | "policy" | "evaluator" | "rules" | "output";
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
        {data.durationMs !== undefined ? <small>{data.durationMs}ms</small> : null}
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
  const edgeData = data as { active?: boolean; lane?: "agentic" | "rules" } | undefined;
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
  const event = [...events].reverse().find((candidate) => candidate.nodeId === nodeId);
  if (!event) return "queued";
  if (event.status === "passed" || event.status === "completed") return "completed";
  if (event.status === "blocked") return "blocked";
  if (event.status === "failed") return "failed";
  if (event.status === "skipped") return "skipped";
  return "running";
}

function durationForNode(nodeId: string, events: RunEvent[]) {
  return [...events].reverse().find((candidate) => candidate.nodeId === nodeId)?.durationMs;
}

function edge(source: string, target: string, lane: "agentic" | "rules", active: boolean): Edge {
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
      const agentY = 72;
      const ruleY = 330;
      const visualNodes: RuntimeNode[] = [
        makeNode("agent-guardrail", "Guardrail", "Typed intake + budget", "agentic", "guardrail", 20, agentY, events),
        makeNode("agent-status-specialist", "Health specialist", "Independent model agent", "agentic", "model", 220, 25, events),
        makeNode("agent-github_status", "github_status", "MCP read tool", "agentic", "tool", 430, 25, events),
        makeNode("agent-incident-specialist", "Incident specialist", "Independent model agent", "agentic", "model", 220, 138, events),
        makeNode("agent-github_incidents", "github_incidents", "MCP read tool", "agentic", "tool", 430, 138, events),
        makeNode("agent-supervisor", "Supervisor", "Reconcile agent handoffs", "agentic", "model", 650, agentY, events),
        makeNode("output-policy", "Dynamic policy", "OPA/Rego decision", "policy", "policy", 860, agentY, events),
        makeNode("agent-evaluate", "Grounding eval", "Required evidence check", "agentic", "evaluator", 1060, agentY, events),
        makeNode("agent-output", "Agent output", "Reconciled conclusion", "agentic", "output", 1260, agentY, events),
        makeNode("rules-fetch", "Fixed intake", "Predefined fields", "rules", "rules", 20, ruleY, events),
        makeNode("rules-github_status", "github_status", "Fixed source input", "rules", "tool", 250, ruleY, events),
        makeNode("rules-github_incidents", "github_incidents", "Fixed source input", "rules", "tool", 470, ruleY, events),
        makeNode("rules-evaluate", "Rule engine", "Configured conditions", "rules", "rules", 700, ruleY, events),
        makeNode("rules-output", "Rule output", "Predefined outcome", "rules", "output", 920, ruleY, events),
      ];
      const paths: Array<[string, string, "agentic" | "rules"]> = [
        ["agent-guardrail", "agent-status-specialist", "agentic"],
        ["agent-guardrail", "agent-incident-specialist", "agentic"],
        ["agent-status-specialist", "agent-github_status", "agentic"],
        ["agent-incident-specialist", "agent-github_incidents", "agentic"],
        ["agent-github_status", "agent-supervisor", "agentic"],
        ["agent-github_incidents", "agent-supervisor", "agentic"],
        ["agent-supervisor", "output-policy", "agentic"],
        ["output-policy", "agent-evaluate", "agentic"],
        ["agent-evaluate", "agent-output", "agentic"],
        ["rules-fetch", "rules-github_status", "rules"],
        ["rules-github_status", "rules-github_incidents", "rules"],
        ["rules-github_incidents", "rules-evaluate", "rules"],
        ["rules-evaluate", "rules-output", "rules"],
      ];
      return {
        nodes: visualNodes,
        edges: paths.map(([source, target, lane]) =>
          edge(source, target, lane, isActive(source, target)),
        ),
      };
    }

    const agentY = 70;
    const ruleY = 310;
    const toolSpacing = 180;
    const agentTools = scenario.requiredTools.map((toolName, index) =>
      makeNode(
        `agent-${toolName}`,
        toolName,
        "MCP read tool",
        "agentic",
        "tool",
        410 + index * toolSpacing,
        agentY,
        events,
      ),
    );
    const ruleTools = scenario.requiredTools.map((toolName, index) =>
      makeNode(
        `rules-${toolName}`,
        toolName,
        "Fixed source input",
        "rules",
        "tool",
        225 + index * toolSpacing,
        ruleY,
        events,
      ),
    );
    const afterAgentTools = 410 + scenario.requiredTools.length * toolSpacing;
    const afterRuleTools = 225 + scenario.requiredTools.length * toolSpacing;

    const visualNodes: RuntimeNode[] = [
      makeNode("agent-guardrail", "Guardrail", "Typed intake + budget", "agentic", "guardrail", 20, agentY, events),
      makeNode("agent-plan", "Plan + act", scenario.agentPattern, "agentic", "model", 215, agentY, events),
      ...agentTools,
      makeNode("output-policy", "Dynamic policy", "OPA/Rego decision", "policy", "policy", afterAgentTools, agentY, events),
      makeNode("agent-evaluate", "Grounding eval", "Required evidence check", "agentic", "evaluator", afterAgentTools + 190, agentY, events),
      makeNode("agent-output", "Agent output", "Adaptive conclusion", "agentic", "output", afterAgentTools + 380, agentY, events),
      makeNode("rules-fetch", "Fixed intake", "Predefined fields", "rules", "rules", 20, ruleY, events),
      ...ruleTools,
      makeNode("rules-evaluate", "Rule engine", "Configured conditions", "rules", "rules", afterRuleTools, ruleY, events),
      makeNode("rules-output", "Rule output", "Predefined outcome", "rules", "output", afterRuleTools + 195, ruleY, events),
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
        edge(
          source,
          target,
          "agentic",
          isActive(source, target),
        ),
      );
    }
    for (let index = 0; index < ruleIds.length - 1; index += 1) {
      const source = ruleIds[index];
      const target = ruleIds[index + 1];
      visualEdges.push(
        edge(
          source,
          target,
          "rules",
          isActive(source, target),
        ),
      );
    }
    return { nodes: visualNodes, edges: visualEdges };
  }, [events, scenario]);

  return (
    <div className="workflow-canvas" aria-label="Live agent and rules execution graph">
      <div className="lane-label lane-label-agent">
        <Bot size={14} />
        <span>Agentic lane</span>
        <small>adapts plan and tools</small>
      </div>
      <div className="lane-label lane-label-rules">
        <Braces size={14} />
        <span>Fixed-rule lane</span>
        <small>evaluates known conditions</small>
      </div>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        fitViewOptions={{ padding: 0.18, maxZoom: 1 }}
        minZoom={0.36}
        maxZoom={1.35}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable
        onNodeClick={(_, node) => {
          const event = [...events].reverse().find((candidate) => candidate.nodeId === node.id);
          if (event) onSelectEvent(event);
        }}
        proOptions={{ hideAttribution: false }}
      >
        <Background variant={BackgroundVariant.Dots} gap={18} size={1} color="#27303d" />
        <Controls showInteractive={false} position="bottom-right" />
      </ReactFlow>
    </div>
  );
}
