"use client";

import {
  Activity,
  BadgeCheck,
  Boxes,
  BrainCircuit,
  Braces,
  Building2,
  ChartNoAxesCombined,
  ClipboardCheck,
  Code2,
  Database,
  GitPullRequest,
  Layers3,
  LockKeyhole,
  Network,
  Server,
  ShieldCheck,
  Siren,
  Sparkles,
  TimerReset,
  Truck,
  Users,
  Workflow,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { motion, useReducedMotion } from "framer-motion";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { ApiStatus } from "@/lib/api";

type IconCard = {
  icon: LucideIcon;
  title: string;
  copy: string;
  stage: "ready" | "planned" | "gated";
};

type CommandCenterProps = {
  apiStatus: ApiStatus;
};

const navItems: Array<{ label: string; icon: LucideIcon }> = [
  { label: "Portfolio", icon: Boxes },
  { label: "Agent Graph", icon: Workflow },
  { label: "Evidence Board", icon: Database },
  { label: "Policy Studio", icon: LockKeyhole },
  { label: "Trace Timeline", icon: Activity },
  { label: "Code Lens", icon: Braces },
];

const portfolio: IconCard[] = [
  {
    icon: GitPullRequest,
    title: "Engineering Issue-to-PR",
    copy: "GitHub issue, repo inspection, test plan, approval-gated PR draft.",
    stage: "ready",
  },
  {
    icon: ShieldCheck,
    title: "Security Remediation",
    copy: "Advisory triage, exploitability analysis, policy-gated patch plan.",
    stage: "planned",
  },
  {
    icon: Users,
    title: "Customer Support",
    copy: "Ticket, account context, retrieval-grounded reply, approval queue.",
    stage: "planned",
  },
  {
    icon: Truck,
    title: "Supplier Risk",
    copy: "Supplier data, approved research, sanctions signal, mitigation brief.",
    stage: "gated",
  },
  {
    icon: ClipboardCheck,
    title: "Finance Exception",
    copy: "Invoice evidence, policy comparison, approval route, audit trail.",
    stage: "gated",
  },
  {
    icon: Siren,
    title: "Incident Investigator",
    copy: "Logs, traces, deploys, CI history, hypothesis graph, RCA draft.",
    stage: "ready",
  },
  {
    icon: Building2,
    title: "Sales / RFP",
    copy: "CRM context, cited research, proposal draft, evaluator pass.",
    stage: "planned",
  },
  {
    icon: BadgeCheck,
    title: "Compliance Evidence",
    copy: "Control mapping, evidence collection, gap analysis, export approval.",
    stage: "planned",
  },
];

const workflowLanes = [
  {
    label: "Engineering",
    source: "GitHub",
    color: "teal",
    steps: ["Issue", "Repo", "Plan", "Patch", "Tests", "PR"],
  },
  {
    label: "Incident",
    source: "Deploys + Logs",
    color: "blue",
    steps: ["Alert", "Timeline", "Traces", "Hypothesis", "RCA", "Approval"],
  },
  {
    label: "Support",
    source: "Tickets + KB",
    color: "amber",
    steps: ["Ticket", "Account", "Docs", "Draft", "Review", "Reply"],
  },
  {
    label: "Finance",
    source: "Invoices",
    color: "rose",
    steps: ["Invoice", "Vendor", "Policy", "Route", "Audit", "Hold"],
  },
];

const stackLayers = [
  ["Rules", "Deterministic checks", "0 ms model cost"],
  ["OPA", "Dynamic policy", "approval and budgets"],
  ["LangGraph", "Stateful runtime", "checkpoints and interrupts"],
  ["MCP", "Typed tools", "schemas and scopes"],
  ["Memory", "Postgres + pgvector", "evidence and retention"],
  ["Evals", "Quality gates", "grounding and safety"],
];

const telemetry = [
  { name: "Rules", value: 44, cost: 0 },
  { name: "Policy", value: 31, cost: 0 },
  { name: "Workflow", value: 18, cost: 12 },
  { name: "Agentic", value: 7, cost: 88 },
];

const traceSeries = [
  { step: "Gate", model: 0, tools: 1, policy: 3 },
  { step: "Plan", model: 3, tools: 2, policy: 2 },
  { step: "Act", model: 2, tools: 6, policy: 5 },
  { step: "Review", model: 4, tools: 2, policy: 4 },
  { step: "Ship", model: 1, tools: 1, policy: 6 },
];

const evidenceRows = [
  ["Tool", "typed MCP contract", "blocked until connector ready"],
  ["Policy", "OPA decision point", "enforced before every action"],
  ["Memory", "Postgres checkpoint", "retention-class metadata"],
  ["Trace", "OpenTelemetry span", "model, tool, cost, approval"],
];

const statusLabel = {
  not_configured: "API not deployed",
  online: "API online",
  unreachable: "API unreachable",
} satisfies Record<ApiStatus["label"], string>;

export function CommandCenter({ apiStatus }: CommandCenterProps) {
  const shouldReduceMotion = useReducedMotion();

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">
            <BrainCircuit size={22} />
          </div>
          <div>
            <div>AegisOps</div>
            <div className="topbar-meta">Agentic Workflow Portfolio</div>
          </div>
        </div>
        <div className="topbar-meta">
          <span className="status-pill status-live">
            <span className="dot" />
            Phase 1 complete
          </span>
          <span className="status-pill status-muted">
            <Server size={14} />
            {statusLabel[apiStatus.label]}
          </span>
        </div>
      </header>

      <div className="command-layout">
        <aside className="sidebar">
          <section className="nav-section">
            <div className="nav-title">Command Center</div>
            {navItems.map(({ label, icon: Icon }, index) => (
              <motion.div
                className={`nav-item ${index === 0 ? "active" : ""}`}
                key={label}
                whileHover={shouldReduceMotion ? undefined : { x: 4 }}
              >
                <Icon size={17} />
                <span>{label}</span>
              </motion.div>
            ))}
          </section>

          <section className="nav-section">
            <div className="nav-title">Runtime Modes</div>
            <div className="mode-stack">
              <div className="mode-row">
                <span>Rule-based</span>
                <strong>$0</strong>
              </div>
              <div className="mode-row">
                <span>Dynamic policy</span>
                <strong>$0</strong>
              </div>
              <div className="mode-row">
                <span>AI workflow</span>
                <strong>metered</strong>
              </div>
              <div className="mode-row locked">
                <span>Agentic live run</span>
                <strong>admin</strong>
              </div>
            </div>
          </section>
        </aside>

        <section className="main cockpit">
          <section className="mission-strip">
            <div className="mission-copy">
              <div className="eyebrow">Production-grade agentic AI</div>
              <h1>Enterprise workflows with every layer visible.</h1>
              <p>
                A governed execution cockpit for real tools, real policies, memory, approvals,
                traces, and deployment gates.
              </p>
            </div>
            <div className="mission-metrics" aria-label="Architecture metrics">
              <Metric value="10" label="workflow modules" />
              <Metric value="4" label="control modes" />
              <Metric value="0" label="fake data paths" />
              <Metric value="100%" label="sensitive actions gated" />
            </div>
          </section>

          <section className="ops-grid">
            <section className="panel command-panel parallel-panel">
              <PanelHeader icon={Network} title="Parallel Workflow Fabric" badge="config-driven" />
              <div className="lane-stack">
                {workflowLanes.map((lane, index) => (
                  <motion.div
                    className={`lane lane-${lane.color}`}
                    key={lane.label}
                    initial={shouldReduceMotion ? false : { opacity: 0, y: 18 }}
                    animate={shouldReduceMotion ? undefined : { opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.08, duration: 0.45 }}
                  >
                    <div className="lane-head">
                      <strong>{lane.label}</strong>
                      <span>{lane.source}</span>
                    </div>
                    <div className="lane-rail">
                      {!shouldReduceMotion && (
                        <motion.span
                          className="lane-pulse"
                          animate={{ x: ["0%", "640%"] }}
                          transition={{
                            repeat: Infinity,
                            duration: 5.2 + index * 0.5,
                            ease: "linear",
                            delay: index * 0.6,
                          }}
                        />
                      )}
                      {lane.steps.map((step) => (
                        <span className="lane-step" key={step}>
                          {step}
                        </span>
                      ))}
                    </div>
                  </motion.div>
                ))}
              </div>
            </section>

            <section className="panel command-panel stack-panel">
              <PanelHeader icon={Layers3} title="Stack Depth" badge="peel layers" />
              <div className="layer-stack">
                {stackLayers.map(([title, body, meta], index) => (
                  <motion.div
                    className="layer-row"
                    key={title}
                    initial={shouldReduceMotion ? false : { opacity: 0, x: 24 }}
                    animate={shouldReduceMotion ? undefined : { opacity: 1, x: 0 }}
                    transition={{ delay: 0.12 + index * 0.06, duration: 0.35 }}
                  >
                    <div className="layer-index">{String(index + 1).padStart(2, "0")}</div>
                    <div>
                      <strong>{title}</strong>
                      <span>{body}</span>
                    </div>
                    <em>{meta}</em>
                  </motion.div>
                ))}
              </div>
            </section>
          </section>

          <section className="telemetry-grid">
            <section className="panel chart-panel">
              <PanelHeader icon={ChartNoAxesCombined} title="Cost Routing Model" badge="unit economics" />
              <div className="chart-frame">
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={telemetry}>
                    <CartesianGrid stroke="rgba(255,255,255,0.08)" vertical={false} />
                    <XAxis dataKey="name" tickLine={false} axisLine={false} stroke="#9aa5b8" />
                    <YAxis hide />
                    <Tooltip
                      cursor={{ fill: "rgba(255,255,255,0.04)" }}
                      contentStyle={{
                        background: "#111722",
                        border: "1px solid rgba(255,255,255,0.14)",
                        borderRadius: 8,
                        color: "#f5f7fb",
                      }}
                    />
                    <Bar dataKey="value" fill="#35c2a7" radius={[6, 6, 0, 0]} />
                    <Bar dataKey="cost" fill="#f4c95d" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </section>

            <section className="panel chart-panel">
              <PanelHeader icon={Activity} title="Trace Composition" badge="observable" />
              <div className="chart-frame">
                <ResponsiveContainer width="100%" height={220}>
                  <AreaChart data={traceSeries}>
                    <defs>
                      <linearGradient id="modelCalls" x1="0" x2="0" y1="0" y2="1">
                        <stop offset="5%" stopColor="#78a6ff" stopOpacity={0.65} />
                        <stop offset="95%" stopColor="#78a6ff" stopOpacity={0.02} />
                      </linearGradient>
                      <linearGradient id="toolCalls" x1="0" x2="0" y1="0" y2="1">
                        <stop offset="5%" stopColor="#35c2a7" stopOpacity={0.65} />
                        <stop offset="95%" stopColor="#35c2a7" stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="rgba(255,255,255,0.08)" vertical={false} />
                    <XAxis dataKey="step" tickLine={false} axisLine={false} stroke="#9aa5b8" />
                    <YAxis hide />
                    <Tooltip
                      contentStyle={{
                        background: "#111722",
                        border: "1px solid rgba(255,255,255,0.14)",
                        borderRadius: 8,
                        color: "#f5f7fb",
                      }}
                    />
                    <Area
                      type="monotone"
                      dataKey="model"
                      stroke="#78a6ff"
                      fill="url(#modelCalls)"
                      strokeWidth={2}
                    />
                    <Area
                      type="monotone"
                      dataKey="tools"
                      stroke="#35c2a7"
                      fill="url(#toolCalls)"
                      strokeWidth={2}
                    />
                    <Area
                      type="monotone"
                      dataKey="policy"
                      stroke="#f4c95d"
                      fill="transparent"
                      strokeWidth={2}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </section>

            <section className="panel evidence-panel">
              <PanelHeader icon={Database} title="Evidence Board" badge="no black box" />
              <div className="evidence-table">
                {evidenceRows.map(([type, contract, state]) => (
                  <div className="evidence-row" key={type}>
                    <span>{type}</span>
                    <strong>{contract}</strong>
                    <em>{state}</em>
                  </div>
                ))}
              </div>
            </section>
          </section>

          <section className="panel portfolio-panel">
            <PanelHeader icon={Sparkles} title="Enterprise Workflow Portfolio" badge="real connectors only" />
            <div className="portfolio">
              {portfolio.map(({ icon: Icon, title, copy, stage }, index) => (
                <motion.article
                  className="workflow-card"
                  key={title}
                  initial={shouldReduceMotion ? false : { opacity: 0, y: 16 }}
                  animate={shouldReduceMotion ? undefined : { opacity: 1, y: 0 }}
                  transition={{ delay: 0.05 * index, duration: 0.35 }}
                  whileHover={shouldReduceMotion ? undefined : { y: -4 }}
                >
                  <div className="workflow-title">
                    <Icon size={18} />
                    <span>{title}</span>
                  </div>
                  <div className="workflow-copy">{copy}</div>
                  <div className={`workflow-stage stage-${stage}`}>
                    {stage === "ready" ? "foundation ready" : stage === "planned" ? "planned" : "connector gated"}
                  </div>
                </motion.article>
              ))}
            </div>
          </section>

          <section className="bottom-grid">
            <section className="panel">
              <PanelHeader icon={TimerReset} title="Build State" badge="Phase 1 complete" />
              <div className="lens-list compact">
                <LensRow label="Completed" value="Architecture, workflow registry, API health, deployable UI" />
                <LensRow label="Next" value="Governance data layer, migrations, OPA baseline" />
                <LensRow label="Live data" value="Disabled until real connectors are configured" />
                <LensRow label="Replay" value="Only from captured real runs" />
              </div>
            </section>

            <section className="panel">
              <PanelHeader icon={Server} title="Backend Runtime" badge={statusLabel[apiStatus.label]} />
              <div className="lens-list compact">
                <LensRow label="API connection" value={apiStatus.message} />
                <LensRow
                  label="Production rule"
                  value="Live workflows stay disabled until backend policy gates are deployed."
                />
              </div>
            </section>

            <section className="panel">
              <PanelHeader icon={Code2} title="Engineer Lens" badge="inspection ready" />
              <div className="code-strip">
                <span>LangGraph</span>
                <span>Pydantic</span>
                <span>MCP</span>
                <span>OPA</span>
                <span>Postgres</span>
                <span>OpenTelemetry</span>
              </div>
            </section>
          </section>
        </section>
      </div>
    </main>
  );
}

function Metric({ value, label }: { value: string; label: string }) {
  return (
    <motion.div className="metric" whileHover={{ y: -3 }}>
      <div className="metric-value">{value}</div>
      <div className="metric-label">{label}</div>
    </motion.div>
  );
}

function PanelHeader({
  icon: Icon,
  title,
  badge,
}: {
  icon: LucideIcon;
  title: string;
  badge: string;
}) {
  return (
    <div className="panel-header">
      <div className="panel-title">
        <Icon size={18} />
        {title}
      </div>
      <span className="badge">{badge}</span>
    </div>
  );
}

function LensRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="lens-row">
      <span className="lens-label">{label}</span>
      <span className="lens-value">{value}</span>
    </div>
  );
}
