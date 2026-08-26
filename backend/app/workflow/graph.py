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
from app.workflow.nodes.update import UpdateNode
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

    run_id = state.get("run_id")
    if not run_id:
        return "commit"

    from app.core.database import SessionLocal
    from app.persistence.models.finding import Finding
    from app.persistence.repositories.finding import FindingRepository
    from app.services.finding_service import FindingService
    from app.core.constants import ReviewDecision

    db = SessionLocal()
    try:
        finding_repo = FindingRepository(db)
        finding_service = FindingService(finding_repo)

        contradictions = state.get("contradictions", [])
        finding_service.sync_contradiction_findings(run_id, contradictions)

        examination = state.get("examination")
        issues = examination.issues if examination else []
        finding_service.sync_checklist_findings(run_id, issues)
        db.commit()

        findings = db.query(Finding).filter(Finding.run_id == run_id).all()
        if not findings:
            return "commit"

        pending = [f for f in findings if f.review_decision == ReviewDecision.PENDING]
        if pending:
            return "findings_review"
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return "commit"



def route_after_findings_review(state: WorkflowState) -> str:
    run_id = state.get("run_id")
    if not run_id:
        return "commit"

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

    return "commit"


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

    revise = ReviseNode(
        model_factory=model_factory,
        model_name=ModelName.GEMINI_2_5_FLASH,
    )

    update = UpdateNode()

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

    from app.workflow.nodes.update import CommitNode, findings_review_node
    commit_node = CommitNode()
    graph.add_node("findings_review", findings_review_node)
    graph.add_node("commit", commit_node)

    graph.add_node("update", update)
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
            "findings_review": "findings_review",
            "commit": "commit",
            "failed": "failed",
        },
    )

    graph.add_conditional_edges(
        "findings_review",
        route_after_findings_review,
        {
            "findings_review": "findings_review",
            "commit": "commit",
        },
    )

    graph.add_edge("commit", "update")
    graph.add_edge("update", END)

    graph.add_edge("failed", END)

    checkpointer = create_checkpointer()

    return graph.compile(
        checkpointer=checkpointer,
    )