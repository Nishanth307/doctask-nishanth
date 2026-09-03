import { CheckCircle2, Loader2, AlertTriangle, XCircle, Circle } from "lucide-react";
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
  const getStageEvents = (stage: WorkflowStage) => {
    return events.filter((e) => e.stage === stage);
  };

  const getStageState = (stage: WorkflowStage) => {
    const stageEvents = getStageEvents(stage);
    const hasCompleted = stageEvents.some((e) => e.status === "completed");
    const hasFailed = stageEvents.some((e) => e.status === "failed");
    const hasStarted = stageEvents.some((e) => e.status === "started" || e.status === "running");

    if (hasFailed) return "failed";
    if (hasCompleted) return "completed";
    if (runStatus === "failed" && currentStage === stage) return "failed";
    if (runStatus === "waiting_for_review" && stage === "review") return "waiting";
    if (currentStage === stage && runStatus === "running") return "running";
    if (hasStarted) return "running";

    const currentIndex = STAGES_ORDER.findIndex((s) => s.stage === currentStage);
    const stageIndex = STAGES_ORDER.findIndex((s) => s.stage === stage);

    if (stageIndex < currentIndex) {
      return "completed";
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

          let icon = <Circle size={16} className="text-slate-300" />;
          let stateClass = "state-pending";

          if (state === "completed") {
            icon = <CheckCircle2 size={16} className="text-emerald-500" />;
            stateClass = "state-completed";
          } else if (state === "failed") {
            icon = <XCircle size={16} className="text-rose-500" />;
            stateClass = "state-failed";
          } else if (state === "running") {
            icon = <Loader2 size={16} className="text-blue-500 animate-spin" />;
            stateClass = "state-running";
          } else if (state === "waiting") {
            icon = <AlertTriangle size={16} className="text-amber-500" />;
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
