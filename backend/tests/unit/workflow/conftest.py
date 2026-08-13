import pytest
from unittest.mock import MagicMock
from app.llm.schemas import ClassificationResult, DocumentCategory, ExtractionResult, ExtractedFact, ExaminationResult

@pytest.fixture(autouse=True)
def mock_default_model_factory(monkeypatch):
    mock_factory_cls = MagicMock()
    mock_factory_instance = MagicMock()
    
    mock_model = MagicMock()
    
    def side_effect_with_structured_output(schema):
        mock_structured_model = MagicMock()
        if schema == ClassificationResult:
            mock_structured_model.invoke.return_value = ClassificationResult(
                document_type=DocumentCategory.CONTRACT,
                confidence=0.95,
                reasoning="The document contains contractual terms.",
            )
        elif schema == ExtractionResult:
            mock_structured_model.invoke.return_value = ExtractionResult(
                facts=[
                    ExtractedFact(field="party_a", value="ABC Ltd", confidence=0.95),
                    ExtractedFact(field="party_b", value="XYZ Ltd", confidence=0.95),
                ]
            )
        elif schema == ExaminationResult:
            mock_structured_model.invoke.return_value = ExaminationResult(
                is_valid=True,
                confidence=0.95,
                issues=[],
                summary="The extracted information is consistent.",
            )
        return mock_structured_model
    
    mock_model.with_structured_output.side_effect = side_effect_with_structured_output
    mock_factory_instance.create_model.return_value = mock_model
    
    mock_factory_cls.return_value = mock_factory_instance
    
    monkeypatch.setattr("app.workflow.graph.DefaultModelFactory", mock_factory_cls)

    from uuid import uuid4
    mock_repo_cls = MagicMock()
    mock_repo_instance = MagicMock()
    persisted_mock = MagicMock()
    persisted_mock.id = uuid4()
    mock_repo_instance.create.return_value = persisted_mock
    mock_repo_cls.return_value = mock_repo_instance
    monkeypatch.setattr("app.workflow.graph.WorkflowResultRepository", mock_repo_cls)

    return mock_factory_instance
