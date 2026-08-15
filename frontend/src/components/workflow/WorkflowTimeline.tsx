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
          let statusIcon = "○";
          if (event.status === "completed" || event.status === "success") {
            statusIcon = "✓";
          } else if (event.status === "running" || event.status === "active") {
            statusIcon = "●";
          } else if (event.status === "failed" || event.status === "error") {
            statusIcon = "✕";
          } else if (event.status === "waiting" || event.status === "waiting_for_review") {
            statusIcon = "⚠";
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
                <span className={`status-icon status-icon-${event.status}`} style={{ fontWeight: "bold" }}>
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
