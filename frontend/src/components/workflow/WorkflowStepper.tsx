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
  GitPullRequest,
  UserCheck,
  CheckSquare,
  CheckCheck,
} from "lucide-react";
import type { WorkflowEventResponse, WorkflowStage, NodeExecutionRecord } from "../../api/types";

interface WorkflowStepperProps {
  events?: WorkflowEventResponse[];
  currentStage: WorkflowStage | string;
  runStatus: string;
  selectedNode?: string | null;
  onSelectNode?: (nodeName: string) => void;
  executionHistory?: NodeExecutionRecord[];
}

interface StageDefinition {
  id: string;
  stage: WorkflowStage | string;
  nodeNames: string[];
  label: string;
  description: string;
  icon: React.ReactNode;
}

const WORKFLOW_STAGES: StageDefinition[] = [
  {
    id: "ingestion",
    stage: "ingestion",
    nodeNames: ["ingestion"],
    label: "Ingest",
    description: "Doc ingestion",
    icon: <FileText size={16} />,
  },
  {
    id: "classification",
    stage: "classification",
    nodeNames: ["classify"],
    label: "Classify",
    description: "Document classification",
    icon: <Layers size={16} />,
  },
  {
    id: "extraction",
    stage: "extraction",
    nodeNames: ["extract"],
    label: "Extract",
    description: "Fact extraction",
    icon: <Search size={16} />,
  },
  {
    id: "reconciliation",
    stage: "reconciliation",
    nodeNames: ["reconcile"],
    label: "Reconcile",
    description: "Cross-doc alignment",
    icon: <GitCompare size={16} />,
  },
  {
    id: "examination",
    stage: "examination",
    nodeNames: ["examine"],
    label: "Examine",
    description: "Rule compliance",
    icon: <ShieldCheck size={16} />,
  },
  {
    id: "generate_changes",
    stage: "generate_changes",
    nodeNames: ["generate_suggested_changes"],
    label: "Changes",
    description: "Generate edits",
    icon: <GitPullRequest size={16} />,
  },
  {
    id: "review",
    stage: "findings_review",
    nodeNames: ["findings_review", "human_review", "revise"],
    label: "Review",
    description: "Human review gate",
    icon: <UserCheck size={16} />,
  },
  {
    id: "apply_validate",
    stage: "apply_edits",
    nodeNames: ["apply_edits", "validate_edits"],
    label: "Apply & Validate",
    description: "Apply edits & verify",
    icon: <CheckSquare size={16} />,
  },
  {
    id: "commit",
    stage: "commit",
    nodeNames: ["commit", "update"],
    label: "Commit",
    description: "Finalize deliverable",
    icon: <CheckCheck size={16} />,
  },
];

export const WorkflowStepper: React.FC<WorkflowStepperProps> = ({
  events = [],
  currentStage,
  runStatus,
  selectedNode,
  onSelectNode,
  executionHistory = [],
}) => {
  const getStageEvents = (def: StageDefinition) => {
    return events.filter((e) => {
      if (e.node_name && def.nodeNames.includes(e.node_name)) {
        return true;
      }
      if (e.stage === def.stage) {
        return true;
      }
      if (def.id === "review" && (e.stage === "review" || e.stage === "findings_review")) {
        return true;
      }
      if (def.id === "apply_validate" && (e.stage === "apply_edits" || e.stage === "validate_edits")) {
        return true;
      }
      if (def.id === "commit" && (e.stage === "commit" || e.stage === "update")) {
        return true;
      }
      return false;
    });
  };

  const getStageAttempts = (def: StageDefinition) => {
    const fromHist = executionHistory.filter((rec) => def.nodeNames.includes(rec.node_name));
    if (fromHist.length > 0) {
      return Math.max(...fromHist.map((h) => h.attempt || 1));
    }
    const stageEvents = getStageEvents(def);
    const maxAttempt = stageEvents.reduce((max, ev) => Math.max(max, ev.attempt || 1), 1);
    return maxAttempt;
  };

  const getStageStatus = (def: StageDefinition, index: number) => {
    const stageEvents = getStageEvents(def);

    const hasFailed = stageEvents.some(
      (e) => e.status === "failed" || e.status === "error"
    );
    const hasCompleted = stageEvents.some(
      (e) => e.status === "completed" || e.status === "success"
    );
    const hasStarted = stageEvents.some((e) => e.status === "started");

    // Review gate special handling
    if (def.id === "review") {
      if (runStatus === "waiting_for_review") {
        return "review_required";
      }
    }

    if (hasFailed) {
      return "failed";
    }

    if (runStatus === "failed") {
      // If this specific stage is where it failed
      if (currentStage === def.stage || stageEvents.some((e) => e.status === "started")) {
        if (!hasCompleted) return "failed";
      }
    }

    if (runStatus === "completed") {
      return "completed";
    }

    if (hasCompleted) {
      return "completed";
    }

    if (hasStarted && runStatus === "running") {
      return "running";
    }

    // Active stage matching currentStage
    const isCurrentlyActive =
      (currentStage === def.stage ||
        (def.id === "review" && (currentStage === "review" || currentStage === "findings_review")) ||
        (def.id === "apply_validate" && (currentStage === "apply_edits" || currentStage === "validate_edits")) ||
        (def.id === "commit" && (currentStage === "commit" || currentStage === "update"))) &&
      runStatus === "running";

    if (isCurrentlyActive) {
      return "running";
    }

    // If subsequent steps completed or are running, infer this prior step is completed
    const anySubsequentActive = WORKFLOW_STAGES.slice(index + 1).some((laterDef) => {
      const laterEvents = getStageEvents(laterDef);
      return (
        laterEvents.some(
          (e) => e.status === "completed" || e.status === "started" || e.status === "success"
        ) ||
        (laterDef.id === "review" && runStatus === "waiting_for_review") ||
        currentStage === laterDef.stage
      );
    });

    if (anySubsequentActive) {
      return "completed";
    }

    return "pending";
  };

  const getStageDuration = (def: StageDefinition) => {
    const stageEvents = getStageEvents(def);
    const totalMs = stageEvents.reduce((acc, ev) => acc + (ev.duration_ms || 0), 0);
    if (totalMs <= 0) return null;
    return totalMs >= 1000 ? `${(totalMs / 1000).toFixed(1)}s` : `${totalMs}ms`;
  };

  const getStatusLabel = (status: string, durationStr: string | null) => {
    switch (status) {
      case "completed":
        return durationStr ? `Done (${durationStr})` : "Completed";
      case "running":
        return "Processing...";
      case "review_required":
        return "Review required";
      case "failed":
        return durationStr ? `Failed (${durationStr})` : "Failed";
      case "pending":
      default:
        return "Pending";
    }
  };

  const renderStatusIcon = (status: string) => {
    switch (status) {
      case "completed":
        return <CheckCircle2 className="step-icon-svg text-emerald-500" size={16} />;
      case "running":
        return <Loader2 className="step-icon-svg text-blue-500 animate-spin" size={16} />;
      case "review_required":
        return <AlertTriangle className="step-icon-svg text-amber-500 animate-bounce-subtle" size={16} />;
      case "failed":
        return <XCircle className="step-icon-svg text-rose-500" size={16} />;
      case "pending":
      default:
        return <Circle className="step-icon-svg text-slate-300" size={14} />;
    }
  };

  return (
    <div className="workflow-stepper-card">
      <div className="workflow-stepper-header">
        <div>
          <h3 className="workflow-stepper-title">Workflow Execution Pipeline</h3>
          <span className="workflow-stepper-subtitle">
            9-stage LangGraph workflow state & real-time telemetry (click stage to view diagnostics)
          </span>
        </div>
        {runStatus === "waiting_for_review" && (
          <span className="badge badge-warning" style={{ fontSize: "12px", padding: "4px 8px" }}>
            Action Required: Review Findings
          </span>
        )}
      </div>

      <div className="workflow-stepper-track">
        {WORKFLOW_STAGES.map((step, idx) => {
          const status = getStageStatus(step, idx);
          const durationStr = getStageDuration(step);
          const attempts = getStageAttempts(step);
          const isSelected = Boolean(selectedNode && step.nodeNames.includes(selectedNode));
          const nextStepStatus =
            idx < WORKFLOW_STAGES.length - 1
              ? getStageStatus(WORKFLOW_STAGES[idx + 1], idx + 1)
              : null;

          // Connector line styling
          let connectorClass = "connector-pending";
          if (
            status === "completed" &&
            (nextStepStatus === "completed" ||
              nextStepStatus === "running" ||
              nextStepStatus === "review_required")
          ) {
            connectorClass = "connector-completed";
          } else if (
            status === "running" ||
            (status === "completed" && nextStepStatus === "pending")
          ) {
            connectorClass = "connector-active";
          }

          return (
            <div
              key={step.id}
              className={`stepper-node-wrapper state-${status}`}
              style={{
                cursor: onSelectNode ? "pointer" : "default",
                padding: "4px",
                borderRadius: "8px",
                transition: "all 0.15s ease",
                backgroundColor: isSelected ? "#eff6ff" : "transparent",
                outline: isSelected ? "2px solid #3b82f6" : "none",
              }}
              onClick={() => onSelectNode && onSelectNode(step.nodeNames[0])}
              title={`Click to view node diagnostics for ${step.label}`}
            >
              <div className="stepper-node">
                <div
                  className={`stepper-circle circle-${status}`}
                  title={`${step.label}: ${getStatusLabel(status, durationStr)} - ${step.description}`}
                >
                  {renderStatusIcon(status)}
                </div>

                <div className="stepper-label-container">
                  <div style={{ display: "flex", alignItems: "center", gap: "4px", justifyContent: "center" }}>
                    <span className="stepper-stage-name">{step.label}</span>
                    {attempts > 1 && (
                      <span
                        style={{
                          fontSize: "10px",
                          fontWeight: 600,
                          padding: "1px 4px",
                          borderRadius: "4px",
                          backgroundColor: status === "failed" ? "#fee2e2" : "#e0e7ff",
                          color: status === "failed" ? "#991b1b" : "#3730a3",
                        }}
                        title={`${attempts} execution attempts`}
                      >
                        att.{attempts}
                      </span>
                    )}
                  </div>
                  <span className={`stepper-status-text status-text-${status}`}>
                    {getStatusLabel(status, durationStr)}
                  </span>
                </div>
              </div>

              {idx < WORKFLOW_STAGES.length - 1 && (
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
