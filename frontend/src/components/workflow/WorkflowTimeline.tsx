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

      <ol className="timeline-log-list">
        {events.map((event) => (
          <li key={event.id} className="timeline-log-item">
            <div>
              <strong>{event.stage}</strong>
            </div>

            <div>
              Status: {event.status}
            </div>

            {event.message && (
              <div>{event.message}</div>
            )}

            {event.duration_ms !== null &&
              event.duration_ms !== undefined && (
                <div>
                  Duration: {event.duration_ms} ms
                </div>
              )}
          </li>
        ))}
      </ol>
    </section>
  );
}

export default WorkflowTimeline;
