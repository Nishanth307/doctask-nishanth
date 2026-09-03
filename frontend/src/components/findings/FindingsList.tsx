import React from "react";
import {
  FileText,
  Check,
  X,
  Clock,
  FileCheck2,
} from "lucide-react";
import type { FindingResponse, FindingSeverity } from "../../api/types";

interface FindingsListProps {
  findings: FindingResponse[];
}

export const FindingsList: React.FC<FindingsListProps> = ({ findings }) => {
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
    if (decision === "needs_resolution") {
      return (
        <span className="finding-decision-pill pill-warning">
          <Clock size={12} /> Needs Resolution
        </span>
      );
    }
    return (
      <span className="finding-decision-pill pill-pending">
        <Clock size={12} /> Pending Review
      </span>
    );
  };

  return (
    <section className="card findings-section-card">
      <div className="section-header-row">
        <div className="flex items-center gap-2">
          <FileCheck2 size={20} className="text-slate-700" />
          <h2 className="section-heading">All Findings & Reconciled Items</h2>
        </div>
        <span className="findings-total-pill">
          {findings.length} item{findings.length === 1 ? "" : "s"}
        </span>
      </div>

      {findings.length === 0 ? (
        <div className="empty-findings-state">
          <p>No findings or discrepancies recorded for this run.</p>
        </div>
      ) : (
        <div className="findings-grid-list">
          {findings.map((finding) => (
            <article key={finding.id} className="finding-summary-card">
              <div className="finding-header-top">
                <h3 className="finding-title">{finding.title}</h3>
                <div className="finding-pill-group">
                  {renderSeverityBadge(finding.severity)}
                  {renderDecisionBadge(finding.review_decision)}
                </div>
              </div>

              <p className="finding-desc-text">{finding.description}</p>

              {finding.citation?.sources &&
                Array.isArray(finding.citation.sources) &&
                finding.citation.sources.length > 0 && (
                  <div className="finding-citations-wrapper">
                    <span className="citations-label">Sources & Citations:</span>
                    <div className="citations-row">
                      {finding.citation.sources.map((src, idx) => (
                        <div key={idx} className="citation-chip">
                          <FileText size={12} className="text-slate-400" />
                          <span className="citation-chip-doc">
                            {src.document || "Source"}:
                          </span>
                          <span className="citation-chip-val">
                            &ldquo;{src.value}&rdquo;
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
};

export default FindingsList;