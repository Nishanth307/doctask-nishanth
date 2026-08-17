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
        <div className="findings-container" style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          {findings.map((finding) => (
            <article
              key={finding.id}
              className="finding-item"
              style={{
                border: "1px solid #e2e8f0",
                borderRadius: "8px",
                padding: "16px",
                backgroundColor: "#ffffff",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "8px" }}>
                <h3 style={{ margin: 0, fontSize: "16px" }}>{finding.title}</h3>
                <span
                  style={{
                    padding: "2px 8px",
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

              <p style={{ margin: "6px 0", color: "#334155" }}>{finding.description}</p>

              <div style={{ display: "flex", gap: "16px", fontSize: "12px", color: "#64748b", margin: "6px 0" }}>
                <span><strong>Severity:</strong> {finding.severity.toUpperCase()}</span>
                <span><strong>Status:</strong> {finding.review_decision.toUpperCase()}</span>
              </div>

              {finding.citation?.sources && Array.isArray(finding.citation.sources) && finding.citation.sources.length > 0 && (
                <div style={{ marginTop: "10px", display: "flex", flexDirection: "column", gap: "6px" }}>
                  <strong style={{ fontSize: "12px", color: "#475569" }}>Sources & Values:</strong>
                  {finding.citation.sources.map((src, idx) => (
                    <div
                      key={idx}
                      style={{
                        backgroundColor: "#f8fafc",
                        border: "1px solid #e2e8f0",
                        borderRadius: "4px",
                        padding: "6px 10px",
                        fontSize: "12px",
                      }}
                    >
                      <span style={{ fontWeight: 600, color: "#1e293b" }}>📄 {src.document || "Source"}</span>: &ldquo;{src.value}&rdquo;
                      {src.source_text && (
                        <div style={{ color: "#64748b", fontStyle: "italic", marginTop: "2px" }}>
                          &ldquo;{src.source_text}&rdquo;
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </article>
          ))}
        </div>

      )}
    </section>
  );
}