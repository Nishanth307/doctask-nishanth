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
  | "pending"
  | "needs_resolution";

export type ApplicationStatus =
  | "pending"
  | "applied"
  | "rejected"
  | "failed"
  | "not_applicable";

export type ValidationStatus =
  | "pending"
  | "passed"
  | "failed"
  | "skipped";

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
  parent_id?: string | null;
  pending_finding_count?: number;
  approved_finding_count?: number;
  rejected_finding_count?: number;
}

export interface FindingSourceCitation {
  document?: string;
  value?: string;
  source_text?: string;
  confidence?: number;
}

export interface FindingCitation {
  type?: string;
  semantic_key?: string;
  sources?: FindingSourceCitation[];
  issues?: string[];
  [key: string]: unknown;
}

export interface FindingResponse {
  id: string;
  run_id?: string;
  document_id?: string | null;
  title: string;
  description: string;
  severity: FindingSeverity;
  review_decision: ReviewDecision;
  citation: FindingCitation | null;
  finding_metadata: Record<string, unknown> | null;
  created_at: string;

  // Canonical proposed-edit fields
  original_value: string | null;
  proposed_value: string | null;
  proposed_edit: string | null;
  source_location: string | null;

  // Lifecycle tracking
  application_status: ApplicationStatus | null;
  validation_status: ValidationStatus | null;
}

export interface ChangeRecord {
  change_id: string;
  finding_id: string;
  run_id: string;
  document_id: string | null;
  source_location: string | null;
  original_value: string;
  new_value: string;
  proposed_edit: string | null;
  reviewer_decision: string;
  application_status: string;
  reason: string;
  applied_at: string;
}

export interface SectionHashInfo {
  before_hash: string;
  after_hash: string;
  changed: boolean;
}

export interface ReportResponse {
  id: string;
  content: string;
  version: number;
  approved: boolean;
  created_at: string;
  updated_at: string;

  // Final document artifact
  final_content: string | null;
  final_file_path: string | null;
  validation_passed: boolean | null;
  validation_summary: string | null;
  change_history: ChangeRecord[] | null;
  section_hashes: Record<string, SectionHashInfo> | null;
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

export interface ExportResponse {
  run_id: string;
  run_name: string;
  status: RunStatus;
  stage: WorkflowStage;
  has_final_document: boolean;
  final_content: string | null;
  total_findings: number;
  approved_findings: number;
  rejected_findings: number;
  applied_changes: number;
  failed_changes: number;
  validation_passed: boolean | null;
  validation_summary: string | null;
  change_history: ChangeRecord[];
  section_hashes: Record<string, SectionHashInfo>;
  findings: FindingResponse[];
}