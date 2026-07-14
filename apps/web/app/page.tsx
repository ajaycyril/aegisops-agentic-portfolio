import {
  Activity,
  BadgeCheck,
  Boxes,
  BrainCircuit,
  Braces,
  Building2,
  ChartNoAxesCombined,
  ClipboardCheck,
  Database,
  GitPullRequest,
  Layers3,
  LockKeyhole,
  Network,
  ShieldCheck,
  Siren,
  TimerReset,
  Truck,
  Users,
  Workflow,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { ApiStatusPanel } from "@/components/api-status-panel";

type IconCard = {
  icon: LucideIcon;
  title: string;
  copy: string;
};

const portfolio: IconCard[] = [
  {
    icon: GitPullRequest,
    title: "Engineering Issue-to-PR",
    copy: "Real GitHub issue, repo inspection, test planning, approval-gated PR draft.",
  },
  {
    icon: ShieldCheck,
    title: "Security Remediation",
    copy: "Dependency advisories, exploitability analysis, policy-gated remediation plan.",
  },
  {
    icon: Users,
    title: "Customer Support Escalation",
    copy: "Ticket context, account history, knowledge retrieval, approved response draft.",
  },
  {
    icon: Truck,
    title: "Supplier Risk",
    copy: "Supplier system, approved research, sanctions signals, mitigation brief.",
  },
  {
    icon: ClipboardCheck,
    title: "Finance Invoice Exception",
    copy: "Invoice evidence, policy comparison, approval route, audit record.",
  },
  {
    icon: Siren,
    title: "Incident Investigator",
    copy: "Logs, traces, deploys, CI history, hypothesis graph, RCA draft.",
  },
  {
    icon: Building2,
    title: "Sales / RFP Agent",
    copy: "CRM context, source-grounded research, proposal draft, evaluator pass.",
  },
  {
    icon: BadgeCheck,
    title: "Compliance Evidence",
    copy: "Control mapping, evidence collection, gap analysis, export approval.",
  },
];

const graphNodes = [
  ["Input", "Real System Event", "GitHub, support, finance, observability, or CRM source."],
  ["Gate", "OPA Policy Check", "Autonomy, tool access, spend, data sensitivity, approval path."],
  ["Plan", "LangGraph Runtime", "Typed state, checkpoints, routing, interrupts, and retries."],
  ["Act", "MCP Tool Layer", "Typed tool schemas with auth scopes and risk classes."],
  ["Reason", "OpenAI Model Call", "Structured output, trace metadata, token and latency budget."],
  ["Remember", "Memory and Retrieval", "Postgres, pgvector, evidence records, retention controls."],
  ["Review", "Evaluator and HITL", "Quality checks and human approval before sensitive actions."],
  ["Ship", "Audited Outcome", "Draft PR, response, RCA, evidence packet, or approved action."],
];

const lenses = [
  ["Orchestration", "LangGraph primary runtime"],
  ["Model layer", "Responses API + Agents SDK specialists"],
  ["Tools", "MCP contracts, typed schemas, auth scopes"],
  ["Policy", "OPA/Rego outside the model"],
  ["Data", "Postgres, pgvector, Redis"],
  ["Safety", "Pydantic, approvals, budgets, audit trail"],
  ["Observability", "OpenTelemetry, LangSmith, Langfuse-ready"],
  ["Deployment", "Vercel web, container API, managed Postgres"],
];

const navItems: Array<{ label: string; icon: LucideIcon }> = [
  { label: "Portfolio", icon: Boxes },
  { label: "Agent Graph", icon: Workflow },
  { label: "Evidence Board", icon: Database },
  { label: "Policy Studio", icon: LockKeyhole },
  { label: "Trace Timeline", icon: Activity },
  { label: "Code Lens", icon: Braces },
];

export default function Home() {
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
          <span className="status-pill">
            <span className="dot" />
            Architecture baseline deployed
          </span>
          <span>Phase 1 foundation runtime complete</span>
        </div>
      </header>

      <div className="layout">
        <aside className="sidebar">
          <section className="nav-section">
            <div className="nav-title">Command Center</div>
            {navItems.map(({ label, icon: Icon }, index) => (
              <div className={`nav-item ${index === 0 ? "active" : ""}`} key={label}>
                <Icon size={17} />
                <span>{label}</span>
              </div>
            ))}
          </section>
          <section className="nav-section">
            <div className="nav-title">Operating Rules</div>
            <div className="lens-list">
              <div className="status-pill">No fake data</div>
              <div className="status-pill">Typed tools only</div>
              <div className="status-pill">Policy before action</div>
            </div>
          </section>
        </aside>

        <section className="main">
          <div className="hero">
            <section className="hero-copy">
              <div className="eyebrow">Production-grade agentic AI</div>
              <h1>Enterprise workflows with every layer visible.</h1>
              <p>
                A visual command center that shows how governed agents plan, use tools, remember,
                retrieve evidence, request approval, emit traces, and produce auditable outcomes
                across real business systems.
              </p>
            </section>

            <section className="metrics-grid" aria-label="Architecture metrics">
              <div className="metric">
                <div className="metric-value">10</div>
                <div className="metric-label">enterprise workflow modules</div>
              </div>
              <div className="metric">
                <div className="metric-value">4</div>
                <div className="metric-label">control modes separated</div>
              </div>
              <div className="metric">
                <div className="metric-value">0</div>
                <div className="metric-label">fake business data allowed</div>
              </div>
              <div className="metric">
                <div className="metric-value">100%</div>
                <div className="metric-label">policy-gated sensitive actions</div>
              </div>
            </section>
          </div>

          <div className="workspace">
            <section className="panel">
              <div className="panel-header">
                <div className="panel-title">
                  <Network size={18} />
                  Stack Execution Graph
                </div>
                <span className="badge">Peel-the-layers UX</span>
              </div>
              <div className="panel-body">
                <div className="graph">
                  {graphNodes.map(([kicker, title, meta]) => (
                    <div className="graph-node" key={title}>
                      <div className="node-kicker">{kicker}</div>
                      <div className="node-title">{title}</div>
                      <div className="node-meta">{meta}</div>
                    </div>
                  ))}
                </div>
              </div>
            </section>

            <section className="panel">
              <div className="panel-header">
                <div className="panel-title">
                  <Layers3 size={18} />
                  Stack Lens
                </div>
              </div>
              <div className="panel-body">
                <div className="lens-list">
                  {lenses.map(([label, value]) => (
                    <div className="lens-row" key={label}>
                      <span className="lens-label">{label}</span>
                      <span className="lens-value">{value}</span>
                    </div>
                  ))}
                </div>
              </div>
            </section>
          </div>

          <section className="panel" style={{ marginTop: 22 }}>
            <div className="panel-header">
              <div className="panel-title">
                <ChartNoAxesCombined size={18} />
                Enterprise Workflow Portfolio
              </div>
              <span className="badge">Connector-gated live runs</span>
            </div>
            <div className="panel-body">
              <div className="portfolio">
                {portfolio.map(({ icon: Icon, title, copy }) => (
                  <article className="workflow-card" key={title}>
                    <div className="workflow-title">
                      <Icon size={18} />
                      <span>{title}</span>
                    </div>
                    <div className="workflow-copy">{copy}</div>
                  </article>
                ))}
              </div>
            </div>
          </section>

          <section className="panel" style={{ marginTop: 22 }}>
            <div className="panel-header">
              <div className="panel-title">
                <TimerReset size={18} />
                Current Build State
              </div>
                <span className="badge">Phase 1 complete</span>
            </div>
            <div className="panel-body">
              <div className="lens-list">
                <div className="lens-row">
                  <span className="lens-label">Completed</span>
                  <span className="lens-value">
                    Architecture, workflow registry, API health, deployable shell
                  </span>
                </div>
                <div className="lens-row">
                  <span className="lens-label">Next</span>
                  <span className="lens-value">Governance data layer, migrations, OPA baseline</span>
                </div>
                <div className="lens-row">
                  <span className="lens-label">Live data</span>
                  <span className="lens-value">Disabled until real connectors are configured</span>
                </div>
                <div className="lens-row">
                  <span className="lens-label">Replay</span>
                  <span className="lens-value">Allowed only from captured real runs</span>
                </div>
              </div>
            </div>
          </section>

          <ApiStatusPanel />
        </section>
      </div>
    </main>
  );
}
