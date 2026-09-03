import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { DocumentUpload } from "../components/runs/DocumentUpload";
import { StatusBadge } from "../components/common/StatusBadge";
import { FileText, BookOpen, CornerDownRight } from "lucide-react";

import {
  createRun,
  getRuns,
  cancelRun,
  deleteRun,
} from "../api/runs";

import type { RunResponse } from "../api/types";

export default function RunsPage() {
  const navigate = useNavigate();

  const [runs, setRuns] = useState<RunResponse[]>([]);
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [files, setFiles] = useState<File[]>([]);
  const [rulesFile, setRulesFile] = useState<File | null>(null);

  const handleCancelRun = async (runId: string) => {
    try {
      setError(null);
      const updated = await cancelRun(runId);
      setRuns((prev) => prev.map((r) => (r.id === runId ? updated : r)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to cancel run");
    }
  };

  const handleDeleteRun = async (runId: string, runName: string) => {
    if (!window.confirm(`Delete "${runName}"?\n\nThis will permanently remove this run and its associated workflow data.`)) {
      return;
    }
    try {
      setError(null);
      await deleteRun(runId);
      setRuns((prev) => prev.filter((r) => r.id !== runId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete run");
    }
  };

  // Filter & sort states
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [stageFilter, setStageFilter] = useState("all");
  const [sortBy, setSortBy] = useState("newest");

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
    if (creating) {
      return;
    }

    const trimmedName = name.trim();

    if (!trimmedName || files.length === 0 || !rulesFile) {
      return;
    }

    try {
      setCreating(true);
      setError(null);

      const run = await createRun(trimmedName, files, rulesFile);

      setName("");
      setFiles([]);
      setRulesFile(null);

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

  // Local filtering and sorting logic
  const filteredRuns = runs
    .filter((run) => {
      const matchesSearch = run.name.toLowerCase().includes(search.toLowerCase());
      const matchesStatus = statusFilter === "all" || run.status === statusFilter;
      const matchesStage = stageFilter === "all" || run.stage === stageFilter;
      return matchesSearch && matchesStatus && matchesStage;
    })
    .sort((a, b) => {
      if (sortBy === "newest") {
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      }
      if (sortBy === "oldest") {
        return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      }
      if (sortBy === "name_asc") {
        return a.name.localeCompare(b.name);
      }
      if (sortBy === "name_desc") {
        return b.name.localeCompare(a.name);
      }
      return 0;
    });

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

        <form onSubmit={handleCreateRun} className="run-form" style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="e.g. Acme Contract Review - August 2026"
            disabled={creating}
            style={{ width: "100%" }}
          />
          <div style={{ fontSize: "12px", color: "#64748b", marginTop: "-4px" }}>
            ⓘ A short name to identify this workflow run.
          </div>

          <DocumentUpload
            files={files}
            onFilesChange={setFiles}
            disabled={creating}
            label="Source documents"
            description="Drop source documents here"
          />

          <DocumentUpload
            files={rulesFile ? [rulesFile] : []}
            onFilesChange={(newFiles) => setRulesFile(newFiles[newFiles.length - 1] ?? null)}
            disabled={creating}
            label="Review rules"
            description="Drop rules / playbook / style guide here"
            multiple={false}
          />

          <button
            type="submit"
            disabled={creating || !name.trim() || files.length === 0 || !rulesFile}
            style={{ alignSelf: "flex-start", marginTop: "8px" }}
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
        <h2>Run History</h2>

        {/* Filter controls */}
        {runs.length > 0 && (
          <div className="run-filters">
            <input
              type="text"
              placeholder="Search runs..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />

            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="all">All statuses</option>
              <option value="pending">Pending</option>
              <option value="running">Running</option>
              <option value="waiting_for_review">Waiting for review</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
              <option value="cancelled">Cancelled</option>
            </select>

            <select
              value={stageFilter}
              onChange={(e) => setStageFilter(e.target.value)}
            >
              <option value="all">All stages</option>
              <option value="ingestion">Ingestion</option>
              <option value="classification">Classification</option>
              <option value="extraction">Extraction</option>
              <option value="reconciliation">Reconciliation</option>
              <option value="examination">Examination</option>
              <option value="review">Review</option>
              <option value="commit">Commit</option>
            </select>

            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
            >
              <option value="newest">Newest first</option>
              <option value="oldest">Oldest first</option>
              <option value="name_asc">Name A–Z</option>
              <option value="name_desc">Name Z–A</option>
            </select>
          </div>
        )}

        {loading ? (
          <p>Loading runs...</p>
        ) : runs.length === 0 ? (
          <div className="empty-state">
            <h3>No runs yet</h3>
            <p>Create your first document-processing run.</p>
          </div>
        ) : filteredRuns.length === 0 ? (
          <div className="empty-state">
            <h3>No matching runs</h3>
            <p>Try changing your search or filters.</p>
          </div>
        ) : (
          <div className="run-list">
            {filteredRuns.map((run) => (
              <article key={run.id} className="run-item">
                <div className="run-item-header">
                  <div>
                    <h3 className="run-name" title={run.name} style={{ margin: 0 }}>
                      {run.name}
                    </h3>
                    {run.parent_id && (
                      <span className="incremental-chip">
                        <CornerDownRight size={12} /> Incremental Update
                      </span>
                    )}
                  </div>
                  <StatusBadge status={run.status} size="sm" />
                </div>

                {run.documents && run.documents.length > 0 && (
                  <div className="run-card-documents">
                    {run.documents.filter(d => !d.is_rules).map((doc) => (
                      <div key={doc.id} className="run-card-document-item" title={doc.filename}>
                        <FileText size={13} className="text-slate-400 inline mr-1" /> {doc.filename}
                      </div>
                    ))}
                    {run.documents.filter(d => d.is_rules).map((doc) => (
                      <div key={doc.id} className="run-card-document-item" title={doc.filename} style={{ fontStyle: "italic", color: "#64748b" }}>
                        <BookOpen size={13} className="text-slate-400 inline mr-1" /> {doc.filename} (Rules)
                      </div>
                    ))}
                  </div>
                )}

                <p>
                  Stage: {run.stage}
                </p>

                <p>
                  Created:{" "}
                  {new Date(run.created_at).toLocaleString()}
                </p>

                <div className="run-item-actions">
                  <button
                    type="button"
                    onClick={() => navigate(`/runs/${run.id}`)}
                  >
                    View Run
                  </button>

                  {(run.status === "pending" || run.status === "running" || run.status === "waiting_for_review") && (
                    <button
                      type="button"
                      className="btn-cancel"
                      onClick={() => handleCancelRun(run.id)}
                    >
                      Cancel
                    </button>
                  )}

                  {(run.status === "completed" || run.status === "failed" || run.status === "cancelled") && (
                    <button
                      type="button"
                      className="btn-delete"
                      onClick={() => handleDeleteRun(run.id, run.name)}
                    >
                      Delete
                    </button>
                  )}
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}