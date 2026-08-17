import { useState } from "react";
import { submitFindingDecision, submitHumanDecision } from "../../api/runs";
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
  const [isFinalizing, setIsFinalizing] = useState(false);
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

  const handleFinalDecision = async (decision: "approve" | "reject") => {
    try {
      setIsFinalizing(true);
      setError(null);
      await submitHumanDecision(runId, { decision });
      await onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to finalize decision");
    } finally {
      setIsFinalizing(false);
    }
  };

  const pendingFindingsCount = findings.filter((f) => f.review_decision === "pending").length;
  const hasPendingFindings = pendingFindingsCount > 0;

  return (
    <section className="card review-queue-section" style={{ marginTop: "24px", border: "2px solid #3b82f6", padding: "20px" }}>
      <h2 style={{ color: "#1e3a8a", margin: "0 0 8px 0" }}>⚠ Human Review Required</h2>
      <p style={{ fontSize: "14px", color: "#64748b", marginBottom: "16px" }}>
        Every finding must be individually approved or rejected. Once all findings are resolved, submit the final decision to resume the workflow.
      </p>

      {findings.length === 0 ? (
        <div style={{ padding: "12px", backgroundColor: "#f0fdf4", borderRadius: "6px", color: "#15803d", marginBottom: "16px" }}>
          ✓ No findings were produced. You can proceed directly to commit the deliverable.
        </div>
      ) : (
        <>
          {hasPendingFindings ? (
            <div style={{ padding: "12px", backgroundColor: "#fffbeb", border: "1px solid #fef3c7", borderRadius: "6px", color: "#b45309", marginBottom: "16px" }}>
              ⚠ {pendingFindingsCount} {pendingFindingsCount === 1 ? "finding requires" : "findings require"} human review.
            </div>
          ) : (
            <div style={{ padding: "12px", backgroundColor: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: "6px", color: "#15803d", marginBottom: "16px" }}>
              ✓ All {findings.length} findings have been reviewed. You can now submit the final decision below to resume the workflow.
            </div>
          )}

          <div className="review-findings-list" style={{ display: "flex", flexDirection: "column", gap: "16px", marginBottom: "20px" }}>

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
                  <span>
                    <strong>Severity:</strong>{" "}
                    <span style={{ fontWeight: "bold", color: finding.severity === "error" || finding.severity === "critical" ? "#dc2626" : "#475569" }}>
                      {finding.severity.toUpperCase()}
                    </span>
                  </span>
                  <span>
                    <strong>Status:</strong>{" "}
                    <span style={{ fontWeight: "bold", textTransform: "uppercase" }}>
                      {finding.review_decision}
                    </span>
                  </span>
                </div>

                {finding.citation?.sources && Array.isArray(finding.citation.sources) && finding.citation.sources.length > 0 && (
                  <div style={{ marginTop: "12px", marginBottom: "12px", display: "flex", flexDirection: "column", gap: "8px" }}>
                    <strong style={{ fontSize: "13px", color: "#334155" }}>Source Citations & Conflicting Values:</strong>
                    {finding.citation.sources.map((src, idx) => (
                      <div
                        key={idx}
                        style={{
                          backgroundColor: "#f8fafc",
                          border: "1px solid #e2e8f0",
                          borderRadius: "6px",
                          padding: "8px 12px",
                          fontSize: "13px",
                        }}
                      >
                        <div style={{ fontWeight: 600, color: "#1e293b", marginBottom: "3px" }}>
                          📄 Source: {src.document || "Document"}
                        </div>
                        {src.value && (
                          <div style={{ color: "#0f172a", marginBottom: "2px" }}>
                            <strong>Value:</strong> &ldquo;{src.value}&rdquo;
                          </div>
                        )}
                        {src.source_text && (
                          <div style={{ color: "#64748b", fontStyle: "italic", fontSize: "12px" }}>
                            &ldquo;{src.source_text}&rdquo;
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}


                <div style={{ display: "flex", gap: "8px", marginTop: "12px" }}>
                  <button
                    type="button"
                    disabled={isSubmitting || finding.review_decision === "approved" || isFinalizing}
                    onClick={() => handleDecision(finding.id, "approve")}
                    style={{
                      padding: "6px 12px",
                      backgroundColor: finding.review_decision === "approved" ? "#bbf7d0" : "#22c55e",
                      color: finding.review_decision === "approved" ? "#15803d" : "#ffffff",
                      border: "none",
                      borderRadius: "4px",
                      cursor: (isSubmitting || finding.review_decision === "approved" || isFinalizing) ? "not-allowed" : "pointer"
                    }}
                  >
                    {isSubmitting ? "Processing..." : finding.review_decision === "approved" ? "Approved" : "Approve"}
                  </button>

                  <button
                    type="button"
                    disabled={isSubmitting || finding.review_decision === "rejected" || isFinalizing}
                    onClick={() => handleDecision(finding.id, "reject")}
                    style={{
                      padding: "6px 12px",
                      backgroundColor: finding.review_decision === "rejected" ? "#fecaca" : "#ef4444",
                      color: finding.review_decision === "rejected" ? "#b91c1c" : "#ffffff",
                      border: "none",
                      borderRadius: "4px",
                      cursor: (isSubmitting || finding.review_decision === "rejected" || isFinalizing) ? "not-allowed" : "pointer"
                    }}
                  >
                    {isSubmitting ? "Processing..." : finding.review_decision === "rejected" ? "Rejected" : "Reject"}
                  </button>
                </div>
              </article>
            );
          })}
          </div>
        </>
      )}



      <div style={{ borderTop: "1px solid #e2e8f0", paddingTop: "16px", marginTop: "16px" }}>
        <h3>Submit Final Review Decision</h3>
        {hasPendingFindings && (
          <p style={{ color: "#ef4444", fontSize: "13px" }}>
            ⚠ You must resolve (Approve or Reject) all findings before submitting the final decision.
          </p>
        )}
        <div style={{ display: "flex", gap: "12px" }}>
          <button
            type="button"
            disabled={hasPendingFindings || isFinalizing}
            onClick={() => handleFinalDecision("approve")}
            style={{
              padding: "8px 16px",
              backgroundColor: (hasPendingFindings || isFinalizing) ? "#cbd5e1" : "#2563eb",
              color: "#ffffff",
              border: "none",
              borderRadius: "4px",
              fontWeight: "bold",
              cursor: (hasPendingFindings || isFinalizing) ? "not-allowed" : "pointer"
            }}
          >
            {isFinalizing ? "Submitting..." : "Approve and Commit Deliverable"}
          </button>

          <button
            type="button"
            disabled={hasPendingFindings || isFinalizing}
            onClick={() => handleFinalDecision("reject")}
            style={{
              padding: "8px 16px",
              backgroundColor: (hasPendingFindings || isFinalizing) ? "#cbd5e1" : "#dc2626",
              color: "#ffffff",
              border: "none",
              borderRadius: "4px",
              fontWeight: "bold",
              cursor: (hasPendingFindings || isFinalizing) ? "not-allowed" : "pointer"
            }}
          >
            {isFinalizing ? "Submitting..." : "Reject and Cancel Workflow"}
          </button>
        </div>
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
