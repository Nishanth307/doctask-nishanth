export type RunStatus =
  | "pending"
  | "running"
  | "waiting_for_review"
  | "completed"
  | "failed"
  | "cancelled";

export type WorkflowStage =
  | "ingestion"
  | "classification"
  | "extraction"
  | "reconciliation"
  | "examination"
  | "update"
  | "review"
  | "commit";

export type FindingSeverity =
  | "info"
  | "warning"
  | "error"
  | "critical";

export type ReviewDecision =
  | "approved"
  | "rejected"
  | "pending";

export interface RunDocumentSummary {
  id: string;
  filename: string;
  is_rules: boolean;
}

export interface RunResponse {
  id: string;
  name: string;
  status: RunStatus;
  stage: WorkflowStage;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  error_message: string | null;
  documents?: RunDocumentSummary[];
}

export interface FindingResponse {
  id: string;
  title: string;
  description: string;
  severity: FindingSeverity;
  review_decision: ReviewDecision;
  citation: Record<string, unknown> | null;
  finding_metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface ReportResponse {
  id: string;
  content: string;
  version: number;
  approved: boolean;
  created_at: string;
  updated_at: string;
}

export interface WorkflowEventResponse {
  id: string;
  stage: WorkflowStage;
  status: string;
  message: string | null;
  duration_ms: number | null;
  created_at: string;
}

export interface WorkflowResultResponse {
  id: string;
  status: string;
  classification: Record<string, unknown>;
  extracted_facts: unknown[];
  reconciliation: Record<string, unknown>;
  examination: Record<string, unknown>;
  human_decision: string | null;
  created_at: string;
  updated_at: string;
}

export interface RunDetailsResponse {
  run: RunResponse;
  findings: FindingResponse[];
  report: ReportResponse | null;
  workflow_events: WorkflowEventResponse[];
  workflow_result: WorkflowResultResponse | null;
}

export interface ReviewResponse {
  run_id: string;
  status: RunStatus;
  stage: WorkflowStage;
  requires_review: boolean;
  findings: FindingResponse[];
}

export interface RunCreate {
  name: string;
}

export interface HumanDecisionRequest {
  decision: string;
}

export interface WorkflowRunResponse {
  thread_id: string;
  state: Record<string, unknown>;
}