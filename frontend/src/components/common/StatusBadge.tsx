import React from "react";
import {
  CheckCircle2,
  Loader2,
  AlertTriangle,
  XCircle,
  Clock,
  MinusCircle,
} from "lucide-react";
import type { RunStatus } from "../../api/types";

interface StatusBadgeProps {
  status: RunStatus | string;
  size?: "sm" | "md" | "lg";
  className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  size = "md",
  className = "",
}) => {
  const normalizedStatus = status.toLowerCase();

  const getStatusConfig = () => {
    switch (normalizedStatus) {
      case "completed":
      case "success":
        return {
          label: "Completed",
          icon: <CheckCircle2 className="status-badge-icon" size={size === "sm" ? 12 : 14} />,
          badgeClass: "badge-completed",
        };
      case "running":
      case "in_progress":
      case "processing":
        return {
          label: "Running",
          icon: <Loader2 className="status-badge-icon animate-spin" size={size === "sm" ? 12 : 14} />,
          badgeClass: "badge-running",
        };
      case "waiting_for_review":
      case "needs_review":
      case "waiting":
        return {
          label: "Waiting for review",
          icon: <AlertTriangle className="status-badge-icon" size={size === "sm" ? 12 : 14} />,
          badgeClass: "badge-review",
        };
      case "failed":
      case "error":
        return {
          label: "Failed",
          icon: <XCircle className="status-badge-icon" size={size === "sm" ? 12 : 14} />,
          badgeClass: "badge-failed",
        };
      case "cancelled":
        return {
          label: "Cancelled",
          icon: <MinusCircle className="status-badge-icon" size={size === "sm" ? 12 : 14} />,
          badgeClass: "badge-cancelled",
        };
      case "pending":
      default:
        return {
          label: normalizedStatus === "pending" ? "Pending" : status.replaceAll("_", " "),
          icon: <Clock className="status-badge-icon" size={size === "sm" ? 12 : 14} />,
          badgeClass: "badge-pending",
        };
    }
  };

  const { label, icon, badgeClass } = getStatusConfig();

  return (
    <span className={`status-badge-saas ${badgeClass} size-${size} ${className}`}>
      {icon}
      <span className="status-badge-text">{label}</span>
    </span>
  );
};
