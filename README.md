# doctask-nishanth 

> 🌐 **Live Application Dashboard**: [https://frontend-alpha-flame-36.vercel.app/runs](https://frontend-alpha-flame-36.vercel.app/runs)

```
doctask-nishanth/
├── README.md                      # setup, architecture, supported formats, assumptions, trade-offs
├── TASK.md                        # instructions and workflow followed while building
├── PROGRESS.md                    # development log, assumptions, and decisions
├── LICENSE
├── Makefile                       # one-command setup/run/test helpers
├── docker-compose.yml             # local development services
├── .env.example                   # environment variable template
├── .gitignore                     # ignore secrets, logs, virtual environments
│
├── backend/
│   ├── pyproject.toml             # Python dependencies and project configuration
│   ├── alembic/                   # database migrations
│   ├── tests/
│   │   ├── unit/                  # unit tests
│   │   ├── integration/           # integration tests
│   │   └── fixtures/              # mocked LLMs, sample documents, test data
│   │
│   └── app/
│       ├── main.py                # FastAPI application entry point
│       │
│       ├── api/
│       │   ├── routes_ingest.py   # upload/watch document endpoints
│       │   ├── routes_runs.py     # start, stop, resume workflow runs
│       │   └── routes_review.py   # approve/reject findings and updates
│       │
│       ├── mcp/
│       │   ├── server.py          # MCP server entry point
│       │   ├── tools.py           # MCP tool definitions
│       │   └── handlers.py        # executes MCP tool requests
│       │
│       ├── workflow/
│       │   ├── graph.py           # LangGraph workflow definition
│       │   ├── state.py           # shared workflow state
│       │   ├── checkpointer.py    # save and restore workflow checkpoints
│       │   └── nodes/
│       │       ├── classify.py    # identify document type
│       │       ├── extract.py     # extract structured facts with citations
│       │       ├── reconcile.py   # detect contradictions across documents
│       │       ├── rule_checker.py     # validate against user rules
│       │       └── update.py      # generate focused document updates
│       │
│       ├── services/
│       │   ├── llm.py             # wrapper around LLM providers
│       │   ├── embeddings.py      # embedding generation
│       │   └── citations.py       # source citation management
│       │
│       ├── prompts/
│       │   ├── classify.md        # classification prompt
│       │   ├── extract.md         # extraction prompt
│       │   ├── reconcile.md       # contradiction detection prompt
│       │   ├── examine.md         # rule checking prompt
│       │   └── update.md          # incremental update prompt
│       │
│       ├── persistence/
│       │   ├── models/            # SQLAlchemy database models
│       │   ├── repositories/      # database access layer
│       │   └── vector_store.py    # pgvector retrieval
│       │
│       ├── schemas/
│       │   ├── run.py             # run request/response models
│       │   ├── review.py          # review API schemas
│       │   ├── document.py        # document schemas
│       │   └── finding.py         # findings and reports schemas
│       │
│       ├── ingestion/
│       │   ├── watcher.py         # monitor incoming documents
│       │   └── loaders/           # PDF, DOCX, TXT loaders
│       │
│       ├── storage/
│       │   ├── uploads/           # uploaded source documents
│       │   ├── generated/         # generated reports and outputs
│       │   └── storage.py         # file storage operations
│       │
│       ├── guardrails/
│       │   └── injection_filter.py # detect prompt injection attempts
│       │
│       ├── costs/
│       │   └── tracker.py         # track tokens, latency, and API costs
│       │
│       ├── core/
│       │   ├── config.py          # application configuration
│       │   ├── logging.py         # centralized logging
│       │   └── security.py        # authentication and security helpers
│       │
│       └── utils/
│           ├── retry.py           # retry helpers
│           ├── hashing.py         # file hashing and deduplication
│           ├── timing.py          # execution timing utilities
│           └── helpers.py         # shared helper functions
│
├── frontend/
│   ├── package.json
│   └── src/
│       ├── App.tsx                # application root
│       ├── pages/                 # application pages
│       ├── components/
│       │   ├── RunTimeline.tsx    # visualize workflow stages
│       │   ├── ReviewQueue.tsx    # human approval interface
│       │   └── ChangeLog.tsx      # change history and audit trail
│       ├── hooks/                 # reusable React hooks
│       ├── services/              # API client layer
│       ├── store/                 # global state management
│       ├── types/                 # TypeScript type definitions
│       └── utils/                 # frontend helper utilities
│
├── use-cases/
│   ├── run-1/                     # first document set
│   └── run-2/                     # second document set for validation
│
└── docs/
    ├── architecture.drawio        # editable architecture diagram
    ├── architecture.png           # exported architecture diagram
    ├── api.md                     # API documentation
    ├── decisions.md               # architectural decisions and trade-offs
    └── writeup.md                 # Task 4 one-page write-up
```

### Relational Domain Model

```text
                         ┌──────────────┐
                         │     Run      │
                         └──────┬───────┘
                                │ 1
                ┌───────────────┼────────────────┐
                │               │                │
               *│              *│               1│
          ┌─────▼─────┐   ┌─────▼─────┐   ┌──────▼──────┐
          │ Document  │   │  Finding  │   │   Report    │
          └───────────┘   └───────────┘   └─────────────┘
                │
                │1
               *│
        ┌───────▼────────┐
        │ DocumentChunk   │
        └────────────────┘

Run
 │
 └───────────────*
                 │
          WorkflowEvent
```


## Kill and Resume

DocTask is engineered to fully survive system process terminations and restart events at any stage using a highly durable checkpoint architecture:

- **Durable Checkpoint Storage**: All intermediate LangGraph state checkpoints are persisted in the PostgreSQL database using a durable `PostgresSaver` connection pool. Checkpoint tables are prepared during API startup lifecycles.
- **Workflow Thread Identification**: Every workflow execution is associated with a stable `thread_id` matching the unique Run ID. Processes restarting can lookup the exact state matching the run identifier.
- **Human-Review State Persistence**: Decisions are stored directly in PostgreSQL on `Finding` models. When a user approves/rejects findings, states are saved, and resuming looks up those decisions to continue the run.
- **Idempotent Commit Boundaries**: The `CommitNode` queries previous reports for the run and updates versions incrementally rather than producing duplicate write records, securing database writes against repeated run triggers.


## Machine/API Driver

DocTask provides a complete, coherent REST and Model Context Protocol (MCP) contract enabling automated programs to drive the document workflow lifecycle:

### REST API Flow
1. **Create Run**: `POST /api/v1/runs` (JSON body: `{"name": "Run Name"}`)
2. **Upload Documents**: `POST /api/v1/runs/{id}/documents?is_rules=false` (multipart form file payload)
3. **Upload Review Rules**: `POST /api/v1/runs/{id}/documents?is_rules=true` (multipart form file playbook payload)
4. **Start Run**: `POST /api/v1/runs/{id}/start`
5. **Get Status & Findings**: `GET /api/v1/runs/{id}` returns findings counts; `GET /api/v1/runs/{id}/details` returns complete findings list
6. **Submit Decisions**: `POST /api/v1/runs/{id}/findings/{finding_id}/decision` (JSON body: `{"decision": "approve" | "reject"}`)
7. **Retrieve Deliverable**: `GET /api/v1/runs/{id}/details` reports property returns final generated deliverable

### MCP Server
An FastMCP adapter server is exposed at `app/mcp/server.py` supporting the tools:
- `create_run(name)`
- `upload_document(run_id, filename, content_base64)`
- `upload_review_rules(run_id, filename, content_base64)`
- `start_run(run_id)`
- `get_run_status(run_id)`
- `get_review_findings(run_id)`
- `decide_finding(run_id, finding_id, decision)`
- `get_run_details(run_id)`
- `process_update(run_id)`


## Watched Folder & Incremental Updates

DocTask supports a configurable filesystem directory scanner for newly arrived files, triggering localized, incremental updates:

### Configuration
Configure the path via the `.env` or system environment variables:
```bash
DOCTASK_WATCH_FOLDER=storage/watch
```

### Discovery & Prevention of Duplicates
- **Supported Formats**: Only `.pdf` and `.docx` extensions are parsed. Others are ignored.
- **Durable Uniqueness**: Computes SHA-256 content hashes for scanned documents. It compares these hashes against the database records of all previous runs to prevent double-processing.

### Incremental vs. Initial Runs
- **Initial Run**: Processes the full document set and playbook rules from scratch.
- **Incremental Run**: Creates an update run record (`parent_id = initial_id`). The system runs the ingestion pipeline only on the newly discovered document, while reusing the user checklist rules from the parent run. Unaffected findings are preserved.

### Provenance, Resume & Concurrency
- **Change History (Provenance)**: The update run documents own their findings, citations, and timestamps, allowing audit records to pinpoint which document triggered which change.
- **Restart/Resume Safety**: State checks use the child run thread checkpointers, so process restarts resume exactly from the interrupted point.
- **Concurrency Locks**: Uses Postgres `FOR UPDATE` query locking during scan operations to prevent multiple workers from starting overlapping processing threads.


## Universal Cloud LLM Multi-Provider Model Pool

DocTask implements a decoupled, provider-agnostic model pool and dynamic router to protect workflow executions against quota exhaustion, provider outages, and rate limits:

- **Provider Independence**: Rather than relying on multiple models from a single ecosystem (e.g., only Gemini), DocTask orchestrates models across distinct cloud providers:
  ```text
  Primary:     Google Gemini (gemini-2.5-flash)
  Fallback 1:  Google Gemini Flash-Lite (gemini-2.5-flash-lite)
  Fallback 2:  Groq Cloud (llama-3.3-70b-versatile)
  Fallback 3:  OpenRouter (openrouter/free)
  ```
- **Dynamic Rotation & 300s Cooldown**: Encountering rate limits (HTTP 429), quota depletion, or provider 503 errors marks the offending model `TEMPORARILY_UNAVAILABLE` with an automatic cooldown timer (`LLM_MODEL_COOLDOWN_SECONDS=300`). Subsequent graph node calls automatically bypass cooled-down models and route to healthy alternatives, self-healing back to `AVAILABLE` once the cooldown period expires.
- **Capability Filtering**: The pool verifies model capabilities (`STRUCTURED_OUTPUT` for strict Pydantic JSON schema adherence vs `TEXT_GENERATION`), ensuring only qualified models receive schema-constrained tasks.
- **Unified Node Routing**: LangGraph nodes do not bind to hardcoded model names; all nodes request model instances through `ModelFactory.create_model_for_node()`, which delegates to the shared router.
- **Generic Error Observability**: Every node execution is shielded by a universal error boundary. Raw exceptions are mapped to a structured taxonomy (`LLM_RATE_LIMIT`, `LLM_QUOTA_EXCEEDED`, `PARSING_ERROR`, `VALIDATION_ERROR`, etc.) and persisted into `workflow_events` with sanitized error summaries and retry metrics for frontend visualization.


## Deployment & Cloud Infrastructure

DocTask is deployed across cloud infrastructure:

### Architecture Mapping
- **Frontend Dashboard**: Deployed on [Vercel](https://frontend-alpha-flame-36.vercel.app/runs) (`https://frontend-alpha-flame-36.vercel.app/runs`).
- **Backend API & LangGraph Engine**: Containerized on **Google Cloud Run** (with fallback on Render Web Service), listening on dynamic `${PORT:-8080}` with automatic Alembic migrations on startup.
- **Database & Checkpointer**: Managed **PostgreSQL with `pgvector`** (Render PostgreSQL, Oregon) storing relational entities and LangGraph checkpoints.
- **Object Storage**: **Google Cloud Storage (GCS)** (`nishanth-billing-sandbox-storage`) managed via `GoogleCloudStorageAdapter` for persistent document and report storage.
- **AI Models**: **Multi-Cloud Model Pool** (Google Gemini `gemini-2.5-flash` / `gemini-2.5-flash-lite`, Groq `llama-3.3-70b-versatile`, OpenRouter `openrouter/free`).

### Build & Deployment Workflow
1. **Container Build (`Dockerfile`)**:
   - Multi-stage build with lightweight CPU PyTorch wheels.
   - Pre-downloads and caches HuggingFace embeddings (`sentence-transformers/all-MiniLM-L6-v2`) in `/app/.cache/huggingface` during the Docker image build, eliminating cold-start latency.
2. **Deploy Backend to Google Cloud Run**:
   ```bash
   gcloud run deploy doctask-backend \
     --source . \
     --env-vars-file env.yaml \
     --region us-central1 \
     --allow-unauthenticated \
     --memory 1Gi \
     --cpu 1 \
     --service-account app-storage-sa@nishanth-billing-sandbox.iam.gserviceaccount.com
   ```
3. **Deploy Frontend to Vercel**:
   Auto-deployed on git push to `main` via Vercel GitHub integration. Local build check:
   ```bash
   cd frontend
   npm run build
   ```