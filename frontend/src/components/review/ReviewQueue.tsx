import { useState } from "react";
import { submitFindingDecision } from "../../api/runs";
import type { FindingResponse } from "../../api/types";

interface ReviewQueueProps {
  runId: string;
  findings: FindingResponse[];
  onRefresh: () => Promise<void>;
}

export function ReviewQueue({
  runId,
  findings,
  onRefresh,
}: ReviewQueueProps) {
  const [submittingIds, setSubmittingIds] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);

  const handleDecision = async (findingId: string, decision: "approve" | "reject") => {
    try {
      setSubmittingIds((prev) => ({ ...prev, [findingId]: true }));
      setError(null);
      await submitFindingDecision(runId, findingId, decision);
      await onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit decision");
    } finally {
      setSubmittingIds((prev) => ({ ...prev, [findingId]: false }));
    }
  };

  if (findings.length === 0) {
    return null;
  }

  return (
    <section className="card review-queue-section" style={{ marginTop: "24px" }}>
      <h2>Human Review - Item-by-Item Gate</h2>
      <p style={{ fontSize: "14px", color: "#64748b", marginBottom: "16px" }}>
        Every finding must be individually approved or rejected before the workflow can proceed to Commit.
      </p>

      <div className="review-findings-list" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
        {findings.map((finding: FindingResponse) => {
          const isSubmitting = !!submittingIds[finding.id];

          return (
            <article
              key={finding.id}
              className="review-finding-card"
              style={{
                border: "1px solid #cbd5e1",
                borderRadius: "8px",
                padding: "16px",
                backgroundColor: finding.review_decision === "approved" ? "#f0fdf4" : finding.review_decision === "rejected" ? "#fef2f2" : "#ffffff",
                transition: "background-color 0.2s ease"
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "8px" }}>
                <h3 style={{ margin: 0 }}>{finding.title}</h3>
                <span
                  style={{
                    padding: "4px 8px",
                    borderRadius: "4px",
                    fontSize: "12px",
                    fontWeight: "bold",
                    textTransform: "uppercase",
                    backgroundColor: finding.review_decision === "approved" ? "#bbf7d0" : finding.review_decision === "rejected" ? "#fecaca" : "#e2e8f0",
                    color: finding.review_decision === "approved" ? "#15803d" : finding.review_decision === "rejected" ? "#b91c1c" : "#475569"
                  }}
                >
                  {finding.review_decision}
                </span>
              </div>

              <p style={{ margin: "8px 0" }}>{finding.description}</p>

              <div style={{ display: "flex", gap: "16px", fontSize: "13px", color: "#64748b", margin: "8px 0" }}>
                <span><strong>Severity:</strong> {finding.severity.toUpperCase()}</span>
                {finding.citation && (
                  <span><strong>Citation:</strong> {JSON.stringify(finding.citation)}</span>
                )}
              </div>

              <div style={{ display: "flex", gap: "8px", marginTop: "12px" }}>
                <button
                  type="button"
                  disabled={isSubmitting || finding.review_decision === "approved"}
                  onClick={() => handleDecision(finding.id, "approve")}
                  style={{
                    padding: "6px 12px",
                    backgroundColor: finding.review_decision === "approved" ? "#bbf7d0" : "#22c55e",
                    color: finding.review_decision === "approved" ? "#15803d" : "#ffffff",
                    border: "none",
                    borderRadius: "4px",
                    cursor: (isSubmitting || finding.review_decision === "approved") ? "not-allowed" : "pointer"
                  }}
                >
                  {isSubmitting ? "Processing..." : finding.review_decision === "approved" ? "Approved" : "Approve"}
                </button>

                <button
                  type="button"
                  disabled={isSubmitting || finding.review_decision === "rejected"}
                  onClick={() => handleDecision(finding.id, "reject")}
                  style={{
                    padding: "6px 12px",
                    backgroundColor: finding.review_decision === "rejected" ? "#fecaca" : "#ef4444",
                    color: finding.review_decision === "rejected" ? "#b91c1c" : "#ffffff",
                    border: "none",
                    borderRadius: "4px",
                    cursor: (isSubmitting || finding.review_decision === "rejected") ? "not-allowed" : "pointer"
                  }}
                >
                  {isSubmitting ? "Processing..." : finding.review_decision === "rejected" ? "Rejected" : "Reject"}
                </button>
              </div>
            </article>
          );
        })}
      </div>

      {error && (
        <p role="alert" className="error-message" style={{ color: "#ef4444", marginTop: "12px" }}>
          {error}
        </p>
      )}
    </section>
  );
}

export default ReviewQueue;
