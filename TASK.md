# Task Instructions & Development Workflow

This document outlines the tasks, technical requirements, and execution workflow followed while building the **DocTask** platform.

---

## Project Overview

DocTask is an enterprise-grade document review and compliance verification system designed to analyze multi-format legal documents, detect cross-document contradictions, enforce custom review playbooks, and support human-in-the-loop decision-making with crash-resilience.

---

## Core Task Milestones

### Task 1: Ingestion, Parsing, & Vector Storage
- [x] **Multi-format Document Loaders**: Implement loaders for `.pdf`, `.docx`, and `.txt` files (`backend/app/ingestion/loaders/`).
- [x] **Content-Based MIME Detection**: Integrate binary magic-byte inspection in `DocumentLoaderFactory` to safely determine file types without trusting user-supplied extensions.
- [x] **Token-Aware Text Chunking**: Implement `TextChunker` with configurable token lengths and sliding-window overlap to preserve context across clause boundaries.
- [x] **Local Embedding Generation**: Integrate `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions) for local, deterministic vector generation without external API latency.
- [x] **PostgreSQL `pgvector` Integration**: Store embeddings and chunk metadata in PostgreSQL with cosine similarity search (`backend/app/persistence/repositories/vector.py`).
- [x] **Pluggable File Storage**: Build `StorageService` with `LocalStorageAdapter` for local disk and `GoogleCloudStorageAdapter` for Google Cloud Storage.

---

### Task 2: LangGraph Orchestration & Checkpointing Engine
- [x] **State Definition**: Model the complete workflow state schema in `WorkflowState` (`backend/app/workflow/state.py`).
- [x] **Classification Node**: Implement `ClassifyNode` with Gemini 2.5 to categorize agreements, identify parties, and distinguish rules/playbooks from source contracts.
- [x] **Extraction Node**: Implement `ExtractNode` to pull structured facts, dates, governing law, obligations, and citations with page numbers.
- [x] **Reconciliation Node**: Implement `ReconcileNode` to cross-examine documents and identify conflicting clauses, liability discrepancies, and contradictions.
- [x] **Rule Examination Node**: Implement `ExamineNode` (rule checker) to evaluate contractual facts against user-provided review checklists and playbooks.
- [x] **Human Review Interruption Nodes**:
  - `human_review`: Macro conflict gate allowing approve (proceed) or reject (route to `ReviseNode`).
  - `findings_review`: Micro finding gate synchronizing individual violations to PostgreSQL and suspending execution via `langgraph.types.interrupt()`.
- [x] **Idempotent Commit Node**: Implement `CommitNode` to assemble approved findings into a versioned Markdown report deliverable (`Report` model).
- [x] **Durable Checkpointing (`PostgresSaver`)**: Back the LangGraph engine with PostgreSQL checkpointer tables, ensuring zero data loss and full kill-and-resume capability using `thread_id = run_id`.

---

### Task 3: Interfaces, Machine Drivers & Continuous Ingestion
- [x] **FastAPI REST API**:
  - `/api/v1/runs`: Create (JSON & multipart), list, retrieve, cancel, and delete runs.
  - `/api/v1/runs/{id}/start`: Trigger workflow graph execution.
  - `/api/v1/runs/{id}/decision`: Resume global workflow interruptions.
  - `/api/v1/runs/{id}/findings/{finding_id}/decision`: Submit granular finding decisions (`approve`/`reject`), auto-resuming upon completion.
  - `/api/v1/runs/{id}/documents`: Ingest source documents and review rules.
  - `/api/v1/runs/{id}/details` & `/events`: Full audit trail and report deliverable access.
- [x] **Model Context Protocol (FastMCP) Server**:
  - Expose 9 native MCP tools in `backend/app/mcp/server.py` for AI agent interaction (`create_run`, `upload_document`, `upload_review_rules`, `start_run`, `get_run_status`, `get_review_findings`, `decide_finding`, `get_run_details`, `process_update`).
- [x] **Watched Folder & Incremental Updates**:
  - Implement directory scanning for `storage/watch` with SHA-256 deduplication.
  - Create parent-child linked runs (`parent_id`) to analyze newly arrived documents incrementally without re-running unchanged parent documents.
- [x] **React 18 + Vite Web Dashboard**:
  - Build interactive user interface with real-time Run Timeline, Findings Review Queue, Document Uploads, and Audit Changelog.

---

### Task 4: Reliability, Hardening, Performance & Documentation
- [x] **LLM Model Fallback Cascade**: Implement automatic failover from `gemini-2.5-pro` to `gemini-2.5-flash` and `gemini-2.0-flash` on HTTP 429/503/quota exhaustion, wrapped in `tenacity` exponential retries.
- [x] **Cold-Start Performance Optimization**: Pre-warm the embedding model in a background daemon thread on FastAPI startup (`lifespan`) and clamp PyTorch to single-threaded CPU execution (`torch.set_num_threads(1)`), eliminating Render/Cloud Run 30s gateway timeouts.
- [x] **Containerization & Deployment**:
  - Multi-stage `Dockerfile` and `docker-compose.yml` for local development.
  - Cloud Run / Render deployment configurations with dynamic `$PORT` handling and health check endpoints.
- [x] **Comprehensive Documentation**:
  - `docs/architecture.drawio`: Interactive visual architecture diagram.
  - `docs/architecture.png`: High-resolution rendered architecture image.
  - `docs/api.md`: Complete REST and MCP tool reference with cURL/Python examples.
  - `docs/decisions.md`: 10 Architectural Decision Records (ADRs) with context, decisions, and trade-offs.
  - `docs/writeup.md`: Formal Task 4 engineering write-up.
  - `PROGRESS.md`: Chronological development and milestone log.

---

## Development & Verification Workflow

### 1. Database & Local Setup
```bash
# Start PostgreSQL with pgvector extension
docker compose up -d

# Run Alembic migrations
cd backend
PYTHONPATH=. ../venv/bin/alembic upgrade head
```

### 2. Code Quality & Linting
```bash
# Run Black code formatter
make format

# Run Ruff linter
make lint
```

### 3. Test Suite Execution
```bash
# Run unit tests
cd backend
../venv/bin/pytest tests/unit/ -v

# Run integration tests
cd backend
../venv/bin/pytest tests/integration/ -v
```

### 4. Running the Application
```bash
# Start backend API (Port 8000)
cd backend
../venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Start frontend dashboard (Port 5173)
cd frontend
npm install
npm run dev
```
