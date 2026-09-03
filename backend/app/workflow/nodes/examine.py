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
        contradictions = state.get("contradictions", [])
        run_id = state.get("run_id")

        if run_id and contradictions:
            from app.core.database import SessionLocal
            from app.persistence.repositories.finding import FindingRepository
            from app.services.finding_service import FindingService

            db = SessionLocal()
            try:
                finding_repo = FindingRepository(db)
                finding_service = FindingService(finding_repo)
                finding_service.sync_contradiction_findings(run_id, contradictions)
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()

        rules_text = "\n\n".join(
            rule.get("text", "")
            for rule in state.get("rules", [])
        )

        if contradictions and not rules_text:
            from app.workflow.conflicts import build_contradiction_examination
            result = build_contradiction_examination(contradictions)
            return {
                **state,
                "examination": result,
                "error": None,
            }



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
If any mandatory requirement in the checklist is missing, incomplete, unsupported, or violated by the document, flag it as an issue in issues.
Do not invent checklist rules. If the user-supplied rules are fully satisfied, return is_valid=True and an empty list of issues.

Return:
- is_valid: whether the document/facts conform to the user-supplied review rules (False if any rule is violated or missing)
- confidence: confidence between 0 and 1
- issues: a list of specific issues found (each describing the violation, rule reference, and the specific section affected)
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

Determine whether the extracted information is valid and consistent with the document.

Return:
- is_valid: whether the extracted information is valid
- confidence: confidence between 0 and 1
- issues: a list of specific issues found
- summary: a concise examination summary

Do not invent information.
Only make conclusions supported by the document and the extracted facts.
"""


            result: ExaminationResult = (
                structured_model.invoke(prompt)
            )

            if run_id and result and result.issues:

                from app.core.database import SessionLocal
                from app.persistence.repositories.finding import FindingRepository
                from app.services.finding_service import FindingService

                db = SessionLocal()
                try:
                    finding_repo = FindingRepository(db)
                    finding_service = FindingService(finding_repo)
                    finding_service.sync_checklist_findings(run_id, result.issues)
                    db.commit()
                except Exception:
                    db.rollback()
                    raise
                finally:
                    db.close()

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