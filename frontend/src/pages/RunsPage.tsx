import { useEffect, useState } from "react";
import { getRuns } from "../api/runs";
import type { RunResponse } from "../api/types";

export default function RunsPage() {
  const [runs, setRuns] = useState<RunResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadRuns() {
      try {
        setLoading(true);
        setError(null);

        const data = await getRuns();

        if (!cancelled) {
          setRuns(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load runs.",
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadRuns();

    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return <p>Loading runs...</p>;
  }

  if (error) {
    return <p role="alert">{error}</p>;
  }

  return (
    <main>
      <header>
        <h1>Runs</h1>
      </header>

      {runs.length === 0 ? (
        <p>No runs yet.</p>
      ) : (
        <section>
          {runs.map((run) => (
            <article key={run.id}>
              <h2>{run.name}</h2>

              <p>
                Status: <strong>{run.status}</strong>
              </p>

              <p>
                Stage: <strong>{run.stage}</strong>
              </p>

              <p>
                Created:{" "}
                {new Date(run.created_at).toLocaleString()}
              </p>
            </article>
          ))}
        </section>
      )}
    </main>
  );
}