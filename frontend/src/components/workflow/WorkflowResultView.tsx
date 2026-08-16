import type { WorkflowResultResponse } from "../../api/types";

interface WorkflowResultViewProps {
  result: WorkflowResultResponse | null;
  runStatus: string;
}

export function WorkflowResultView({ result, runStatus }: WorkflowResultViewProps) {
  if (!result) {
    return (
      <section className="card workflow-result-section">
        <h2>Workflow Result</h2>
        <p>
          {runStatus === "waiting_for_review"
            ? "Workflow result is pending review completion."
            : "No workflow result is available yet."}
        </p>
      </section>
    );
  }

  return (
    <section className="card workflow-result-section">
      <h2>Workflow Result</h2>

      {result && (
        <p>
          <strong>Status:</strong> {result.status}
        </p>
      )}

      {(result?.human_decision || runStatus === "waiting_for_review") && (
        <div style={{ marginTop: "16px", paddingTop: "16px", borderTop: "1px solid #e2e8f0" }}>
          <h3 style={{ margin: "0 0 8px 0" }}>Review History</h3>
          {result?.human_decision ? (
            <div>
              <p style={{ margin: "4px 0" }}>
                <strong>Decision:</strong> <span style={{ textTransform: "capitalize", fontWeight: "bold" }}>{result.human_decision}ed</span>
              </p>
              <p style={{ fontSize: "12px", color: "#94a3b8", margin: "4px 0" }}>
                <strong>Reviewed at:</strong> {new Date(result.updated_at).toLocaleString()}
              </p>
            </div>
          ) : (
            <p style={{ color: "#d97706", margin: "4px 0" }}>Waiting for human decision</p>
          )}
        </div>
      )}
    </section>
  );
}
