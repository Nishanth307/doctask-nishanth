import type { FindingResponse } from "../../api/types";

interface FindingsListProps {
  findings: FindingResponse[];
}

export function FindingsList({ findings }: FindingsListProps) {
  return (
    <section className="card findings-section">
      <h2>Findings</h2>

      {findings.length === 0 ? (
        <p>No findings were produced.</p>
      ) : (
        <div className="findings-container">
          {findings.map((finding) => (
            <article key={finding.id} className="finding-item">
              <h3>{finding.title}</h3>

              <p>{finding.description}</p>

              <p>
                <strong>Severity:</strong> {finding.severity}
              </p>

              <p>
                <strong>Review:</strong> {finding.review_decision}
              </p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}