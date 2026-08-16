import { useEffect, useState, useCallback } from "react";
import { Link, useParams } from "react-router-dom";

import { getRunDetails, startRun } from "../api/runs";
import type { RunDetailsResponse } from "../api/types";
import { RunTimeline } from "../components/RunTimeline";
import { ReviewQueue } from "../components/review/ReviewQueue";
import { FindingsList } from "../components/findings/FindingsList";
import { ReportView } from "../components/findings/ReportView";
import { WorkflowResultView } from "../components/workflow/WorkflowResultView";
import { WorkflowTimeline } from "../components/workflow/WorkflowTimeline";
import { useRunPolling } from "../hooks/useRunPolling";

function RunDetailsPage() {
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
      <main>
        <p>Loading run details...</p>
      </main>
    );
  }

  if (error && !run) {
    return (
      <main>
        <div role="alert" className="error-alert">
          <h2>Unable to load run</h2>
          <p>{error}</p>
          <button type="button" onClick={handleRetry}>
            Retry
          </button>
        </div>
        <Link to="/runs">← Back to Runs</Link>
      </main>
    );
  }

  if (!run || !details) {
    return (
      <main>
        <p>Run not found.</p>
        <Link to="/runs">← Back to Runs</Link>
      </main>
    );
  }

  return (
    <main>
      <Link to="/runs">← Back to Runs</Link>

      <h1>{run.name}</h1>

      <section>
        <p>
          <strong>Status:</strong>{" "}
          <span className={`status-badge status-${run.status}`} style={{ display: "inline-flex", verticalAlign: "middle" }}>
            {run.status === "running" && <span className="running-dot">●</span>}
            {run.status === "waiting_for_review" && "⚠ "}
            {run.status === "completed" && "✓ "}
            {run.status === "failed" && "✕ "}
            {run.status.replaceAll("_", " ")}
          </span>
        </p>

        <p>
          <strong>Stage:</strong> {run.stage}
        </p>

        <p>
          <strong>Created:</strong>{" "}
          {new Date(run.created_at).toLocaleString()}
        </p>

        <p>
          <strong>Updated:</strong>{" "}
          {new Date(run.updated_at).toLocaleString()}
        </p>

        {run.completed_at && (
          <p>
            <strong>Completed:</strong>{" "}
            {new Date(run.completed_at).toLocaleString()}
          </p>
        )}

        {run.error_message && (
          <p>
            <strong>Error:</strong> {run.error_message}
          </p>
        )}

        {run.documents && run.documents.length > 0 && (
          <div style={{ marginTop: "16px", display: "flex", flexDirection: "column", gap: "12px" }}>
            <div>
              <strong style={{ display: "block", marginBottom: "4px" }}>Source Documents</strong>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                {run.documents.filter(d => !d.is_rules).map((doc) => (
                  <span key={doc.id} className="badge" style={{ backgroundColor: "#f1f5f9", padding: "4px 8px", borderRadius: "4px", fontSize: "13px" }}>
                    📄 {doc.filename}
                  </span>
                ))}
                {run.documents.filter(d => !d.is_rules).length === 0 && (
                  <span style={{ color: "#64748b", fontSize: "13px" }}>No source documents</span>
                )}
              </div>
            </div>
            <div>
              <strong style={{ display: "block", marginBottom: "4px" }}>Review Rules</strong>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                {run.documents.filter(d => d.is_rules).map((doc) => (
                  <span key={doc.id} className="badge" style={{ backgroundColor: "#f1f5f9", padding: "4px 8px", borderRadius: "4px", fontSize: "13px" }}>
                    📋 {doc.filename} (Playbook)
                  </span>
                ))}
                {run.documents.filter(d => d.is_rules).length === 0 && (
                  <span style={{ color: "#64748b", fontSize: "13px" }}>No review rules document</span>
                )}
              </div>
            </div>
          </div>
        )}
      </section>

      {run.status === "pending" && (
        <button
          type="button"
          onClick={handleStart}
          disabled={starting}
        >
          {starting ? "Starting..." : "Start Workflow"}
        </button>
      )}

      {run.status === "running" && (
        <p className="processing-indicator">Workflow is processing...</p>
      )}

      {run.status === "failed" && (
        <section className="card failed-card" role="alert">
          <h2>Workflow Failed</h2>
          <p>
            {run.error_message ?? "The workflow failed unexpectedly."}
          </p>
        </section>
      )}

      {run.status === "waiting_for_review" && (
        <ReviewQueue
          runId={run.id}
          findings={details.findings}
          onRefresh={fetchDetails}
        />
      )}

      {actionError && <p role="alert" className="error-message">{actionError}</p>}
      {error && <p>{error}</p>}

      <RunTimeline
        events={details.workflow_events}
        currentStage={run.stage}
        runStatus={run.status}
      />

      <WorkflowTimeline events={details.workflow_events} />

      <FindingsList findings={details.findings} />

      <ReportView report={details.report} />

      <WorkflowResultView
        result={details.workflow_result}
        runStatus={run.status}
      />
    </main>
  );
}

export default RunDetailsPage;