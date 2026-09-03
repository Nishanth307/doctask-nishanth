import React, { useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  Terminal,
  CheckCircle2,
  Clock,
  Loader2,
  XCircle,
  AlertTriangle,
  Cpu,
  Calendar,
  Layers,
  Hash,
} from "lucide-react";
import type { WorkflowEventResponse, WorkflowResultResponse } from "../../api/types";

interface ExecutionDetailsProps {
  runId: string;
  workflowId?: string;
  parentId?: string | null;
  currentStage: string;
  runStatus: string;
  createdAt: string;
  updatedAt: string;
  completedAt?: string | null;
  errorMessage?: string | null;
  events: WorkflowEventResponse[];
  workflowResult?: WorkflowResultResponse | null;
}

export const ExecutionDetails: React.FC<ExecutionDetailsProps> = ({
  runId,
  workflowId,
  parentId,
  currentStage,
  runStatus,
  createdAt,
  updatedAt,
  completedAt,
  errorMessage,
  events = [],
  workflowResult,
}) => {
  const [isOpen, setIsOpen] = useState(false);

  const renderEventStatusIcon = (status: string) => {
    switch (status.toLowerCase()) {
      case "completed":
      case "success":
        return <CheckCircle2 size={14} className="text-emerald-500" />;
      case "running":
      case "started":
        return <Loader2 size={14} className="text-blue-500 animate-spin" />;
      case "failed":
      case "error":
        return <XCircle size={14} className="text-rose-500" />;
      case "waiting":
      case "waiting_for_review":
        return <AlertTriangle size={14} className="text-amber-500" />;
      default:
        return <Clock size={14} className="text-slate-400" />;
    }
  };

  return (
    <div className="execution-details-accordion">
      <button
        type="button"
        className="execution-details-toggle"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
      >
        <div className="toggle-left">
          <Terminal size={16} className="text-slate-500" />
          <span className="toggle-title">Execution details</span>
          <span className="toggle-badge">
            {events.length} event{events.length === 1 ? "" : "s"}
          </span>
        </div>

        <div className="toggle-right">
          <span className="toggle-state-hint">{isOpen ? "Hide" : "Show"} details</span>
          {isOpen ? (
            <ChevronDown size={18} className="text-slate-500 transition-transform" />
          ) : (
            <ChevronRight size={18} className="text-slate-500 transition-transform" />
          )}
        </div>
      </button>

      {isOpen && (
        <div className="execution-details-content">
          {/* Diagnostic Metadata Grid */}
          <div className="execution-meta-grid">
            <div className="meta-cell">
              <span className="meta-label">
                <Hash size={13} /> Run ID
              </span>
              <span className="meta-value font-mono">{runId}</span>
            </div>

            {workflowId && (
              <div className="meta-cell">
                <span className="meta-label">
                  <Cpu size={13} /> Workflow Thread ID
                </span>
                <span className="meta-value font-mono">{workflowId}</span>
              </div>
            )}

            {parentId && (
              <div className="meta-cell">
                <span className="meta-label">
                  <Layers size={13} /> Parent Run ID
                </span>
                <span className="meta-value font-mono">{parentId}</span>
              </div>
            )}

            <div className="meta-cell">
              <span className="meta-label">
                <Layers size={13} /> Current Stage
              </span>
              <span className="meta-value capitalize">{currentStage.replaceAll("_", " ")}</span>
            </div>

            <div className="meta-cell">
              <span className="meta-label">
                <Clock size={13} /> Status
              </span>
              <span className="meta-value capitalize">{runStatus.replaceAll("_", " ")}</span>
            </div>

            <div className="meta-cell">
              <span className="meta-label">
                <Calendar size={13} /> Created
              </span>
              <span className="meta-value">{new Date(createdAt).toLocaleString()}</span>
            </div>

            <div className="meta-cell">
              <span className="meta-label">
                <Calendar size={13} /> Last Updated
              </span>
              <span className="meta-value">{new Date(updatedAt).toLocaleString()}</span>
            </div>

            {completedAt && (
              <div className="meta-cell">
                <span className="meta-label">
                  <Calendar size={13} /> Completed
                </span>
                <span className="meta-value">{new Date(completedAt).toLocaleString()}</span>
              </div>
            )}
          </div>

          {errorMessage && (
            <div className="execution-error-box">
              <XCircle size={16} className="text-rose-500" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Workflow Events Log */}
          <div className="execution-events-section">
            <h4 className="events-heading">Workflow Execution Log</h4>
            {events.length === 0 ? (
              <p className="events-empty">No execution events recorded for this run.</p>
            ) : (
              <div className="events-timeline-list">
                {events.map((event) => {
                  const durationText =
                    event.duration_ms !== null && event.duration_ms !== undefined
                      ? event.duration_ms >= 1000
                        ? `${(event.duration_ms / 1000).toFixed(1)}s`
                        : `${event.duration_ms}ms`
                      : null;

                  return (
                    <div key={event.id} className="event-log-entry">
                      <div className="event-status-indicator">
                        {renderEventStatusIcon(event.status)}
                      </div>

                      <div className="event-main-content">
                        <div className="event-primary-line">
                          <span className="event-stage-tag">
                            {event.stage.replaceAll("_", " ")}
                          </span>
                          <span className="event-status-tag">
                            {event.status}
                          </span>
                          {durationText && (
                            <span className="event-duration-tag">
                              {durationText}
                            </span>
                          )}
                          <span className="event-timestamp">
                            {new Date(event.created_at).toLocaleTimeString()}
                          </span>
                        </div>

                        {event.message && (
                          <div className="event-message-text">{event.message}</div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Workflow Result Details */}
          {workflowResult && (
            <div className="execution-result-section">
              <h4 className="events-heading">Engine State Summary</h4>
              <div className="state-summary-pills">
                <span className="state-summary-pill">
                  Status: <strong>{workflowResult.status}</strong>
                </span>
                {workflowResult.human_decision && (
                  <span className="state-summary-pill">
                    Human Gate: <strong>{workflowResult.human_decision}</strong>
                  </span>
                )}
                {workflowResult.extracted_facts && (
                  <span className="state-summary-pill">
                    Facts Extracted: <strong>{workflowResult.extracted_facts.length}</strong>
                  </span>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
