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
                ExaminationResult,
            )

            classification = state.get("classification")

            document_type = (
                classification.document_type
                if classification
                else "other"
            )

            extracted_facts = state.get(
                "extracted_facts",
                [],
            )

            document_text = "\n\n".join(
                document.get("text", "")
                for document in state.get("documents", [])
            )

            rules_text = "\n\n".join(
                rule.get("text", "")
                for rule in state.get("rules", [])
            )

            if rules_text:
                prompt = f"""
You are a document examination system.

Evaluate the extracted facts from the source documents against the user-supplied review rules/checklist.

Original source document text:
{document_text}

Extracted facts:
{extracted_facts}

User-supplied review rules / checklist:
{rules_text}

Determine whether the extracted information and source documents violate or conform to the user-supplied review rules/checklist.
Do not invent checklist rules. If the user-supplied rules are not violated, return is_valid=True and an empty list of issues.

Return:
- is_valid: whether the document/facts conform to the user-supplied review rules
- confidence: confidence between 0 and 1
- issues: a list of specific issues found (each issue should describe the violation and reference the source/rule)
- summary: a concise examination summary
"""
            else:
                prompt = f"""
You are a document examination system.

Evaluate the extracted information from the document.

Document type:

{document_type}

Original document:

{document_text}

Extracted facts:

{extracted_facts}

Determine whether the extracted information is valid and
consistent with the document.

Return:
- is_valid: whether the extracted information is valid
- confidence: confidence between 0 and 1
- issues: a list of specific issues found
- summary: a concise examination summary

Do not invent information.
Only make conclusions supported by the document and
the extracted facts.

Return an examination result.
"""

            result: ExaminationResult = (
                structured_model.invoke(prompt)
            )

            return {
                **state,
                "examination": result,
                "error": None,
            }

        except Exception as exc:
            return {
                **state,
                "retry_count": retry_count + 1,
                "error": str(exc),
            }