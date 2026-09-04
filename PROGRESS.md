# DocTask Development Progress Log & Audit History

This document chronicles the chronological development log, engineering milestones, technical iterations, assumptions, and validation results across the lifecycle of the **DocTask** project.

---

## Chronological Development Milestones

### Phase 1: Project Scaffolding & Foundations
- **Repository Setup**: Initialized directory layout separating `backend/` (FastAPI, SQLAlchemy, LangGraph), `frontend/` (React, TypeScript, Vite), and `docs/`.
- **Relational Domain Models**: Designed SQLAlchemy models with Alembic migrations:
  - `Run`: Tracks lifecycle status (`pending`, `running`, `waiting_for_review`, `completed`, `failed`), stages, and `parent_id` for incremental runs.
  - `Document` & `DocumentChunk`: Multi-file records with SHA-256 hash checksums, `is_rules` flag, and pgvector embeddings.
  - `Finding`: Captures severity, descriptions, citations, and human review decisions (`pending`, `approved`, `rejected`).
  - `Report`: Versioned final deliverable storing generated markdown summaries and approved findings.
  - `WorkflowEvent` & `WorkflowResult`: Fine-grained telemetry tracking stage execution durations and raw intermediate outputs.
- **Database Migrations**: Generated initial Alembic migration enabling the `vector` extension and indexing foreign keys.

---

### Phase 2: Ingestion & Vector Pipeline Implementation
- **Multi-Format Loaders**: Implemented `PyMuPDFLoader` (PDF), `DocxLoader` (DOCX), and `TxtLoader` (TXT).
- **Magic-Byte Sniffing**: Replaced file extension assumptions in `DocumentLoaderFactory` with binary MIME magic-byte sniffing (`%PDF-`, Zip PK header, UTF-8/ASCII), preventing parser crashes on spoofed or stripped extensions.
- **Token-Aware Chunking**: Built `TextChunker` using recursive character splitting with sliding token overlap.
- **pgvector Vector Store**: Implemented `VectorRepository` with cosine similarity search for finding relevant context during extraction and rule examination.
- **Pluggable Storage Layer**: Created `StorageService` with `LocalStorageAdapter` for local disk and `GoogleCloudStorageAdapter` for Google Cloud Storage, configurable via `STORAGE_BACKEND`.

---

### Phase 3: LangGraph Workflow Engine & Checkpointing
- **Workflow State Design**: Structured `WorkflowState` encapsulating input document IDs, classification, extracted facts, detected contradictions, playbook examination results, human decisions, and error states.
- **Core Workflow Nodes**:
  - `ClassifyNode`: Classifies document types and isolates review playbooks.
  - `ExtractNode`: Extracts clauses, obligations, dates, parties, and exact page citations.
  - `ReconcileNode`: Identifies contradictions across multi-document agreements (e.g. conflicting terms or governing jurisdictions).
  - `ExamineNode`: Evaluates document facts against uploaded rule checklists.
  - `CommitNode`: Idempotently builds the final markdown deliverable from approved findings and updates report versions.
  - `UpdateNode`: Completes the workflow execution and synchronizes status flags.
- **Two-Tier Human Review Interruption**:
  - Engineered global conflict pause (`human_review`) with approve/reject branch routing to `ReviseNode`.
  - Engineered granular finding review pause (`findings_review`) using `langgraph.types.interrupt()`, storing findings in the database and allowing asynchronous approval per finding.
- **Durable Checkpointing**: Configured `PostgresSaver` in `backend/app/workflow/checkpointer.py`. Checkpoint tables (`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`) are automatically initialized on startup, enabling seamless kill-and-resume execution via `thread_id = run_id`.

---

### Phase 4: API Gateway, Machine Driver & Continuous Ingestion
- **FastAPI Endpoints**:
  - Standardized `/api/v1/runs` endpoints for creating runs (via JSON or multipart upload), starting workflows, retrieving details, and canceling runs.
  - Implemented `/api/v1/runs/{id}/findings/{finding_id}/decision` for per-finding human approvals, auto-resuming paused workflows when all findings are resolved.
  - Built `/api/v1/documents` for querying uploaded documents with `is_rules` filtering.
- **Model Context Protocol (FastMCP)**:
  - Built `backend/app/mcp/server.py` exposing 9 standardized tools for autonomous AI agent systems (`create_run`, `upload_document`, `upload_review_rules`, `start_run`, `get_run_status`, `get_review_findings`, `decide_finding`, `get_run_details`, `process_update`).
- **Watched Folder Scanning**:
  - Built directory watcher for `storage/watch` with SHA-256 deduplication to skip already-indexed files.
  - Implemented parent-child run relationships (`parent_id`) allowing incremental delta updates without reprocessing entire document corpuses.
- **React 18 Frontend Dashboard**:
  - Developed UI with real-time Run Timeline (`useRunPolling`), interactive Findings Review Queue, Document Upload modals, and ChangeLog views.

---

### Phase 5: Production Hardening, Performance & Cloud Deployment
- **Cold-Start Optimization**:
  - Discovered that cold-starting `sentence-transformers` on 1-core containers (Render/Cloud Run) caused 20+ second delays, exceeding 30-second gateway proxy timeouts.
  - Resolved by launching embedding pre-warming in a background daemon thread during FastAPI lifespan startup and clamping PyTorch to single-threaded CPU execution (`torch.set_num_threads(1)`).
- **LLM Model Fallback Cascade**:
  - Implemented automatic fallback chain from `gemini-2.5-pro` to `gemini-2.5-flash` and `gemini-2.0-flash` on HTTP 429/503 or quota limits, with `tenacity` exponential retries.
- **Cloud Run / Render Compatibility**:
  - Supported dynamic `$PORT` environment variable in Docker startup commands.
  - Added root `/` and `/health` health-check endpoints.
  - Configured CORS for `*.vercel.app` deployments.
  - Added GCS adapter support with clean environment-driven switching.

---

### Phase 6: Documentation Suite Completion
- **`docs/architecture.drawio`**: Created complete, editable XML architecture diagram for Draw.io / diagrams.net.
- **`docs/architecture.png`**: Rendered high-resolution (3200x2300) visual diagram capturing all subsystems, flows, and data boundaries.
- **`docs/api.md`**: Authored exhaustive REST API reference, FastMCP tool specs, and Python SDK driver examples.
- **`docs/decisions.md`**: Documented 10 Architectural Decision Records (ADRs) with rationale, alternatives, and trade-offs.
- **`docs/writeup.md`**: Completed formal Task 4 engineering write-up.
- **`TASK.md`** & **`PROGRESS.md`**: Fully populated project requirements, checklists, and execution logs.

---

### Phase 7: Node Error Observability & Structured Document Remediation
- **Comprehensive Error Boundaries**:
  - Implemented universal error handling across all LangGraph nodes without hardcoding node names.
  - Added structured error hierarchy (`backend/app/core/errors.py`) with retryability classification and sanitization.
  - Persisted error telemetry (`error_type`, `error_message`, `retryable`, `attempt_number`) to `workflow_events` and database.
  - Extended frontend workflow stepper and node details panel with live error diagnosis, attempt counters, and retry controls.
- **Agentic Document Mutation & Post-Edit Validation**:
  - Structured change proposals (`DocumentChangeProposal`) supporting `INSERT_PARAGRAPH`, `REPLACE_PARAGRAPH`, `DELETE_PARAGRAPH`, and `APPEND_SECTION`.
  - Added deterministic string/paragraph patching (`apply_edits`) and post-edit integrity validation (`validate_edits`).
  - Added full export and download routes (`/api/v1/runs/{id}/export`, `/export/download`, `/final-document`) with cryptographic SHA-256 section comparison.

---

### Phase 8: Universal Cloud LLM Multi-Provider Model Pool & Cloud Deployment
- **Universal Cloud Model Pool & Router**:
  - Engineered thread-safe `ModelPool` with dynamic rotation across Google Gemini (`gemini-2.5-flash`, `gemini-2.5-flash-lite`), Groq (`llama-3.3-70b-versatile`), and OpenRouter (`openrouter/free`).
  - Implemented 300s automatic cooldown window on quota/rate-limit errors with transparent self-healing.
  - Decoupled LangGraph nodes from specific model names; all nodes query the unified router with capability filtering (`STRUCTURED_OUTPUT` vs `TEXT_GENERATION`).
- **Cloud Infrastructure Deployment**:
  - Applied database schema migrations (`c4f1e83b9a12` and `d5e2390f4a13`) to production Render PostgreSQL database.
  - Built and deployed containerized backend to Google Cloud Run (`us-central1`).
  - Synchronized and verified frontend edge deployment on Vercel.

---

## Key Assumptions & Constraints

1. **Document Formats**: Primary enterprise support is focused on `.pdf`, `.docx`, and `.txt` files. Non-standard proprietary formats are converted or parsed via fallback plain text.
2. **Deterministic Checkpointing**: Workflow resumption assumes the underlying PostgreSQL database remains accessible and transactions are committed at each node boundary.
3. **Single Active Review Session**: While findings can be reviewed asynchronously via API or UI, concurrent write locks prevent conflicting decisions from colliding during workflow resumption.
4. **Local vs Cloud Embedding Execution**: Local CPU-based embedding (`sentence-transformers/all-MiniLM-L6-v2`) was selected over remote embedding APIs to maintain deterministic latency, zero per-chunk API costs, and full offline testability.

---

## Verification & Test Results

- **Unit Tests**: All repository, loader, chunker, and model factory unit tests pass (`pytest backend/tests/unit/`).
- **Integration Tests**: Workflow state transitions, human-in-the-loop pause/resume cycles, and API route endpoints pass (`pytest backend/tests/integration/`).
- **Kill-and-Resume Validation**: Tested by issuing `SIGTERM` to the backend process during workflow execution; upon process restart, triggering `/start` successfully retrieved the thread state and resumed without duplicated node executions.
- **MIME Sniffing Validation**: Tested with misnamed files (e.g. DOCX renamed to `.pdf` and plain text without extensions); correctly routed to their appropriate parsers without errors.
