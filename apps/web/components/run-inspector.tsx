"use client";

import { ExternalLink, FileSearch, Radio, ShieldCheck, Timer, Wrench } from "lucide-react";

import type { RunEvent } from "@/lib/agentic/contracts";

function formatTime(timestamp: string) {
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    fractionalSecondDigits: 3,
  }).format(new Date(timestamp));
}

export function RunInspector({
  events,
  selected,
  onSelect,
}: {
  events: RunEvent[];
  selected: RunEvent | null;
  onSelect: (event: RunEvent) => void;
}) {
  const evidenceCount = events.filter((event) => event.type === "evidence_captured").length;
  const toolCount = events.filter((event) => event.type === "tool_completed").length;
  const policyCount = events.filter(
    (event) => event.type === "policy_decision" || event.type === "guardrail_decision",
  ).length;

  return (
    <aside className="run-inspector">
      <div className="inspector-metrics">
        <div><Radio size={14} /><span>{events.length}</span><small>events</small></div>
        <div><Wrench size={14} /><span>{toolCount}</span><small>tools</small></div>
        <div><FileSearch size={14} /><span>{evidenceCount}</span><small>evidence</small></div>
        <div><ShieldCheck size={14} /><span>{policyCount}</span><small>gates</small></div>
      </div>

      <div className="inspector-section-head">
        <div>
          <span className="section-kicker">Live trace</span>
          <h2>Execution events</h2>
        </div>
        <span className="stream-indicator"><i /> streaming</span>
      </div>

      <div className="event-feed" role="log" aria-live="polite">
        {events.length === 0 ? (
          <div className="empty-trace">
            <Radio size={20} />
            <strong>Ready for a real run</strong>
            <span>Events appear here as LangGraph, tools, policy, and rules execute.</span>
          </div>
        ) : (
          [...events].reverse().map((event) => (
            <button
              className={`event-row lane-${event.lane} status-${event.status} ${selected?.id === event.id ? "selected" : ""}`}
              key={event.id}
              onClick={() => onSelect(event)}
              type="button"
            >
              <span className="event-dot" />
              <span className="event-copy">
                <strong>{event.label}</strong>
                <small>{event.actor}</small>
              </span>
              <time>{formatTime(event.timestamp)}</time>
            </button>
          ))
        )}
      </div>

      {selected ? (
        <div className="event-detail">
          <div className="event-detail-head">
            <span className={`status-pill status-${selected.status}`}>{selected.status}</span>
            {selected.durationMs !== undefined ? (
              <span><Timer size={13} /> {selected.durationMs}ms</span>
            ) : null}
          </div>
          <h3>{selected.label}</h3>
          <p>{selected.summary}</p>
          <dl>
            <div><dt>Node</dt><dd>{selected.nodeId}</dd></div>
            <div><dt>Lane</dt><dd>{selected.lane}</dd></div>
            <div><dt>Trace</dt><dd>{selected.traceId?.slice(0, 16) ?? "pending"}</dd></div>
          </dl>
          {selected.evidence ? (
            <a href={selected.evidence.sourceUrl} target="_blank" rel="noreferrer">
              Open source evidence <ExternalLink size={13} />
            </a>
          ) : null}
          {selected.data ? <pre>{JSON.stringify(selected.data, null, 2)}</pre> : null}
        </div>
      ) : null}
    </aside>
  );
}
