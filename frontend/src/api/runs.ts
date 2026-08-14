import { apiClient } from "./client";

import type {
    HumanDecisionRequest,
    ReviewResponse,
    RunCreate,
    RunDetailsResponse,
    RunResponse,
    WorkflowRunResponse,
} from "./types";

export function getRuns(): Promise<RunResponse[]> {
    return apiClient<RunResponse[]>("/runs");
}

export function createRun(payload: RunCreate): Promise<RunResponse>{
    return  apiClient<RunResponse>("/runs",{
        method: "POST",
        body: JSON.stringify(payload),
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