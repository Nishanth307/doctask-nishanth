from uuid import uuid4
from unittest.mock import MagicMock
import pytest

from app.llm.enums import ModelName
from app.llm.schemas import (
    ClassificationResult,
    DocumentCategory,
    ExtractionResult,
    ExtractedFact,
    ExaminationResult,
)
from app.persistence.models.finding import Finding
from app.persistence.models.run import Run
from app.core.constants import FindingSeverity, ReviewDecision
from app.workflow.graph import build_workflow


class TestNegativeContradictionsAndReviewRules:
    """
    Negative test cases verifying that contradictions between documents
    and violations against review rules are accurately identified, persisted
    as Finding records in the database, and gated by human review.
    """

    def test_negative_contradiction_between_documents_creates_finding(self, db_session):
        run_id = uuid4()
        run = Run(id=run_id, name="Test Negative Conflict Run")
        db_session.add(run)
        db_session.commit()

        model_factory = MagicMock()
        model = MagicMock()

        class_res = ClassificationResult(
            document_type=DocumentCategory.CONTRACT,
            confidence=0.95,
            reasoning="Contract document corpus",
        )

        # Document 1 has 12 months, Document 2 has 36 months
        extract_res_doc1 = ExtractionResult(
            facts=[
                ExtractedFact(
                    field="contract term",
                    semantic_key="agreement.duration",
                    value="12 months",
                    confidence=0.90,
                    source_document="negative_contract_v1.pdf",
                    source_text="The agreement lasts for 12 months.",
                )
            ]
        )
        extract_res_doc2 = ExtractionResult(
            facts=[
                ExtractedFact(
                    field="agreement length",
                    semantic_key="agreement.duration",
                    value="36 months",
                    confidence=0.95,
                    source_document="negative_contract_v2.pdf",
                    source_text="The agreement has a term of 36 months.",
                )
            ]
        )

        extraction_iter = iter([extract_res_doc1, extract_res_doc2])

        def side_effect_with_structured_output(schema):
            mock_structured = MagicMock()
            if schema == ClassificationResult:
                mock_structured.invoke.return_value = class_res
            elif schema == ExtractionResult:
                mock_structured.invoke.side_effect = lambda *args, **kwargs: next(extraction_iter)
            elif schema == ExaminationResult:
                # Should not be reached if examine builds contradiction examination directly
                mock_structured.invoke.return_value = ExaminationResult(
                    is_valid=False,
                    confidence=0.95,
                    issues=["Contradiction found"],
                    summary="Corpus has conflicts",
                )
            return mock_structured

        model.with_structured_output.side_effect = side_effect_with_structured_output
        model_factory.create_model.return_value = model

        workflow = build_workflow(model_factory)

        state = {
            "run_id": run_id,
            "document_ids": [],
            "documents": [
                {
                    "id": "doc1",
                    "filename": "negative_contract_v1.pdf",
                    "text": "The agreement lasts for 12 months.",
                },
                {
                    "id": "doc2",
                    "filename": "negative_contract_v2.pdf",
                    "text": "The agreement has a term of 36 months.",
                },
            ],
            "rules": [],
            "retry_count": 0,
            "max_retries": 3,
        }
        config = {"configurable": {"thread_id": str(run_id)}}

        # Run workflow: should halt or reach review due to contradictions
        result = workflow.invoke(state, config)

        # 1. Verify contradictions in workflow state
        assert "contradictions" in result
        assert len(result["contradictions"]) == 1
        contradiction = result["contradictions"][0]
        assert contradiction["semantic_key"] == "agreement.duration"
        assert len(contradiction["values"]) == 2

        # 2. Verify Findings in DB
        db_findings = db_session.query(Finding).filter(Finding.run_id == run_id).all()
        assert len(db_findings) == 1

        finding = db_findings[0]
        assert finding.severity == FindingSeverity.ERROR
        assert finding.review_decision == ReviewDecision.PENDING
        assert finding.title == "Conflicting contract term"
        assert "Conflicting values were found" in finding.description
        assert finding.finding_metadata["semantic_key"] == "agreement.duration"
        assert finding.citation["type"] == "contradiction"
        assert len(finding.citation["sources"]) == 2

    def test_negative_review_rules_violation_creates_policy_findings(self, db_session):
        run_id = uuid4()
        run = Run(id=run_id, name="Test Negative Review Rules Run")
        db_session.add(run)
        db_session.commit()

        model_factory = MagicMock()
        model = MagicMock()

        class_res = ClassificationResult(
            document_type=DocumentCategory.CONTRACT,
            confidence=0.95,
            reasoning="Contract document",
        )

        extract_res = ExtractionResult(
            facts=[
                ExtractedFact(
                    field="governing law",
                    semantic_key="agreement.governing_law",
                    value="State of California",
                    confidence=0.95,
                    source_document="vendor_agreement.pdf",
                    source_text="This agreement is governed by the laws of the State of California.",
                ),
                ExtractedFact(
                    field="liability cap",
                    semantic_key="agreement.liability_cap",
                    value="Unlimited",
                    confidence=0.90,
                    source_document="vendor_agreement.pdf",
                    source_text="Liability shall be unlimited for all breach events.",
                ),
            ]
        )

        # Examination evaluating against rules detects violations
        exam_res = ExaminationResult(
            is_valid=False,
            confidence=0.95,
            issues=[
                "Governing law is California, but Rule 1 requires Delaware law.",
                "Liability is unlimited, violating Rule 2 requiring liability capped at 1x contract value.",
            ],
            summary="The agreement violates 2 policy checklist rules.",
        )

        def side_effect_with_structured_output(schema):
            mock_structured = MagicMock()
            if schema == ClassificationResult:
                mock_structured.invoke.return_value = class_res
            elif schema == ExtractionResult:
                mock_structured.invoke.return_value = extract_res
            elif schema == ExaminationResult:
                mock_structured.invoke.return_value = exam_res
            return mock_structured

        model.with_structured_output.side_effect = side_effect_with_structured_output
        model_factory.create_model.return_value = model

        workflow = build_workflow(model_factory)

        state = {
            "run_id": run_id,
            "document_ids": [],
            "documents": [
                {
                    "id": "doc1",
                    "filename": "vendor_agreement.pdf",
                    "text": "This agreement is governed by California law. Liability is unlimited.",
                }
            ],
            "rules": [
                {"id": "rule1", "filename": "legal_playbook.txt", "text": "Rule 1: Governing law must be Delaware."},
                {"id": "rule2", "filename": "legal_playbook.txt", "text": "Rule 2: Liability must be capped at 1x contract value."},
            ],
            "retry_count": 0,
            "max_retries": 3,
        }
        config = {"configurable": {"thread_id": str(run_id)}}

        result = workflow.invoke(state, config)

        # 1. State check
        assert result["examination"].is_valid is False
        assert len(result["examination"].issues) == 2

        # 2. Database findings check
        db_findings = db_session.query(Finding).filter(Finding.run_id == run_id).all()
        assert len(db_findings) == 2

        for finding in db_findings:
            assert finding.severity == FindingSeverity.ERROR
            assert finding.review_decision == ReviewDecision.PENDING
            assert finding.title == "Policy Violation"
            assert finding.finding_metadata["type"] == "violation"

        descriptions = {f.description for f in db_findings}
        assert "Governing law is California, but Rule 1 requires Delaware law." in descriptions
        assert "Liability is unlimited, violating Rule 2 requiring liability capped at 1x contract value." in descriptions

    def test_negative_combined_contradictions_and_rules_full_lifecycle(self, db_session):
        from langgraph.types import Command
        from app.persistence.models.report import Report

        run_id = uuid4()
        run = Run(id=run_id, name="Test Combined Lifecycle Run")
        db_session.add(run)
        db_session.commit()

        model_factory = MagicMock()
        model = MagicMock()

        class_res = ClassificationResult(
            document_type=DocumentCategory.CONTRACT,
            confidence=0.95,
            reasoning="Contracts",
        )

        doc1_facts = ExtractionResult(
            facts=[
                ExtractedFact(
                    field="contract term",
                    semantic_key="agreement.duration",
                    value="12 months",
                    confidence=0.90,
                    source_document="contract_a.pdf",
                    source_text="Contract term is 12 months.",
                ),
            ]
        )
        doc2_facts = ExtractionResult(
            facts=[
                ExtractedFact(
                    field="agreement length",
                    semantic_key="agreement.duration",
                    value="36 months",
                    confidence=0.95,
                    source_document="contract_b.pdf",
                    source_text="Agreement length is 36 months.",
                ),
            ]
        )

        extraction_iter = iter([doc1_facts, doc2_facts])

        exam_res = ExaminationResult(
            is_valid=False,
            confidence=0.95,
            issues=[
                "Rule violation: Contract exceeds maximum duration limit of 24 months.",
            ],
            summary="Found rule violations in addition to cross-document contradictions.",
        )

        def side_effect_with_structured_output(schema):
            mock_structured = MagicMock()
            if schema == ClassificationResult:
                mock_structured.invoke.return_value = class_res
            elif schema == ExtractionResult:
                mock_structured.invoke.side_effect = lambda *args, **kwargs: next(extraction_iter)
            elif schema == ExaminationResult:
                mock_structured.invoke.return_value = exam_res
            return mock_structured

        model.with_structured_output.side_effect = side_effect_with_structured_output
        model_factory.create_model.return_value = model

        workflow = build_workflow(model_factory)

        state = {
            "run_id": run_id,
            "document_ids": [],
            "documents": [
                {"id": "doc1", "filename": "contract_a.pdf", "text": "Contract term is 12 months."},
                {"id": "doc2", "filename": "contract_b.pdf", "text": "Agreement length is 36 months."},
            ],
            "rules": [
                {"id": "rule1", "filename": "rules.txt", "text": "Rule: Contract term must not exceed 24 months."}
            ],
            "retry_count": 0,
            "max_retries": 3,
        }
        config = {"configurable": {"thread_id": str(run_id)}}

        # First invoke: interrupts at human review due to contradiction
        result = workflow.invoke(state, config)
        assert "__interrupt__" in result

        # Check DB finding for contradiction exists
        db_findings = db_session.query(Finding).filter(Finding.run_id == run_id).all()
        assert len(db_findings) == 1
        assert db_findings[0].finding_metadata["type"] == "contradiction"

        # Resume human review: approve
        result_resumed = workflow.invoke(Command(resume="approve"), config)

        # After resume and examine, findings review should interrupt if there are pending findings
        db_session.expire_all()
        findings_after_examine = db_session.query(Finding).filter(Finding.run_id == run_id).all()
        assert len(findings_after_examine) >= 1

        # Approve all findings in DB
        for f in findings_after_examine:
            f.review_decision = ReviewDecision.APPROVED
        db_session.commit()

        # Resume findings review to commit
        final_state = workflow.invoke(Command(resume="approve"), config)
        assert final_state.get("status") == "completed"

        # Verify generated report
        report = db_session.query(Report).filter(Report.run_id == run_id).first()
        assert report is not None
        assert report.approved is True
        assert "Conflicting contract term" in report.content

    def test_negative_missing_mandatory_insurance_requirement(self, db_session):
        run_id = uuid4()
        run = Run(id=run_id, name="Test Missing Insurance Requirement Run")
        db_session.add(run)
        db_session.commit()

        model_factory = MagicMock()
        model = MagicMock()

        class_res = ClassificationResult(
            document_type=DocumentCategory.CONTRACT,
            confidence=0.95,
            reasoning="Vendor services agreement",
        )

        vendor_doc_text = """VENDOR SERVICES AGREEMENT

This Agreement is between Acme Corporation and Beta Services Ltd.

Term: 24 months.

Payment is due within 30 days of invoice receipt.

Either party may terminate this Agreement with 30 days written notice.

The Vendor shall maintain commercially reasonable insurance coverage
during the term of this Agreement.

Governing law: New York.

No specific minimum insurance coverage amount is stated in this agreement."""

        checklist_rules_text = """VENDOR CONTRACT REVIEW CHECKLIST

The contract must contain:

1. Contract term.
2. Payment terms.
3. Termination notice period.
4. Governing law.
5. General liability insurance coverage of at least $2,000,000.

A finding must be raised when a mandatory requirement is missing,
incomplete, or does not meet the stated minimum.

Do not infer missing information.
If the contract does not state a minimum insurance amount,
report the requirement as unsupported or missing."""

        extract_res = ExtractionResult(
            facts=[
                ExtractedFact(
                    field="contract term",
                    semantic_key="agreement.duration",
                    value="24 months",
                    confidence=0.95,
                    source_document="vendor_agreement.pdf",
                    source_text="Term: 24 months.",
                ),
                ExtractedFact(
                    field="payment terms",
                    semantic_key="payment.due_period",
                    value="30 days",
                    confidence=0.95,
                    source_document="vendor_agreement.pdf",
                    source_text="Payment is due within 30 days of invoice receipt.",
                ),
                ExtractedFact(
                    field="termination notice",
                    semantic_key="agreement.termination_notice",
                    value="30 days",
                    confidence=0.95,
                    source_document="vendor_agreement.pdf",
                    source_text="Either party may terminate this Agreement with 30 days written notice.",
                ),
                ExtractedFact(
                    field="insurance coverage",
                    semantic_key="insurance.coverage",
                    value="commercially reasonable insurance coverage",
                    confidence=0.90,
                    source_document="vendor_agreement.pdf",
                    source_text="The Vendor shall maintain commercially reasonable insurance coverage during the term of this Agreement.",
                ),
                ExtractedFact(
                    field="governing law",
                    semantic_key="agreement.governing_law",
                    value="New York",
                    confidence=0.95,
                    source_document="vendor_agreement.pdf",
                    source_text="Governing law: New York.",
                ),
            ]
        )

        exam_res = ExaminationResult(
            is_valid=False,
            confidence=0.95,
            issues=[
                "Missing required insurance coverage amount: General liability insurance coverage of at least $2,000,000 is required by checklist rule 5, but vendor_agreement.pdf only states 'commercially reasonable insurance coverage' with no minimum coverage amount specified. Requirement is unsupported.",
            ],
            summary="The agreement fails checklist rule 5 because minimum $2,000,000 general liability insurance is missing.",
        )

        def side_effect_with_structured_output(schema):
            mock_structured = MagicMock()
            if schema == ClassificationResult:
                mock_structured.invoke.return_value = class_res
            elif schema == ExtractionResult:
                mock_structured.invoke.return_value = extract_res
            elif schema == ExaminationResult:
                mock_structured.invoke.return_value = exam_res
            return mock_structured

        model.with_structured_output.side_effect = side_effect_with_structured_output
        model_factory.create_model.return_value = model

        workflow = build_workflow(model_factory)

        state = {
            "run_id": run_id,
            "document_ids": [],
            "documents": [
                {
                    "id": "doc1",
                    "filename": "vendor_agreement.pdf",
                    "text": vendor_doc_text,
                }
            ],
            "rules": [
                {
                    "id": "rule_doc",
                    "filename": "vendor_contract_checklist.pdf",
                    "text": checklist_rules_text,
                }
            ],
            "retry_count": 0,
            "max_retries": 3,
        }
        config = {"configurable": {"thread_id": str(run_id)}}

        result = workflow.invoke(state, config)

        # 1. State check
        assert result["examination"].is_valid is False
        assert len(result["examination"].issues) == 1
        assert "insurance" in result["examination"].issues[0].lower()

        # 2. Database findings check
        db_findings = db_session.query(Finding).filter(Finding.run_id == run_id).all()
        assert len(db_findings) == 1

        finding = db_findings[0]
        assert finding.severity == FindingSeverity.ERROR
        assert finding.review_decision == ReviewDecision.PENDING
        assert finding.title == "Policy Violation"
        assert finding.finding_metadata["type"] == "violation"
        assert "2,000,000" in finding.description
        assert "insurance" in finding.description.lower()


