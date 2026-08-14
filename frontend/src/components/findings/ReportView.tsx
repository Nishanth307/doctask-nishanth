import type { ReportResponse } from "../../api/types";

interface ReportViewProps {
  report: ReportResponse | null;
}

export function ReportView({ report }: ReportViewProps) {
  return (
    <section className="card report-section">
      <h2>Final Report</h2>

      {!report ? (
        <p>No report has been generated yet.</p>
      ) : (
        <div className="report-container">
          <p>
            <strong>Version:</strong> {report.version}
          </p>

          <p>
            <strong>Approved:</strong> {report.approved ? "Yes" : "No"}
          </p>

          <div className="report-content-box">
            <h3>Report Content</h3>
            <p className="report-markdown">{report.content}</p>
          </div>
        </div>
      )}
    </section>
  );
}
