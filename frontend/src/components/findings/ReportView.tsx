import React from "react";
import { FileCheck, ShieldCheck, CheckCircle2 } from "lucide-react";
import type { ReportResponse } from "../../api/types";

interface ReportViewProps {
  report: ReportResponse | null;
}

export const ReportView: React.FC<ReportViewProps> = ({ report }) => {
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

  return (
    <section className="card report-section-card">
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
        </div>
      </div>

      <div className="report-markdown-container">
        <div className="report-markdown-header">
          <CheckCircle2 size={16} className="text-emerald-500" />
          <span>Verified Audit Report</span>
        </div>
        <div className="report-content-body">
          <pre className="report-pre-text">{report.content}</pre>
        </div>
      </div>
    </section>
  );
};

export default ReportView;
