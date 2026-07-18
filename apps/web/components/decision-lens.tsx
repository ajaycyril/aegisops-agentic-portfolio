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
import { useEffect, useRef } from "react";

import { MessageResponse } from "@/components/ai-elements/message";
import type { RunEvent } from "@/lib/agentic/contracts";
import type { ScenarioDefinition } from "@/lib/agentic/scenarios";

type DecisionState = "queued" | "running" | "completed" | "blocked";

type StoryDatum = {
  label: string;
  value: string;
};

type StoryStage = {
  id: string;
  step: number;
  title: string;
  owner: string;
  icon: LucideIcon;
  state: DecisionState;
  input: StoryDatum[];
  controlLabel: string;
  control: string;
  output: StoryDatum[];
  why: string;
  event?: RunEvent;
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

function asRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function asStrings(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "not provided";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) {
    const shown = value.slice(0, 3).map(displayValue).join(", ");
    return value.length > 3 ? `${shown} +${value.length - 3} more` : shown;
  }
  const entries = Object.entries(asRecord(value));
  if (entries.length === 0) return "empty object";
  return entries
    .slice(0, 3)
    .map(([key, item]) => `${key}: ${displayValue(item)}`)
    .join(" · ");
}

function dataRows(
  value: unknown,
  limit = 4,
  prefix = "",
): StoryDatum[] {
  return Object.entries(asRecord(value))
    .slice(0, limit)
    .map(([label, item]) => ({
      label: prefix ? `${prefix}.${label}` : label,
      value: displayValue(item),
    }));
}

function toolNames(event?: RunEvent) {
  return asStrings(event?.data?.toolCalls);
}

function StoryStageCard({
  stage,
  lane,
  onSelectEvent,
}: {
  stage: StoryStage;
  lane: "agentic" | "rules";
  onSelectEvent: (event: RunEvent) => void;
}) {
  const Icon = stage.icon;
  return (
    <article className={`story-stage story-stage-${lane} state-${stage.state}`}>
      <header>
        <span className="story-stage-number">{stage.step}</span>
        <span className="story-stage-icon"><Icon size={18} /></span>
        <span className="story-stage-title">
          <small>{stage.owner}</small>
          <strong>{stage.title}</strong>
        </span>
        <span className="story-stage-state">{stage.state}</span>
      </header>
      <div className="story-stage-section">
        <span className="story-data-label">Input</span>
        <div className="story-data-list">
          {stage.input.length > 0 ? stage.input.map((datum, index) => (
            <div key={`${stage.id}-input-${index}-${datum.label}`}>
              <small>{datum.label}</small><strong>{datum.value}</strong>
            </div>
          )) : <p>Waiting for live input</p>}
        </div>
      </div>
      <div className="story-stage-section story-control">
        <span className="story-data-label">{stage.controlLabel}</span>
        <p>{stage.control}</p>
      </div>
      <div className="story-stage-section">
        <span className="story-data-label">Output</span>
        <div className="story-data-list">
          {stage.output.length > 0 ? stage.output.map((datum, index) => (
            <div key={`${stage.id}-output-${index}-${datum.label}`}>
              <small>{datum.label}</small><strong>{datum.value}</strong>
            </div>
          )) : <p>Waiting for this stage</p>}
        </div>
      </div>
      <div className="story-why">
        <span>{lane === "agentic" ? "Why this is agentic" : "What is fixed here"}</span>
        <p>{stage.why}</p>
      </div>
      {stage.event ? (
        <button type="button" onClick={() => onSelectEvent(stage.event!)}>
          <Eye size={14} /> Inspect trace event
        </button>
      ) : null}
    </article>
  );
}

function StoryLane({
  stages,
  lane,
  onSelectEvent,
}: {
  stages: StoryStage[];
  lane: "agentic" | "rules";
  onSelectEvent: (event: RunEvent) => void;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const activeStage = stages.find((stage) => stage.state === "running")
    ?? [...stages].reverse().find((stage) => stage.state === "completed" || stage.state === "blocked");
  const activeStageId = activeStage?.id;

  useEffect(() => {
    if (!activeStageId || !window.matchMedia("(min-width: 781px)").matches) return;
    const activeElement = scrollRef.current?.querySelector<HTMLElement>('[data-active="true"]');
    if (!activeElement || !scrollRef.current) return;
    scrollRef.current.scrollTo({
      behavior: "smooth",
      left: activeElement.offsetLeft - scrollRef.current.clientWidth / 2 + activeElement.clientWidth / 2,
    });
  }, [activeStageId]);

  return (
    <section className={`story-lane story-lane-${lane}`}>
      <div className="story-lane-heading">
        <span className="story-lane-icon">
          {lane === "agentic" ? <Bot size={20} /> : <Braces size={20} />}
        </span>
        <div>
          <span>{lane === "agentic" ? "Agentic execution" : "Deterministic execution"}</span>
          <strong>{lane === "agentic" ? "Observes, decides, acts, and can adapt" : "Fetches fixed facts and evaluates fixed conditions"}</strong>
        </div>
        <small>{lane === "agentic" ? "Control changes with evidence" : "Control is fully preconfigured"}</small>
      </div>
      <div className="story-stage-scroll" ref={scrollRef}>
        {stages.map((stage, index) => (
          <div className="story-stage-wrap" data-active={stage.id === activeStageId} key={stage.id}>
            <StoryStageCard stage={stage} lane={lane} onSelectEvent={onSelectEvent} />
            {index < stages.length - 1 ? (
              <span className={`story-connector state-${stage.state}`} aria-hidden="true">
                <ArrowRight size={18} />
              </span>
            ) : null}
          </div>
        ))}
      </div>
    </section>
  );
}

export function DecisionLens({
  scenario,
  input,
  events,
  answer,
  onSelectEvent,
}: {
  scenario: ScenarioDefinition;
  input: Record<string, string>;
  events: RunEvent[];
  answer: string;
  onSelectEvent: (event: RunEvent) => void;
}) {
  const configuredInput = scenario.inputFields.map((field) => ({
    label: field.label,
    value: input[field.key] || "not provided",
  }));
  const runStarted = latest(events, (event) => event.type === "run_started");
  const guardrail = latest(events, (event) => event.type === "guardrail_decision");
  const modelToolDecision = events.find(
    (event) => event.type === "model_step" && toolNames(event).length > 0,
  );
  const selectedTools = toolNames(modelToolDecision);
  const agentToolStarts = events.filter(
    (event) => event.lane === "agentic" && event.type === "tool_started",
  );
  const agentToolCompletes = events.filter(
    (event) => event.lane === "agentic" && event.type === "tool_completed",
  );
  const latestAgentTool = agentToolCompletes.at(-1) ?? agentToolStarts.at(-1);
  const toolArguments = agentToolStarts.flatMap((event) =>
    dataRows(event.data?.arguments, 2, event.label),
  ).slice(0, 5);
  const evidenceEvents = events.filter((event) => event.type === "evidence_captured");
  const evidenceRows = evidenceEvents.flatMap((event) => [
    { label: event.evidence?.source ?? event.label, value: event.evidence?.title ?? event.summary },
    ...dataRows(event.evidence?.fields, 3),
  ]).slice(0, 8);
  const handoffs = events.filter((event) => event.type === "agent_handoff");
  const handoff = handoffs.at(-1);
  const finalModelStep = latest(events, (event) => event.type === "model_step");
  const supervisor = latest(events, (event) => event.nodeId === "agent-supervisor");
  const adaptationEvent = supervisor ?? handoff ?? finalModelStep;
  const policy = latest(events, (event) => event.type === "policy_decision");
  const evaluation = latest(
    events,
    (event) => event.nodeId === "agent-evaluate" && event.type === "node_completed",
  );
  const agentOutput = latest(
    events,
    (event) => event.lane === "agentic" && event.type === "lane_completed",
  );

  const rulesFetch = latest(events, (event) => event.nodeId === "rules-fetch");
  const rulesToolEvents = events.filter(
    (event) => event.lane === "rules" && event.type === "tool_completed",
  );
  const rulesEvaluateStarted = latest(
    events,
    (event) => event.nodeId === "rules-evaluate" && event.type === "node_started",
  );
  const rulesEvaluate = latest(events, (event) => event.nodeId === "rules-evaluate");
  const ruleEvaluations = events.filter((event) => event.type === "rule_evaluated");
  const rulesOutput = latest(events, (event) => event.nodeId === "rules-output");
  const facts = dataRows(rulesEvaluateStarted?.data?.facts, 8);
  const matchedEvents = asStrings(rulesOutput?.data?.matchedEvents ?? rulesEvaluate?.data?.matchedEvents);

  const agentStages: StoryStage[] = [
    {
      id: "bounded-goal",
      step: 1,
      title: "Bound the goal",
      owner: "HUMAN + LANGGRAPH",
      icon: Target,
      state: stateFromEvent(guardrail ?? runStarted),
      input: configuredInput,
      controlLabel: "Guardrail",
      control: guardrail?.summary ?? "Typed scope, tool allowlist, spend ceiling, and approval requirement are checked before execution.",
      output: guardrail
        ? [
            { label: "intake", value: guardrail.status },
            { label: "approved tools", value: scenario.requiredTools.join(", ") },
          ]
        : [{ label: "configured tools", value: scenario.requiredTools.join(", ") }],
      why: "The goal and safety boundary stay human-controlled; autonomy starts only inside that approved boundary.",
      event: guardrail ?? runStarted,
    },
    {
      id: "model-decision",
      step: 2,
      title: "Choose the next action",
      owner: "MODEL WITHIN GRAPH",
      icon: GitBranch,
      state: stateFromEvent(modelToolDecision),
      input: [
        { label: "goal", value: scenario.businessOutcome },
        { label: "available tools", value: scenario.requiredTools.join(", ") },
      ],
      controlLabel: "Observable decision",
      control: modelToolDecision?.summary ?? "The model may choose only policy-approved tools; its selected action will appear here as an execution summary.",
      output: selectedTools.length > 0
        ? selectedTools.map((tool) => ({ label: "selected tool", value: tool }))
        : [{ label: "selection", value: "waiting for model step" }],
      why: "The next action is selected from the situation observed at run time, rather than hard-coded before the run.",
      event: modelToolDecision,
    },
    {
      id: "typed-action",
      step: 3,
      title: "Execute typed tools",
      owner: "AI SDK + MCP",
      icon: Wrench,
      state: stateFromEvent(latestAgentTool),
      input: toolArguments.length > 0
        ? toolArguments
        : [{ label: "typed contract", value: scenario.requiredTools.join(", ") }],
      controlLabel: "Action boundary",
      control: latestAgentTool?.summary ?? "The tool call is schema-validated, read-only, traced, and executed through the MCP boundary.",
      output: agentToolCompletes.length > 0
        ? agentToolCompletes.map((event) => ({
            label: event.label,
            value: `${event.durationMs ?? 0}ms · ${asStrings(event.data?.fields).length} fields`,
          }))
        : [{ label: "result", value: "waiting for live source" }],
      why: "The agent turns its selected action into a governed system call; it cannot call an unapproved tool or invent the result.",
      event: latestAgentTool,
    },
    {
      id: "observation",
      step: 4,
      title: "Observe validated state",
      owner: "LIVE SOURCE + ZOD",
      icon: Eye,
      state: stateFromEvent(evidenceEvents.at(-1)),
      input: agentToolCompletes.length > 0
        ? agentToolCompletes.map((event) => ({ label: event.label, value: event.summary }))
        : [{ label: "source response", value: "waiting for tool output" }],
      controlLabel: "Evidence check",
      control: evidenceEvents.length > 0
        ? `${evidenceEvents.length} live source record${evidenceEvents.length === 1 ? "" : "s"} passed the evidence contract.`
        : "Raw source responses must pass the Zod evidence contract before the model can use them.",
      output: evidenceRows.length > 0
        ? evidenceRows
        : [{ label: "validated evidence", value: "appears here during the run" }],
      why: "New evidence changes the context available to the next decision, so the workflow can respond to an unexpected state.",
      event: evidenceEvents.at(-1),
    },
    {
      id: "adaptation",
      step: 5,
      title: scenario.orchestration === "multi_agent" ? "Reconcile specialists" : "Adapt and synthesize",
      owner: scenario.orchestration === "multi_agent" ? "LANGGRAPH SUPERVISOR" : "MODEL",
      icon: RefreshCw,
      state: stateFromEvent(adaptationEvent),
      input: [
        { label: "validated records", value: String(evidenceEvents.length) },
        { label: "agent handoffs", value: String(handoffs.length) },
      ],
      controlLabel: "Adaptive step",
      control: adaptationEvent?.summary ?? scenario.agenticAdvantage,
      output: adaptationEvent
        ? [
            { label: "controller", value: adaptationEvent.actor },
            { label: "next state", value: adaptationEvent.label },
          ]
        : [{ label: "next action", value: "depends on observed evidence" }],
      why: scenario.orchestration === "multi_agent"
        ? "Specialists can disagree or reveal different facts; a supervisor reconciles their evidence before reaching a conclusion."
        : "The model can stop, synthesize, or seek another approved observation based on what the previous action returned.",
      event: adaptationEvent,
    },
    {
      id: "verification",
      step: 6,
      title: "Verify and release",
      owner: "OPA + GROUNDING EVAL",
      icon: policy?.status === "blocked" ? ShieldCheck : BadgeCheck,
      state: stateFromEvent(evaluation ?? policy),
      input: [
        { label: "required evidence", value: String(evaluation?.data?.requiredEvidence ?? scenario.requiredTools.length) },
        { label: "captured evidence", value: String(evaluation?.data?.capturedEvidence ?? evidenceEvents.length) },
      ],
      controlLabel: "Release decision",
      control: policy?.summary ?? "OPA evaluates side effects and the evaluator checks that every required source grounded the answer.",
      output: [
        { label: "grounding", value: evaluation?.label ?? "waiting for evaluator" },
        { label: "workflow", value: agentOutput?.status ?? "not released" },
      ],
      why: "Agentic does not mean uncontrolled: independent policy and evidence checks decide whether the result may leave the workflow.",
      event: evaluation ?? policy,
    },
  ];

  const ruleStages: StoryStage[] = [
    {
      id: "fixed-fields",
      step: 1,
      title: "Read fixed inputs",
      owner: "CONFIGURATION",
      icon: Target,
      state: stateFromEvent(rulesFetch ?? runStarted),
      input: configuredInput,
      controlLabel: "Fixed contract",
      control: `The workflow always requests ${scenario.requiredTools.join(", ")}; there is no model deciding what evidence to seek.`,
      output: [{ label: "preselected sources", value: scenario.requiredTools.join(", ") }],
      why: "Inputs and sources were chosen by a developer in advance; this lane cannot decide that different evidence is needed.",
      event: rulesFetch ?? runStarted,
    },
    {
      id: "fixed-fetch",
      step: 2,
      title: "Fetch configured facts",
      owner: "MCP + ZOD",
      icon: Wrench,
      state: stateFromEvent(rulesToolEvents.at(-1)),
      input: scenario.requiredTools.map((tool) => ({ label: "configured tool", value: tool })),
      controlLabel: "Prewired action",
      control: rulesToolEvents.at(-1)?.summary ?? "Every run calls the same typed sources and normalizes the same fact fields.",
      output: facts.length > 0
        ? facts
        : [{ label: "normalized facts", value: "waiting for live source" }],
      why: "The same calls happen for every case, even when one source reveals that a different investigation would be more useful.",
      event: rulesToolEvents.at(-1) ?? rulesFetch,
    },
    {
      id: "fixed-conditions",
      step: 3,
      title: "Evaluate conditions",
      owner: "JSON-RULES-ENGINE",
      icon: Braces,
      state: stateFromEvent(rulesEvaluate),
      input: facts.length > 0
        ? facts
        : [{ label: "fact set", value: "fixed schema, awaiting values" }],
      controlLabel: "Configured logic",
      control: rulesEvaluate?.summary ?? "Versioned conditions compare normalized values against predefined operators and thresholds.",
      output: ruleEvaluations.length > 0
        ? ruleEvaluations.map((event) => ({
            label: event.label,
            value: `${event.status}: ${event.summary}`,
          })).slice(0, 6)
        : [{ label: "rule results", value: "waiting for evaluation" }],
      why: "The engine is reliable for known conditions, but it cannot interpret ambiguity or create a new investigation path.",
      event: rulesEvaluate,
    },
    {
      id: "fixed-outcome",
      step: 4,
      title: "Return known outcome",
      owner: "CONFIGURATION",
      icon: BadgeCheck,
      state: stateFromEvent(rulesOutput),
      input: [{ label: "matched events", value: matchedEvents.length > 0 ? matchedEvents.join(", ") : "none" }],
      controlLabel: "Stopping boundary",
      control: rulesOutput?.summary ?? scenario.ruleBoundary,
      output: [
        { label: "outcome", value: rulesOutput?.label ?? "waiting for rule result" },
        { label: "replanning", value: "not available" },
      ],
      why: "A matched condition returns its predefined outcome. An unmatched or unfamiliar case simply stops without investigating further.",
      event: rulesOutput,
    },
  ];

  return (
    <section className="decision-lens" aria-label="Readable agentic and deterministic execution story">
      <div className="decision-lens-head">
        <div>
          <span className="section-kicker">Live execution story</span>
          <h3>Every input, control decision, and output in sequence</h3>
        </div>
        <span><Eye size={14} /> observable execution summaries · no private chain-of-thought</span>
      </div>
      <StoryLane stages={agentStages} lane="agentic" onSelectEvent={onSelectEvent} />
      <StoryLane stages={ruleStages} lane="rules" onSelectEvent={onSelectEvent} />

      <section className="result-comparison" aria-label="Agentic and deterministic output comparison">
        <div className="result-comparison-head">
          <span className="section-kicker">Outcome comparison</span>
          <h3>Same live inputs. Different capability boundary.</h3>
        </div>
        <div className="result-columns">
          <div className="result-column result-agentic">
            <header><Bot size={18} /><span><small>AGENTIC OUTPUT</small><strong>Grounded adaptive conclusion</strong></span></header>
            <div className="result-body">
              {answer ? (
                <MessageResponse>{answer}</MessageResponse>
              ) : (
                <p>Run both lanes to stream the agent’s cited conclusion here while its trace is still visible above.</p>
              )}
            </div>
            <footer>{scenario.agenticAdvantage}</footer>
          </div>
          <div className="result-column result-rules">
            <header><Braces size={18} /><span><small>DETERMINISTIC OUTPUT</small><strong>Configured outcome match</strong></span></header>
            <div className="result-body">
              <strong>{rulesOutput?.label ?? "No result yet"}</strong>
              <p>{rulesOutput?.summary ?? "Run both lanes to evaluate the versioned rules against the same live facts."}</p>
              {matchedEvents.length > 0 ? (
                <div className="matched-events">
                  {matchedEvents.map((event) => <span key={event}>{event}</span>)}
                </div>
              ) : null}
            </div>
            <footer>{scenario.ruleBoundary}</footer>
          </div>
        </div>
        <div className="agentic-verdict">
          <span><GitBranch size={16} /> Why agentic for this case</span>
          <strong>{scenario.agenticAdvantage}</strong>
          <p>Use rules for the known, repeatable boundary. Use the agent only where evidence can be ambiguous, the next useful action depends on what was just observed, or multiple findings must be reconciled.</p>
        </div>
      </section>
    </section>
  );
}
