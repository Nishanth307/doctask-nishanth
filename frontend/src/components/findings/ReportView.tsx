import React, { useState } from "react";
import {
  FileCheck,
  ShieldCheck,
  CheckCircle2,
  FileText,
  Download,
  XCircle,
  Hash,
  History,
  BadgeCheck,
  AlertCircle,
} from "lucide-react";
import type { ReportResponse, ChangeRecord, SectionHashInfo } from "../../api/types";

interface ReportViewProps {
  report: ReportResponse | null;
  runId?: string;
}

type ReportTab = "final-document" | "audit-report" | "provenance";

export const ReportView: React.FC<ReportViewProps> = ({ report, runId }) => {
  const [activeTab, setActiveTab] = useState<ReportTab>(
    report?.final_content ? "final-document" : "audit-report"
  );

  if (!report) {
    return (
      <section className="card report-section-card">
        <div className="section-header-row">
          <div className="flex items-center gap-2">
            <FileCheck size={20} className="text-slate-700" />
            <h2 className="section-heading">Final Deliverable Report</h2>
          </div>
        </div>
        <p className="text-slate-500 text-sm">
          No deliverable report has been generated yet. The final report is generated during the commit stage.
        </p>
      </section>
    );
  }

  const hasFinalDocument = !!report.final_content;
  const validationPassed = report.validation_passed;
  const changeHistory = report.change_history || [];
  const sectionHashes = report.section_hashes || {};

  const appliedChanges = changeHistory.filter((c) => c.application_status === "applied");
  const rejectedChanges = changeHistory.filter((c) => c.application_status === "rejected");
  const failedChanges = changeHistory.filter((c) => c.application_status === "failed");

  const handleDownload = () => {
    if (!report.final_content) return;
    const blob = new Blob([report.final_content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `final_contract_${runId || "document"}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const renderValidationBadge = () => {
    if (validationPassed === null || validationPassed === undefined) return null;
    if (validationPassed) {
      return (
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
          <BadgeCheck size={13} />
          Validation Passed
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-red-50 text-red-700 border border-red-200">
        <AlertCircle size={13} />
        Validation Failed
      </span>
    );
  };

  return (
    <section className="card report-section-card">
      {/* Header */}
      <div className="section-header-row">
        <div className="flex items-center gap-2">
          <FileCheck size={20} className="text-emerald-600" />
          <h2 className="section-heading">Final Deliverable Report</h2>
        </div>

        <div className="report-meta-badges">
          <span className="meta-pill">Version {report.version}</span>
          {report.approved && (
            <span className="meta-pill pill-approved">
              <ShieldCheck size={13} /> Approved Deliverable
            </span>
          )}
          {renderValidationBadge()}
          {hasFinalDocument && (
            <button
              type="button"
              onClick={handleDownload}
              className="meta-pill pill-download flex items-center gap-1 cursor-pointer hover:bg-blue-100 transition-colors"
            >
              <Download size={13} />
              Download Final Contract
            </button>
          )}
        </div>
      </div>

      {/* Change summary bar */}
      {changeHistory.length > 0 && (
        <div className="change-summary-bar">
          <div className="change-summary-item change-applied">
            <CheckCircle2 size={14} />
            <span>{appliedChanges.length} edit{appliedChanges.length !== 1 ? "s" : ""} applied</span>
          </div>
          <div className="change-summary-item change-rejected">
            <XCircle size={14} />
            <span>{rejectedChanges.length} rejected</span>
          </div>
          {failedChanges.length > 0 && (
            <div className="change-summary-item change-failed">
              <AlertCircle size={14} />
              <span>{failedChanges.length} failed</span>
            </div>
          )}
          {report.validation_summary && (
            <div className="change-summary-validation">
              {report.validation_summary}
            </div>
          )}
        </div>
      )}

      {/* Tab Bar */}
      <div className="report-tab-bar" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "final-document"}
          id="tab-final-document"
          className={`report-tab ${activeTab === "final-document" ? "active" : ""} ${!hasFinalDocument ? "disabled" : ""}`}
          onClick={() => hasFinalDocument && setActiveTab("final-document")}
          disabled={!hasFinalDocument}
        >
          <FileText size={14} />
          Final Contract
          {!hasFinalDocument && <span className="tab-badge-pending">Pending</span>}
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "audit-report"}
          id="tab-audit-report"
          className={`report-tab ${activeTab === "audit-report" ? "active" : ""}`}
          onClick={() => setActiveTab("audit-report")}
        >
          <ShieldCheck size={14} />
          Audit Report
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "provenance"}
          id="tab-provenance"
          className={`report-tab ${activeTab === "provenance" ? "active" : ""}`}
          onClick={() => setActiveTab("provenance")}
        >
          <History size={14} />
          Provenance
          {changeHistory.length > 0 && (
            <span className="tab-badge-count">{changeHistory.length}</span>
          )}
        </button>
      </div>

      {/* Tab Content */}
      <div className="report-tab-content">
        {/* Final Contract Tab */}
        {activeTab === "final-document" && (
          <div className="report-final-doc-panel">
            {hasFinalDocument ? (
              <>
                <div className="report-markdown-header">
                  <CheckCircle2 size={16} className="text-emerald-500" />
                  <span>Final Contract Document</span>
                  {renderValidationBadge()}
                </div>
                <div className="report-content-body">
                  <pre className="report-pre-text">{report.final_content}</pre>
                </div>

                {/* Section Hash Proof */}
                {Object.keys(sectionHashes).length > 1 && (
                  <div className="section-hash-table-wrapper">
                    <div className="section-hash-table-header">
                      <Hash size={14} />
                      <span>Unchanged Content Proof (SHA-256 Section Hashes)</span>
                    </div>
                    <table className="section-hash-table">
                      <thead>
                        <tr>
                          <th>Section</th>
                          <th>Before Hash</th>
                          <th>After Hash</th>
                          <th>Changed?</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(sectionHashes)
                          .filter(([key]) => key !== "_full_document")
                          .map(([section, hashes]) => {
                            const h = hashes as SectionHashInfo;
                            return (
                              <tr key={section} className={h.changed ? "row-changed" : "row-unchanged"}>
                                <td className="section-name-cell">{section}</td>
                                <td className="hash-cell">{h.before_hash?.slice(0, 12)}...</td>
                                <td className="hash-cell">{h.after_hash?.slice(0, 12)}...</td>
                                <td className="changed-cell">
                                  {h.changed ? (
                                    <span className="changed-yes">Modified</span>
                                  ) : (
                                    <span className="changed-no">Unchanged</span>
                                  )}
                                </td>
                              </tr>
                            );
                          })}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            ) : (
              <div className="report-pending-notice">
                <FileText size={32} className="text-slate-300" />
                <p>The final contract document has not been generated yet.</p>
                <p className="text-sm text-slate-500">
                  It will appear here once all findings are reviewed and the workflow commits.
                </p>
              </div>
            )}
          </div>
        )}

        {/* Audit Report Tab */}
        {activeTab === "audit-report" && (
          <div className="report-markdown-container">
            <div className="report-markdown-header">
              <ShieldCheck size={16} className="text-emerald-500" />
              <span>Verified Audit Report</span>
            </div>
            <div className="report-content-body">
              <pre className="report-pre-text">{report.content}</pre>
            </div>
          </div>
        )}

        {/* Provenance Tab */}
        {activeTab === "provenance" && (
          <div className="report-provenance-panel">
            {changeHistory.length === 0 ? (
              <div className="report-pending-notice">
                <History size={32} className="text-slate-300" />
                <p>No change history available yet.</p>
              </div>
            ) : (
              <>
                <div className="provenance-legend">
                  <span className="provenance-legend-item legend-applied">Applied</span>
                  <span className="provenance-legend-item legend-rejected">Rejected</span>
                  {failedChanges.length > 0 && (
                    <span className="provenance-legend-item legend-failed">Failed</span>
                  )}
                </div>
                <div className="provenance-timeline">
                  {changeHistory.map((record: ChangeRecord) => (
                    <div
                      key={record.change_id}
                      className={`provenance-record status-${record.application_status}`}
                    >
                      <div className="provenance-record-header">
                        <span className={`provenance-status-dot dot-${record.application_status}`} />
                        <span className="provenance-record-title">
                          {record.proposed_edit ||
                            (record.original_value && record.new_value
                              ? `${record.original_value} → ${record.new_value}`
                              : "Edit Record")}
                        </span>
                        <span className={`provenance-decision-tag tag-${record.reviewer_decision}`}>
                          {record.reviewer_decision}
                        </span>
                      </div>

                      {record.source_location && (
                        <div className="provenance-record-location">
                          Location: {record.source_location}
                        </div>
                      )}

                      <div className="provenance-record-reason">{record.reason}</div>

                      <div className="provenance-record-timestamp">
                        {new Date(record.applied_at).toLocaleString()}
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </section>
  );
};

export default ReportView;
