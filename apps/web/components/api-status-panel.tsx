import { Server } from "lucide-react";

import { getApiStatus } from "@/lib/api";

export async function ApiStatusPanel() {
  const status = await getApiStatus();

  const value =
    status.label === "online"
      ? `${status.health.service}: ${status.health.status}`
      : status.label.replace("_", " ");

  return (
    <section className="panel" style={{ marginTop: 22 }}>
      <div className="panel-header">
        <div className="panel-title">
          <Server size={18} />
          Backend Runtime
        </div>
        <span className={`badge ${status.label === "online" ? "" : "badge-muted"}`}>{value}</span>
      </div>
      <div className="panel-body">
        <div className="lens-list">
          <div className="lens-row">
            <span className="lens-label">API connection</span>
            <span className="lens-value">{status.message}</span>
          </div>
          <div className="lens-row">
            <span className="lens-label">Production rule</span>
            <span className="lens-value">Live workflows stay disabled until backend policy gates are deployed.</span>
          </div>
        </div>
      </div>
    </section>
  );
}
