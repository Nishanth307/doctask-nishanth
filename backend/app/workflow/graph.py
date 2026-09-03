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
from langgraph.graph import END, START, StateGraph

from app.llm.enums import ModelName
from app.llm.factory import DefaultModelFactory, ModelFactory
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


def failed_node(state: WorkflowState) -> WorkflowState:
    return {
        **state,
        "status": "failed",
    }


def should_retry(state: WorkflowState) -> bool:
    if not state.get("error"):
        return False

    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)

    return retry_count < max_retries


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

    return "apply_edits"


def route_after_findings_review(state: WorkflowState) -> str:
    run_id = state.get("run_id")
    if not run_id:
        return "apply_edits"

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

    return "apply_edits"


def route_after_reconcile(state: WorkflowState) -> str:
    if state.get("error"):
        if should_retry(state):
            return "reconcile"
        return "failed"

    run_id = state.get("run_id")
    if run_id:
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
            raise
        finally:
            db.close()

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

    classify_node = ClassifyNode(
        model_factory=model_factory,
        model_name=ModelName.GEMINI_2_5_FLASH,
    )

    extract_node = ExtractNode(
        model_factory=model_factory,
        model_name=ModelName.GEMINI_2_5_FLASH,
    )

    reconcile_node = ReconcileNode()

    examine = ExamineNode(
        model_factory=model_factory,
        model_name=ModelName.GEMINI_2_5_FLASH,
    )

    from app.workflow.nodes.generate_suggested_changes import GenerateSuggestedChangesNode
    generate_suggested_changes_node = GenerateSuggestedChangesNode(
        model_factory=model_factory,
        model_name=ModelName.GEMINI_2_5_FLASH,
    )

    revise = ReviseNode(
        model_factory=model_factory,
        model_name=ModelName.GEMINI_2_5_FLASH,
    )

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

    graph.add_node("classify", classify_with_retry)
    graph.add_node("extract", extract_node)
    graph.add_node("reconcile", reconcile_node)
    graph.add_node("human_review", human_review_node)
    graph.add_node("revise", revise)
    graph.add_node("examine", examine)
    graph.add_node("generate_suggested_changes", generate_suggested_changes_node)
    graph.add_node("findings_review", findings_review_node)
    graph.add_node("apply_edits", apply_edits_node)
    graph.add_node("validate_edits", validate_edits_node)
    graph.add_node("commit", commit_node)
    graph.add_node("update", update_node)
    graph.add_node("failed", failed_node)

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