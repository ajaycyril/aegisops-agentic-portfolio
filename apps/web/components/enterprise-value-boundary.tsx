import { Bot, Braces, GitBranch } from "lucide-react";

import type { ScenarioDefinition } from "@/lib/agentic/scenarios";

export function EnterpriseValueBoundary({
  scenario,
}: {
  scenario: ScenarioDefinition;
}) {
  return (
    <section
      className="value-boundary"
      aria-label={`${scenario.name} enterprise value boundary`}
    >
      <div className="value-context">
        <span>Production integration pattern</span>
        <strong>{scenario.businessOutcome}</strong>
        <small>{scenario.enterpriseSystems}</small>
      </div>
      <div className="value-comparison">
        <div className="value-side value-traditional">
          <span className="value-icon">
            <Braces size={16} />
          </span>
          <span>
            <small>TRADITIONAL AUTOMATION</small>
            <strong>{scenario.ruleBoundary}</strong>
          </span>
        </div>
        <GitBranch className="value-branch" size={18} />
        <div className="value-side value-agentic">
          <span className="value-icon">
            <Bot size={16} />
          </span>
          <span>
            <small>AGENTIC ADVANTAGE</small>
            <strong>{scenario.agenticAdvantage}</strong>
          </span>
        </div>
      </div>
    </section>
  );
}
