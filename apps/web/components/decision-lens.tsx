"use client";

import {
  ArrowRight,
  BadgeCheck,
  Bot,
  Braces,
  Eye,
  GitBranch,
  RefreshCw,
  ShieldCheck,
  Target,
  Wrench,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Fragment } from "react";

import type { RunEvent } from "@/lib/agentic/contracts";
import type { ScenarioDefinition } from "@/lib/agentic/scenarios";

type DecisionState = "queued" | "running" | "completed" | "blocked";

type DecisionPhase = {
  id: string;
  title: string;
  owner: string;
  detail: string;
  icon: LucideIcon;
  event?: RunEvent;
  state: DecisionState;
};

function stateFromEvent(event?: RunEvent): DecisionState {
  if (!event) return "queued";
  if (event.status === "running") return "running";
  if (event.status === "failed" || event.status === "blocked") return "blocked";
  return "completed";
}

function latest(events: RunEvent[], predicate: (event: RunEvent) => boolean) {
  return [...events].reverse().find(predicate);
}

function toolNames(event?: RunEvent) {
  const value = event?.data?.toolCalls;
  return Array.isArray(value) ? value.filter((tool): tool is string => typeof tool === "string") : [];
}

function DecisionTrack({
  phases,
  lane,
  onSelectEvent,
}: {
  phases: DecisionPhase[];
  lane: "agentic" | "rules";
  onSelectEvent: (event: RunEvent) => void;
}) {
  return (
    <div className={`decision-track decision-track-${lane}`}>
      <div className="decision-track-label">
        {lane === "agentic" ? <Bot size={14} /> : <Braces size={14} />}
        <span>{lane === "agentic" ? "Observe-decide-act loop" : "Prewired rule path"}</span>
        <small>{lane === "agentic" ? "control can change after evidence" : "same conditions every run"}</small>
      </div>
      <div className="decision-phases">
        {phases.map((phase, index) => {
          const Icon = phase.icon;
          return (
            <Fragment key={phase.id}>
              <button
                className={`decision-phase state-${phase.state}`}
                disabled={!phase.event}
                onClick={() => phase.event && onSelectEvent(phase.event)}
                type="button"
              >
                <span className="decision-owner">{phase.owner}</span>
                <span className="decision-icon"><Icon size={15} /></span>
                <strong>{phase.title}</strong>
                <small>{phase.detail}</small>
              </button>
              {index < phases.length - 1 ? (
                <span className={`decision-connector ${phase.state === "running" ? "active" : ""}`}>
                  <ArrowRight size={13} />
                </span>
              ) : null}
            </Fragment>
          );
        })}
      </div>
    </div>
  );
}

export function DecisionLens({
  scenario,
  events,
  onSelectEvent,
}: {
  scenario: ScenarioDefinition;
  events: RunEvent[];
  onSelectEvent: (event: RunEvent) => void;
}) {
  const runStarted = latest(events, (event) => event.type === "run_started");
  const guardrail = latest(events, (event) => event.type === "guardrail_decision");
  const modelToolDecision = events.find(
    (event) => event.type === "model_step" && toolNames(event).length > 0,
  );
  const selectedTools = toolNames(modelToolDecision);
  const toolEvent = latest(
    events,
    (event) => event.lane === "agentic" && event.type === "tool_completed",
  ) ?? latest(events, (event) => event.lane === "agentic" && event.type === "tool_started");
  const evidenceEvents = events.filter((event) => event.type === "evidence_captured");
  const evidenceEvent = evidenceEvents.at(-1);
  const handoff = latest(events, (event) => event.type === "agent_handoff");
  const finalModelStep = latest(events, (event) => event.type === "model_step");
  const adaptationEvent = handoff ?? finalModelStep;
  const policy = latest(events, (event) => event.type === "policy_decision");
  const evaluation = latest(
    events,
    (event) => event.nodeId === "agent-evaluate" && event.type === "node_completed",
  );
  const verificationEvent = evaluation ?? policy;

  const agentPhases: DecisionPhase[] = [
    {
      id: "bounded-goal",
      title: "Bounded goal",
      owner: "HUMAN + GRAPH",
      detail: guardrail ? "scope and budget accepted" : `${scenario.requiredTools.length} approved tools`,
      icon: Target,
      event: guardrail ?? runStarted,
      state: stateFromEvent(guardrail ?? runStarted),
    },
    {
      id: "model-decision",
      title: "Choose action",
      owner: "MODEL",
      detail:
        selectedTools.length > 0
          ? selectedTools.join(" + ")
          : "select from approved tools",
      icon: GitBranch,
      event: modelToolDecision,
      state: stateFromEvent(modelToolDecision),
    },
    {
      id: "typed-action",
      title: "Execute tool",
      owner: "MCP",
      detail: toolEvent?.label ?? "typed call and result",
      icon: Wrench,
      event: toolEvent,
      state: stateFromEvent(toolEvent),
    },
    {
      id: "observation",
      title: "Observe state",
      owner: "LIVE SOURCE + ZOD",
      detail:
        evidenceEvents.length > 0
          ? `${evidenceEvents.length} validated record${evidenceEvents.length === 1 ? "" : "s"}`
          : "evidence changes context",
      icon: Eye,
      event: evidenceEvent,
      state: stateFromEvent(evidenceEvent),
    },
    {
      id: "adaptation",
      title: scenario.orchestration === "multi_agent" ? "Reconcile" : "Adapt or stop",
      owner: "MODEL",
      detail: handoff
        ? `${String(handoff.data?.evidenceCount ?? 0)} records handed to supervisor`
        : finalModelStep
          ? "synthesize after observation"
          : "next step depends on result",
      icon: RefreshCw,
      event: adaptationEvent,
      state: stateFromEvent(adaptationEvent),
    },
    {
      id: "verification",
      title: "Verify boundary",
      owner: "OPA + EVAL",
      detail: evaluation?.label ?? policy?.label ?? "policy and grounding",
      icon: verificationEvent?.status === "blocked" ? ShieldCheck : BadgeCheck,
      event: verificationEvent,
      state: stateFromEvent(verificationEvent),
    },
  ];

  const rulesFetch = latest(events, (event) => event.nodeId === "rules-fetch");
  const rulesTool = latest(
    events,
    (event) => event.lane === "rules" && event.type === "tool_completed",
  );
  const rulesEvaluate = latest(events, (event) => event.nodeId === "rules-evaluate");
  const rulesOutput = latest(events, (event) => event.nodeId === "rules-output");
  const rulePhases: DecisionPhase[] = [
    {
      id: "fixed-fields",
      title: "Fixed fields",
      owner: "CONFIG",
      detail: scenario.requiredTools.join(" + "),
      icon: Target,
      event: rulesFetch,
      state: stateFromEvent(rulesFetch),
    },
    {
      id: "fixed-fetch",
      title: "Fetch values",
      owner: "MCP",
      detail: rulesTool?.label ?? "preselected sources",
      icon: Wrench,
      event: rulesTool,
      state: stateFromEvent(rulesTool),
    },
    {
      id: "fixed-conditions",
      title: "Match conditions",
      owner: "RULE ENGINE",
      detail: rulesEvaluate?.summary ?? "versioned thresholds",
      icon: Braces,
      event: rulesEvaluate,
      state: stateFromEvent(rulesEvaluate),
    },
    {
      id: "fixed-outcome",
      title: "Known outcome",
      owner: "CONFIG",
      detail: rulesOutput?.summary ?? "no replanning branch",
      icon: BadgeCheck,
      event: rulesOutput,
      state: stateFromEvent(rulesOutput),
    },
  ];

  return (
    <section className="decision-lens" aria-label="Observable agent decisions compared with fixed rules">
      <div className="decision-lens-head">
        <div><span className="section-kicker">Observable decision ledger</span><h3>Where control actually lives</h3></div>
        <span><Eye size={13} /> execution summaries · no hidden chain-of-thought</span>
      </div>
      <DecisionTrack phases={agentPhases} lane="agentic" onSelectEvent={onSelectEvent} />
      <DecisionTrack phases={rulePhases} lane="rules" onSelectEvent={onSelectEvent} />
    </section>
  );
}
