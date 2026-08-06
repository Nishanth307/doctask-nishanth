from enum import Enum


# model ----
class LLMProvider(str, Enum):
    GEMINI = "gemini"
    OLLAMA = "ollama"
    OPENAI = "openai"


class GeminiModel(str, Enum):
    GEMINI_2_5_FLASH = "gemini-2.5-flash"
    GEMINI_2_5_PRO = "gemini-2.5-pro"
    GEMINI_2_5_FLASH_LITE = "gemini-2.5-flash-lite"


class OllamaModel(str, Enum):
    MISTRAL = "mistral"
    LLAMA3 = "llama3"


# ----


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_FOR_REVIEW = "waiting_for_review"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# work flow -----
class WorkflowStage(str, Enum):
    INGESTION = "ingestion"
    CLASSIFICATION = "classification"
    EXTRACTION = "extraction"
    RECONCILIATION = "reconciliation"
    EXAMINATION = "examination"
    UPDATE = "update"
    REVIEW = "review"
    COMMIT = "commit"


class ReviewDecision(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING = "pending"


class FindingSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# document
class DocumentType(str, Enum):
    CONTRACT = "contract"
    AMENDMENT = "amendment"
    INVOICE = "invoice"
    MEETING_NOTES = "meeting_notes"
    COMPLIANCE = "compliance"
    STYLE_GUIDE = "style_guide"
    UNKNOWN = "unknown"


# Why these?
# RunStatus → Track the overall execution state.
# WorkflowStage → Display the current LangGraph node in the timeline UI.
# ReviewDecision → Used by the review API and frontend.
# FindingSeverity → Classify rule violations and conflicts.
# DocumentType → Output of the classification node.
# LLMProvider → Matches the model factory you'll build later.

# later add
# │   ├── __init__.py
# │   ├── document.py
# │   ├── workflow.py
# │   ├── review.py
# │   └── model.py
