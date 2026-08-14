import { useEffect } from "react";
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
  useEffect(() => {
    if (!details) {
      return;
    }

    const run = details.run;
    const shouldPoll =
      run.status === "pending" ||
      run.status === "running";

    if (!shouldPoll) {
      return;
    }

    const interval = window.setInterval(async () => {
      try {
        const updatedDetails = await getRunDetails(runId);
        onUpdate(updatedDetails);
      } catch (err) {
        console.error("Polling error:", err);
      }
    }, intervalMs);

    return () => {
      window.clearInterval(interval);
    };
  }, [runId, details, onUpdate, intervalMs]);
}
