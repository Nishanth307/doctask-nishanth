import { apiRequest } from "./client";

import type {
    HumanDecisionRequest,
    ReviewResponse,
    RunCreate,
    RunDetailsResponse,
    RunResponse,
    WorkflowRunResponse,
} from "./types";

export function getRuns(): Promise<RunResponse[]> {
    return apiRequest<RunResponse[]>("/runs");
}

export function createRun(payload: RunCreate): Promise<RunResponse>{
    return apiRequest<RunResponse>("/runs",{
        method: "POST",
        body: JSON.stringify(payload),
    });
}

export function getRun(runId: string): Promise<RunResponse> {
    return apiRequest<RunResponse>(`/runs/${runId}`);
}

export function getRunDetails(
    runId: string,
): Promise<RunDetailsResponse> {
    return apiRequest<RunDetailsResponse>(
        `/runs/${runId}/details`,
    );
}

export function startRun(
    runId: string,
): Promise<WorkflowRunResponse> {
    return apiRequest<WorkflowRunResponse>(
        `/runs/${runId}/start`,
        {
            method: "POST"
        },
    );
}

export function getRunReview(
    runId: string,
): Promise<ReviewResponse> {
    return apiRequest<ReviewResponse>(`/runs/${runId}/review`);
}

export function submitHumanDecision(
    runId: string,
    payload: HumanDecisionRequest,
): Promise<WorkflowRunResponse> {
    return apiRequest<WorkflowRunResponse>(
        `/runs/${runId}/decision`,
        {
            method: "POST",
            body: JSON.stringify(payload),
        },
    );
}