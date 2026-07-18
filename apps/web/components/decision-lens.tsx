"use client";

import {
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
import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";

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
  if (value === null || value === undefined || value === "")
    return "not provided";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean")
    return String(value);
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

function dataRows(value: unknown, limit = 4, prefix = ""): StoryDatum[] {
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

function StageFocusCard({
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
    <motion.article
      className={`focus-stage focus-stage-${lane} state-${stage.state}`}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.34, ease: [0.22, 1, 0.36, 1] }}
    >
      <header className="focus-stage-head">
        <span className="focus-stage-icon">
          <Icon size={21} />
        </span>
        <span>
          <small>
            Stage {stage.step} · {stage.owner}
          </small>
          <strong>{stage.title}</strong>
        </span>
        <span className="focus-stage-state">
          <i />
          {stage.state}
        </span>
      </header>
      <div className="focus-stage-flow">
        <section className="focus-block focus-input">
          <span className="focus-block-label">What came in</span>
          <div className="focus-data-list">
            {stage.input.length > 0 ? (
              stage.input.map((datum, index) => (
                <div key={`${stage.id}-input-${index}-${datum.label}`}>
                  <small>{datum.label}</small>
                  <strong>{datum.value}</strong>
                </div>
              ))
            ) : (
              <p>Waiting for live input</p>
            )}
          </div>
        </section>
        <section className="focus-block focus-decision">
          <span className="focus-block-label">
            {lane === "agentic"
              ? "Decision / control applied"
              : "Decision logic applied"}
          </span>
          <strong>{stage.controlLabel}</strong>
          <p>{stage.control}</p>
          <div className="focus-rationale">
            <small>
              {lane === "agentic"
                ? "Observable decision basis"
                : "Strength and boundary"}
            </small>
            <p>{stage.why}</p>
          </div>
        </section>
        <section className="focus-block focus-output">
          <span className="focus-block-label">What came out</span>
          <div className="focus-data-list">
            {stage.output.length > 0 ? (
              stage.output.map((datum, index) => (
                <div key={`${stage.id}-output-${index}-${datum.label}`}>
                  <small>{datum.label}</small>
                  <strong>{datum.value}</strong>
                </div>
              ))
            ) : (
              <p>Waiting for this stage</p>
            )}
          </div>
        </section>
      </div>
      <footer className="focus-stage-footer">
        <span>
          {stage.event
            ? "Backed by a live trace event"
            : "Planned stage · run to observe the actual decision"}
        </span>
        {stage.event ? (
          <button type="button" onClick={() => onSelectEvent(stage.event!)}>
            <Eye size={14} /> Open evidence
          </button>
        ) : null}
      </footer>
    </motion.article>
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
  const activeStage =
    stages.find((stage) => stage.state === "running") ??
    [...stages]
      .reverse()
      .find(
        (stage) => stage.state === "completed" || stage.state === "blocked",
      );
  const activeStageId = activeStage?.id ?? stages[0].id;
  const [manualSelection, setManualSelection] = useState<{
    stageId: string;
    activeStageId: string;
  } | null>(null);
  const selectedStageId =
    manualSelection?.activeStageId === activeStageId
      ? manualSelection.stageId
      : activeStageId;
  const selectedStage =
    stages.find((stage) => stage.id === selectedStageId) ?? stages[0];

  return (
    <section className={`story-lane story-lane-${lane}`}>
      <div className="story-lane-heading">
        <span className="story-lane-icon">
          {lane === "agentic" ? <Bot size={20} /> : <Braces size={20} />}
        </span>
        <div>
          <span>
            {lane === "agentic"
              ? "Agentic execution"
              : "Deterministic execution"}
          </span>
          <strong>
            {lane === "agentic"
              ? "Observes, decides, acts, and can adapt"
              : "Validates, derives, decides, and audits exactly"}
          </strong>
        </div>
        <small>
          {lane === "agentic"
            ? "Evidence can change the next step"
            : "Strong inside its encoded world model"}
        </small>
      </div>
      <nav className="stage-progress" aria-label={`${lane} stages`}>
        {stages.map((stage) => (
          <button
            className={`state-${stage.state} ${selectedStage.id === stage.id ? "selected" : ""}`}
            aria-current={selectedStage.id === stage.id ? "step" : undefined}
            key={stage.id}
            onClick={() =>
              setManualSelection({ stageId: stage.id, activeStageId })
            }
            type="button"
          >
            <span>{stage.step}</span>
            <small>{stage.title}</small>
          </button>
        ))}
      </nav>
      <AnimatePresence mode="wait" initial={false}>
        <StageFocusCard
          key={selectedStage.id}
          stage={selectedStage}
          lane={lane}
          onSelectEvent={onSelectEvent}
        />
      </AnimatePresence>
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
  const guardrail = latest(
    events,
    (event) => event.type === "guardrail_decision",
  );
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
  const toolArguments = agentToolStarts
    .flatMap((event) => dataRows(event.data?.arguments, 2, event.label))
    .slice(0, 5);
  const evidenceEvents = events.filter(
    (event) => event.type === "evidence_captured",
  );
  const evidenceRows = evidenceEvents
    .flatMap((event) => [
      {
        label: event.evidence?.source ?? event.label,
        value: event.evidence?.title ?? event.summary,
      },
      ...dataRows(event.evidence?.fields, 3),
    ])
    .slice(0, 8);
  const handoffs = events.filter((event) => event.type === "agent_handoff");
  const handoff = handoffs.at(-1);
  const finalModelStep = latest(events, (event) => event.type === "model_step");
  const supervisor = latest(
    events,
    (event) => event.nodeId === "agent-supervisor",
  );
  const adaptationEvent = supervisor ?? handoff ?? finalModelStep;
  const policy = latest(events, (event) => event.type === "policy_decision");
  const evaluation = latest(
    events,
    (event) =>
      event.nodeId === "agent-evaluate" && event.type === "node_completed",
  );
  const agentOutput = latest(
    events,
    (event) => event.lane === "agentic" && event.type === "lane_completed",
  );

  const rulesFetch = latest(events, (event) => event.nodeId === "rules-fetch");
  const rulesContract = latest(
    events,
    (event) => event.nodeId === "rules-contract",
  );
  const rulesNormalize = latest(
    events,
    (event) => event.nodeId === "rules-normalize",
  );
  const rulesDerive = latest(
    events,
    (event) => event.nodeId === "rules-derive",
  );
  const rulesToolEvents = events.filter(
    (event) => event.lane === "rules" && event.type === "tool_completed",
  );
  const rulesEvaluateStarted = latest(
    events,
    (event) =>
      event.nodeId === "rules-evaluate" && event.type === "node_started",
  );
  const rulesEvaluate = latest(
    events,
    (event) => event.nodeId === "rules-evaluate",
  );
  const ruleEvaluations = events.filter(
    (event) => event.type === "rule_evaluated",
  );
  const rulesOutput = latest(
    events,
    (event) => event.nodeId === "rules-output",
  );
  const facts = dataRows(
    rulesDerive?.data?.facts ?? rulesEvaluateStarted?.data?.facts,
    8,
  );
  const matchedEvents = asStrings(
    rulesOutput?.data?.matchedEvents ?? rulesEvaluate?.data?.matchedEvents,
  );

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
      control:
        guardrail?.summary ??
        "Typed scope, tool allowlist, spend ceiling, and approval requirement are checked before execution.",
      output: guardrail
        ? [
            { label: "intake", value: guardrail.status },
            {
              label: "approved tools",
              value: scenario.requiredTools.join(", "),
            },
          ]
        : [
            {
              label: "configured tools",
              value: scenario.requiredTools.join(", "),
            },
          ],
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
      control:
        modelToolDecision?.summary ??
        "The model may choose only policy-approved tools; its selected action will appear here as an execution summary.",
      output:
        selectedTools.length > 0
          ? selectedTools.map((tool) => ({
              label: "selected tool",
              value: tool,
            }))
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
      input:
        toolArguments.length > 0
          ? toolArguments
          : [
              {
                label: "typed contract",
                value: scenario.requiredTools.join(", "),
              },
            ],
      controlLabel: "Action boundary",
      control:
        latestAgentTool?.summary ??
        "The tool call is schema-validated, read-only, traced, and executed through the MCP boundary.",
      output:
        agentToolCompletes.length > 0
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
      input:
        agentToolCompletes.length > 0
          ? agentToolCompletes.map((event) => ({
              label: event.label,
              value: event.summary,
            }))
          : [{ label: "source response", value: "waiting for tool output" }],
      controlLabel: "Evidence check",
      control:
        evidenceEvents.length > 0
          ? `${evidenceEvents.length} live source record${evidenceEvents.length === 1 ? "" : "s"} passed the evidence contract.`
          : "Raw source responses must pass the Zod evidence contract before the model can use them.",
      output:
        evidenceRows.length > 0
          ? evidenceRows
          : [
              {
                label: "validated evidence",
                value: "appears here during the run",
              },
            ],
      why: "New evidence changes the context available to the next decision, so the workflow can respond to an unexpected state.",
      event: evidenceEvents.at(-1),
    },
    {
      id: "adaptation",
      step: 5,
      title:
        scenario.orchestration === "multi_agent"
          ? "Reconcile specialists"
          : "Adapt and synthesize",
      owner:
        scenario.orchestration === "multi_agent"
          ? "LANGGRAPH SUPERVISOR"
          : "MODEL",
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
      why:
        scenario.orchestration === "multi_agent"
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
        {
          label: "required evidence",
          value: String(
            evaluation?.data?.requiredEvidence ?? scenario.requiredTools.length,
          ),
        },
        {
          label: "captured evidence",
          value: String(
            evaluation?.data?.capturedEvidence ?? evidenceEvents.length,
          ),
        },
      ],
      controlLabel: "Release decision",
      control:
        policy?.summary ??
        "OPA evaluates side effects and the evaluator checks that every required source grounded the answer.",
      output: [
        {
          label: "grounding",
          value: evaluation?.label ?? "waiting for evaluator",
        },
        { label: "workflow", value: agentOutput?.status ?? "not released" },
      ],
      why: "Agentic does not mean uncontrolled: independent policy and evidence checks decide whether the result may leave the workflow.",
      event: evaluation ?? policy,
    },
  ];

  const ruleStages: StoryStage[] = [
    {
      id: "deterministic-contract",
      step: 1,
      title: "Validate decision contract",
      owner: "ZOD + REGISTRY",
      icon: Target,
      state: stateFromEvent(rulesContract ?? runStarted),
      input: configuredInput,
      controlLabel: "Versioned boundary",
      control:
        rulesContract?.summary ??
        "The input schema, source allowlist, rule version, and approved outcomes are validated before any source is called.",
      output: [
        {
          label: "approved sources",
          value: scenario.requiredTools.join(", "),
        },
        { label: "fallback", value: "manual exception review" },
      ],
      why: "This is a production strength: every permitted input and outcome is explicit, testable, and reproducible. Its boundary is the model encoded here.",
      event: rulesContract ?? runStarted,
    },
    {
      id: "deterministic-fetch",
      step: 2,
      title: "Plan configured evidence",
      owner: "VERSIONED DECISION GRAPH",
      icon: GitBranch,
      state: stateFromEvent(rulesFetch),
      input: [
        { label: "decision goal", value: scenario.businessOutcome },
        {
          label: "available connectors",
          value: scenario.requiredTools.join(", "),
        },
      ],
      controlLabel: "Precompiled evidence plan",
      control:
        rulesFetch?.summary ??
        "A tested graph selects the exact source set required for this decision class without model cost or model variance.",
      output: scenario.requiredTools.map((tool) => ({
        label: "scheduled tool",
        value: tool,
      })),
      why: "For known cases this is faster and more predictable than an agent. It cannot add a new source when the observed case falls outside the encoded plan.",
      event: rulesFetch,
    },
    {
      id: "deterministic-action",
      step: 3,
      title: "Execute typed connectors",
      owner: "MCP",
      icon: Wrench,
      state: stateFromEvent(rulesToolEvents.at(-1)),
      input: scenario.requiredTools.map((tool) => ({
        label: "configured tool",
        value: tool,
      })),
      controlLabel: "Auditable source acquisition",
      control:
        rulesToolEvents.at(-1)?.summary ??
        "The configured connectors run with schema-checked arguments, timeouts, and trace events.",
      output:
        rulesToolEvents.length > 0
          ? rulesToolEvents.map((event) => ({
              label: event.label,
              value: `${event.durationMs ?? 0}ms · ${event.status}`,
            }))
          : [{ label: "connector results", value: "waiting for live sources" }],
      why: "This lane uses the same production MCP boundary as the agent, so the comparison is about decision capability rather than weaker integrations.",
      event: rulesToolEvents.at(-1) ?? rulesFetch,
    },
    {
      id: "deterministic-facts",
      step: 4,
      title: "Normalize and derive facts",
      owner: "ZOD + TYPED TRANSFORMS",
      icon: Eye,
      state: stateFromEvent(rulesDerive ?? rulesNormalize),
      input:
        rulesNormalize?.data?.sourceCount !== undefined
          ? [
              {
                label: "validated sources",
                value: String(rulesNormalize.data.sourceCount),
              },
            ]
          : [{ label: "source records", value: "waiting for validation" }],
      controlLabel: "Reproducible fact model",
      control:
        rulesDerive?.summary ??
        rulesNormalize?.summary ??
        "Source contracts and deterministic transforms produce the same typed facts for the same evidence.",
      output:
        facts.length > 0
          ? facts
          : [{ label: "decision facts", value: "waiting for derivation" }],
      why: "Explicit derivations make audit and regression testing excellent. They cannot interpret a new semantic signal until engineers add it to the model.",
      event: rulesDerive ?? rulesNormalize,
    },
    {
      id: "deterministic-evaluate",
      step: 5,
      title: "Evaluate decision table",
      owner: "JSON-RULES-ENGINE",
      icon: Braces,
      state: stateFromEvent(rulesEvaluate),
      input:
        facts.length > 0
          ? facts
          : [{ label: "fact set", value: "fixed schema, awaiting values" }],
      controlLabel: "Configured logic",
      control:
        rulesEvaluate?.summary ??
        "Versioned conditions compare normalized values against predefined operators and thresholds.",
      output:
        ruleEvaluations.length > 0
          ? ruleEvaluations
              .map((event) => ({
                label: event.label,
                value: `${event.status}: ${event.summary}`,
              }))
              .slice(0, 6)
          : [{ label: "rule results", value: "waiting for evaluation" }],
      why: "The engine handles complex, versioned combinations reliably. It cannot resolve ambiguity that was never represented as a fact or condition.",
      event: rulesEvaluate,
    },
    {
      id: "deterministic-outcome",
      step: 6,
      title: "Release governed outcome",
      owner: "DECISION SERVICE",
      icon: BadgeCheck,
      state: stateFromEvent(rulesOutput),
      input: [
        {
          label: "matched events",
          value: matchedEvents.length > 0 ? matchedEvents.join(", ") : "none",
        },
      ],
      controlLabel: "Versioned release",
      control: rulesOutput?.summary ?? scenario.ruleBoundary,
      output: [
        {
          label: "outcome",
          value: rulesOutput?.label ?? "waiting for rule result",
        },
        { label: "exception path", value: "manual review" },
      ],
      why: "Known outcomes are fast, consistent, and explainable. Novel cases are safely escalated, but this lane cannot create a new evidence plan or synthesize a new response.",
      event: rulesOutput,
    },
  ];

  return (
    <section
      className="decision-lens"
      aria-label="Readable agentic and deterministic execution story"
    >
      <div className="decision-lens-head">
        <div>
          <span className="section-kicker">Live execution story</span>
          <h3>Follow one decision at a time</h3>
        </div>
        <span>
          <Eye size={14} /> stage-controlled live trace · observable decision
          basis, not private chain-of-thought
        </span>
      </div>
      <div className="story-lanes">
        <StoryLane
          stages={agentStages}
          lane="agentic"
          onSelectEvent={onSelectEvent}
        />
        <StoryLane
          stages={ruleStages}
          lane="rules"
          onSelectEvent={onSelectEvent}
        />
      </div>

      <section
        className="result-comparison"
        aria-label="Agentic and deterministic output comparison"
      >
        <div className="result-comparison-head">
          <span className="section-kicker">Outcome comparison</span>
          <h3>Same live inputs. Different capability boundary.</h3>
        </div>
        <div className="result-columns">
          <div className="result-column result-agentic">
            <header>
              <Bot size={18} />
              <span>
                <small>AGENTIC OUTPUT</small>
                <strong>Grounded adaptive conclusion</strong>
              </span>
            </header>
            <div className="result-body">
              {answer ? (
                <MessageResponse>{answer}</MessageResponse>
              ) : (
                <p>
                  Run both lanes to stream the agent’s cited conclusion here
                  while its trace is still visible above.
                </p>
              )}
            </div>
            <footer>{scenario.agenticAdvantage}</footer>
          </div>
          <div className="result-column result-rules">
            <header>
              <Braces size={18} />
              <span>
                <small>DETERMINISTIC OUTPUT</small>
                <strong>Configured outcome match</strong>
              </span>
            </header>
            <div className="result-body">
              <strong>{rulesOutput?.label ?? "No result yet"}</strong>
              <p>
                {rulesOutput?.summary ??
                  "Run both lanes to evaluate the versioned rules against the same live facts."}
              </p>
              {matchedEvents.length > 0 ? (
                <div className="matched-events">
                  {matchedEvents.map((event) => (
                    <span key={event}>{event}</span>
                  ))}
                </div>
              ) : null}
            </div>
            <footer>{scenario.ruleBoundary}</footer>
          </div>
        </div>
        <div className="agentic-verdict">
          <span>
            <GitBranch size={16} /> Why agentic for this case
          </span>
          <strong>{scenario.agenticAdvantage}</strong>
          <p>
            Use rules for the known, repeatable boundary. Use the agent only
            where evidence can be ambiguous, the next useful action depends on
            what was just observed, or multiple findings must be reconciled.
          </p>
        </div>
      </section>
    </section>
  );
}
