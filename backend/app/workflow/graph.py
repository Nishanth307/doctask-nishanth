"""LangGraph workflow definition for DocTask.

Lifecycle (happy path):
  START → classify → extract → reconcile → [human_review] → examine
        → findings_review (interrupt) → apply_edits → validate_edits → commit → update → END

Branching decisions:
  - classify failure → retry or failed
  - extract failure → retry or failed
  - reconcile failure → retry or failed
  - contradictions or pending review → findings_review (interrupt gate)
  - No pending findings → apply_edits directly after examine
  - apply_edits failure → failed
  - validate_edits failure → commit (validation failure is recorded but doesn't abort)
  - commit → update → END
"""
from datetime import datetime, timezone
import time
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.errors import GraphInterrupt

from app.core.errors import classify_error, sanitize_error_message, ErrorCategory
from app.core.logging import logger

from app.core.config import settings
from app.llm.enums import ModelName
from app.llm.context import clear_last_llm_call, get_last_llm_call
from app.llm.factory import DefaultModelFactory, ModelFactory, AllProvidersFailedError
from app.persistence.repositories.workflow_result import WorkflowResultRepository
from app.workflow.checkpointer import create_checkpointer
from app.workflow.nodes.classify import ClassifyNode
from app.workflow.nodes.examine import ExamineNode
from app.workflow.nodes.extract import ExtractNode
from app.workflow.nodes.human_review import human_review_node
from app.workflow.nodes.reconcile import ReconcileNode
from app.workflow.nodes.revise import ReviseNode
from app.workflow.nodes.update import CommitNode, UpdateNode, findings_review_node
from app.workflow.nodes.apply_edits import ApplyEditsNode
from app.workflow.nodes.validate_edits import ValidateEditsNode
from app.workflow.retry import execute_with_retry
from app.workflow.state import WorkflowState

from app.core.constants import WorkflowStage

# Map LangGraph node names → WorkflowStage enum values for event recording
NODE_STAGE_MAP: dict[str, WorkflowStage] = {
    "classify": WorkflowStage.CLASSIFICATION,
    "extract": WorkflowStage.EXTRACTION,
    "reconcile": WorkflowStage.RECONCILIATION,
    "human_review": WorkflowStage.REVIEW,
    "revise": WorkflowStage.REVIEW,
    "examine": WorkflowStage.EXAMINATION,
    "generate_suggested_changes": WorkflowStage.GENERATE_CHANGES,
    "findings_review": WorkflowStage.FINDINGS_REVIEW,
    "apply_edits": WorkflowStage.APPLY_EDITS,
    "validate_edits": WorkflowStage.VALIDATE_EDITS,
    "commit": WorkflowStage.COMMIT,
    "update": WorkflowStage.UPDATE,
    "failed": WorkflowStage.COMMIT,
}

# Map LangGraph node names → upstream predecessor node for node-specific rewinding
UPSTREAM_NODE_MAP: dict[str, Any] = {
    "classify": START,
    "extract": "classify",
    "reconcile": "extract",
    "human_review": "reconcile",
    "revise": "human_review",
    "examine": "reconcile",
    "generate_suggested_changes": "examine",
    "findings_review": "generate_suggested_changes",
    "apply_edits": "findings_review",
    "validate_edits": "apply_edits",
    "commit": "validate_edits",
    "update": "commit",
}


def _record_db_event(
    run_id: Any,
    stage: WorkflowStage,
    status: str,
    message: str | None = None,
    duration_ms: int | None = None,
    node_name: str | None = None,
    error_type: str | None = None,
    attempt: int = 1,
    retryable: bool | None = None,
    checkpoint_id: str | None = None,
) -> None:
    try:
        from app.core.database import SessionLocal
        from app.persistence.repositories.workflow_event import WorkflowEventRepository
        from app.services.workflow_event_service import WorkflowEventService

        db = SessionLocal()
        try:
            event_repo = WorkflowEventRepository(db)
            event_service = WorkflowEventService(event_repo)
            event_service.record(
                run_id=run_id,
                stage=stage,
                status=status,
                message=message,
                duration_ms=duration_ms,
                node_name=node_name,
                error_type=error_type,
                attempt=attempt,
                retryable=retryable,
                checkpoint_id=checkpoint_id,
            )
            db.commit()
        finally:
            db.close()
    except Exception:
        pass


def _make_emitting_wrapper(node_name: str, node_fn):
    """Universal LangGraph node execution wrapper for error handling, attempt tracking, and checkpointing."""

    def wrapper(state: WorkflowState) -> WorkflowState:
        run_id = state.get("run_id")
        stage = NODE_STAGE_MAP.get(node_name, WorkflowStage.INGESTION)
        checkpoint_id = str(run_id) if run_id else None

        node_attempts = dict(state.get("node_attempts") or {})
        attempt = node_attempts.get(node_name, 0) + 1
        node_attempts[node_name] = attempt

        execution_history = list(state.get("execution_history") or [])
        start_time = time.monotonic()
        now_iso = datetime.now(timezone.utc).isoformat()

        # Record 'started' event
        if run_id:
            _record_db_event(
                run_id=run_id,
                stage=stage,
                status="started",
                message=f"Node '{node_name}' started (attempt {attempt})",
                node_name=node_name,
                attempt=attempt,
                checkpoint_id=checkpoint_id,
            )

        # Execute node within resilient boundary
        clear_last_llm_call()
        try:
            result = node_fn(state)
        except GraphInterrupt:
            # Control-flow interrupt for human review gate; must propagate to LangGraph
            raise
        except Exception as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            category, retryable, sanitized_msg = classify_error(exc)
            logger.error(
                f"Node '{node_name}' failed on attempt {attempt} [{category.value}]: {sanitized_msg}",
                exc_info=True,
            )

            provider_attempts = getattr(exc, "provider_attempts", None)
            llm_meta = get_last_llm_call()
            if not provider_attempts and llm_meta:
                provider_attempts = llm_meta.get("provider_attempts")

            error_record = {
                "node_name": node_name,
                "error_type": category.value,
                "error_message": sanitized_msg,
                "error_timestamp": now_iso,
                "retryable": retryable,
                "attempt": attempt,
                "checkpoint_id": checkpoint_id,
                "reason": "This failure requires user intervention or configuration changes." if not retryable else None,
                "provider_attempts": provider_attempts,
            }

            execution_record = {
                "node_name": node_name,
                "status": "failed",
                "attempt": attempt,
                "duration_ms": duration_ms,
                "error_type": category.value,
                "error_message": sanitized_msg,
                "retryable": retryable,
                "timestamp": now_iso,
                "provider_attempts": provider_attempts,
            }
            execution_history.append(execution_record)

            if run_id:
                _record_db_event(
                    run_id=run_id,
                    stage=stage,
                    status="failed",
                    message=f"Node '{node_name}' failed: {sanitized_msg}",
                    duration_ms=duration_ms,
                    node_name=node_name,
                    error_type=category.value,
                    attempt=attempt,
                    retryable=retryable,
                    checkpoint_id=checkpoint_id,
                )

            return {
                **state,
                "current_node": node_name,
                "node_attempts": node_attempts,
                "execution_history": execution_history,
                "last_error": error_record,
                "error": sanitized_msg,
                "status": "failed",
            }

        duration_ms = int((time.monotonic() - start_time) * 1000)

        # Check if node returned error in state dict
        has_error = result.get("error") if isinstance(result, dict) else False
        if has_error:
            raw_err = result.get("error", "Unknown error")
            category, retryable, sanitized_msg = classify_error(raw_err)
            llm_meta = get_last_llm_call()
            provider_attempts = llm_meta.get("provider_attempts") if llm_meta else None

            error_record = {
                "node_name": node_name,
                "error_type": category.value,
                "error_message": sanitized_msg,
                "error_timestamp": now_iso,
                "retryable": retryable,
                "attempt": attempt,
                "checkpoint_id": checkpoint_id,
                "reason": "This failure requires user intervention or configuration changes." if not retryable else None,
                "provider_attempts": provider_attempts,
            }
            execution_record = {
                "node_name": node_name,
                "status": "failed",
                "attempt": attempt,
                "duration_ms": duration_ms,
                "error_type": category.value,
                "error_message": sanitized_msg,
                "retryable": retryable,
                "timestamp": now_iso,
                "provider_attempts": provider_attempts,
            }
            execution_history.append(execution_record)

            if run_id:
                _record_db_event(
                    run_id=run_id,
                    stage=stage,
                    status="failed",
                    message=f"Node '{node_name}' failed: {sanitized_msg}",
                    duration_ms=duration_ms,
                    node_name=node_name,
                    error_type=category.value,
                    attempt=attempt,
                    retryable=retryable,
                    checkpoint_id=checkpoint_id,
                )

            return {
                **state,
                **result,
                "current_node": node_name,
                "node_attempts": node_attempts,
                "execution_history": execution_history,
                "last_error": error_record,
                "error": sanitized_msg,
                "status": "failed",
            }

        # Success case
        llm_meta = get_last_llm_call()
        execution_record = {
            "node_name": node_name,
            "status": "completed",
            "attempt": attempt,
            "duration_ms": duration_ms,
            "error_type": None,
            "error_message": None,
            "retryable": None,
            "timestamp": now_iso,
        }

        completed_msg = f"Node '{node_name}' completed"
        if llm_meta:
            execution_record["provider"] = llm_meta.get("provider")
            execution_record["model"] = llm_meta.get("model")
            execution_record["fallback_level"] = llm_meta.get("fallback_level")
            execution_record["fallback_used"] = llm_meta.get("fallback_used")
            execution_record["provider_attempts"] = llm_meta.get("provider_attempts")
            execution_record["input_tokens"] = llm_meta.get("input_tokens")
            execution_record["output_tokens"] = llm_meta.get("output_tokens")
            execution_record["total_tokens"] = llm_meta.get("total_tokens")

            if llm_meta.get("fallback_used"):
                completed_msg = (
                    f"Node '{node_name}' completed via fallback to "
                    f"{llm_meta.get('provider')} ({llm_meta.get('model')})"
                )
            elif llm_meta.get("provider"):
                completed_msg = f"Node '{node_name}' completed ({llm_meta.get('provider')})"

        execution_history.append(execution_record)

        if run_id:
            _record_db_event(
                run_id=run_id,
                stage=stage,
                status="completed",
                message=completed_msg,
                duration_ms=duration_ms,
                node_name=node_name,
                attempt=attempt,
                checkpoint_id=checkpoint_id,
            )

        return {
            **state,
            **result,
            "current_node": node_name,
            "node_attempts": node_attempts,
            "execution_history": execution_history,
            "last_error": None,

            "error": None,
        }

    return wrapper


def failed_node(state: WorkflowState) -> WorkflowState:
    run_id = state.get("run_id")
    error_msg = state.get("error", "Workflow failed")
    if run_id:
        try:
            from app.core.database import SessionLocal
            from app.persistence.models.run import Run
            from app.core.constants import RunStatus

            db = SessionLocal()
            try:
                run = db.query(Run).filter(Run.id == run_id).first()
                if run:
                    run.status = RunStatus.FAILED
                    run.error_message = error_msg
                    db.commit()
            finally:
                db.close()
        except Exception:
            pass

    return {
        **state,
        "status": "failed",
    }


def should_retry(state: WorkflowState) -> bool:
    if not state.get("error"):
        return False

    last_error = state.get("last_error")
    if last_error:
        err_type = last_error.get("error_type")
        if err_type in (
            "VALIDATION",
            "CONFIGURATION",
            "AUTHENTICATION_ERROR",
            "INVALID_REQUEST",
            "DOCUMENT_PROCESSING",
        ):
            return False

    node_name = state.get("current_node")
    node_attempts = state.get("node_attempts") or {}
    attempt = node_attempts.get(node_name) if node_name and node_name in node_attempts else state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)

    return attempt < max_retries


def route_after_classify(state: WorkflowState) -> str:
    if not state.get("error"):
        return "extract"

    if should_retry(state):
        return "classify"

    return "failed"


def route_after_extract(state: WorkflowState) -> str:
    if not state.get("error"):
        return "reconcile"

    if should_retry(state):
        return "extract"

    return "failed"


def route_after_examine(state: WorkflowState) -> str:
    if state.get("error"):
        if should_retry(state):
            return "examine"
        return "failed"

    return "generate_suggested_changes"


def route_after_generate_suggested_changes(state: WorkflowState) -> str:
    if state.get("error"):
        if should_retry(state):
            return "generate_suggested_changes"
        return "failed"

    run_id = state.get("run_id")
    if not run_id:
        return "apply_edits"

    try:
        from app.core.database import SessionLocal
        from app.persistence.models.finding import Finding
        from app.core.constants import ReviewDecision

        db = SessionLocal()
        try:
            findings = db.query(Finding).filter(Finding.run_id == run_id).all()
            if not findings:
                return "apply_edits"

            pending = [f for f in findings if f.review_decision == ReviewDecision.PENDING]
            if pending:
                return "findings_review"
        finally:
            db.close()
    except Exception:
        pass

    return "apply_edits"


def route_after_findings_review(state: WorkflowState) -> str:
    run_id = state.get("run_id")
    if not run_id:
        return "apply_edits"

    try:
        from app.core.database import SessionLocal
        from app.persistence.models.finding import Finding
        from app.core.constants import ReviewDecision

        db = SessionLocal()
        try:
            pending = db.query(Finding).filter(
                Finding.run_id == run_id,
                Finding.review_decision == ReviewDecision.PENDING
            ).all()
            if pending:
                return "findings_review"
        finally:
            db.close()
    except Exception:
        pass

    return "apply_edits"


def route_after_reconcile(state: WorkflowState) -> str:
    if state.get("error"):
        if should_retry(state):
            return "reconcile"
        return "failed"

    run_id = state.get("run_id")
    if run_id:
        try:
            from app.core.database import SessionLocal
            from app.persistence.repositories.finding import FindingRepository
            from app.services.finding_service import FindingService

            db = SessionLocal()
            try:
                finding_repo = FindingRepository(db)
                finding_service = FindingService(finding_repo)
                contradictions = state.get("contradictions", [])
                if contradictions:
                    finding_service.sync_contradiction_findings(run_id, contradictions)
                    db.commit()
            except Exception:
                db.rollback()
            finally:
                db.close()
        except Exception:
            pass

    if state.get("human_review_required", False):
        return "human_review"

    return "examine"


def route_after_human_review(state: WorkflowState) -> str:
    decision = state.get("human_decision")

    if decision == "approve":
        return "examine"

    if decision == "reject":
        return "revise"

    return "human_review"


def route_after_apply_edits(state: WorkflowState) -> str:
    if state.get("error"):
        return "failed"
    return "validate_edits"


def build_workflow(
    model_factory: ModelFactory | None = None,
    repository: WorkflowResultRepository | None = None,
):
    model_factory = model_factory or DefaultModelFactory()
    if repository is None:
        from app.core.database import SessionLocal
        repository = WorkflowResultRepository(SessionLocal())

    classify_node = ClassifyNode(model_factory=model_factory)
    extract_node = ExtractNode(model_factory=model_factory)
    reconcile_node = ReconcileNode()
    examine = ExamineNode(model_factory=model_factory)

    from app.workflow.nodes.generate_suggested_changes import GenerateSuggestedChangesNode
    generate_suggested_changes_node = GenerateSuggestedChangesNode(model_factory=model_factory)
    revise = ReviseNode(model_factory=model_factory)


    apply_edits_node = ApplyEditsNode()
    validate_edits_node = ValidateEditsNode()
    commit_node = CommitNode()
    update_node = UpdateNode()

    def classify_with_retry(state: WorkflowState) -> WorkflowState:
        return execute_with_retry(
            classify_node,
            state,
        )

    graph = StateGraph(WorkflowState)

    graph.add_node("classify", _make_emitting_wrapper("classify", classify_with_retry))
    graph.add_node("extract", _make_emitting_wrapper("extract", extract_node))
    graph.add_node("reconcile", _make_emitting_wrapper("reconcile", reconcile_node))
    graph.add_node("human_review", _make_emitting_wrapper("human_review", human_review_node))
    graph.add_node("revise", _make_emitting_wrapper("revise", revise))
    graph.add_node("examine", _make_emitting_wrapper("examine", examine))
    graph.add_node("generate_suggested_changes", _make_emitting_wrapper("generate_suggested_changes", generate_suggested_changes_node))
    graph.add_node("findings_review", _make_emitting_wrapper("findings_review", findings_review_node))
    graph.add_node("apply_edits", _make_emitting_wrapper("apply_edits", apply_edits_node))
    graph.add_node("validate_edits", _make_emitting_wrapper("validate_edits", validate_edits_node))
    graph.add_node("commit", _make_emitting_wrapper("commit", commit_node))
    graph.add_node("update", _make_emitting_wrapper("update", update_node))
    graph.add_node("failed", _make_emitting_wrapper("failed", failed_node))

    graph.add_edge(START, "classify")

    graph.add_conditional_edges(
        "classify",
        route_after_classify,
        {
            "classify": "classify",
            "extract": "extract",
            "failed": "failed",
        },
    )

    graph.add_conditional_edges(
        "extract",
        route_after_extract,
        {
            "extract": "extract",
            "reconcile": "reconcile",
            "failed": "failed",
        },
    )

    graph.add_conditional_edges(
        "reconcile",
        route_after_reconcile,
        {
            "reconcile": "reconcile",
            "human_review": "human_review",
            "examine": "examine",
            "failed": "failed",
        },
    )

    graph.add_conditional_edges(
        "human_review",
        route_after_human_review,
        {
            "human_review": "human_review",
            "examine": "examine",
            "revise": "revise",
        },
    )

    graph.add_edge("revise", "reconcile")

    graph.add_conditional_edges(
        "examine",
        route_after_examine,
        {
            "examine": "examine",
            "generate_suggested_changes": "generate_suggested_changes",
            "failed": "failed",
        },
    )

    graph.add_conditional_edges(
        "generate_suggested_changes",
        route_after_generate_suggested_changes,
        {
            "generate_suggested_changes": "generate_suggested_changes",
            "findings_review": "findings_review",
            "apply_edits": "apply_edits",
            "failed": "failed",
        },
    )

    graph.add_conditional_edges(
        "findings_review",
        route_after_findings_review,
        {
            "findings_review": "findings_review",
            "apply_edits": "apply_edits",
        },
    )

    graph.add_conditional_edges(
        "apply_edits",
        route_after_apply_edits,
        {
            "validate_edits": "validate_edits",
            "failed": "failed",
        },
    )

    # validate_edits always goes to commit (validation failure is recorded not aborted)
    graph.add_edge("validate_edits", "commit")
    graph.add_edge("commit", "update")
    graph.add_edge("update", END)

    graph.add_edge("failed", END)

    checkpointer = create_checkpointer()

    return graph.compile(
        checkpointer=checkpointer,
    )