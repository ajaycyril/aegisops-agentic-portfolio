"use client";

import {
  BadgeCheck,
  Bot,
  Braces,
  Eye,
  GitBranch,
  Network,
  Play,
  RefreshCw,
  ShieldCheck,
  StepForward,
  Target,
  Wrench,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";

import { MessageResponse } from "@/components/ai-elements/message";
import { WorkflowCanvas } from "@/components/workflow-canvas";
import type { RunEvent } from "@/lib/agentic/contracts";
import type { ScenarioDefinition } from "@/lib/agentic/scenarios";

type DecisionState = "queued" | "running" | "completed" | "blocked";

type StoryDatum = {
  label: string;
  value: string;
  provenance?:
    "Scenario input" | "Live source" | "Policy snapshot" | "Runtime trace";
};

type StoryStage = {
  id: string;
  step: number;
  title: string;
  owner: string;
  icon: LucideIcon;
  state: DecisionState;
  objective: string;
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
      <motion.div
        className="stage-objective"
        initial={{ opacity: 0, x: -8 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: 0.08, duration: 0.28 }}
      >
        <small>Outcome targeted in this stage</small>
        <strong>{stage.objective}</strong>
      </motion.div>
      <div className="focus-stage-flow">
        <section className="focus-block focus-input">
          <span className="focus-block-label">Inputs available</span>
          <div className="focus-data-list">
            {stage.input.length > 0 ? (
              stage.input.map((datum, index) => (
                <div key={`${stage.id}-input-${index}-${datum.label}`}>
                  <small>
                    {datum.label}
                    {datum.provenance ? <i>{datum.provenance}</i> : null}
                  </small>
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
            {lane === "agentic" ? "Decision or action" : "Decision logic"}
          </span>
          <strong>{stage.controlLabel}</strong>
          <p>{stage.control}</p>
          <div className="focus-rationale">
            <small>
              {lane === "agentic"
                ? "Why this step matters"
                : "Strength and boundary"}
            </small>
            <p>{stage.why}</p>
          </div>
        </section>
        <section className="focus-block focus-output">
          <span className="focus-block-label">Stage result</span>
          <div className="focus-data-list">
            {stage.output.length > 0 ? (
              stage.output.map((datum, index) => (
                <div key={`${stage.id}-output-${index}-${datum.label}`}>
                  <small>
                    {datum.label}
                    {datum.provenance ? <i>{datum.provenance}</i> : null}
                  </small>
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
  currentStage,
  onSelectStage,
  onSelectEvent,
}: {
  stages: StoryStage[];
  lane: "agentic" | "rules";
  currentStage: number;
  onSelectStage: (stage: number) => void;
  onSelectEvent: (event: RunEvent) => void;
}) {
  const selectedStage = stages[currentStage - 1] ?? stages[0];

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
            onClick={() => onSelectStage(stage.step)}
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
  currentStage,
  availableStage,
  presentationMode,
  canAdvance,
  onSetPresentationMode,
  onAdvanceStage,
  onSelectStage,
  onSelectEvent,
}: {
  scenario: ScenarioDefinition;
  input: Record<string, string>;
  events: RunEvent[];
  answer: string;
  currentStage: number;
  availableStage: number;
  presentationMode: "manual" | "auto";
  canAdvance: boolean;
  onSetPresentationMode: (mode: "manual" | "auto") => void;
  onAdvanceStage: () => void;
  onSelectStage: (stage: number) => void;
  onSelectEvent: (event: RunEvent) => void;
}) {
  const isHassantuk = scenario.id === "hassantuk_villa_response";
  const configuredInput = isHassantuk
    ? [
        { label: "alarm signal", value: input.alarmType || "not provided" },
        {
          label: "triggered sensors",
          value: input.sensorCount || "not provided",
        },
        { label: "detector zone", value: input.detectorZone || "not provided" },
        {
          label: "resident verification",
          value: input.occupantsStatus || "not provided",
        },
        {
          label: "private history",
          value: `alarms: ${input.priorAlarmHistory || "not provided"} · maintenance: ${input.maintenanceHistory || "not provided"}`,
        },
        {
          label: "visual context",
          value: input.visualEvidence || "not provided",
        },
        {
          label: "side-effect boundary",
          value: `resident call: ${input.residentCallAction || "not provided"} · drone: ${input.droneDispatchAction || "not provided"}`,
        },
        {
          label: "response area",
          value: `${input.latitude || "not provided"}, ${input.longitude || "not provided"}`,
        },
      ].map((datum) => ({ ...datum, provenance: "Scenario input" as const }))
    : scenario.inputFields.map((field) => ({
        label: field.label,
        value: input[field.key] || "not provided",
        provenance: "Scenario input" as const,
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
        provenance:
          event.evidence?.fields?.retrievalMode !== undefined
            ? ("Policy snapshot" as const)
            : ("Live source" as const),
      },
      ...dataRows(event.evidence?.fields, 3),
    ])
    .slice(0, 8);
  const policyEvidence = evidenceEvents.find(
    (event) => event.evidence?.fields?.scenarioId === scenario.id,
  );
  const policyChunks = Array.isArray(policyEvidence?.evidence?.fields?.chunks)
    ? policyEvidence.evidence.fields.chunks
    : [];
  const policyRows: StoryDatum[] = policyChunks
    .slice(0, 3)
    .map((value, index) => {
      const chunk = asRecord(value);
      return {
        label: `policy citation ${index + 1}`,
        value: `${displayValue(chunk.authority)} · ${displayValue(chunk.title)} · ${displayValue(chunk.version)}`,
        provenance: "Policy snapshot" as const,
      };
    });
  const handoffs = events.filter((event) => event.type === "agent_handoff");
  const handoff = handoffs.at(-1);
  const specialistCount = Math.max(
    handoffs.length,
    asStrings(handoff?.data?.from).length,
  );
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
  const agentObjectives = isHassantuk
    ? [
        "Accept a bounded villa alarm case without authorizing resident contact, drone launch, or emergency dispatch.",
        "Select the next evidence source needed to verify the alarm and prepare a safe response.",
        "Retrieve the current Hassantuk protocol, governing UAE policy, and local response conditions through typed read-only connectors.",
        "Validate the returned evidence and expose missing private alarm, maintenance, resident, or visual context.",
        "Reconcile alarm priority, resident verification, and the value of drone or thermal overwatch into one response plan.",
        "Release a grounded recommendation while holding automated calls, drone launch, and Civil Defence dispatch for authorized approval.",
      ]
    : [
        "Accept a bounded case and enforce its tool, budget, and side-effect limits.",
        "Choose the most useful approved evidence action for the current case.",
        "Execute operational connectors and governed policy retrieval, then capture traceable results.",
        "Validate source evidence and policy citations before either can influence the next decision.",
        "Adapt the response or reconcile specialist findings into one case-specific plan.",
        "Release only a grounded, policy-compliant recommendation.",
      ];
  const ruleObjectives = isHassantuk
    ? [
        "Validate the villa alarm envelope and bind it to a versioned response policy.",
        "Precompile the exact official and environmental evidence required for this alarm class.",
        "Acquire the same live protocol, policy corpus, and conditions used by the agentic lane.",
        "Derive reproducible alarm-priority, verification, weather, and approval facts.",
        "Match the fact set against the complete versioned response decision table.",
        "Return a known verification route or safe exception without claiming a call, launch, or dispatch occurred.",
      ]
    : [
        "Validate the versioned decision contract and safe exception path.",
        "Precompile the exact evidence plan for this known decision class.",
        "Execute configured operational connectors and governed policy retrieval.",
        "Normalize evidence and derive reproducible decision facts.",
        "Match the fact set against the versioned decision table.",
        "Release a known outcome or route the case to manual exception review.",
      ];

  const agentStages: StoryStage[] = [
    {
      id: "bounded-goal",
      step: 1,
      title: isHassantuk ? "Bound alarm intake" : "Bound the goal",
      owner: "HUMAN + LANGGRAPH",
      icon: Target,
      state: stateFromEvent(guardrail ?? runStarted),
      objective: agentObjectives[0],
      input: configuredInput,
      controlLabel: "Safety and autonomy boundary",
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
      title: isHassantuk
        ? "Choose verification action"
        : "Choose the next action",
      owner: "MODEL WITHIN GRAPH",
      icon: GitBranch,
      state: stateFromEvent(modelToolDecision),
      objective: agentObjectives[1],
      input: [
        { label: "goal", value: scenario.businessOutcome },
        { label: "available tools", value: scenario.requiredTools.join(", ") },
      ],
      controlLabel: "Selected evidence action",
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
      title: isHassantuk
        ? "Retrieve protocol, policy, conditions"
        : "Retrieve evidence and policy",
      owner: "AI SDK + MCP",
      icon: Wrench,
      state: stateFromEvent(latestAgentTool),
      objective: agentObjectives[2],
      input:
        toolArguments.length > 0
          ? toolArguments
          : [
              {
                label: "typed contract",
                value: scenario.requiredTools.join(", "),
              },
            ],
      controlLabel: "Typed connector execution",
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
      title: isHassantuk ? "Assess alarm priority" : "Observe validated state",
      owner: "LIVE SOURCE + ZOD",
      icon: Eye,
      state: stateFromEvent(evidenceEvents.at(-1)),
      objective: agentObjectives[3],
      input:
        agentToolCompletes.length > 0
          ? agentToolCompletes.map((event) => ({
              label: event.label,
              value: event.summary,
            }))
          : [{ label: "source response", value: "waiting for tool output" }],
      controlLabel: "Evidence validation result",
      control:
        evidenceEvents.length > 0
          ? `${evidenceEvents.length} live source record${evidenceEvents.length === 1 ? "" : "s"} passed the evidence contract.`
          : "Raw source responses must pass the Zod evidence contract before the model can use them.",
      output:
        evidenceRows.length > 0
          ? [...policyRows, ...evidenceRows].slice(0, 8)
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
      title: isHassantuk
        ? "Plan resident and drone response"
        : scenario.orchestration === "multi_agent"
          ? "Reconcile specialists"
          : "Adapt and synthesize",
      owner:
        scenario.orchestration === "multi_agent"
          ? "LANGGRAPH SUPERVISOR"
          : "MODEL",
      icon: RefreshCw,
      state: stateFromEvent(adaptationEvent),
      objective: agentObjectives[4],
      input: [
        {
          label: "validated records",
          value:
            evidenceEvents.length > 0
              ? String(evidenceEvents.length)
              : "pending live run",
        },
        {
          label: "specialist reports",
          value:
            specialistCount > 0 ? String(specialistCount) : "pending live run",
        },
      ],
      controlLabel: isHassantuk ? "Response synthesis" : "Adaptive synthesis",
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
      title: isHassantuk ? "Authorize or hold dispatch" : "Verify and release",
      owner: "OPA + GROUNDING EVAL",
      icon: policy?.status === "blocked" ? ShieldCheck : BadgeCheck,
      state: stateFromEvent(evaluation ?? policy),
      objective: agentObjectives[5],
      input: [
        {
          label: "required evidence",
          value: String(
            evaluation?.data?.requiredEvidence ?? scenario.requiredTools.length,
          ),
        },
        {
          label: "captured evidence",
          value:
            evaluation?.data?.capturedEvidence !== undefined
              ? String(evaluation.data.capturedEvidence)
              : evidenceEvents.length > 0
                ? String(evidenceEvents.length)
                : "pending live run",
        },
      ],
      controlLabel: "Release and side-effect decision",
      control:
        policy?.summary ??
        "OPA evaluates side effects and the evaluator checks that every required source grounded the answer.",
      output: [
        {
          label: "grounding",
          value: evaluation?.label ?? "waiting for evaluator",
        },
        { label: "workflow", value: agentOutput?.status ?? "not released" },
        ...(answer
          ? [{ label: "response brief", value: answer.slice(0, 260) }]
          : []),
      ],
      why: "Agentic does not mean uncontrolled: independent policy and evidence checks decide whether the result may leave the workflow.",
      event: evaluation ?? policy,
    },
  ];

  const ruleStages: StoryStage[] = [
    {
      id: "deterministic-contract",
      step: 1,
      title: isHassantuk
        ? "Validate alarm contract"
        : "Validate decision contract",
      owner: "ZOD + REGISTRY",
      icon: Target,
      state: stateFromEvent(rulesContract ?? runStarted),
      objective: ruleObjectives[0],
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
      title: isHassantuk ? "Plan known evidence" : "Plan configured evidence",
      owner: "VERSIONED DECISION GRAPH",
      icon: GitBranch,
      state: stateFromEvent(rulesFetch),
      objective: ruleObjectives[1],
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
      title: isHassantuk
        ? "Fetch protocol, policy, conditions"
        : "Fetch evidence and policy",
      owner: "MCP",
      icon: Wrench,
      state: stateFromEvent(rulesToolEvents.at(-1)),
      objective: ruleObjectives[2],
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
      title: isHassantuk
        ? "Derive risk and readiness"
        : "Normalize and derive facts",
      owner: "ZOD + TYPED TRANSFORMS",
      icon: Eye,
      state: stateFromEvent(rulesDerive ?? rulesNormalize),
      objective: ruleObjectives[3],
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
      title: isHassantuk ? "Apply response policy" : "Evaluate decision table",
      owner: "JSON-RULES-ENGINE",
      icon: Braces,
      state: stateFromEvent(rulesEvaluate),
      objective: ruleObjectives[4],
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
      title: isHassantuk
        ? "Release verification route"
        : "Release governed outcome",
      owner: "DECISION SERVICE",
      icon: BadgeCheck,
      state: stateFromEvent(rulesOutput),
      objective: ruleObjectives[5],
      input: [
        {
          label: "matched events",
          value:
            matchedEvents.length > 0
              ? matchedEvents.join(", ")
              : rulesOutput
                ? "no configured outcome matched"
                : "pending live run",
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
          <h3>Step through the same decision in both systems</h3>
        </div>
        <div
          className="presentation-controls presentation-controls-primary"
          aria-label="Stage playback controls"
        >
          <div
            className="presentation-mode"
            role="group"
            aria-label="Progress mode"
          >
            <button
              className={presentationMode === "manual" ? "active" : ""}
              onClick={() => onSetPresentationMode("manual")}
              type="button"
            >
              <StepForward size={13} /> Manual
            </button>
            <button
              className={presentationMode === "auto" ? "active" : ""}
              onClick={() => onSetPresentationMode("auto")}
              type="button"
            >
              <Play size={12} fill="currentColor" /> Auto
            </button>
          </div>
          <span>
            Stage {currentStage} of 6 · {availableStage} live
          </span>
          <button
            className="next-stage-button"
            onClick={onAdvanceStage}
            disabled={!canAdvance || presentationMode === "auto"}
            type="button"
          >
            <StepForward size={14} /> Next stage
          </button>
        </div>
      </div>
      <div className="story-lanes">
        <StoryLane
          stages={agentStages}
          lane="agentic"
          currentStage={currentStage}
          onSelectStage={onSelectStage}
          onSelectEvent={onSelectEvent}
        />
        <StoryLane
          stages={ruleStages}
          lane="rules"
          currentStage={currentStage}
          onSelectStage={onSelectStage}
          onSelectEvent={onSelectEvent}
        />
      </div>

      <motion.section
        className="inline-topology"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.42, ease: [0.22, 1, 0.36, 1] }}
        aria-label="Live workflow topology"
      >
        <header>
          <span>
            <Network size={16} /> Live topology
          </span>
          <strong>
            Every lit node is backed by the same received trace shown above.
          </strong>
        </header>
        <WorkflowCanvas
          scenario={scenario}
          events={events}
          onSelectEvent={onSelectEvent}
        />
      </motion.section>

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
