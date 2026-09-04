import { useEffect, useRef } from "react";
import type { RunDetailsResponse } from "../api/types";
import { getRunDetails } from "../api/runs";

interface UseRunPollingProps {
  runId: string;
  details: RunDetailsResponse | null;
  onUpdate: (details: RunDetailsResponse) => void;
  intervalMs?: number;
}

export function useRunPolling({
  runId,
  details,
  onUpdate,
  intervalMs = 2000,
}: UseRunPollingProps) {
  const errorCountRef = useRef(0);

  useEffect(() => {
    if (!details) {
      return;
    }

    const run = details.run;
    const isWaitingForReview = run.status === "waiting_for_review";
    const shouldPoll =
      run.status === "pending" ||
      run.status === "running" ||
      isWaitingForReview;

    if (!shouldPoll) {
      return;
    }

    const effectiveInterval = isWaitingForReview ? Math.max(intervalMs, 4000) : intervalMs;

    const interval = window.setInterval(async () => {
      try {
        const updatedDetails = await getRunDetails(runId);
        errorCountRef.current = 0;
        onUpdate(updatedDetails);
      } catch (err) {
        errorCountRef.current += 1;
        if (errorCountRef.current <= 3) {
          console.warn(`Polling attempt failed (${errorCountRef.current}), will retry automatically...`, err);
        }
      }
    }, effectiveInterval);

    return () => {
      window.clearInterval(interval);
    };
  }, [runId, details, onUpdate, intervalMs]);
}
