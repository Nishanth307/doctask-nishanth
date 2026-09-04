from app.llm.enums import ModelName
from app.llm.factory import ModelFactory
from app.llm.schemas import ClassificationResult
from app.workflow.state import WorkflowState


class ClassifyNode:
    def __init__(
        self,
        model_factory: ModelFactory,
        model_name: ModelName | str | None = None,
    ) -> None:
        self.model_factory = model_factory
        self.model_name = model_name

    def __call__(
        self,
        state: WorkflowState,
    ) -> WorkflowState:
        retry_count = state.get("retry_count", 0)

        # Used by tests to simulate a classification failure.
        if state.get("simulate_failure"):
            return {
                **state,
                "retry_count": retry_count + 1,
                "error": "Classification failed",
            }

        try:
            model = self.model_factory.create_model(
                self.model_name,
            )

            structured_model = model.with_structured_output(
                ClassificationResult,
            )

            document_text = "\n\n".join(
                document.get("text", "")
                for document in state.get("documents", [])
            )

            prompt = f"""
You are a document classification system.

Classify the document into exactly one of these categories:

- contract
- policy
- report
- invoice
- other

Return:
- document_type
- confidence between 0 and 1
- concise reasoning

Do not invent information.

Document:

{document_text}
"""

            result: ClassificationResult = (
                structured_model.invoke(prompt)
            )

            return {
                **state,
                "classification": result,
                "error": None,
            }

        except Exception as exc:
            return {
                **state,
                "retry_count": retry_count + 1,
                "error": str(exc),
            }