from uuid import uuid4
from unittest.mock import MagicMock
import pytest
from langgraph.types import Command

from app.workflow.graph import build_workflow
from app.llm.enums import ModelName
from app.llm.schemas import ClassificationResult, DocumentCategory, ExtractionResult, ExtractedFact, ExaminationResult
from app.persistence.models.run import Run
from app.persistence.repositories.workflow_result import WorkflowResultRepository


def get_mock_model_factory(classification_res=None, extraction_res=None, examination_res=None):
    model_factory = MagicMock()
    model = MagicMock()

    def side_effect_with_structured_output(schema):
        mock_structured_model = MagicMock()
        if schema == ClassificationResult:
            mock_structured_model.invoke.return_value = classification_res or ClassificationResult(
                document_type=DocumentCategory.CONTRACT,
                confidence=0.95,
                reasoning="Standard contract",
            )
        elif schema == ExtractionResult:
            mock_structured_model.invoke.return_value = extraction_res or ExtractionResult(
                facts=[
                    ExtractedFact(field="party_a", value="ABC Ltd", confidence=0.95),
                ]
            )
        elif schema == ExaminationResult:
            mock_structured_model.invoke.return_value = examination_res or ExaminationResult(
                is_valid=True,
                confidence=0.95,
                issues=[],
                summary="Looks good",
            )
        return mock_structured_model

    model.with_structured_output.side_effect = side_effect_with_structured_output
    model_factory.create_model.return_value = model
    return model_factory


class TestWorkflowGraphIntegration:

    def test_normal_successful_path(self, db_session):
        # 1. Arrange Run row in DB
        run_id = uuid4()
        run = Run(id=run_id, name="Success Path Run")
        db_session.add(run)
        db_session.commit()

        model_factory = get_mock_model_factory()
        repository = WorkflowResultRepository(db_session)
        workflow = build_workflow(model_factory=model_factory, repository=repository)

        state = {
            "run_id": run_id,
            "document_ids": [],
            "documents": [{"text": "Agreement document"}],
            "retry_count": 0,
            "max_retries": 3,
        }
        config = {"configurable": {"thread_id": str(run_id)}}

        # 2. Act
        result = workflow.invoke(state, config)

        # 3. Assert
        assert result["status"] == "completed"
        assert result["human_review_required"] is False
        assert result["classification"] is not None
        assert len(result["extracted_facts"]) > 0
        assert result["examination"]["is_valid"] is True

        # Check DB persistence
        persisted = repository.get_by_run_id(run_id)
        assert persisted is not None
        assert persisted.status == "completed"
        assert persisted.run_id == run_id
        assert persisted.classification["document_type"] == "contract"

    def test_human_approval_path(self, db_session):
        # 1. Arrange Run row in DB
        run_id = uuid4()
        run = Run(id=run_id, name="Human Approval Run")
        db_session.add(run)
        db_session.commit()

        # Mock returns low confidence fact (0.50) to trigger human review
        low_confidence_fact = ExtractionResult(
            facts=[
                ExtractedFact(field="party_a", value="ABC Ltd", confidence=0.50),
            ]
        )
        model_factory = get_mock_model_factory(extraction_res=low_confidence_fact)
        repository = WorkflowResultRepository(db_session)
        workflow = build_workflow(model_factory=model_factory, repository=repository)

        state = {
            "run_id": run_id,
            "document_ids": [],
            "documents": [{"text": "Agreement document"}],
            "retry_count": 0,
            "max_retries": 3,
        }
        config = {"configurable": {"thread_id": str(run_id)}}

        # 2. Act -> first invoke (should interrupt)
        interrupted = workflow.invoke(state, config)

        # 3. Assert interruption
        assert "__interrupt__" in interrupted
        interrupt = interrupted["__interrupt__"][0]
        assert interrupt.value["type"] == "human_review"

        # 4. Act -> resume with approval
        result = workflow.invoke(Command(resume="approve"), config)

        # 5. Assert final result
        assert result["status"] == "completed"
        assert result["human_decision"] == "approve"
        assert result["human_review_required"] is True

        # Check DB persistence
        persisted = repository.get_by_run_id(run_id)
        assert persisted is not None
        assert persisted.human_decision == "approve"

    def test_human_rejection_revision_path(self, db_session):
        # 1. Arrange Run row in DB
        run_id = uuid4()
        run = Run(id=run_id, name="Human Rejection Run")
        db_session.add(run)
        db_session.commit()

        # Mock returns low confidence fact (0.50) to trigger human review
        low_confidence_fact = ExtractionResult(
            facts=[
                ExtractedFact(field="party_a", value="ABC Ltd", confidence=0.50),
            ]
        )
        model_factory = get_mock_model_factory(extraction_res=low_confidence_fact)
        repository = WorkflowResultRepository(db_session)
        workflow = build_workflow(model_factory=model_factory, repository=repository)

        state = {
            "run_id": run_id,
            "document_ids": [],
            "documents": [{"text": "Agreement document"}],
            "retry_count": 0,
            "max_retries": 3,
        }
        config = {"configurable": {"thread_id": str(run_id)}}

        # 2. Act -> first invoke (should interrupt)
        workflow.invoke(state, config)

        # 3. Act -> resume with reject and provide updated high-confidence facts
        result = workflow.invoke(
            Command(
                resume="reject",
                update={
                    "extracted_facts": [
                        {"field": "party_a", "value": "ABC Ltd", "confidence": 0.95}
                    ]
                },
            ),
            config,
        )

        # 4. Assert final result
        assert result["status"] == "completed"
        assert result["human_decision"] == "reject"

        # Check DB persistence
        persisted = repository.get_by_run_id(run_id)
        assert persisted is not None
        assert persisted.human_decision == "reject"

    def test_classification_retry_path(self, db_session):
        # 1. Arrange Run row in DB
        run_id = uuid4()
        run = Run(id=run_id, name="Retry Run")
        db_session.add(run)
        db_session.commit()

        model_factory = MagicMock()
        model = MagicMock()
        mock_structured_model = MagicMock()

        # Mock invoke to throw exception twice, then succeed
        call_count = 0
        def side_effect_invoke(prompt):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise RuntimeError("Temporary LLM error")
            return ClassificationResult(
                document_type=DocumentCategory.CONTRACT,
                confidence=0.95,
                reasoning="Passed after retry",
            )

        mock_structured_model.invoke.side_effect = side_effect_invoke

        def side_effect_with_structured_output(schema):
            if schema == ClassificationResult:
                return mock_structured_model
            elif schema == ExtractionResult:
                mock_extract = MagicMock()
                mock_extract.invoke.return_value = ExtractionResult(
                    facts=[ExtractedFact(field="party_a", value="ABC Ltd", confidence=0.95)]
                )
                return mock_extract
            elif schema == ExaminationResult:
                mock_examine = MagicMock()
                mock_examine.invoke.return_value = ExaminationResult(
                    is_valid=True, confidence=0.95, issues=[], summary="Checked"
                )
                return mock_examine

        model.with_structured_output.side_effect = side_effect_with_structured_output
        model_factory.create_model.return_value = model

        repository = WorkflowResultRepository(db_session)
        workflow = build_workflow(model_factory=model_factory, repository=repository)

        state = {
            "run_id": run_id,
            "max_retries": 3,
            "documents": [{"text": "Doc"}],
        }
        config = {"configurable": {"thread_id": str(run_id)}}

        # 2. Act
        result = workflow.invoke(state, config)

        # 3. Assert
        assert result["retry_count"] == 2
        assert result["error"] is None
        assert result["status"] == "completed"

    def test_classification_terminal_failure_path(self, db_session):
        # 1. Arrange Run row in DB
        run_id = uuid4()
        run = Run(id=run_id, name="Terminal Failure Run")
        db_session.add(run)
        db_session.commit()

        model_factory = MagicMock()
        model = MagicMock()
        mock_structured_model = MagicMock()

        # Always throw exception on classify
        mock_structured_model.invoke.side_effect = RuntimeError("Permanent LLM error")

        def side_effect_with_structured_output(schema):
            if schema == ClassificationResult:
                return mock_structured_model
            return MagicMock()

        model.with_structured_output.side_effect = side_effect_with_structured_output
        model_factory.create_model.return_value = model

        repository = WorkflowResultRepository(db_session)
        workflow = build_workflow(model_factory=model_factory, repository=repository)

        state = {
            "run_id": run_id,
            "max_retries": 3,
            "documents": [{"text": "Doc"}],
        }
        config = {"configurable": {"thread_id": str(run_id)}}

        # 2. Act
        result = workflow.invoke(state, config)

        # 3. Assert terminal failure
        assert result["retry_count"] == 3
        assert result["error"] == "Permanent LLM error"
        assert result.get("status") is None  # Never reached update node
