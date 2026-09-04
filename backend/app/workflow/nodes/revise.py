from app.llm.enums import ModelName
from app.llm.factory import ModelFactory
from app.llm.schemas import ExtractionResult
from app.workflow.state import WorkflowState


class ReviseNode:
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

        try:
            model = self.model_factory.create_model(
                self.model_name,
            )

            structured_model = model.with_structured_output(
                ExtractionResult,
            )

            document_text = "\n\n".join(
                document.get("text", "")
                for document in state.get("documents", [])
            )

            extracted_facts = state.get(
                "extracted_facts",
                [],
            )

            human_decision = state.get(
                "human_decision",
            )

            prompt = f"""
You are revising extracted information from a document
after human review.

The human reviewer rejected the previous extraction.

Human decision:

{human_decision}

Previous extracted facts:

{extracted_facts}

Original document:

{document_text}

Revise the extracted facts based only on information
supported by the original document.

Do not invent information.

Return the revised facts with:
- field
- value
- confidence between 0 and 1
"""

            result: ExtractionResult = (
                structured_model.invoke(prompt)
            )

            return {
                **state,
                "extracted_facts": [
                    fact.model_dump()
                    for fact in result.facts
                ],
                "human_review_required": False,
                "error": None,
            }

        except Exception as exc:
            return {
                **state,
                "retry_count": retry_count + 1,
                "error": str(exc),
            }
