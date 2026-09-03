# DocTask API & MCP Specification Reference

This document provides a comprehensive technical reference for the DocTask REST API and Model Context Protocol (FastMCP) server.

---

## 1. Overview & Connection Details

- **Base URL**: `http://localhost:8000` (Local) / Custom Cloud Run/Render Host
- **API Version Prefix**: `/api/v1`
- **Supported Content Types**:
  - `application/json` (Standard payloads)
  - `multipart/form-data` (Document uploads and batch run creations)
- **CORS Support**: Configurable via `CORS_ORIGINS` environment variable, with native support for `*.vercel.app` origins.

---

## 2. Core Domain Enums & Models

### `RunStatus`
| Value | Description |
| :--- | :--- |
| `pending` | Run created; awaiting documents or execution trigger. |
| `running` | Actively processing through LangGraph workflow nodes. |
| `waiting_for_review` | Paused at an interruption boundary awaiting human decision. |
| `completed` | Pipeline executed successfully; final report committed. |
| `failed` | Run terminated abnormally (e.g. unhandled error or retries exhausted). |
| `cancelled` | Explicitly aborted by user/client request. |

### `WorkflowStage`
| Value | Description |
| :--- | :--- |
| `idle` | Inactive / created. |
| `ingest` | Document parsing, chunking, and embedding generation. |
| `classify` | Determining document types, contracts, and rule sets. |
| `extract` | Identifying structured clauses, obligations, dates, and citations. |
| `reconcile` | Detecting cross-document contradictions and conflicts. |
| `human_review` | Human review gate for conflicting document statements. |
| `examine` | Validating document facts against uploaded playbook rules. |
| `findings_review` | Human decision gate for individual findings. |
| `commit` | Compiling approved findings into the persistent markdown report. |
| `update` | Final state synchronization and audit logging. |

### `FindingSeverity`
- `low`: Informational or minor deviations.
- `medium`: Notable ambiguities, discrepancies, or policy warnings.
- `high`: Critical contractual conflicts, obligations breached, or strict rule violations.

### `ReviewDecision`
- `pending`: Awaiting human review decision.
- `approved`: Finding validated and accepted into the final report.
- `rejected`: Finding dismissed as false positive or accepted risk.

---

## 3. REST API Endpoints

### 3.1. Runs Management

#### `POST /api/v1/runs`
Create a new workflow run. Supports two modes:

**Mode A: JSON Payload (Empty Run)**
```http
POST /api/v1/runs HTTP/1.1
Content-Type: application/json

{
  "name": "Acquisition Due Diligence 2026"
}
```

**Mode B: Multipart Form (Run Creation with File Uploads)**
```http
POST /api/v1/runs HTTP/1.1
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary

------WebKitFormBoundary
Content-Disposition: form-data; name="name"

Acquisition Due Diligence 2026
------WebKitFormBoundary
Content-Disposition: form-data; name="files"; filename="master_services_agreement.pdf"
Content-Type: application/pdf

<binary PDF bytes>
------WebKitFormBoundary
Content-Disposition: form-data; name="rules_file"; filename="legal_playbook.docx"
Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document

<binary DOCX bytes>
------WebKitFormBoundary--
```

**Response (`201 Created`):**
```json
{
  "id": "7b7e8d42-5f3a-4a8a-9e23-7a98ef123456",
  "name": "Acquisition Due Diligence 2026",
  "status": "pending",
  "stage": "idle",
  "created_at": "2026-09-03T18:00:00Z",
  "updated_at": "2026-09-03T18:00:00Z",
  "completed_at": null,
  "error_message": null,
  "documents": [
    {
      "id": "11111111-2222-3333-4444-555555555555",
      "filename": "master_services_agreement.pdf",
      "is_rules": false
    },
    {
      "id": "66666666-7777-8888-9999-000000000000",
      "filename": "legal_playbook.docx",
      "is_rules": true
    }
  ],
  "pending_finding_count": 0,
  "approved_finding_count": 0,
  "rejected_finding_count": 0,
  "parent_id": null
}
```

---

#### `GET /api/v1/runs`
Retrieve all existing runs ordered by creation date descending.

**Response (`200 OK`):**
```json
[
  {
    "id": "7b7e8d42-5f3a-4a8a-9e23-7a98ef123456",
    "name": "Acquisition Due Diligence 2026",
    "status": "waiting_for_review",
    "stage": "findings_review",
    "created_at": "2026-09-03T18:00:00Z",
    "updated_at": "2026-09-03T18:02:15Z",
    "completed_at": null,
    "error_message": null,
    "documents": [],
    "pending_finding_count": 3,
    "approved_finding_count": 1,
    "rejected_finding_count": 0,
    "parent_id": null
  }
]
```

---

#### `GET /api/v1/runs/{run_id}`
Retrieve high-level summary and counts for a single run.

**Path Parameters:**
- `run_id` (UUID, required): The target run identifier.

**Response (`200 OK`):** Returns a `RunResponse` object.

---

#### `GET /api/v1/runs/{run_id}/details`
Retrieve comprehensive details including all associated findings, final deliverable report, workflow execution events, and raw node outputs.

**Response (`200 OK`):**
```json
{
  "run": {
    "id": "7b7e8d42-5f3a-4a8a-9e23-7a98ef123456",
    "name": "Acquisition Due Diligence 2026",
    "status": "completed",
    "stage": "update",
    "created_at": "2026-09-03T18:00:00Z",
    "updated_at": "2026-09-03T18:05:00Z",
    "completed_at": "2026-09-03T18:05:00Z",
    "error_message": null,
    "documents": [],
    "pending_finding_count": 0,
    "approved_finding_count": 2,
    "rejected_finding_count": 1,
    "parent_id": null
  },
  "findings": [
    {
      "id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
      "title": "Conflicting Governing Law Clauses",
      "description": "Master Services Agreement stipulates Delaware law, whereas SOW-1 specifies California jurisdiction.",
      "severity": "high",
      "review_decision": "approved",
      "citation": {
        "source": "master_services_agreement.pdf",
        "page": 14,
        "clause": "12.1"
      },
      "finding_metadata": {
        "confidence": 0.96
      },
      "created_at": "2026-09-03T18:02:00Z"
    }
  ],
  "report": {
    "id": "f9e8d7c6-b5a4-3210-9876-543210fedcba",
    "content": "# Final Contract Review Report\n\n## Summary\nContract review completed with 1 approved policy violation.\n\n## Approved Findings & Policy Violations\n### ⚠️ Conflicting Governing Law Clauses (Severity: HIGH)\nMaster Services Agreement stipulates Delaware law, whereas SOW-1 specifies California jurisdiction.\n*Citation: {'source': 'master_services_agreement.pdf', 'page': 14, 'clause': '12.1'}*",
    "version": 1,
    "approved": true,
    "created_at": "2026-09-03T18:04:30Z",
    "updated_at": "2026-09-03T18:04:30Z"
  },
  "workflow_events": [
    {
      "id": "c1d2e3f4-0000-1111-2222-333344445555",
      "run_id": "7b7e8d42-5f3a-4a8a-9e23-7a98ef123456",
      "stage": "classify",
      "status": "completed",
      "message": "Classified 2 documents successfully",
      "duration_ms": 1420,
      "created_at": "2026-09-03T18:00:15Z"
    }
  ],
  "workflow_result": {
    "id": "b1a2c3d4-4444-5555-6666-777788889999",
    "status": "completed",
    "classification": { "agreement_type": "MSA" },
    "extracted_facts": [],
    "reconciliation": { "conflicts_found": 1 },
    "examination": { "violations_found": 1 },
    "human_decision": "approved",
    "created_at": "2026-09-03T18:04:30Z",
    "updated_at": "2026-09-03T18:05:00Z"
  }
}
```

---

#### `POST /api/v1/runs/{run_id}/start`
Initiates the LangGraph execution graph for the specified run.

**Response (`200 OK`):**
```json
{
  "thread_id": "7b7e8d42-5f3a-4a8a-9e23-7a98ef123456",
  "state": {
    "run_id": "7b7e8d42-5f3a-4a8a-9e23-7a98ef123456",
    "status": "waiting_for_review",
    "stage": "findings_review"
  }
}
```

---

#### `POST /api/v1/runs/{run_id}/decision`
Resumes a workflow paused at the global `human_review` node.

**Request Body:**
```json
{
  "decision": "approve"
}
```
*Allowed decisions: `"approve"` (advances to rule examination) or `"reject"` (routes to revise node).*

**Response (`200 OK`):** Returns `WorkflowRunResponse`.

---

#### `POST /api/v1/runs/{run_id}/findings/{finding_id}/decision`
Submits an approval or rejection decision for a specific finding. When all findings for a run are resolved, if the run was in `waiting_for_review`, the system automatically resumes the workflow to commit the final report deliverable.

**Path Parameters:**
- `run_id` (UUID, required): The run identifier.
- `finding_id` (UUID, required): The finding identifier.

**Request Body:**
```json
{
  "decision": "approve"
}
```

**Response (`200 OK`):**
```json
{
  "id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
  "title": "Conflicting Governing Law Clauses",
  "description": "Master Services Agreement stipulates Delaware law...",
  "severity": "high",
  "review_decision": "approved",
  "citation": { "source": "master_services_agreement.pdf" },
  "finding_metadata": {},
  "created_at": "2026-09-03T18:02:00Z"
}
```

---

#### `POST /api/v1/runs/{run_id}/updates`
Triggers immediate file discovery on the configured watched directory (`DOCTASK_WATCH_FOLDER`), performing SHA-256 deduplication. If new documents are discovered, creates an incremental child run linked via `parent_id` and executes delta analysis.

**Response (`200 OK`):**
Returns the newly created child `RunResponse`, or `null` if no new unindexed documents were detected.

---

#### `POST /api/v1/runs/{run_id}/cancel`
Gracefully halts an in-progress or paused run, updating status to `cancelled`.

---

#### `DELETE /api/v1/runs/{run_id}`
Deletes a run and cascades deletion across its associated findings, reports, events, and document records.

---

### 3.2. Document Ingestion Endpoints

#### `POST /api/v1/runs/{run_id}/documents`
Uploads a document file to associate with a run. The loader automatically verifies the binary magic bytes, chunks text, generates embeddings, and saves vectors to PostgreSQL `pgvector`.

**Query Parameters:**
- `is_rules` (bool, default: `false`): Set to `true` if uploading a review playbook/checklist; set to `false` for target contractual documents.

**Payload:** `multipart/form-data` with field `file`.

**Response (`201 Created`):**
```json
{
  "id": "11111111-2222-3333-4444-555555555555",
  "run_id": "7b7e8d42-5f3a-4a8a-9e23-7a98ef123456",
  "filename": "amendment_no_1.pdf",
  "file_path": "storage/uploads/11111111-2222-3333-4444-555555555555_amendment_no_1.pdf",
  "file_type": "application/pdf",
  "is_rules": false,
  "checksum": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "created_at": "2026-09-03T18:01:00Z"
}
```

---

#### `GET /api/v1/documents`
Lists documents across all runs.

**Query Parameters:**
- `is_rules` (bool, optional): Filter by source documents (`false`) or review rule playbooks (`true`).

---

### 3.3. System & Health Endpoints

- `GET /` or `HEAD /`: Returns `{"status": "ok", "message": "DocTask API is running"}`
- `GET /health` or `HEAD /health`: Returns `{"status": "healthy"}`

---

## 4. Model Context Protocol (FastMCP) Tools Reference

The DocTask MCP server is exposed at `app/mcp/server.py`. It enables autonomous AI agents (such as Claude Desktop, Gemini CLI, or custom agent sidecars) to drive document workflows via standardized MCP tool calls.

### 4.1. `create_run(name: str) -> dict`
Creates a new run.
```json
// Tool Call
{ "name": "Vendor Audit Q3" }

// Return Value
{
  "id": "12345678-1234-1234-1234-123456789abc",
  "name": "Vendor Audit Q3",
  "status": "pending",
  "stage": "idle"
}
```

### 4.2. `upload_document(run_id: str, filename: str, content_base64: str) -> dict`
Uploads and indexes a source contract/document encoded in base64 format.

### 4.3. `upload_review_rules(run_id: str, filename: str, content_base64: str) -> dict`
Uploads and indexes a compliance checklist or playbook rule document in base64 format (`is_rules=True`).

### 4.4. `start_run(run_id: str) -> dict`
Executes the workflow graph for the specified run until completion or human-review interruption.

### 4.5. `get_run_status(run_id: str) -> dict`
Returns run lifecycle flags, active stage, and finding breakdown:
```json
{
  "id": "12345678-1234-1234-1234-123456789abc",
  "status": "waiting_for_review",
  "stage": "findings_review",
  "pending_count": 2,
  "approved_count": 1,
  "rejected_count": 0,
  "completed": false,
  "failed": false
}
```

### 4.6. `get_review_findings(run_id: str) -> list[dict]`
Retrieves all generated findings with their titles, descriptions, severities, and current decisions.

### 4.7. `decide_finding(run_id: str, finding_id: str, decision: str) -> dict`
Applies `"approve"` or `"reject"` to a specific finding. If all findings are decided, automatically triggers workflow resumption to compile the final deliverable.

### 4.8. `get_run_details(run_id: str) -> dict`
Retrieves run metadata and the complete generated Markdown report deliverable.

### 4.9. `process_update(run_id: str) -> dict`
Triggers folder watch polling to incrementally ingest new documents and generate update delta runs.

---

## 5. End-to-End Machine Driver Script (Python Example)

```python
import base64
import requests
import time

BASE_URL = "http://localhost:8000/api/v1"

# 1. Create Run
res = requests.post(f"{BASE_URL}/runs", json={"name": "API Automated Audit"})
run_id = res.json()["id"]

# 2. Upload Document
with open("contract.pdf", "rb") as f:
    requests.post(
        f"{BASE_URL}/runs/{run_id}/documents?is_rules=false",
        files={"file": ("contract.pdf", f, "application/pdf")}
    )

# 3. Upload Rules
with open("playbook.docx", "rb") as f:
    requests.post(
        f"{BASE_URL}/runs/{run_id}/documents?is_rules=true",
        files={"file": ("playbook.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    )

# 4. Start Run
requests.post(f"{BASE_URL}/runs/{run_id}/start")

# 5. Poll Status
while True:
    status_data = requests.get(f"{BASE_URL}/runs/{run_id}").json()
    print("Current Stage:", status_data["stage"], "Status:", status_data["status"])
    if status_data["status"] in ("waiting_for_review", "completed", "failed"):
        break
    time.sleep(2)

# 6. Handle Review Findings
if status_data["status"] == "waiting_for_review":
    details = requests.get(f"{BASE_URL}/runs/{run_id}/details").json()
    for finding in details["findings"]:
        # Approve high severity findings, reject others
        decision = "approve" if finding["severity"] == "high" else "reject"
        requests.post(
            f"{BASE_URL}/runs/{run_id}/findings/{finding['id']}/decision",
            json={"decision": decision}
        )

# 7. Retrieve Final Deliverable
final_details = requests.get(f"{BASE_URL}/runs/{run_id}/details").json()
print("Final Report Deliverable:\n", final_details["report"]["content"])
```
