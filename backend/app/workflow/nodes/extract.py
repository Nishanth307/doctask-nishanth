from app.llm.enums import ModelName
from app.llm.factory import ModelFactory
from app.llm.schemas import ExtractionResult
from app.workflow.state import WorkflowState


class ExtractNode:
    def __init__(
        self,
        model_factory: ModelFactory,
        model_name: ModelName,
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

            classification = state.get("classification")

            document_type = (
                classification.document_type
                if classification
                else "other"
            )

            prompt = f"""
You are a document information extraction system.

The document was classified as:

{document_type}

Extract the important factual information from the document.

For every fact return:
- field
- value
- confidence between 0 and 1

Do not invent information.
Only extract information supported by the document.

Document:

{document_text}
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
                "error": None,
            }

        except Exception as exc:
            return {
                **state,
                "retry_count": retry_count + 1,
                "error": str(exc),
            }