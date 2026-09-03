import { useEffect, useState, useCallback } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft,
  Play,
  FileText,
  BookOpen,
  Calendar,
  AlertCircle,
  RotateCcw,
} from "lucide-react";

import { getRunDetails, startRun } from "../api/runs";
import type { RunDetailsResponse } from "../api/types";
import { StatusBadge } from "../components/common/StatusBadge";
import { WorkflowStepper } from "../components/workflow/WorkflowStepper";
import { ReviewQueue } from "../components/review/ReviewQueue";
import { FindingsList } from "../components/findings/FindingsList";
import { ReportView } from "../components/findings/ReportView";
import { ExecutionDetails } from "../components/workflow/ExecutionDetails";
import { useRunPolling } from "../hooks/useRunPolling";

export function RunDetailsPage() {
  const { runId } = useParams<{ runId: string }>();

  const [details, setDetails] = useState<RunDetailsResponse | null>(null);
  const [loading, setLoading] = useState(!!runId);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(runId ? null : "Run ID is missing.");
  const [actionError, setActionError] = useState<string | null>(null);

  const run = details?.run;

  const handleUpdateDetails = useCallback((updatedDetails: RunDetailsResponse) => {
    setDetails(updatedDetails);
  }, []);

  useRunPolling({
    runId: runId ?? "",
    details,
    onUpdate: handleUpdateDetails,
  });

  useEffect(() => {
    let active = true;

    async function load() {
      if (!runId) {
        return;
      }

      try {
        const res = await getRunDetails(runId);
        if (active) {
          setDetails(res);
        }
      } catch (err) {
        if (active) {
          console.error(err);
          setError("Failed to load run details.");
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void load();

    return () => {
      active = false;
    };
  }, [runId]);

  const fetchDetails = useCallback(async () => {
    if (!runId) {
      return;
    }
    const res = await getRunDetails(runId);
    setDetails(res);
  }, [runId]);

  const handleRetry = () => {
    setLoading(true);
    setError(null);
    fetchDetails()
      .catch((err) => {
        console.error(err);
        setError("Failed to load run details.");
      })
      .finally(() => {
        setLoading(false);
      });
  };

  async function handleStart() {
    if (!runId) {
      return;
    }

    try {
      setStarting(true);
      setActionError(null);

      await startRun(runId);
      await fetchDetails();
    } catch (err) {
      console.error(err);
      setActionError(
        err instanceof Error
          ? err.message
          : "Failed to start workflow."
      );
    } finally {
      setStarting(false);
    }
  }

  if (loading) {
    return (
      <main className="details-container">
        <div className="details-loading-state">
          <div className="spinner-saas" />
          <p>Loading contract review session...</p>
        </div>
      </main>
    );
  }

  if (error && !run) {
    return (
      <main className="details-container">
        <div role="alert" className="error-alert-card">
          <div className="flex items-center gap-3">
            <AlertCircle className="text-rose-600" size={24} />
            <div>
              <h2 className="text-lg font-semibold text-rose-900">Unable to load run</h2>
              <p className="text-sm text-rose-700">{error}</p>
            </div>
          </div>
          <div className="mt-4 flex items-center gap-3">
            <button type="button" onClick={handleRetry} className="btn-secondary flex items-center gap-2">
              <RotateCcw size={14} /> Retry
            </button>
            <Link to="/runs" className="back-link flex items-center gap-2">
              <ArrowLeft size={16} /> Back to Runs
            </Link>
          </div>
        </div>
      </main>
    );
  }

  if (!run || !details) {
    return (
      <main className="details-container">
        <div className="card empty-card">
          <p>Run not found.</p>
          <Link to="/runs" className="back-link mt-4 flex items-center gap-2">
            <ArrowLeft size={16} /> Back to Runs
          </Link>
        </div>
      </main>
    );
  }

  const sourceDocs = run.documents?.filter((d) => !d.is_rules) || [];
  const ruleDocs = run.documents?.filter((d) => d.is_rules) || [];

  return (
    <main className="details-container">
      {/* Navigation Breadcrumb */}
      <div className="details-nav-row">
        <Link to="/runs" className="back-link flex items-center gap-2">
          <ArrowLeft size={16} /> Back to Runs
        </Link>
      </div>

      {/* Contract Review SaaS Header */}
      <header className="contract-review-header">
        <div className="header-primary-content">
          <div className="header-meta-sup">
            <span className="contract-category-label">Contract Review</span>
            {run.parent_id && (
              <span className="incremental-badge">Incremental Update</span>
            )}
          </div>

          <div className="header-title-row">
            <h1 className="contract-title">{run.name}</h1>
            <StatusBadge status={run.status} size="lg" />
          </div>

          <div className="header-metadata-row">
            <div className="meta-item">
              <Calendar size={14} className="text-slate-400" />
              <span>Created {new Date(run.created_at).toLocaleDateString()} at {new Date(run.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
            </div>

            {sourceDocs.length > 0 && (
              <div className="doc-pill-list">
                {sourceDocs.map((doc) => (
                  <span key={doc.id} className="doc-chip doc-chip-source" title={`Source Document: ${doc.filename}`}>
                    <FileText size={13} />
                    <span>{doc.filename}</span>
                  </span>
                ))}
              </div>
            )}

            {ruleDocs.length > 0 && (
              <div className="doc-pill-list">
                {ruleDocs.map((doc) => (
                  <span key={doc.id} className="doc-chip doc-chip-rule" title={`Playbook Rules: ${doc.filename}`}>
                    <BookOpen size={13} />
                    <span>{doc.filename}</span>
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Primary Header Action */}
        {run.status === "pending" && (
          <div className="header-action-panel">
            <button
              type="button"
              onClick={handleStart}
              disabled={starting}
              className="btn-start-workflow flex items-center gap-2"
            >
              <Play size={16} fill="currentColor" />
              {starting ? "Starting Workflow..." : "Start Workflow"}
            </button>
          </div>
        )}
      </header>

      {actionError && (
        <div role="alert" className="error-alert-banner">
          <AlertCircle size={16} />
          <span>{actionError}</span>
        </div>
      )}

      {/* Visual Stepper Timeline */}
      <WorkflowStepper
        events={details.workflow_events}
        currentStage={run.stage}
        runStatus={run.status}
      />

      {/* Human Review Queue (Two-Column Interface) */}
      {run.status === "waiting_for_review" && (
        <ReviewQueue
          runId={run.id}
          findings={details.findings}
          onRefresh={fetchDetails}
        />
      )}

      {/* Final Deliverable Report */}
      <ReportView report={details.report} />

      {/* Reconciled Findings List (when not in active review gate) */}
      {run.status !== "waiting_for_review" && details.findings.length > 0 && (
        <FindingsList findings={details.findings} />
      )}

      {/* Secondary Collapsible Execution Details Accordion */}
      <ExecutionDetails
        runId={run.id}
        workflowId={details.workflow_result?.id}
        parentId={run.parent_id}
        currentStage={run.stage}
        runStatus={run.status}
        createdAt={run.created_at}
        updatedAt={run.updated_at}
        completedAt={run.completed_at}
        errorMessage={run.error_message}
        events={details.workflow_events}
        workflowResult={details.workflow_result}
      />
    </main>
  );
}

export default RunDetailsPage;