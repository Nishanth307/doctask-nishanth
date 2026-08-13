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
    return state


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
    if not state.get("error"):
        return "update"

    if should_retry(state):
        return "examine"

    return "failed"


def route_after_reconcile(state: WorkflowState) -> str:
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
            "human_review": "human_review",
            "examine": "examine",
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
            "update": "update",
            "failed": "failed",
        },
    )
    graph.add_edge("update", END)

    graph.add_edge("failed", END)

    checkpointer = create_checkpointer()

    return graph.compile(
        checkpointer=checkpointer,
    )