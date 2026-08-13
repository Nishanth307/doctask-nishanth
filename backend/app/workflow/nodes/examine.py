from app.llm.enums import ModelName
from app.llm.factory import ModelFactory
from app.llm.schemas import ExaminationResult
from app.workflow.state import WorkflowState


class ExamineNode:
    def __init__(
        self,
        model_factory: ModelFactory,
        model_name: ModelName,
    ) -> None:
        self.model_factory = model_factory
        self.model_name = model_name

    def __call__(self, state: WorkflowState) -> WorkflowState:
        model = self.model_factory.create_model(
            self.model_name,
        )

        structured_model = model.with_structured_output(
            ExaminationResult,
        )

        document_text = "\n\n".join(
            document.get("text", "")
            for document in state.get("documents", [])
        )

        extracted_facts = state.get(
            "extracted_facts",
            [],
        )

        prompt = f"""
You are a document validation and examination system.

Review the extracted information against the source document.

Determine:
- whether the extracted information is valid
- confidence between 0 and 1
- any issues
- a concise summary

Do not invent information.

Source document:

{document_text}

Extracted information:

{extracted_facts}
"""

        result: ExaminationResult = structured_model.invoke(
            prompt,
        )

        return {
            **state,
            "examination": result.model_dump(),
            "error": None,
        }