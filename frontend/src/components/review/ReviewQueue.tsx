import { useState } from "react";
import {
  AlertTriangle,
  Check,
  X,
  CheckCircle2,
  XCircle,
  FileText,
  FileSearch,
  ArrowRight,
  ShieldAlert,
  HelpCircle,
} from "lucide-react";
import { submitFindingDecision, submitHumanDecision } from "../../api/runs";
import type { FindingResponse, FindingSeverity } from "../../api/types";

interface ReviewQueueProps {
  runId: string;
  findings: FindingResponse[];
  onRefresh: () => Promise<void>;
}

export function ReviewQueue({ runId, findings, onRefresh }: ReviewQueueProps) {
  const [selectedFindingId, setSelectedFindingId] = useState<string>(
    findings.length > 0 ? findings[0].id : ""
  );
  const [submittingIds, setSubmittingIds] = useState<Record<string, boolean>>({});
  const [isFinalizing, setIsFinalizing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Active selected finding
  const activeFinding =
    findings.find((f) => f.id === selectedFindingId) || findings[0] || null;

  // Counts
  const pendingFindingsCount = findings.filter((f) => f.review_decision === "pending").length;
  const approvedCount = findings.filter((f) => f.review_decision === "approved").length;
  const rejectedCount = findings.filter((f) => f.review_decision === "rejected").length;
  const hasPendingFindings = pendingFindingsCount > 0;

  // Severity counts
  const severityCounts = findings.reduce(
    (acc, finding) => {
      const sev = finding.severity?.toLowerCase() || "info";
      acc[sev] = (acc[sev] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

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

  const renderSeverityBadge = (severity: FindingSeverity | string) => {
    const s = severity?.toLowerCase() || "info";
    let badgeClass = "badge-severity-info";
    let label = "Info";

    if (s === "critical" || s === "high" || s === "error") {
      badgeClass = "badge-severity-critical";
      label = s === "critical" ? "Critical" : "High";
    } else if (s === "warning" || s === "medium") {
      badgeClass = "badge-severity-warning";
      label = "Medium";
    }

    return (
      <span className={`finding-severity-pill ${badgeClass}`}>
        {label}
      </span>
    );
  };

  const renderDecisionBadge = (decision: string) => {
    if (decision === "approved") {
      return (
        <span className="finding-decision-pill pill-approved">
          <Check size={12} /> Approved
        </span>
      );
    }
    if (decision === "rejected") {
      return (
        <span className="finding-decision-pill pill-rejected">
          <X size={12} /> Rejected
        </span>
      );
    }
    return (
      <span className="finding-decision-pill pill-pending">
        Pending
      </span>
    );
  };

  return (
    <section className="review-cockpit-card">
      {/* Review Header Banner */}
      <div className="review-cockpit-header">
        <div className="review-title-area">
          <div className="review-icon-badge">
            <AlertTriangle size={20} className="text-amber-600" />
          </div>
          <div>
            <h2 className="review-header-title">Human Review Required</h2>
            <p className="review-header-subtitle">
              {hasPendingFindings
                ? `${pendingFindingsCount} of ${findings.length} findings require your attention before the workflow can proceed.`
                : `All ${findings.length} findings have been reviewed. You can now finalize the review.`}
            </p>
          </div>
        </div>

        {/* Severity & Progress Badges */}
        <div className="review-header-metrics">
          <div className="severity-pills-row">
            {(severityCounts["critical"] || severityCounts["error"] || severityCounts["high"]) ? (
              <span className="metric-pill pill-critical">
                {(severityCounts["critical"] || 0) + (severityCounts["error"] || 0) + (severityCounts["high"] || 0)} High
              </span>
            ) : null}
            {(severityCounts["warning"] || severityCounts["medium"]) ? (
              <span className="metric-pill pill-warning">
                {(severityCounts["warning"] || 0) + (severityCounts["medium"] || 0)} Medium
              </span>
            ) : null}
            {severityCounts["info"] ? (
              <span className="metric-pill pill-info">
                {severityCounts["info"]} Low
              </span>
            ) : null}
          </div>

          <div className="review-progress-indicator">
            <span className="progress-fraction">
              {approvedCount + rejectedCount} / {findings.length} Resolved
            </span>
            <div className="progress-mini-bar">
              <div
                className="progress-mini-fill"
                style={{
                  width: `${findings.length > 0 ? ((approvedCount + rejectedCount) / findings.length) * 100 : 0}%`,
                }}
              />
            </div>
          </div>
        </div>
      </div>

      {findings.length === 0 ? (
        <div className="review-empty-state">
          <CheckCircle2 size={24} className="text-emerald-500" />
          <p>No findings were flagged. You can proceed directly to commit the deliverable.</p>
        </div>
      ) : (
        /* Two-Column Review Layout */
        <div className="review-two-column-layout">
          {/* Left Column: Compact Findings List */}
          <div className="review-findings-column">
            <div className="column-header-bar">
              <span>Findings ({findings.length})</span>
            </div>
            <div className="review-findings-scroll-list">
              {findings.map((finding, idx) => {
                const isSelected = activeFinding?.id === finding.id;
                return (
                  <button
                    key={finding.id}
                    type="button"
                    onClick={() => setSelectedFindingId(finding.id)}
                    className={`compact-finding-item ${isSelected ? "selected" : ""} status-${finding.review_decision}`}
                  >
                    <div className="compact-finding-top">
                      <span className="compact-finding-index">{idx + 1}.</span>
                      <span className="compact-finding-title">{finding.title}</span>
                    </div>

                    <div className="compact-finding-meta">
                      {renderSeverityBadge(finding.severity)}
                      {renderDecisionBadge(finding.review_decision)}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Right Column: Selected Finding Details */}
          <div className="review-detail-column">
            {activeFinding ? (
              <div className="finding-inspector">
                {/* Inspector Header */}
                <div className="inspector-header">
                  <div className="inspector-title-row">
                    <div className="inspector-title-group">
                      <h3 className="inspector-title">{activeFinding.title}</h3>
                      <div className="inspector-badges">
                        {renderSeverityBadge(activeFinding.severity)}
                        {renderDecisionBadge(activeFinding.review_decision)}
                      </div>
                    </div>

                    {/* Quick Decision Buttons */}
                    <div className="inspector-actions">
                      <button
                        type="button"
                        disabled={
                          submittingIds[activeFinding.id] ||
                          activeFinding.review_decision === "rejected" ||
                          isFinalizing
                        }
                        onClick={() => handleDecision(activeFinding.id, "reject")}
                        className={`btn-decision btn-reject ${
                          activeFinding.review_decision === "rejected" ? "active" : ""
                        }`}
                      >
                        <X size={15} />
                        {submittingIds[activeFinding.id] ? "Updating..." : "Reject"}
                      </button>

                      <button
                        type="button"
                        disabled={
                          submittingIds[activeFinding.id] ||
                          activeFinding.review_decision === "approved" ||
                          isFinalizing
                        }
                        onClick={() => handleDecision(activeFinding.id, "approve")}
                        className={`btn-decision btn-approve ${
                          activeFinding.review_decision === "approved" ? "active" : ""
                        }`}
                      >
                        <Check size={15} />
                        {submittingIds[activeFinding.id] ? "Updating..." : "Approve"}
                      </button>
                    </div>
                  </div>

                  {/* Section / Category metadata */}
                  {(activeFinding.citation?.semantic_key || activeFinding.citation?.type) && (
                    <div className="inspector-metadata-tag">
                      <FileSearch size={14} />
                      <span>
                        Scope: {activeFinding.citation?.semantic_key || activeFinding.citation?.type}
                      </span>
                    </div>
                  )}
                </div>

                {/* Inspector Content Body */}
                <div className="inspector-body">
                  {/* Rationale / Description */}
                  <div className="inspector-section">
                    <h4 className="section-label">Why this was flagged</h4>
                    <div className="rationale-box">
                      <p>{activeFinding.description}</p>
                    </div>
                  </div>

                  {/* Citation / Sources comparison */}
                  {activeFinding.citation?.sources &&
                    Array.isArray(activeFinding.citation.sources) &&
                    activeFinding.citation.sources.length > 0 && (
                      <div className="inspector-section">
                        <h4 className="section-label">Source Citations & Conflicting Data</h4>
                        <div className="citation-cards-grid">
                          {activeFinding.citation.sources.map((src, sIdx) => (
                            <div key={sIdx} className="citation-card">
                              <div className="citation-card-header">
                                <FileText size={14} className="text-slate-500" />
                                <span className="citation-doc-name">
                                  {src.document || "Document Reference"}
                                </span>
                              </div>
                              {src.value && (
                                <div className="citation-value-row">
                                  <span className="citation-val-label">Value:</span>
                                  <span className="citation-val-text">&ldquo;{src.value}&rdquo;</span>
                                </div>
                              )}
                              {src.source_text && (
                                <blockquote className="citation-quote">
                                  &ldquo;{src.source_text}&rdquo;
                                </blockquote>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                  {/* Proposed Change / Remediation */}
                  {activeFinding.finding_metadata?.recommendation ? (
                    <div className="inspector-section">
                      <h4 className="section-label">Proposed change</h4>
                      <div className="proposed-change-box">
                        <ArrowRight size={16} className="text-blue-600" />
                        <p>{String(activeFinding.finding_metadata.recommendation)}</p>
                      </div>
                    </div>
                  ) : null}
                </div>
              </div>
            ) : (
              <div className="inspector-empty">
                <HelpCircle size={32} className="text-slate-400" />
                <p>Select a finding from the left to view its details and make a decision.</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Final Workflow Commitment Bar */}
      <div className="review-finalize-bar">
        <div className="finalize-info">
          <ShieldAlert size={18} className="text-slate-500" />
          <span>
            {hasPendingFindings
              ? "All findings must be decided before committing or rejecting the run."
              : "All findings are resolved. You can now commit the deliverable or reject the run."}
          </span>
        </div>

        <div className="finalize-actions">
          <button
            type="button"
            disabled={hasPendingFindings || isFinalizing}
            onClick={() => handleFinalDecision("reject")}
            className="btn-finalize btn-finalize-reject"
          >
            <XCircle size={16} />
            {isFinalizing ? "Submitting..." : "Reject and Cancel Workflow"}
          </button>

          <button
            type="button"
            disabled={hasPendingFindings || isFinalizing}
            onClick={() => handleFinalDecision("approve")}
            className="btn-finalize btn-finalize-approve"
          >
            <CheckCircle2 size={16} />
            {isFinalizing ? "Submitting..." : "Approve and Commit Deliverable"}
          </button>
        </div>
      </div>

      {error && (
        <div role="alert" className="review-error-banner">
          <XCircle size={16} />
          <span>{error}</span>
        </div>
      )}
    </section>
  );
}

export default ReviewQueue;
