from langgraph.graph import END, START, StateGraph
from app.workflow.checkpointer import create_checkpointer
from app.workflow.state import WorkflowState
from app.workflow.nodes.human_review import human_review_node

def classify_node(state: WorkflowState) -> WorkflowState:
    retry_count = state.get("retry_count",0)
    if state.get("simulate_failure", False):
        return {
            **state,
            "retry_count": retry_count + 1,
            "error":  "Classification failed",
        }
    return {
        **state,
        "error": None
    }

def extract_node(state: WorkflowState) -> WorkflowState:
    return state

def reconcile_node(state: WorkflowState) -> WorkflowState:
    return state

def revise_node(state: WorkflowState) -> WorkflowState:
    return state

def examine_node(state: WorkflowState) -> WorkflowState:
    return state

def update_node(state: WorkflowState) -> WorkflowState:
    return state

def failed_node(state: WorkflowState) -> WorkflowState:
    return state

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

def route_after_classify(state: WorkflowState) -> str:
    if state.get("error"):
        retry_count = state.get("retry_count", 0)
        max_tries = state.get("max_retries", 3)

        if retry_count < max_tries:
            
            return "classify"
        return "failed"
    return "extract"

def build_workflow():
    graph = StateGraph(WorkflowState)

# Nodes
    graph.add_node("classify", classify_node)
    graph.add_node("extract", extract_node)
    graph.add_node("reconcile", reconcile_node)
    graph.add_node("human_review", human_review_node)
    graph.add_node("revise", revise_node)
    graph.add_node("examine", examine_node)
    graph.add_node("update", update_node)
    graph.add_node("failed", failed_node)

    #Entry point
    graph.add_edge(START, "classify")

    # Classification → conditional routing
    graph.add_conditional_edges(
        "classify",
        route_after_classify,
        {
            "classify": "classify",
            "extract": "extract",
            "failed": "failed",
        },
    )

    #Normal flow
    graph.add_edge("extract","reconcile")

     # Reconciliation → human review or continue
    graph.add_conditional_edges(
        "reconcile",
        route_after_reconcile,
        {
            "human_review": "human_review",
            "examine": "examine",
        },
    )

    # Human decision → examine or revise
    graph.add_conditional_edges(
        "human_review",
        route_after_human_review,
        {
            "human_review": "human_review",
            "examine": "examine",
            "revise": "revise",
        },
    )

    # Revision goes back through reconciliation for re-evaluation
    graph.add_edge("revise", "reconcile")

    # Final processing
    graph.add_edge("examine", "update")
    graph.add_edge("update", END)

    #Terminal Failure
    graph.add_edge("failed", END)

    checkpointer = create_checkpointer()

    return graph.compile(
        checkpointer=checkpointer,
    )



#                     ┌──────── retry ────────┐
#                     │                       │
# START → classify ───┴──→ extract → reconcile
#                                       │
#                               ┌───────┴────────┐
#                               │                │
#                          human review      no review
#                               │                │
#                               ▼                ▼
#                        human_review          examine
#                               │                │
#                        ┌──────┴──────┐         │
#                        ▼             ▼         │
#                     approve       reject       │
#                        │             │          │
#                        ▼             ▼          │
#                     examine        revise ──────┘
#                        │
#                        ▼
#                      update
#                        │
#                        ▼
#                       END

# workflow
#    ↓
# needs human decision
#    ↓
# PAUSE
#    ↓
# user provides decision
#    ↓
# RESUME