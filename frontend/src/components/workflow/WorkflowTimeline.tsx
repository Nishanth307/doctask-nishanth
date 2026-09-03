import { CheckCircle2, Loader2, AlertTriangle, XCircle, Circle } from "lucide-react";
import type { WorkflowEventResponse } from "../../api/types";

interface WorkflowTimelineProps {
  events: WorkflowEventResponse[];
}

export function WorkflowTimeline({ events }: WorkflowTimelineProps) {
  if (events.length === 0) {
    return (
      <section className="card workflow-timeline-log">
        <h2>Workflow Timeline</h2>
        <p>No workflow events recorded.</p>
      </section>
    );
  }

  return (
    <section className="card workflow-timeline-log">
      <h2>Workflow Timeline Log</h2>

      <ol className="timeline-log-list" style={{ listStyleType: "none", paddingLeft: 0 }}>
        {events.map((event) => {
          let statusIcon = <Circle size={14} className="text-slate-400" />;
          if (event.status === "completed" || event.status === "success") {
            statusIcon = <CheckCircle2 size={14} className="text-emerald-500" />;
          } else if (event.status === "running" || event.status === "active") {
            statusIcon = <Loader2 size={14} className="text-blue-500 animate-spin" />;
          } else if (event.status === "failed" || event.status === "error") {
            statusIcon = <XCircle size={14} className="text-rose-500" />;
          } else if (event.status === "waiting" || event.status === "waiting_for_review") {
            statusIcon = <AlertTriangle size={14} className="text-amber-500" />;
          }

          const durationText =
            event.duration_ms !== null && event.duration_ms !== undefined
              ? event.duration_ms >= 1000
                ? `${(event.duration_ms / 1000).toFixed(1)} s`
                : `${event.duration_ms} ms`
              : null;

          return (
            <li key={event.id} className="timeline-log-item" style={{ marginBottom: "16px", paddingLeft: "8px", borderLeft: "2px solid #e2e8f0" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span className={`status-icon status-icon-${event.status}`}>
                  {statusIcon}
                </span>
                <strong style={{ textTransform: "capitalize" }}>{event.stage.replaceAll("_", " ")}</strong>
              </div>

              {event.message && (
                <div style={{ color: "#475569", margin: "4px 0" }}>{event.message}</div>
              )}

              <div style={{ fontSize: "12px", color: "#94a3b8" }}>
                <span>{new Date(event.created_at).toLocaleString()}</span>
                {durationText && <span> • {durationText}</span>}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

export default WorkflowTimeline;
