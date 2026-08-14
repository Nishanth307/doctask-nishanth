import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  createRun,
  getRuns,
} from "../api/runs";

import type { RunResponse } from "../api/types";

export default function RunsPage() {
  const navigate = useNavigate();

  const [runs, setRuns] = useState<RunResponse[]>([]);
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        const result = await getRuns();
        if (active) {
          setRuns(result);
        }
      } catch (err) {
        if (active) {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load runs",
          );
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void load();

    return () => {
      active = false;
    };
  }, []);

  const handleRetry = async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await getRuns();
      setRuns(result);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to load runs",
      );
    } finally {
      setLoading(false);
    }
  };

  const handleCreateRun = async (
    event: React.FormEvent<HTMLFormElement>,
  ) => {
    event.preventDefault();

    const trimmedName = name.trim();

    if (!trimmedName) {
      return;
    }

    try {
      setCreating(true);
      setError(null);

      const run = await createRun({
        name: trimmedName,
      });

      setName("");

      navigate(`/runs/${run.id}`);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to create run",
      );
    } finally {
      setCreating(false);
    }
  };

  return (
    <div>
      <header className="page-header">
        <h1>Runs</h1>
        <p>
          Create and monitor document-processing workflows.
        </p>
      </header>

      <section className="card">
        <h2>Create Run</h2>

        <form onSubmit={handleCreateRun} className="run-form">
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Run name"
            disabled={creating}
          />

          <button
            type="submit"
            disabled={creating || !name.trim()}
          >
            {creating ? "Creating..." : "Create Run"}
          </button>
        </form>
      </section>

      {error && (
        <section className="card" role="alert">
          <strong>Something went wrong</strong>
          <p>{error}</p>

          <button
            type="button"
            onClick={handleRetry}
          >
            Retry
          </button>
        </section>
      )}

      <section className="card">
        <h2>Recent Runs</h2>

        {loading ? (
          <p>Loading runs...</p>
        ) : runs.length === 0 ? (
          <p>No runs yet. Create your first run above.</p>
        ) : (
          <div className="run-list">
            {runs.map((run) => (
              <article key={run.id} className="run-item">
                <div className="run-item-header">
                  <h3>{run.name}</h3>
                  <span
                    className={`status-badge status-${run.status}`}
                  >
                    {run.status.replaceAll("_", " ")}
                  </span>
                </div>

                <p>
                  Stage: {run.stage}
                </p>

                <p>
                  Created:{" "}
                  {new Date(run.created_at).toLocaleString()}
                </p>

                <button
                  type="button"
                  onClick={() =>
                    navigate(`/runs/${run.id}`)
                  }
                >
                  View Run
                </button>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}