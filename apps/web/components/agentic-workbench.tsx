"use client";

import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport, isToolOrDynamicToolUIPart } from "ai";
import {
  Activity,
  Bot,
  Braces,
  CheckCircle2,
  CircleStop,
  Code2,
  Database,
  ExternalLink,
  Gauge,
  Layers3,
  LoaderCircle,
  Play,
  Radio,
  RefreshCw,
  Scale,
  Settings2,
  ShieldCheck,
  Sparkles,
  Waypoints,
  Wrench,
} from "lucide-react";
import { useMemo, useState } from "react";

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
import { EnterpriseValueBoundary } from "@/components/enterprise-value-boundary";
import { RunInspector } from "@/components/run-inspector";
import { StackArchitecture } from "@/components/stack-architecture";
import { WorkflowCanvas } from "@/components/workflow-canvas";
import type { AegisUIMessage, RunEvent } from "@/lib/agentic/contracts";
import { scenarios, type ScenarioDefinition } from "@/lib/agentic/scenarios";

type DetailView = "answer" | "tools" | "stack";

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
          <strong>Fixed rules</strong>
          <small>Known facts to predefined outcome</small>
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
  const answer = useMemo(() => extractText(messages), [messages]);
  const toolParts = useMemo(() => extractToolParts(messages), [messages]);
  const agentToolEvents = events.filter(
    (event) => event.lane === "agentic" && event.type === "tool_started",
  );
  const isRunning = status === "submitted" || status === "streaming";
  const latestAgent = [...events]
    .reverse()
    .find(
      (event) => event.lane === "agentic" && event.type === "lane_completed",
    );
  const latestRules = [...events]
    .reverse()
    .find((event) => event.lane === "rules" && event.type === "lane_completed");
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

  const inspectedEvent = selectedEvent ?? events.at(-1) ?? null;

  const selectScenario = (next: ScenarioDefinition) => {
    stop();
    setScenario(next);
    setInput(next.defaultInput);
    setMessages([]);
    setSelectedEvent(null);
    setDetailView("answer");
  };

  const startRun = async () => {
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
    : events.at(-1)?.type === "run_completed"
      ? events.at(-1)?.status
      : isRunning
        ? "running"
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
          {isRunning ? (
            <LoaderCircle className="spin" size={14} />
          ) : (
            <Activity size={14} />
          )}
          {runState}
        </div>
      </header>

      <ScenarioRail selected={scenario} onSelect={selectScenario} />

      <section className="run-config" aria-labelledby="workflow-title">
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
        <div className="input-grid">
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
        </div>
        <div className="run-actions">
          <div className="tune-summary">
            <Settings2 size={14} />
            <span>{controls.model.replace("openai/", "")}</span>
            <span>{controls.maxToolCalls} tool calls</span>
            <span>${controls.maxCostUsd.toFixed(2)} ceiling</span>
          </div>
          {isRunning ? (
            <button className="run-button stop" onClick={stop} type="button">
              <CircleStop size={17} /> Stop run
            </button>
          ) : (
            <button className="run-button" onClick={startRun} type="button">
              <Play size={17} fill="currentColor" /> Run both live
            </button>
          )}
        </div>
      </section>

      <ModeStrip />
      <EnterpriseValueBoundary scenario={scenario} />

      <section className="execution-workspace">
        <div className="canvas-panel">
          <div className="panel-heading">
            <div>
              <span className="section-kicker">Live execution canvas</span>
              <h2>Agent decides. Rules match.</h2>
            </div>
            <div className="canvas-stats">
              <span>
                <Wrench size={13} /> {agentToolEvents.length} agent tools
              </span>
              <span>
                <Gauge size={13} /> {inputTokens + outputTokens} tokens · $
                {directApiEquivalent.toFixed(4)} equiv.
              </span>
              <span>
                <Radio size={13} /> {events.length} events
              </span>
            </div>
          </div>
          <WorkflowCanvas
            scenario={scenario}
            events={events}
            onSelectEvent={setSelectedEvent}
          />
          <DecisionLens
            scenario={scenario}
            events={events}
            onSelectEvent={setSelectedEvent}
          />
          <div className="lane-outcomes">
            <div className="agent-outcome">
              <span>
                <Bot size={15} /> Agentic result
              </span>
              <p>
                {latestAgent?.summary ??
                  "Will adapt its plan, choose tools, ground evidence, and pass policy before output."}
              </p>
            </div>
            <div className="rule-outcome">
              <span>
                <Braces size={15} /> Fixed-rule result
              </span>
              <p>
                {latestRules?.summary ??
                  "Will fetch predefined fields, evaluate configured conditions, and stop at the known outcome boundary."}
              </p>
            </div>
          </div>
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
        <RunInspector
          events={events}
          selected={inspectedEvent}
          onSelect={setSelectedEvent}
        />
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

      <section className="run-detail" id="live-evidence">
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

      <section className="tuning-drawer" aria-label="Runtime controls">
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
        <span>No synthetic business records. Public live sources only.</span>
      </footer>
    </main>
  );
}
