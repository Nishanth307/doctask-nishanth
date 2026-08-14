import type { WorkflowEventResponse, WorkflowStage } from "../api/types";

interface RunTimelineProps {
  events: WorkflowEventResponse[];
  currentStage: WorkflowStage;
  runStatus: string;
}

const STAGES_ORDER: { stage: WorkflowStage; label: string }[] = [
  { stage: "ingestion", label: "Ingestion" },
  { stage: "classification", label: "Classification" },
  { stage: "extraction", label: "Extraction" },
  { stage: "reconciliation", label: "Reconciliation" },
  { stage: "examination", label: "Examination" },
  { stage: "review", label: "Review" },
  { stage: "commit", label: "Commit" },
];

export function RunTimeline({ events, currentStage, runStatus }: RunTimelineProps) {
  // Helper to find events for a specific stage
  const getStageEvents = (stage: WorkflowStage) => {
    return events.filter((e) => e.stage === stage);
  };

  // Helper to determine the state of a stage
  const getStageState = (stage: WorkflowStage) => {
    const stageEvents = getStageEvents(stage);
    const hasCompleted = stageEvents.some((e) => e.status === "completed");
    const hasFailed = stageEvents.some((e) => e.status === "failed");
    const hasStarted = stageEvents.some((e) => e.status === "started" || e.status === "running");

    if (hasFailed) return "failed";
    if (hasCompleted) return "completed";
    
    // If the run itself failed at this stage
    if (runStatus === "failed" && currentStage === stage) return "failed";
    
    // If the run is waiting for review at the review stage
    if (runStatus === "waiting_for_review" && stage === "review") return "waiting";

    if (currentStage === stage && runStatus === "running") return "running";
    if (hasStarted) return "running";

    // Determine if it is past or future based on order
    const currentIndex = STAGES_ORDER.findIndex((s) => s.stage === currentStage);
    const stageIndex = STAGES_ORDER.findIndex((s) => s.stage === stage);

    if (stageIndex < currentIndex) {
      return "completed"; // Assume completed if we are past it
    }

    return "pending";
  };

  return (
    <div className="workflow-timeline">
      <h2>Workflow Progress</h2>
      <div className="timeline-stages">
        {STAGES_ORDER.map(({ stage, label }, index) => {
          const state = getStageState(stage);
          const stageEvents = getStageEvents(stage);
          const latestEvent = stageEvents[stageEvents.length - 1];

          let icon = "○";
          let stateClass = "state-pending";

          if (state === "completed") {
            icon = "✓";
            stateClass = "state-completed";
          } else if (state === "failed") {
            icon = "✗";
            stateClass = "state-failed";
          } else if (state === "running") {
            icon = "→";
            stateClass = "state-running";
          } else if (state === "waiting") {
            icon = "⚠";
            stateClass = "state-waiting";
          }

          return (
            <div key={stage} className={`timeline-item ${stateClass}`}>
              <div className="timeline-line-wrapper">
                <div className="timeline-icon">{icon}</div>
                {index < STAGES_ORDER.length - 1 && <div className="timeline-line"></div>}
              </div>
              <div className="timeline-content">
                <span className="stage-label">{label}</span>
                {latestEvent && latestEvent.message && (
                  <span className="stage-message">{latestEvent.message}</span>
                )}
                {latestEvent && latestEvent.duration_ms !== null && (
                  <span className="stage-duration">({latestEvent.duration_ms}ms)</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
