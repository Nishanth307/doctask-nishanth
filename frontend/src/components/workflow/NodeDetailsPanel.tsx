import React, { useState } from "react";
import {
  AlertOctagon,
  CheckCircle2,
  Clock,
  Copy,
  Check,
  RefreshCw,
  X,
  XCircle,
  Database,
  Brain,
  FileCode,
  ShieldAlert,
  HelpCircle,
  Timer,
  AlertTriangle,
} from "lucide-react";
import type { NodeError, NodeExecutionRecord, ErrorCategory } from "../../api/types";

interface NodeDetailsPanelProps {
  runId: string;
  nodeName: string;
  stageName?: string;
  status?: string;
  lastError?: NodeError | null;
  executionHistory?: NodeExecutionRecord[];
  onRetryNode: (nodeName: string) => Promise<void>;
  isRetrying?: boolean;
  onClose?: () => void;
}

const CATEGORY_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  TRANSIENT: { bg: "bg-blue-50", text: "text-blue-700", border: "border-blue-200" },
  PERMANENT: { bg: "bg-rose-50", text: "text-rose-700", border: "border-rose-200" },
  VALIDATION: { bg: "bg-amber-50", text: "text-amber-700", border: "border-amber-200" },
  CONFIGURATION: { bg: "bg-red-50", text: "text-red-700", border: "border-red-200" },
  DEPENDENCY: { bg: "bg-orange-50", text: "text-orange-700", border: "border-orange-200" },
  TIMEOUT: { bg: "bg-amber-50", text: "text-amber-700", border: "border-amber-200" },
  RATE_LIMIT: { bg: "bg-yellow-50", text: "text-yellow-700", border: "border-yellow-200" },
  QUOTA_EXHAUSTED: { bg: "bg-rose-50", text: "text-rose-700", border: "border-rose-200" },
  NETWORK_ERROR: { bg: "bg-blue-50", text: "text-blue-700", border: "border-blue-200" },
  PROVIDER_UNAVAILABLE: { bg: "bg-amber-50", text: "text-amber-700", border: "border-amber-200" },
  AUTHENTICATION_ERROR: { bg: "bg-red-50", text: "text-red-700", border: "border-red-200" },
  INVALID_REQUEST: { bg: "bg-orange-50", text: "text-orange-700", border: "border-orange-200" },
  MODEL_NOT_FOUND: { bg: "bg-purple-50", text: "text-purple-700", border: "border-purple-200" },
  CONTEXT_LENGTH: { bg: "bg-yellow-50", text: "text-yellow-700", border: "border-yellow-200" },
  STRUCTURED_OUTPUT_ERROR: { bg: "bg-indigo-50", text: "text-indigo-700", border: "border-indigo-200" },
  DATABASE: { bg: "bg-cyan-50", text: "text-cyan-700", border: "border-cyan-200" },
  STORAGE: { bg: "bg-teal-50", text: "text-teal-700", border: "border-teal-200" },
  LLM: { bg: "bg-purple-50", text: "text-purple-700", border: "border-purple-200" },
  DOCUMENT_PROCESSING: { bg: "bg-indigo-50", text: "text-indigo-700", border: "border-indigo-200" },
  UNKNOWN: { bg: "bg-slate-100", text: "text-slate-700", border: "border-slate-200" },
};

function getCategoryIcon(category: string) {
  switch (category) {
    case "LLM":
    case "MODEL_NOT_FOUND":
      return <Brain size={14} className="inline mr-1" />;
    case "DATABASE":
    case "STORAGE":
      return <Database size={14} className="inline mr-1" />;
    case "TIMEOUT":
      return <Timer size={14} className="inline mr-1" />;
    case "VALIDATION":
    case "STRUCTURED_OUTPUT_ERROR":
      return <FileCode size={14} className="inline mr-1" />;
    case "RATE_LIMIT":
    case "QUOTA_EXHAUSTED":
    case "PROVIDER_UNAVAILABLE":
      return <AlertTriangle size={14} className="inline mr-1 text-amber-500" />;
    case "CONFIGURATION":
    case "AUTHENTICATION_ERROR":
    case "DEPENDENCY":
    case "PERMANENT":
      return <AlertOctagon size={14} className="inline mr-1" />;
    default:
      return <HelpCircle size={14} className="inline mr-1" />;
  }
}


export const NodeDetailsPanel: React.FC<NodeDetailsPanelProps> = ({
  nodeName,
  stageName,
  status = "unknown",
  lastError,
  executionHistory = [],
  onRetryNode,
  isRetrying = false,
  onClose,
}) => {
  const [copied, setCopied] = useState(false);

  // Filter history for this node
  const nodeAttempts = executionHistory.filter((rec) => rec.node_name === nodeName);
  const relevantError =
    lastError && lastError.node_name === nodeName
      ? lastError
      : nodeAttempts.find((a) => a.status === "failed")
      ? {
          node_name: nodeName,
          error_type: nodeAttempts.find((a) => a.status === "failed")?.error_type || "UNKNOWN",
          error_message: nodeAttempts.find((a) => a.status === "failed")?.error_message || "Unknown error",
          error_timestamp: nodeAttempts.find((a) => a.status === "failed")?.timestamp || "",
          retryable: nodeAttempts.find((a) => a.status === "failed")?.retryable ?? true,
          attempt: nodeAttempts.find((a) => a.status === "failed")?.attempt || 1,
          provider: nodeAttempts.find((a) => a.status === "failed")?.provider,
          model: nodeAttempts.find((a) => a.status === "failed")?.model,
          fallback_level: nodeAttempts.find((a) => a.status === "failed")?.fallback_level,
          fallback_used: nodeAttempts.find((a) => a.status === "failed")?.fallback_used,
          provider_attempts: nodeAttempts.find((a) => a.status === "failed")?.provider_attempts,
        }
      : null;

  const latestRecord = nodeAttempts.length > 0 ? nodeAttempts[nodeAttempts.length - 1] : undefined;
  const providerAttempts = relevantError?.provider_attempts || latestRecord?.provider_attempts || [];
  const currentProvider = relevantError?.provider || latestRecord?.provider;
  const currentModel = relevantError?.model || latestRecord?.model;
  const fallbackUsed = relevantError?.fallback_used || latestRecord?.fallback_used;
  const fallbackLevel = relevantError?.fallback_level ?? latestRecord?.fallback_level;

  const isFailed = status === "failed" || Boolean(relevantError);
  const catColor = relevantError
    ? CATEGORY_COLORS[relevantError.error_type as ErrorCategory] || CATEGORY_COLORS.UNKNOWN
    : CATEGORY_COLORS.UNKNOWN;

  const handleCopy = () => {
    if (relevantError?.error_message) {
      navigator.clipboard.writeText(relevantError.error_message);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div
      style={{
        marginTop: "1.5rem",
        marginBottom: "1.5rem",
        borderRadius: "10px",
        border: isFailed ? "1px solid #fecdd3" : "1px solid #e2e8f0",
        backgroundColor: isFailed ? "#fff5f5" : "#ffffff",
        boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.05)",
        overflow: "hidden",
      }}
    >
      {/* Panel Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "12px 18px",
          borderBottom: isFailed ? "1px solid #fee2e2" : "1px solid #f1f5f9",
          backgroundColor: isFailed ? "#ffe4e6" : "#f8fafc",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          {isFailed ? (
            <XCircle size={18} color="#e11d48" />
          ) : status === "completed" ? (
            <CheckCircle2 size={18} color="#10b981" />
          ) : (
            <Clock size={18} color="#64748b" />
          )}
          <span style={{ fontWeight: 600, fontSize: "15px", color: "#1e293b" }}>
            Node Diagnostics: <span style={{ fontFamily: "monospace", color: "#0f172a" }}>{nodeName}</span>
          </span>
          {stageName && (
            <span
              style={{
                fontSize: "12px",
                color: "#64748b",
                backgroundColor: "#e2e8f0",
                padding: "2px 8px",
                borderRadius: "12px",
              }}
            >
              Stage: {stageName}
            </span>
          )}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          {isFailed && (
            <button
              onClick={() => onRetryNode(nodeName)}
              disabled={isRetrying}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "6px",
                padding: "6px 14px",
                backgroundColor: isRetrying ? "#94a3b8" : "#2563eb",
                color: "#ffffff",
                fontSize: "13px",
                fontWeight: 500,
                borderRadius: "6px",
                border: "none",
                cursor: isRetrying ? "not-allowed" : "pointer",
                boxShadow: "0 1px 2px rgba(0,0,0,0.05)",
              }}
            >
              <RefreshCw size={14} className={isRetrying ? "animate-spin" : ""} />
              {isRetrying ? "Retrying Node..." : "Retry Node"}
            </button>
          )}

          {onClose && (
            <button
              onClick={onClose}
              style={{
                background: "transparent",
                border: "none",
                cursor: "pointer",
                padding: "4px",
                color: "#64748b",
              }}
              title="Close panel"
            >
              <X size={18} />
            </button>
          )}
        </div>
      </div>

      {/* Panel Body */}
      <div style={{ padding: "16px 18px" }}>
        {/* LLM Provider & Metadata Bar (if this node used an LLM) */}
        {currentProvider && (
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "10px",
              alignItems: "center",
              padding: "8px 12px",
              backgroundColor: "#f8fafc",
              border: "1px solid #e2e8f0",
              borderRadius: "6px",
              marginBottom: "14px",
              fontSize: "12px",
            }}
          >
            <span style={{ fontWeight: 600, color: "#334155" }}>
              <Brain size={14} className="inline mr-1 text-purple-600" />
              Provider: <span style={{ fontFamily: "monospace", color: "#0f172a" }}>{currentProvider}</span>
            </span>
            {currentModel && (
              <span style={{ color: "#64748b" }}>
                Model: <span style={{ fontFamily: "monospace", color: "#1e293b" }}>{currentModel}</span>
              </span>
            )}
            {fallbackUsed && (
              <span
                style={{
                  padding: "2px 8px",
                  borderRadius: "4px",
                  backgroundColor: "#fffbeb",
                  color: "#b45309",
                  border: "1px solid #fde68a",
                  fontWeight: 600,
                  fontSize: "11px",
                }}
              >
                ⚠ Fallback Used (Tier {fallbackLevel})
              </span>
            )}
            {latestRecord?.total_tokens !== undefined && latestRecord?.total_tokens !== null && (
              <span style={{ color: "#64748b", marginLeft: "auto" }}>
                Tokens: <strong>{latestRecord.input_tokens ?? "-"}</strong> in / <strong>{latestRecord.output_tokens ?? "-"}</strong> out (<strong>{latestRecord.total_tokens}</strong> total)
              </span>
            )}
          </div>
        )}

        {/* Error Details if Failed */}
        {isFailed && relevantError && (
          <div
            style={{
              backgroundColor: "#ffffff",
              borderRadius: "8px",
              border: "1px solid #fda4af",
              padding: "14px",
              marginBottom: "16px",
            }}
          >
            <div style={{ display: "flex", flexWrap: "wrap", gap: "10px", alignItems: "center", marginBottom: "10px" }}>
              {/* Category Pill */}
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  fontSize: "12px",
                  fontWeight: 600,
                  padding: "3px 10px",
                  borderRadius: "6px",
                  border: `1px solid ${catColor.border}`,
                  backgroundColor: isFailed ? "#fef2f2" : "#f8fafc",
                  color: isFailed ? "#be123c" : "#334155",
                }}
              >
                {getCategoryIcon(relevantError.error_type)}
                Category: {relevantError.error_type}
              </span>

              {/* Retryable status */}
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  fontSize: "12px",
                  fontWeight: 500,
                  padding: "3px 10px",
                  borderRadius: "6px",
                  backgroundColor: relevantError.retryable ? "#ecfdf5" : "#fef2f2",
                  color: relevantError.retryable ? "#047857" : "#b91c1c",
                  border: relevantError.retryable ? "1px solid #a7f3d0" : "1px solid #fecaca",
                }}
              >
                {relevantError.retryable ? "✓ Retryable" : "⚠ Permanent (Non-retryable)"}
              </span>

              {/* Attempt Counter */}
              <span style={{ fontSize: "12px", color: "#64748b" }}>
                Attempt: <strong>{relevantError.attempt}</strong>
              </span>

              {relevantError.checkpoint_id && (
                <span style={{ fontSize: "12px", color: "#64748b", fontFamily: "monospace" }}>
                  Checkpoint: {relevantError.checkpoint_id.slice(0, 8)}...
                </span>
              )}
            </div>

            {/* Error Message Box */}
            <div
              style={{
                position: "relative",
                backgroundColor: "#0f172a",
                color: "#f8fafc",
                borderRadius: "6px",
                padding: "12px 14px",
                fontFamily: "ui-monospace, monospace",
                fontSize: "13px",
                lineHeight: "1.5",
                wordBreak: "break-all",
                marginTop: "8px",
              }}
            >
              <button
                onClick={handleCopy}
                style={{
                  position: "absolute",
                  top: "8px",
                  right: "8px",
                  backgroundColor: "rgba(255,255,255,0.1)",
                  border: "none",
                  borderRadius: "4px",
                  padding: "4px 8px",
                  color: "#cbd5e1",
                  fontSize: "11px",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: "4px",
                }}
                title="Copy error message"
              >
                {copied ? <Check size={12} color="#4ade80" /> : <Copy size={12} />}
                {copied ? "Copied" : "Copy"}
              </button>
              <div style={{ color: "#fca5a5", fontWeight: 600, marginBottom: "4px" }}>Error Message:</div>
              <div>{relevantError.error_message}</div>
            </div>

            {/* Provider Fallback Attempts Breakdown */}
            {providerAttempts && providerAttempts.length > 0 && (
              <div
                style={{
                  marginTop: "12px",
                  border: "1px solid #fed7aa",
                  backgroundColor: "#fffbeb",
                  borderRadius: "6px",
                  padding: "10px 12px",
                }}
              >
                <div style={{ fontWeight: 600, fontSize: "12px", color: "#9a3412", marginBottom: "6px" }}>
                  Provider Fallback Attempts:
                </div>
                {providerAttempts.map((pa, idx) => (
                  <div
                    key={idx}
                    style={{
                      fontSize: "12px",
                      color: "#7c2d12",
                      display: "flex",
                      justifyContent: "space-between",
                      padding: "4px 0",
                      borderBottom: idx < providerAttempts.length - 1 ? "1px dashed #fed7aa" : "none",
                    }}
                  >
                    <span style={{ fontFamily: "monospace", fontWeight: 600 }}>
                      {pa.provider} ({pa.model})
                    </span>
                    <span style={{ fontWeight: 600, color: "#c2410c" }}>
                      [{pa.error_type || "FAILED"}]
                    </span>
                    <span
                      style={{
                        color: "#9a3412",
                        maxWidth: "280px",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                      title={pa.error_message}
                    >
                      {pa.error_message || "Failed"}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* Non-retryable Guidance */}
            {!relevantError.retryable && (
              <div
                style={{
                  marginTop: "10px",
                  padding: "10px 12px",
                  backgroundColor: "#fff1f2",
                  borderRadius: "6px",
                  border: "1px solid #ffe4e6",
                  fontSize: "13px",
                  color: "#9f1239",
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                }}
              >
                <ShieldAlert size={16} />
                <span>
                  <strong>Configuration Required:</strong> This failure cannot be resolved by automatic retries alone. Check credentials, configuration, or document format before re-executing.
                </span>
              </div>
            )}
          </div>
        )}

        {/* Attempt History */}
        {nodeAttempts.length > 0 && (
          <div>
            <div style={{ fontSize: "13px", fontWeight: 600, color: "#475569", marginBottom: "8px" }}>
              Execution History for <span style={{ fontFamily: "monospace" }}>{nodeName}</span> ({nodeAttempts.length} attempt{nodeAttempts.length > 1 ? "s" : ""})
            </div>
            <div
              style={{
                border: "1px solid #e2e8f0",
                borderRadius: "6px",
                overflow: "hidden",
                fontSize: "12px",
              }}
            >
              <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
                <thead>
                  <tr style={{ backgroundColor: "#f8fafc", borderBottom: "1px solid #e2e8f0", color: "#64748b" }}>
                    <th style={{ padding: "8px 12px" }}>Attempt</th>
                    <th style={{ padding: "8px 12px" }}>Status</th>
                    <th style={{ padding: "8px 12px" }}>Provider / Model</th>
                    <th style={{ padding: "8px 12px" }}>Duration</th>
                    <th style={{ padding: "8px 12px" }}>Type / Message</th>
                    <th style={{ padding: "8px 12px" }}>Timestamp</th>
                  </tr>
                </thead>
                <tbody>
                  {nodeAttempts.map((rec, idx) => (
                    <tr
                      key={idx}
                      style={{
                        borderBottom: idx < nodeAttempts.length - 1 ? "1px solid #f1f5f9" : "none",
                        backgroundColor: rec.status === "failed" ? "#fff5f5" : "#ffffff",
                      }}
                    >
                      <td style={{ padding: "8px 12px", fontWeight: 600 }}>#{rec.attempt}</td>
                      <td style={{ padding: "8px 12px" }}>
                        <span
                          style={{
                            padding: "2px 6px",
                            borderRadius: "4px",
                            fontWeight: 500,
                            backgroundColor:
                              rec.status === "completed"
                                ? "#ecfdf5"
                                : rec.status === "failed"
                                ? "#fee2e2"
                                : "#eff6ff",
                            color:
                              rec.status === "completed"
                                ? "#065f46"
                                : rec.status === "failed"
                                ? "#991b1b"
                                : "#1e40af",
                          }}
                        >
                          {rec.status.toUpperCase()}
                        </span>
                      </td>
                      <td style={{ padding: "8px 12px", fontFamily: "monospace", fontSize: "11px", color: "#475569" }}>
                        {rec.provider ? `${rec.provider} (${rec.model || "default"})` : "-"}
                      </td>
                      <td style={{ padding: "8px 12px", color: "#64748b" }}>
                        {rec.duration_ms ? `${rec.duration_ms}ms` : "-"}
                      </td>
                      <td style={{ padding: "8px 12px", maxWidth: "260px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {rec.error_type ? (
                          <span style={{ fontWeight: 500, color: "#b91c1c", marginRight: "6px" }}>
                            [{rec.error_type}]
                          </span>
                        ) : null}
                        <span color="#475569">{rec.error_message || "Completed successfully"}</span>
                      </td>
                      <td style={{ padding: "8px 12px", color: "#64748b" }}>
                        {rec.timestamp ? new Date(rec.timestamp).toLocaleTimeString() : "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

