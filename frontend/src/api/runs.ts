import { apiClient } from "./client";

import type {
    HumanDecisionRequest,
    ReviewResponse,
    RunDetailsResponse,
    RunResponse,
    WorkflowRunResponse,
    FindingResponse,
} from "./types";

export function getRuns(): Promise<RunResponse[]> {
    return apiClient<RunResponse[]>("/runs");
}

export function createRun(
  name: string,
  files: File[],
  rulesFile: File | null,
): Promise<RunResponse> {
  const formData = new FormData();
  formData.append("name", name);
  for (const file of files) {
    formData.append("files", file);
  }
  if (rulesFile) {
    formData.append("rules_file", rulesFile);
  }

  return apiClient<RunResponse>("/runs", {
    method: "POST",
    body: formData,
  });
}

export function getRun(runId: string): Promise<RunResponse> {
    return apiClient<RunResponse>(`/runs/${runId}`);
}

export function getRunDetails(
    runId: string,
): Promise<RunDetailsResponse> {
    return apiClient<RunDetailsResponse>(
        `/runs/${runId}/details`,
    );
}

export function startRun(
    runId: string,
): Promise<WorkflowRunResponse> {
    return apiClient<WorkflowRunResponse>(
        `/runs/${runId}/start`,
        {
            method: "POST"
        },
    );
}

export function retryRun(
    runId: string,
): Promise<WorkflowRunResponse> {
    return apiClient<WorkflowRunResponse>(
        `/runs/${runId}/retry`,
        {
            method: "POST",
        },
    );
}

export function retryNode(
    runId: string,
    nodeName: string,
): Promise<WorkflowRunResponse> {
    return apiClient<WorkflowRunResponse>(
        `/runs/${runId}/retry/${encodeURIComponent(nodeName)}`,
        {
            method: "POST",
        },
    );
}

export function getRunReview(
    runId: string,
): Promise<ReviewResponse> {
    return apiClient<ReviewResponse>(`/runs/${runId}/review`);
}

export function submitHumanDecision(
    runId: string,
    payload: HumanDecisionRequest,
): Promise<WorkflowRunResponse> {
    return apiClient<WorkflowRunResponse>(
        `/runs/${runId}/decision`,
        {
            method: "POST",
            body: JSON.stringify(payload),
        },
    );
}

export function cancelRun(runId: string): Promise<RunResponse> {
  return apiClient<RunResponse>(`/runs/${runId}/cancel`, {
    method: "POST",
  });
}

export function deleteRun(runId: string): Promise<void> {
  return apiClient<void>(`/runs/${runId}`, {
    method: "DELETE",
  });
}

export function submitFindingDecision(
  runId: string,
  findingId: string,
  decision: "approve" | "reject",
): Promise<FindingResponse> {
  return apiClient<FindingResponse>(`/runs/${runId}/findings/${findingId}/decision`, {
    method: "POST",
    body: JSON.stringify({ decision }),
  });
}