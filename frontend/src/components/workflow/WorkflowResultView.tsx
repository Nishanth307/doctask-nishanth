import type { WorkflowResultResponse } from "../../api/types";

interface WorkflowResultViewProps {
  result: WorkflowResultResponse | null;
}

export function WorkflowResultView({ result }: WorkflowResultViewProps) {
  if (!result) {
    return (
      <section className="card workflow-result-section">
        <h2>Workflow Result</h2>
        <p>No workflow result is available yet.</p>
      </section>
    );
  }

  return (
    <section className="card workflow-result-section">
      <h2>Workflow Result</h2>

      <p>
        <strong>Status:</strong> {result.status}
      </p>

      {result.human_decision && (
        <p>
          <strong>Human Decision:</strong> {result.human_decision}
        </p>
      )}
    </section>
  );
}
