import { useState } from "react";
import type {
  FindingResponse,
  ReviewResponse,
} from "../../api/types";

interface ReviewQueueProps {
  review: ReviewResponse | null;
  onDecision: (decision: "approved" | "rejected") => Promise<void>;
}

export function ReviewQueue({
  review,
  onDecision,
}: ReviewQueueProps) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!review) {
    return null;
  }

  const handleDecision = async (
    decision: "approved" | "rejected",
  ) => {
    try {
      setSubmitting(true);
      setError(null);

      await onDecision(decision);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to submit decision",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="card review-queue-section">
      <h2>Human Review</h2>

      {review.findings.length === 0 ? (
        <p>No findings require review.</p>
      ) : (
        <div className="review-findings-list">
          {review.findings.map(
            (finding: FindingResponse) => (
              <article key={finding.id} className="review-finding-card">
                <h3>{finding.title}</h3>

                <p>{finding.description}</p>

                <p>
                  <strong>Severity:</strong>{" "}
                  {finding.severity}
                </p>

                {finding.citation && (
                  <p>
                    <strong>Citation:</strong>{" "}
                    {JSON.stringify(finding.citation)}
                  </p>
                )}
              </article>
            ),
          )}
        </div>
      )}

      {error && (
        <p role="alert" className="error-message">
          {error}
        </p>
      )}

      <div className="review-actions">
        <button
          type="button"
          disabled={submitting}
          onClick={() => handleDecision("approved")}
        >
          {submitting ? "Submitting..." : "Approve"}
        </button>

        <button
          type="button"
          disabled={submitting}
          onClick={() => handleDecision("rejected")}
        >
          {submitting ? "Submitting..." : "Reject"}
        </button>
      </div>
    </section>
  );
}

export default ReviewQueue;
