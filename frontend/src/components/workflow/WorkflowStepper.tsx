import React from "react";
import {
  CheckCircle2,
  Loader2,
  AlertTriangle,
  XCircle,
  Circle,
  FileText,
  Layers,
  Search,
  GitCompare,
  ShieldCheck,
  UserCheck,
  CheckCheck,
} from "lucide-react";
import type { WorkflowEventResponse, WorkflowStage } from "../../api/types";

interface WorkflowStepperProps {
  events?: WorkflowEventResponse[];
  currentStage: WorkflowStage | string;
  runStatus: string;
}

interface StageDefinition {
  stage: WorkflowStage;
  label: string;
  description: string;
  icon: React.ReactNode;
}

const DEFAULT_STAGES: StageDefinition[] = [
  {
    stage: "ingestion",
    label: "Ingestion",
    description: "Document parsing",
    icon: <FileText size={16} />,
  },
  {
    stage: "classification",
    label: "Classification",
    description: "Doc type & rules",
    icon: <Layers size={16} />,
  },
  {
    stage: "extraction",
    label: "Extraction",
    description: "Entity & clause facts",
    icon: <Search size={16} />,
  },
  {
    stage: "reconciliation",
    label: "Reconciliation",
    description: "Cross-doc alignment",
    icon: <GitCompare size={16} />,
  },
  {
    stage: "examination",
    label: "Examination",
    description: "Policy & rule check",
    icon: <ShieldCheck size={16} />,
  },
  {
    stage: "review",
    label: "Human Review",
    description: "Decision gate",
    icon: <UserCheck size={16} />,
  },
  {
    stage: "commit",
    label: "Commit",
    description: "Finalize deliverable",
    icon: <CheckCheck size={16} />,
  },
];

export const WorkflowStepper: React.FC<WorkflowStepperProps> = ({
  events = [],
  currentStage,
  runStatus,
}) => {
  const getStageEvents = (stage: WorkflowStage) => {
    return events.filter((e) => e.stage === stage);
  };

  const getStageStatus = (stage: WorkflowStage, index: number) => {
    const stageEvents = getStageEvents(stage);
    const hasCompleted = stageEvents.some(
      (e) => e.status === "completed" || e.status === "success"
    );
    const hasFailed = stageEvents.some(
      (e) => e.status === "failed" || e.status === "error"
    );
    const isCurrentlyActive = currentStage === stage && runStatus === "running";

    if (hasFailed || (runStatus === "failed" && currentStage === stage)) {
      return "failed";
    }
    if (hasCompleted) {
      return "completed";
    }
    if (stage === "review" && (runStatus === "waiting_for_review" || currentStage === "review")) {
      if (runStatus === "waiting_for_review") return "review_required";
      if (runStatus === "completed") return "completed";
    }
    if (isCurrentlyActive) {
      return "running";
    }

    const currentIndex = DEFAULT_STAGES.findIndex((s) => s.stage === currentStage);
    if (currentIndex !== -1 && index < currentIndex) {
      return "completed";
    }

    return "pending";
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case "completed":
        return "Completed";
      case "running":
        return "Processing...";
      case "review_required":
        return "Needs attention";
      case "failed":
        return "Failed";
      case "pending":
      default:
        return "Pending";
    }
  };

  const renderStatusIcon = (status: string) => {
    switch (status) {
      case "completed":
        return <CheckCircle2 className="step-icon-svg text-emerald-500" size={18} />;
      case "running":
        return <Loader2 className="step-icon-svg text-blue-500 animate-spin" size={18} />;
      case "review_required":
        return <AlertTriangle className="step-icon-svg text-amber-500 animate-bounce-subtle" size={18} />;
      case "failed":
        return <XCircle className="step-icon-svg text-rose-500" size={18} />;
      case "pending":
      default:
        return <Circle className="step-icon-svg text-slate-300" size={16} />;
    }
  };

  return (
    <div className="workflow-stepper-card">
      <div className="workflow-stepper-header">
        <h3 className="workflow-stepper-title">Workflow Progress</h3>
        <span className="workflow-stepper-subtitle">
          Real-time pipeline execution stages
        </span>
      </div>

      <div className="workflow-stepper-track">
        {DEFAULT_STAGES.map((step, idx) => {
          const status = getStageStatus(step.stage, idx);
          const nextStepStatus =
            idx < DEFAULT_STAGES.length - 1
              ? getStageStatus(DEFAULT_STAGES[idx + 1].stage, idx + 1)
              : null;

          // Connector line styling
          let connectorClass = "connector-pending";
          if (status === "completed" && (nextStepStatus === "completed" || nextStepStatus === "running" || nextStepStatus === "review_required")) {
            connectorClass = "connector-completed";
          } else if (status === "running" || (status === "completed" && nextStepStatus === "pending")) {
            connectorClass = "connector-active";
          }

          return (
            <div key={step.stage} className={`stepper-node-wrapper state-${status}`}>
              <div className="stepper-node">
                <div className={`stepper-circle circle-${status}`} title={`${step.label}: ${getStatusLabel(status)}`}>
                  {renderStatusIcon(status)}
                </div>

                <div className="stepper-label-container">
                  <span className="stepper-stage-name">{step.label}</span>
                  <span className={`stepper-status-text status-text-${status}`}>
                    {getStatusLabel(status)}
                  </span>
                </div>
              </div>

              {idx < DEFAULT_STAGES.length - 1 && (
                <div className={`stepper-connector ${connectorClass}`}>
                  <div className="connector-progress-line" />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
