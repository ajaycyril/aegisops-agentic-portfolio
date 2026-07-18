"use client";

import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport, isToolOrDynamicToolUIPart } from "ai";
import {
  Activity,
  Bot,
  Braces,
  CheckCircle2,
  ChevronDown,
  CircleStop,
  Code2,
  Database,
  ExternalLink,
  FastForward,
  Layers3,
  ListTree,
  LoaderCircle,
  Network,
  PanelRightOpen,
  Play,
  Radio,
  RefreshCw,
  Scale,
  Settings2,
  ShieldCheck,
  Sparkles,
  StepForward,
  Waypoints,
  Wrench,
} from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";

import {
  Message,
  MessageContent,
  MessageResponse,
} from "@/components/ai-elements/message";
import {
  Tool,
  ToolContent,
  ToolHeader,
  ToolInput,
  ToolOutput,
  type ToolPart,
} from "@/components/ai-elements/tool";
import { DecisionLens } from "@/components/decision-lens";
import { RunInspector } from "@/components/run-inspector";
import { StackArchitecture } from "@/components/stack-architecture";
import { WorkflowCanvas } from "@/components/workflow-canvas";
import type { AegisUIMessage, RunEvent } from "@/lib/agentic/contracts";
import { scenarios, type ScenarioDefinition } from "@/lib/agentic/scenarios";

type DetailView = "answer" | "tools" | "stack";
type ExecutionView = "story" | "topology";
type PresentationMode = "manual" | "auto";

const modelPrices: Record<string, { input: number; output: number }> = {
  "openai/gpt-4.1-mini": { input: 0.4, output: 1.6 },
  "openai/gpt-4o-mini": { input: 0.15, output: 0.6 },
};

function extractEvents(messages: AegisUIMessage[]) {
  const streamedEvents = messages.flatMap((message) =>
    message.parts.flatMap((part) =>
      part.type === "data-run-event" ? [part.data] : [],
    ),
  );
  return [
    ...new Map(streamedEvents.map((event) => [event.id, event])).values(),
  ].sort((left, right) => left.sequence - right.sequence);
}

function extractText(messages: AegisUIMessage[]) {
  return messages
    .filter((message) => message.role === "assistant")
    .flatMap((message) => message.parts)
    .filter(
      (part): part is Extract<typeof part, { type: "text" }> =>
        part.type === "text",
    )
    .map((part) => part.text)
    .join("");
}

function extractToolParts(messages: AegisUIMessage[]) {
  return messages
    .filter((message) => message.role === "assistant")
    .flatMap((message) => message.parts)
    .filter(isToolOrDynamicToolUIPart);
}

function presentationStage(event: RunEvent) {
  if (event.type === "run_started" || event.type === "guardrail_decision")
    return 1;
  if (
    event.type === "model_step" &&
    Array.isArray(event.data?.toolCalls) &&
    event.data.toolCalls.length > 0
  )
    return 2;
  if (event.type === "tool_started" || event.type === "tool_completed")
    return 3;
  if (
    event.type === "evidence_captured" ||
    event.nodeId === "rules-normalize" ||
    event.nodeId === "rules-derive"
  )
    return 4;
  if (
    event.type === "rule_evaluated" ||
    event.type === "agent_handoff" ||
    event.nodeId === "rules-evaluate" ||
    event.nodeId === "agent-supervisor" ||
    event.type === "model_step"
  )
    return 5;
  if (
    event.type === "policy_decision" ||
    event.type === "lane_completed" ||
    event.type === "run_completed" ||
    event.nodeId === "agent-evaluate"
  )
    return 6;
  return event.lane === "rules" && event.nodeId === "rules-contract" ? 1 : 2;
}

function useStagePresentation(events: RunEvent[]) {
  const [stage, setStage] = useState(1);
  const [mode, setMode] = useState<PresentationMode>("manual");
  const agentStage = Math.max(
    1,
    ...events.filter((event) => event.lane !== "rules").map(presentationStage),
  );
  const rulesStage = Math.max(
    1,
    ...events
      .filter((event) => event.lane === "rules" || event.lane === "system")
      .map(presentationStage),
  );
  const availableStage =
    events.length > 0 ? Math.min(agentStage, rulesStage) : 1;

  useEffect(() => {
    if (mode !== "auto" || stage >= availableStage) return;
    const timer = window.setTimeout(
      () => setStage((current) => Math.min(current + 1, availableStage)),
      3000,
    );
    return () => window.clearTimeout(timer);
  }, [availableStage, mode, stage]);

  const presentedEvents = events.filter(
    (event) => presentationStage(event) <= stage,
  );

  return {
    presentedEvents,
    stage,
    availableStage,
    mode,
    setMode,
    canAdvance: stage < availableStage,
    isPresenting: events.length > 0 && stage < 6,
    advanceStage: () =>
      setStage((current) => Math.min(current + 1, availableStage)),
    resetPresentation: () => setStage(1),
    showFinalState: () => setStage(6),
  };
}

function ToolInvocation({ part }: { part: ToolPart }) {
  return (
    <Tool
      className="model-tool-call"
      defaultOpen={part.state !== "output-available"}
    >
      {part.type === "dynamic-tool" ? (
        <ToolHeader
          type={part.type}
          state={part.state}
          toolName={part.toolName}
        />
      ) : (
        <ToolHeader type={part.type} state={part.state} />
      )}
      <ToolContent>
        <ToolInput input={part.input} />
        <ToolOutput output={part.output} errorText={part.errorText} />
      </ToolContent>
    </Tool>
  );
}

function RuntimeToolTrace({
  event,
  events,
}: {
  event: RunEvent;
  events: RunEvent[];
}) {
  const completion = events.find(
    (candidate) =>
      candidate.type === "tool_completed" && candidate.nodeId === event.nodeId,
  );
  const evidence = events.find(
    (candidate) =>
      candidate.type === "evidence_captured" &&
      candidate.nodeId === `evidence-${event.label}`,
  )?.evidence;

  return (
    <article className="runtime-tool-trace">
      <div className="runtime-tool-head">
        <span>
          <Wrench size={14} /> {event.label}
        </span>
        <small>{completion?.durationMs ?? 0}ms · MCP SDK v1</small>
      </div>
      <div className="runtime-tool-io">
        <div>
          <strong>Typed input</strong>
          <pre>{JSON.stringify(event.data?.arguments ?? {}, null, 2)}</pre>
        </div>
        <div>
          <strong>Validated result</strong>
          <pre>
            {JSON.stringify(
              evidence?.fields ?? completion?.data ?? {},
              null,
              2,
            )}
          </pre>
        </div>
      </div>
      {evidence ? (
        <a href={evidence.sourceUrl} target="_blank" rel="noreferrer">
          Open live source <ExternalLink size={12} />
        </a>
      ) : null}
    </article>
  );
}

function ScenarioRail({
  selected,
  onSelect,
}: {
  selected: ScenarioDefinition;
  onSelect: (scenario: ScenarioDefinition) => void;
}) {
  return (
    <nav className="scenario-rail" aria-label="Live use cases">
      {scenarios.map((scenario) => {
        const Icon = scenario.icon;
        return (
          <button
            className={`scenario-tab accent-${scenario.accent} ${selected.id === scenario.id ? "active" : ""}`}
            key={scenario.id}
            onClick={() => onSelect(scenario)}
            type="button"
          >
            <Icon size={17} />
            <span>{scenario.shortName}</span>
            <small>{scenario.domain}</small>
          </button>
        );
      })}
    </nav>
  );
}

function ModeStrip() {
  return (
    <div className="mode-strip" aria-label="Automation spectrum">
      <div>
        <Braces size={15} />
        <span>
          <strong>Deterministic system</strong>
          <small>Typed facts to versioned decision</small>
        </span>
      </div>
      <i />
      <div>
        <Scale size={15} />
        <span>
          <strong>Dynamic policy</strong>
          <small>Context to allow, block, approve</small>
        </span>
      </div>
      <i />
      <div>
        <Waypoints size={15} />
        <span>
          <strong>AI workflow</strong>
          <small>Model inside a fixed graph</small>
        </span>
      </div>
      <i />
      <div className="mode-agentic">
        <Bot size={15} />
        <span>
          <strong>Agentic</strong>
          <small>Plans, selects tools, evaluates</small>
        </span>
      </div>
    </div>
  );
}

export function AgenticWorkbench() {
  const [scenario, setScenario] = useState(scenarios[0]);
  const [input, setInput] = useState<Record<string, string>>(
    scenarios[0].defaultInput,
  );
  const [selectedEvent, setSelectedEvent] = useState<RunEvent | null>(null);
  const [detailView, setDetailView] = useState<DetailView>("answer");
  const [executionView, setExecutionView] = useState<ExecutionView>("story");
  const [setupOpen, setSetupOpen] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [technicalOpen, setTechnicalOpen] = useState(false);
  const [controls, setControls] = useState({
    maxToolCalls: 4,
    maxCostUsd: 0.05,
    requireApproval: true,
    model: "openai/gpt-4.1-mini",
  });

  const transport = useMemo(
    () => new DefaultChatTransport<AegisUIMessage>({ api: "/api/agent-runs" }),
    [],
  );
  const { messages, sendMessage, setMessages, status, stop, error } =
    useChat<AegisUIMessage>({ transport, experimental_throttle: 35 });

  const events = useMemo(() => extractEvents(messages), [messages]);
  const {
    presentedEvents,
    stage: presentationStageNumber,
    availableStage,
    mode: presentationMode,
    setMode: setPresentationMode,
    canAdvance,
    isPresenting,
    advanceStage,
    resetPresentation,
    showFinalState,
  } = useStagePresentation(events);
  const answer = useMemo(() => extractText(messages), [messages]);
  const toolParts = useMemo(() => extractToolParts(messages), [messages]);
  const agentToolEvents = events.filter(
    (event) => event.lane === "agentic" && event.type === "tool_started",
  );
  const presentedAgentToolCount = presentedEvents.filter(
    (event) => event.lane === "agentic" && event.type === "tool_started",
  ).length;
  const isRunning = status === "submitted" || status === "streaming";
  const modelSteps = events.filter((event) => event.type === "model_step");
  const inputTokens = modelSteps.reduce(
    (total, event) => total + Number(event.data?.inputTokens ?? 0),
    0,
  );
  const outputTokens = modelSteps.reduce(
    (total, event) => total + Number(event.data?.outputTokens ?? 0),
    0,
  );
  const pricing =
    modelPrices[controls.model] ?? modelPrices["openai/gpt-4.1-mini"];
  const directApiEquivalent =
    (inputTokens * pricing.input + outputTokens * pricing.output) / 1_000_000;

  const inspectedEvent = selectedEvent ?? presentedEvents.at(-1) ?? null;
  const presentedAnswer = presentedEvents.some(
    (event) => event.lane === "agentic" && event.type === "lane_completed",
  )
    ? answer
    : "";

  const inspectEvent = (event: RunEvent) => {
    setSelectedEvent(event);
    setInspectorOpen(true);
  };

  const selectScenario = (next: ScenarioDefinition) => {
    stop();
    setScenario(next);
    setInput(next.defaultInput);
    setMessages([]);
    setSelectedEvent(null);
    setDetailView("answer");
    setExecutionView("story");
    setSetupOpen(false);
    setInspectorOpen(false);
    resetPresentation();
  };

  const startRun = async () => {
    resetPresentation();
    setMessages([]);
    setSelectedEvent(null);
    setDetailView("answer");
    await sendMessage(
      { text: scenario.prompt(input) },
      { body: { scenarioId: scenario.id, input, controls } },
    );
  };

  const runState = error
    ? "failed"
    : isRunning
      ? "running"
      : isPresenting
        ? "presenting"
        : events.at(-1)?.type === "run_completed"
          ? events.at(-1)?.status
          : "ready";

  return (
    <main className="workbench-shell">
      <header className="workbench-topbar">
        <div className="product-lockup">
          <div className="product-mark">
            <Layers3 size={20} />
          </div>
          <div>
            <strong>AegisOps</strong>
            <span>Live enterprise agent systems lab</span>
          </div>
        </div>
        <div className="runtime-badges">
          <span>
            <i className="live-dot" /> live public data
          </span>
          <span>
            <Sparkles size={13} /> GitHub Models free
          </span>
          <span>
            <ShieldCheck size={13} /> read-only
          </span>
          <span>
            <Database size={13} /> Postgres-ready
          </span>
          <a
            href="https://github.com/ajaycyril/aegisops-agentic-portfolio"
            target="_blank"
            rel="noreferrer"
          >
            <Code2 size={13} /> Source
          </a>
        </div>
        <div className={`run-state state-${runState}`}>
          {isRunning || isPresenting ? (
            <LoaderCircle className="spin" size={14} />
          ) : (
            <Activity size={14} />
          )}
          {runState}
        </div>
      </header>

      <ScenarioRail selected={scenario} onSelect={selectScenario} />

      <section
        className={`run-config ${setupOpen ? "setup-open" : ""}`}
        aria-labelledby="workflow-title"
      >
        <div className="workflow-identity">
          <div className="workflow-kickers">
            <span className="section-kicker">{scenario.domain}</span>
            <span className={`orchestration-chip ${scenario.orchestration}`}>
              {scenario.orchestration === "multi_agent"
                ? "3 model agents"
                : "single adaptive agent"}
            </span>
          </div>
          <h1 id="workflow-title">{scenario.name}</h1>
          <p>{scenario.description}</p>
          <a href="#live-evidence">
            <Radio size={13} /> {scenario.sourceLabel}{" "}
            <ExternalLink size={12} />
          </a>
        </div>
        <AnimatePresence initial={false}>
          {setupOpen ? (
            <motion.div
              className="input-grid run-setup-fields"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
            >
              {scenario.inputFields.map((field) => (
                <label key={field.key}>
                  <span>{field.label}</span>
                  <input
                    value={input[field.key] ?? ""}
                    placeholder={field.placeholder}
                    onChange={(event) =>
                      setInput((current) => ({
                        ...current,
                        [field.key]: event.target.value,
                      }))
                    }
                    disabled={isRunning}
                  />
                </label>
              ))}
            </motion.div>
          ) : null}
        </AnimatePresence>
        <div className="run-actions">
          <div className="tune-summary">
            {scenario.inputFields.map((field) => (
              <span key={field.key}>
                {field.label}: <b>{input[field.key]}</b>
              </span>
            ))}
          </div>
          <div className="run-command-row">
            <button
              className={`setup-toggle ${setupOpen ? "active" : ""}`}
              onClick={() => setSetupOpen((current) => !current)}
              aria-expanded={setupOpen}
              type="button"
            >
              <Settings2 size={15} /> {setupOpen ? "Close setup" : "Edit setup"}
            </button>
            {isRunning ? (
              <button className="run-button stop" onClick={stop} type="button">
                <CircleStop size={17} /> Stop run
              </button>
            ) : isPresenting ? (
              <button
                className="run-button presenting"
                onClick={showFinalState}
                type="button"
              >
                <FastForward size={17} /> Show final state
              </button>
            ) : (
              <button className="run-button" onClick={startRun} type="button">
                <Play size={17} fill="currentColor" /> Run both live
              </button>
            )}
          </div>
        </div>
      </section>

      <section
        className={`execution-workspace ${inspectorOpen ? "with-inspector" : "without-inspector"}`}
      >
        <div className="canvas-panel">
          <div className="panel-heading">
            <div>
              <span className="section-kicker">Live execution canvas</span>
              <h2>Agent decides. Rules match.</h2>
            </div>
            <div className="canvas-heading-tools">
              <div
                className="presentation-controls"
                aria-label="Stage playback controls"
              >
                <div
                  className="presentation-mode"
                  role="group"
                  aria-label="Progress mode"
                >
                  <button
                    className={presentationMode === "manual" ? "active" : ""}
                    onClick={() => setPresentationMode("manual")}
                    type="button"
                  >
                    Manual
                  </button>
                  <button
                    className={presentationMode === "auto" ? "active" : ""}
                    onClick={() => setPresentationMode("auto")}
                    type="button"
                  >
                    Auto
                  </button>
                </div>
                <span>Stage {presentationStageNumber} of 6</span>
                <button
                  className="next-stage-button"
                  onClick={advanceStage}
                  disabled={!canAdvance || presentationMode === "auto"}
                  type="button"
                >
                  <StepForward size={14} /> Next stage
                </button>
              </div>
              <div
                className="execution-view-switch"
                role="tablist"
                aria-label="Execution visualization"
              >
                <button
                  className={executionView === "story" ? "active" : ""}
                  onClick={() => setExecutionView("story")}
                  role="tab"
                  aria-selected={executionView === "story"}
                  type="button"
                >
                  <ListTree size={14} /> Decision story
                </button>
                <button
                  className={executionView === "topology" ? "active" : ""}
                  onClick={() => setExecutionView("topology")}
                  role="tab"
                  aria-selected={executionView === "topology"}
                  type="button"
                >
                  <Network size={14} /> Topology
                </button>
              </div>
              <div className="canvas-stats">
                <span>
                  <Wrench size={13} /> {presentedAgentToolCount} agent tools
                </span>
                <span>
                  <Activity size={13} /> {presentationStageNumber}/6 shown ·{" "}
                  {availableStage}/6 ready
                </span>
                <button
                  className={inspectorOpen ? "active" : ""}
                  onClick={() => setInspectorOpen((current) => !current)}
                  type="button"
                  title="Toggle trace inspector"
                >
                  <PanelRightOpen size={13} /> Trace details
                </button>
              </div>
            </div>
          </div>
          {executionView === "story" ? (
            <DecisionLens
              scenario={scenario}
              input={input}
              events={presentedEvents}
              answer={presentedAnswer}
              onSelectEvent={inspectEvent}
            />
          ) : (
            <WorkflowCanvas
              scenario={scenario}
              events={presentedEvents}
              onSelectEvent={inspectEvent}
            />
          )}
          <div className="run-economics" aria-label="Run unit economics">
            <div>
              <span>Public demo charge</span>
              <strong>$0.0000</strong>
              <small>GitHub Models free tier</small>
            </div>
            <div>
              <span>Direct API equivalent</span>
              <strong>${directApiEquivalent.toFixed(5)}</strong>
              <small>Measured input + output tokens</small>
            </div>
            <div>
              <span>Deterministic model cost</span>
              <strong>$0.0000</strong>
              <small>json-rules-engine, no LLM</small>
            </div>
          </div>
        </div>
        {inspectorOpen ? (
          <RunInspector
            events={presentedEvents}
            selected={inspectedEvent}
            onSelect={setSelectedEvent}
          />
        ) : null}
      </section>

      {error ? (
        <div className="runtime-error" role="alert">
          <strong>Stream transport failed</strong>
          <span>{error.message}</span>
          <button type="button" onClick={startRun}>
            <RefreshCw size={14} /> Retry
          </button>
        </div>
      ) : null}

      <section className="technical-disclosure" id="live-evidence">
        <button
          type="button"
          onClick={() => setTechnicalOpen((current) => !current)}
          aria-expanded={technicalOpen}
        >
          <span>
            <Layers3 size={15} />
            <strong>Technical evidence</strong>
            <small>tool payloads · stack map · cost controls</small>
          </span>
          <ChevronDown className={technicalOpen ? "open" : ""} size={16} />
        </button>
      </section>

      {technicalOpen ? <ModeStrip /> : null}

      <section className={`run-detail ${technicalOpen ? "" : "is-hidden"}`}>
        <div
          className="detail-tabs"
          role="tablist"
          aria-label="Run detail views"
        >
          <button
            className={detailView === "answer" ? "active" : ""}
            onClick={() => setDetailView("answer")}
            type="button"
          >
            <Sparkles size={14} /> Agent answer
          </button>
          <button
            className={detailView === "tools" ? "active" : ""}
            onClick={() => setDetailView("tools")}
            type="button"
          >
            <Wrench size={14} /> Tool I/O <span>{agentToolEvents.length}</span>
          </button>
          <button
            className={detailView === "stack" ? "active" : ""}
            onClick={() => setDetailView("stack")}
            type="button"
          >
            <Layers3 size={14} /> Live stack map
          </button>
        </div>

        {detailView === "answer" ? (
          <div className="answer-view">
            <div className="answer-heading">
              <div>
                <span className="section-kicker">Grounded synthesis</span>
                <h2>Model output</h2>
              </div>
              {answer ? (
                <span>
                  <CheckCircle2 size={14} /> streamed through AI SDK
                </span>
              ) : null}
            </div>
            {answer ? (
              <Message from="assistant">
                <MessageContent>
                  <MessageResponse isAnimating={isRunning}>
                    {answer}
                  </MessageResponse>
                </MessageContent>
              </Message>
            ) : (
              <div className="answer-empty">
                <Bot size={24} />
                <strong>No generated answer yet</strong>
                <span>
                  Start a run to watch tool calls, evidence, and the final
                  grounded brief stream here.
                </span>
              </div>
            )}
          </div>
        ) : null}

        {detailView === "tools" ? (
          <div className="tools-view">
            <div className="answer-heading">
              <div>
                <span className="section-kicker">Typed MCP boundary</span>
                <h2>Actual model tool invocations</h2>
              </div>
              <span>{agentToolEvents.length} live calls</span>
            </div>
            {agentToolEvents.length > 0 ? (
              <div className="runtime-tool-list">
                {agentToolEvents.map((event) => (
                  <RuntimeToolTrace
                    key={event.id}
                    event={event}
                    events={events}
                  />
                ))}
              </div>
            ) : (
              <div className="answer-empty">
                <Wrench size={24} />
                <strong>No tool calls yet</strong>
                <span>
                  Tool arguments and validated MCP results appear here as the
                  model executes.
                </span>
              </div>
            )}
            {toolParts.length > 0 ? (
              <div className="message-tool-stream">
                <span className="section-kicker">AI SDK message parts</span>
                {toolParts.map((part) => (
                  <ToolInvocation
                    key={`${part.type}-${part.toolCallId}`}
                    part={part}
                  />
                ))}
              </div>
            ) : null}
          </div>
        ) : null}

        {detailView === "stack" ? (
          <div className="stack-view">
            <div className="answer-heading">
              <div>
                <span className="section-kicker">Architecture ownership</span>
                <h2>Live control and data flow</h2>
              </div>
              <span>click a lit node to inspect its trace event</span>
            </div>
            <StackArchitecture
              scenario={scenario}
              events={events}
              onSelectEvent={setSelectedEvent}
            />
          </div>
        ) : null}
      </section>

      <section
        className={`tuning-drawer ${technicalOpen ? "" : "is-hidden"}`}
        aria-label="Runtime controls"
      >
        <div>
          <Settings2 size={15} />
          <strong>Runtime controls</strong>
          <span>Applied to the next run</span>
        </div>
        <label>
          <span>
            Tool limit <b>{controls.maxToolCalls}</b>
          </span>
          <input
            type="range"
            min="2"
            max="8"
            value={controls.maxToolCalls}
            onChange={(event) =>
              setControls((current) => ({
                ...current,
                maxToolCalls: Number(event.target.value),
              }))
            }
          />
        </label>
        <label>
          <span>
            Spend ceiling <b>${controls.maxCostUsd.toFixed(2)}</b>
          </span>
          <input
            type="range"
            min="0.01"
            max="0.25"
            step="0.01"
            value={controls.maxCostUsd}
            onChange={(event) =>
              setControls((current) => ({
                ...current,
                maxCostUsd: Number(event.target.value),
              }))
            }
          />
        </label>
        <label className="select-control">
          <span>Model route</span>
          <select
            value={controls.model}
            onChange={(event) =>
              setControls((current) => ({
                ...current,
                model: event.target.value,
              }))
            }
          >
            <option value="openai/gpt-4.1-mini">GPT-4.1 mini</option>
            <option value="openai/gpt-4o-mini">GPT-4o mini</option>
          </select>
        </label>
        <label className="approval-toggle">
          <input
            type="checkbox"
            checked={controls.requireApproval}
            disabled
            readOnly
          />
          <span>
            <i />
            <b>Human approval enforced</b>
          </span>
        </label>
      </section>

      <footer className="workbench-footer">
        <span>AegisOps production agent portfolio</span>
        <span>
          Operator inputs are labeled. External evidence records are live.
        </span>
      </footer>
    </main>
  );
}
