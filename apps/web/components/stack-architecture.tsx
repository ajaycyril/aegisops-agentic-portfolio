"use client";

import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import {
  Activity,
  Bot,
  Braces,
  Database,
  GitBranch,
  Radio,
  Scale,
  ShieldCheck,
  Waypoints,
  Wrench,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { memo, useMemo } from "react";

import type { RunEvent } from "@/lib/agentic/contracts";
import type { ScenarioDefinition } from "@/lib/agentic/scenarios";

type StackState = "ready" | "running" | "observed" | "blocked";
type StackDomain = "experience" | "runtime" | "control" | "external";

type StackNodeData = Record<string, unknown> & {
  eyebrow: string;
  title: string;
  subtitle: string;
  signal: string;
  icon: LucideIcon;
  state: StackState;
  domain: StackDomain;
  eventId?: string;
};

type StackNode = Node<StackNodeData, "stack">;

const StackNodeView = memo(({ data }: NodeProps<StackNode>) => {
  const Icon = data.icon;
  return (
    <div className={`stack-node domain-${data.domain} state-${data.state}`}>
      <Handle type="target" position={Position.Left} />
      <span className="stack-node-eyebrow">{data.eyebrow}</span>
      <div className="stack-node-main">
        <span className="stack-node-icon"><Icon size={16} /></span>
        <span><strong>{data.title}</strong><small>{data.subtitle}</small></span>
      </div>
      <em>{data.signal}</em>
      <Handle type="source" position={Position.Right} />
    </div>
  );
});

StackNodeView.displayName = "StackNodeView";

const nodeTypes = { stack: StackNodeView };

function stateFor(events: RunEvent[], predicate: (event: RunEvent) => boolean): StackState {
  const matching = events.filter(predicate);
  if (matching.length === 0) return "ready";
  const current = matching.at(-1);
  if (current?.status === "running") return "running";
  if (current?.status === "blocked") return "blocked";
  return "observed";
}

function stackNode(
  id: string,
  position: { x: number; y: number },
  data: StackNodeData,
): StackNode {
  return { id, type: "stack", position, data };
}

function stackEdge(
  source: string,
  target: string,
  label: string,
  active: boolean,
  domain: StackDomain,
): Edge {
  const colors: Record<StackDomain, string> = {
    experience: "#7da7ff",
    runtime: "#43d1b5",
    control: "#edc55f",
    external: "#9aa6b6",
  };
  return {
    id: `${source}-${target}`,
    source,
    target,
    label,
    animated: active,
    style: { stroke: colors[domain], strokeWidth: active ? 2.2 : 1.2, opacity: active ? 0.95 : 0.42 },
    labelStyle: { fill: "#7f8c9d", fontSize: 7 },
    labelBgStyle: { fill: "#090d12", fillOpacity: 0.92 },
    markerEnd: { type: MarkerType.ArrowClosed, color: colors[domain], width: 13, height: 13 },
  };
}

export function StackArchitecture({
  scenario,
  events,
  onSelectEvent,
}: {
  scenario: ScenarioDefinition;
  events: RunEvent[];
  onSelectEvent: (event: RunEvent) => void;
}) {
  const { nodes, edges } = useMemo(() => {
    const running = events.length > 0 && events.at(-1)?.type !== "run_completed";
    const modelEvents = events.filter((event) => event.type === "model_step");
    const agentToolEvents = events.filter(
      (event) => event.lane === "agentic" && event.type === "tool_completed",
    );
    const evidenceEvents = events.filter((event) => event.type === "evidence_captured");
    const policyEvents = events.filter(
      (event) => event.type === "guardrail_decision" || event.type === "policy_decision",
    );
    const ruleEvents = events.filter((event) => event.type === "rule_evaluated");
    const latestModel = modelEvents.at(-1);
    const latestTool = agentToolEvents.at(-1);
    const latestEvidence = evidenceEvents.at(-1);
    const latestPolicy = policyEvents.at(-1);
    const latestRule = ruleEvents.at(-1);

    const visualNodes: StackNode[] = [
      stackNode("experience", { x: 10, y: 185 }, {
        eyebrow: "EXPERIENCE",
        title: "React Flow + AI Elements",
        subtitle: "graph, trace, tool I/O",
        signal: `${events.length} rendered events`,
        icon: Waypoints,
        domain: "experience",
        state: events.length > 0 ? "observed" : "ready",
        eventId: events.at(-1)?.id,
      }),
      stackNode("stream", { x: 220, y: 185 }, {
        eyebrow: "STREAMING GATEWAY",
        title: "Next.js + AI SDK",
        subtitle: "UIMessage event transport",
        signal: running ? "stream open" : events.length > 0 ? "stream complete" : "ready",
        icon: Radio,
        domain: "experience",
        state: stateFor(events, (event) => event.lane === "system"),
        eventId: events.find((event) => event.type === "run_started")?.id,
      }),
      stackNode("langgraph", { x: 440, y: 48 }, {
        eyebrow: "ORCHESTRATION",
        title: "LangGraph JS",
        subtitle: "state, fan-out, fan-in",
        signal: scenario.orchestration === "multi_agent" ? "3 agent graph" : "single agent graph",
        icon: GitBranch,
        domain: "runtime",
        state: stateFor(events, (event) => event.lane === "agentic"),
        eventId: events.find((event) => event.lane === "agentic")?.id,
      }),
      stackNode("rules", { x: 440, y: 322 }, {
        eyebrow: "DETERMINISTIC LANE",
        title: "json-rules-engine",
        subtitle: "versioned conditions",
        signal: `${ruleEvents.length} rules evaluated`,
        icon: Braces,
        domain: "control",
        state: stateFor(events, (event) => event.lane === "rules"),
        eventId: latestRule?.id,
      }),
      stackNode("agent", { x: 660, y: 25 }, {
        eyebrow: "AGENT LOOP",
        title: "AI SDK ToolLoopAgent",
        subtitle: "decide, call, observe, stop",
        signal: `${modelEvents.length} model decisions`,
        icon: Bot,
        domain: "runtime",
        state: stateFor(events, (event) => event.type === "model_step"),
        eventId: latestModel?.id,
      }),
      stackNode("policy", { x: 660, y: 170 }, {
        eyebrow: "DYNAMIC POLICY",
        title: "OPA + Rego WASM",
        subtitle: "allow, block, approve",
        signal: `${policyEvents.length} policy decisions`,
        icon: Scale,
        domain: "control",
        state: stateFor(events, (event) => event.lane === "policy"),
        eventId: latestPolicy?.id,
      }),
      stackNode("state", { x: 660, y: 315 }, {
        eyebrow: "STATE + MEMORY",
        title: "LangGraph Checkpointer",
        subtitle: "PostgresSaver adapter",
        signal: "MemorySaver public mode",
        icon: Database,
        domain: "control",
        state: events.length > 0 ? "observed" : "ready",
      }),
      stackNode("mcp", { x: 880, y: 35 }, {
        eyebrow: "TOOL PROTOCOL",
        title: "MCP TypeScript SDK",
        subtitle: "typed client/server boundary",
        signal: `${agentToolEvents.length} completed calls`,
        icon: Wrench,
        domain: "runtime",
        state: stateFor(events, (event) => event.lane === "agentic" && event.type.startsWith("tool_")),
        eventId: latestTool?.id,
      }),
      stackNode("contracts", { x: 880, y: 180 }, {
        eyebrow: "CONTRACTS + GUARDRAILS",
        title: "Zod",
        subtitle: "request and evidence schemas",
        signal: `${evidenceEvents.length} payloads validated`,
        icon: ShieldCheck,
        domain: "control",
        state: stateFor(events, (event) => event.type === "evidence_captured" || event.type === "guardrail_decision"),
        eventId: latestEvidence?.id,
      }),
      stackNode("telemetry", { x: 880, y: 325 }, {
        eyebrow: "OBSERVABILITY",
        title: "Trace + OTel telemetry",
        subtitle: "tokens, latency, actors",
        signal: `${events.length} trace events`,
        icon: Activity,
        domain: "experience",
        state: events.length > 0 ? "observed" : "ready",
        eventId: events.at(-1)?.id,
      }),
      stackNode("model", { x: 1100, y: 20 }, {
        eyebrow: "MODEL PROVIDER",
        title: "GitHub Models / OpenAI",
        subtitle: "OpenAI-compatible inference",
        signal: latestModel?.actor ?? "provider adapter ready",
        icon: Bot,
        domain: "external",
        state: stateFor(events, (event) => event.type === "model_step"),
        eventId: latestModel?.id,
      }),
      stackNode("sources", { x: 1100, y: 145 }, {
        eyebrow: "LIVE SYSTEMS",
        title: scenario.sourceLabel,
        subtitle: "official source APIs",
        signal: `${evidenceEvents.length} evidence records`,
        icon: Radio,
        domain: "external",
        state: stateFor(events, (event) => event.type === "evidence_captured"),
        eventId: latestEvidence?.id,
      }),
    ];

    const active = events.length > 0;
    const visualEdges = [
      stackEdge("experience", "stream", "run + render", running, "experience"),
      stackEdge("stream", "langgraph", "typed request", running, "runtime"),
      stackEdge("stream", "rules", "same evidence contract", running, "control"),
      stackEdge("langgraph", "agent", "node state", running, "runtime"),
      stackEdge("langgraph", "policy", "policy input", running, "control"),
      stackEdge("langgraph", "state", "checkpoint", running, "control"),
      stackEdge("agent", "mcp", "tool call", running, "runtime"),
      stackEdge("agent", "model", "model step", running, "external"),
      stackEdge("mcp", "sources", "read-only API", running, "external"),
      stackEdge("sources", "contracts", "source payload", running, "control"),
      stackEdge("rules", "mcp", "fixed fetch", running, "control"),
      stackEdge("contracts", "telemetry", "validated event", running, "experience"),
      stackEdge("policy", "telemetry", "decision", running, "experience"),
      stackEdge("state", "telemetry", "run state", running, "experience"),
      stackEdge("telemetry", "experience", "live trace", active && running, "experience"),
    ];
    return { nodes: visualNodes, edges: visualEdges };
  }, [events, scenario]);

  return (
    <div className="stack-architecture" aria-label="Live agentic stack architecture">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.12, maxZoom: 1 }}
        minZoom={0.35}
        maxZoom={1.3}
        nodesDraggable={false}
        nodesConnectable={false}
        onNodeClick={(_, node) => {
          const eventId = String(node.data.eventId ?? "");
          const event = events.find((candidate) => candidate.id === eventId);
          if (event) onSelectEvent(event);
        }}
        proOptions={{ hideAttribution: false }}
      >
        <Background variant={BackgroundVariant.Dots} gap={18} size={1} color="#27303d" />
        <Controls showInteractive={false} position="bottom-right" />
      </ReactFlow>
      <div className="stack-domain-legend">
        <span className="domain-experience">Experience + telemetry</span>
        <span className="domain-runtime">Agent runtime</span>
        <span className="domain-control">Deterministic control</span>
        <span className="domain-external">External systems</span>
      </div>
    </div>
  );
}
