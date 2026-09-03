# Architectural Decision Records (ADRs) & Trade-offs

This document records the key architectural decisions, rationale, alternatives considered, and trade-offs made during the design and implementation of DocTask.

---

## ADR-001: LangGraph with PostgreSQL Checkpointing (`PostgresSaver`) for Crash-Resilience

### Context
Document analysis pipelines involve multiple heterogeneous steps: ingestion, semantic extraction, multi-document cross-examination, and human review. In cloud-native and serverless environments (e.g., Google Cloud Run, Render, Kubernetes), instances may undergo graceful shutdowns, autoscaling scale-downs, or unexpected process terminations (OOM, container restarts). Without durable state management, a process crash midway through analysis forfeits all previously executed LLM steps, leading to wasted API tokens and corrupted workflow states.

### Decision
We adopted **LangGraph** with a **PostgreSQL-backed checkpointer (`PostgresSaver`)**.
- Every workflow run is assigned a deterministic `thread_id` matching its primary relational entity `run_id`.
- LangGraph writes its intermediate graph state, step outputs, and interruption snapshots into PostgreSQL tables (`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`).
- The application lifespan verifies and initializes checkpointer tables on startup.

### Alternatives Considered
1. **In-Memory Checkpointing (`MemorySaver`)**: Highly performant for testing, but state is completely lost upon container restart.
2. **Celery / RabbitMQ**: Excellent for distributed task queues, but complex to orchestrate stateful multi-step cycles, conditional branching, and pause-resume interruptions for human-in-the-loop decisions.
3. **Temporal / Cadence**: Extremely robust for long-running workflows, but introduces massive operational infrastructure overhead and language SDK complexity disproportionate to the service requirements.

### Trade-offs & Consequences
- **Pros**: 100% kill-and-resume resilience. A killed server immediately resumes from the last completed node upon restart.
- **Cons**: Requires persistent relational storage access and introduces a minor I/O latency penalty per node transition to serialize state.

---

## ADR-002: Structured Pydantic Output Generation with LLM Fallback Cascade

### Context
Unstructured text outputs from LLMs lead to prompt drift, hallucinated formatting, and parsing errors during downstream entity matching and contradiction detection. Additionally, high-end models (such as `gemini-2.5-pro`) occasionally encounter HTTP 429 (Rate Limit), HTTP 503 (Overloaded), or quota exhaustion during peak concurrent workloads.

### Decision
1. **Schema Enforcement**: All LLM interactions use strict Pydantic schemas (e.g., `DocumentClassification`, `ExtractedFacts`, `ExaminationResult`) enforcing structured JSON outputs.
2. **Model Fallback Cascade**: If the primary reasoning model (`gemini-2.5-pro`) encounters rate limits or quota exhaustion, the factory automatically cascades down the fallback priority chain:
   ```
   gemini-2.5-pro ──(429/503/Quota)──► gemini-2.5-flash ──(429/503/Quota)──► gemini-2.0-flash
   ```
3. **Network Resilience**: Transient socket and connection errors are handled via `tenacity` exponential backoff retries before triggering model fallback.

### Alternatives Considered
- **Single Model with Raw Markdown Prompts**: Highly fragile; downstream parsers break when models alter heading formats or omit JSON delimiters.
- **Immediate Hard Failure on 429**: Results in brittle user experience and failed batch runs during API traffic spikes.

### Trade-offs & Consequences
- **Pros**: Guarantees typed data across the entire execution graph and prevents downtime during provider quota events.
- **Cons**: Fallback models may produce slightly lower reasoning fidelity on subtle legal nuances compared to the pro model, though schema adherence remains intact.

---

## ADR-003: Integrated Vector Search via PostgreSQL `pgvector` vs Dedicated Vector Store

### Context
Semantic retrieval is necessary to match extracted document facts against compliance checklist rules and identify conflicting clauses across disparate contracts.

### Decision
We chose **`pgvector`** hosted directly within the application PostgreSQL database.
- Embeddings are generated using `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions).
- Document chunks store their vector embeddings directly in the `document_chunks` table with cosine similarity indexing.

### Alternatives Considered
1. **Dedicated Vector Databases (Pinecone, Qdrant, Milvus)**:
   - Introduce external network hops, distinct authentication keys, and dual-write consistency issues between the relational database and the vector index.
2. **Local In-Memory Vector Indices (FAISS, Chroma)**:
   - Do not survive container restarts or multi-worker horizontal scaling without complex volume sharing.

### Trade-offs & Consequences
- **Pros**: Atomic transactions across documents, chunks, and embeddings; simplified backups; single database connection string; zero distributed sync drift.
- **Cons**: Slightly higher CPU and memory overhead on PostgreSQL during vector indexing compared to dedicated specialized vector engines.

---

## ADR-004: Binary Magic-Byte Document Inspection over File Extensions

### Context
Users and machine drivers frequently upload files with missing, mismatched, or altered file extensions (e.g., uploading a Word document named `.pdf` or a raw text document with no extension). Blindly trusting file extensions leads to parser crashes (such as PyMuPDF throwing syntax errors on DOCX binaries).

### Decision
Implement **magic-byte MIME type inspection** in `DocumentLoaderFactory` using file signature analysis. The factory inspects the initial byte headers of the uploaded payload before delegating to:
- `PyMuPDFLoader` for PDF magic bytes (`%PDF-`)
- `DocxLoader` for Zip-container Office Open XML bytes (`PK\x03\x04`)
- `TxtLoader` for UTF-8/ASCII plain text

### Alternatives Considered
- **Strict File Extension Validation**: Rejects valid files whose extensions were stripped during transmission or downloads.
- **Trial-and-Error Parsing**: Attempting one parser and catching exceptions; inefficient and pollutes logs with spurious tracebacks.

### Trade-offs & Consequences
- **Pros**: Robust defense against malformed uploads and parser crashes; enhanced security against basic MIME-spoofing attacks.
- **Cons**: Requires reading the first chunk of bytes into memory before routing.

---

## ADR-005: Pluggable Storage Layer via Factory Pattern (Local Disk + Google Cloud Storage)

### Context
Development takes place locally via Docker Compose (mounting local filesystem volumes), whereas production targets serverless cloud environments (Google Cloud Run) where local disks are ephemeral and non-shared across instances.

### Decision
Implement an abstract `StorageService` interface with two implementations:
1. `LocalStorageAdapter`: Writes files to local filesystem paths (e.g., `storage/uploads/`).
2. `GoogleCloudStorageAdapter`: Streams blobs directly to Google Cloud Storage (GCS) buckets using standard ADC (Application Default Credentials).
- The active backend is resolved dynamically at runtime by `StorageFactory` using the `STORAGE_BACKEND` environment variable (`local` vs `gcs`).

### Alternatives Considered
- **Local Disk with Persistent Volume Claims**: Difficult and expensive to manage on serverless platforms like Google Cloud Run or Render.
- **Direct S3/GCS Code in Routes**: Hardcodes cloud dependencies into local testing environments, requiring active cloud credentials for unit tests.

### Trade-offs & Consequences
- **Pros**: Seamless development experience offline with zero configuration; instant transition to production cloud object storage with one environment variable change.
- **Cons**: Requires maintaining mock implementations and storage abstractions across all file operations.

---

## ADR-006: Two-Tier Human-in-the-Loop Interruption Architecture

### Context
Legal compliance systems require human judgment. However, interrupting execution for every minor step causes user fatigue, while fully autonomous execution creates legal liability.

### Decision
We engineered a **two-tier human-in-the-loop interruption model**:
1. **Tier 1: Global Conflict Interruption (`human_review` node)**
   - Triggered only when the `ReconcileNode` identifies critical cross-document contradictions exceeding safety thresholds.
   - The user can choose to **Approve** (proceed to rule examination) or **Reject** (route to the `revise` node to re-align context).
2. **Tier 2: Granular Finding Interruption (`findings_review` node)**
   - All detected policy violations and rule deviations are persisted as `Finding` records in PostgreSQL.
   - The workflow graph executes `langgraph.types.interrupt()` and enters `waiting_for_review`.
   - Users or machine drivers can inspect findings individually and submit decisions (`approve` or `reject`) via API or UI.
   - Once all findings are resolved, the workflow automatically resumes and executes `commit` to build the final report.

### Alternatives Considered
- **All-or-Nothing Approval**: Approving or rejecting the entire run en bloc; prevents users from accepting specific low-risk risks while dismissing false positives.
- **Synchronous Human Review**: Holding HTTP requests open while waiting for human input; fails immediately due to HTTP gateway timeouts.

### Trade-offs & Consequences
- **Pros**: Optimal balance of automation and governance; granular audit trail; fully asynchronous.
- **Cons**: Requires frontend polling or webhook triggers to notify clients when review gates are activated.

---

## ADR-007: SHA-256 Deduplication and Parent-Child Incremental Run Hierarchy

### Context
Organizations continuously receive updated agreements, addenda, and revisions. Re-running entire document corpuses from scratch is wasteful and obscures what changed between versions.

### Decision
1. **Content Hashing**: Every ingested file is hashed using SHA-256.
2. **Watched Folder Ingestion (`storage/watch`)**: When files are placed into the watched folder, the scanner queries PostgreSQL for existing checksums. If a document hash has already been processed, it is skipped.
3. **Parent-Child Run Linkage**: When a new document arrives for an existing contract set, an incremental run is created with `parent_id` referencing the initial run.
   - The child run reuses the established playbook rules and parent document context.
   - Only the delta document is chunked, embedded, and examined.
   - Provenance is retained, allowing users to trace exactly which document introduced each finding.

### Alternatives Considered
- **In-Place Mutation**: Overwriting the original run record; destroys historical audit trails and breaks reproducibility.
- **Full Reprocessing**: Running a complete new run from scratch; doubles token costs and loses the diff perspective.

### Trade-offs & Consequences
- **Pros**: Substantial savings in LLM tokens and execution time; explicit version lineage and delta tracking.
- **Cons**: Schema complexity requiring `parent_id` foreign keys and recursive parent lookup logic during context retrieval.

---

## ADR-008: Dual Machine Interface (REST API and Model Context Protocol / FastMCP)

### Context
Modern enterprise software must be accessible both by standard frontend web applications and by autonomous AI agents operating within agent ecosystems (e.g., Claude Desktop, Antigravity, Cursor, LangChain agents).

### Decision
We exposed dual interfaces backed by shared service repositories:
1. **FastAPI REST API**: Idiomatic HTTP endpoints for standard web apps, mobile clients, and script automation.
2. **FastMCP Server**: Standard Model Context Protocol server exposing 9 structured tools (`create_run`, `upload_document`, `upload_review_rules`, `start_run`, `get_run_status`, `get_review_findings`, `decide_finding`, `get_run_details`, `process_update`).

### Alternatives Considered
- **REST Only**: Forces agent frameworks to rely on custom OpenAPI parsers or custom integration code.
- **MCP Only**: Prevents traditional frontend dashboards and curl commands from interacting easily with the platform.

### Trade-offs & Consequences
- **Pros**: Complete interoperability with both web browsers and autonomous agent swarms; standardized tool contracts.
- **Cons**: Requires keeping tool definitions in sync with REST route signatures.

---

## ADR-009: Background Embedding Warmup & Single-Threaded PyTorch Execution

### Context
In containerized environments (Render, Cloud Run), the initial load of `sentence-transformers/all-MiniLM-L6-v2` into CPU memory takes 15-25 seconds on constrained 0.5-1.0 vCPU instances. When this load occurs during the first incoming HTTP request, the edge proxy terminates the connection due to a 30-second gateway timeout (HTTP 502/504). Furthermore, multi-threaded PyTorch CPU operations can cause CPU contention and thrashing on single-core instances.

### Decision
1. **Startup Warmup**: Pre-warm the embedding model in a background daemon thread during application lifespan startup (`lifespan` in `main.py`).
2. **Thread Clamping**: Enforce `torch.set_num_threads(1)` to prevent CPU thread oversubscription.
3. **Singleton Caching**: Cache the embedding model instance globally in memory across requests.

### Alternatives Considered
- **Remote Embedding API (e.g., OpenAI or Vertex AI Embeddings)**: Eliminates local compute, but introduces external API latency, rate limits, and network cost for every document chunk.
- **Synchronous Startup Blocking**: Delays container ready checks, causing cloud health-check probes to fail and restart the container.

### Trade-offs & Consequences
- **Pros**: Completely resolves cold-start gateway timeouts; delivers instantaneous response times on subsequent document uploads.
- **Cons**: Minor memory baseline footprint (~150MB) held resident in the container process.

---

## ADR-010: Idempotent Commit Phase for Final Deliverable Reports

### Context
Due to network interruptions, client retries, or resuming paused workflows, the final commit step (`CommitNode`) might be executed multiple times for a single run.

### Decision
The `CommitNode` operates under strict idempotency constraints:
- Queries existing reports for the current `run_id`.
- If an existing report is found, updates its markdown content and increments the `version` integer rather than inserting duplicate records.
- Only incorporates findings that carry `review_decision = APPROVED`.
- Operates inside an explicit database transaction boundary with rollback protection.

### Alternatives Considered
- **Blind Insert**: Inserting a new row on every completion; results in duplicate conflicting reports for the same run.
- **Pre-Commit Wipe**: Deleting previous reports before inserting; risks losing historical report versions during unexpected transaction rollbacks.

### Trade-offs & Consequences
- **Pros**: Completely prevents duplicate reports; guarantees clean version increments and auditable deliverable states.
- **Cons**: Requires maintaining report version numbers in the database schema.
