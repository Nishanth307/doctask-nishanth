"""
ACME V1 vs V2 Contradiction and Finding Persistence Integration Tests
====================================================================

Tests the 7 specific requirements from the problem statement:
1. Two-document contradiction: Given V1 and V2, contradictions == 5.
2. Finding persistence: After sync, findings == 5, PENDING, ERROR, matching run_id.
3. Provenance: Every contradiction finding contains both documents in citation["sources"].
4. No automatic resolution: Conflicting values remain present.
5. Identical documents: Same values produce 0 contradictions for that key.
6. Frontend API: GET /runs/{run_id}/details returns persisted findings.
7. Human review: Run reaches WAITING_FOR_REVIEW when pending findings exist.
"""

from uuid import uuid4
import pytest
from fastapi.testclient import TestClient

from app.core.constants import FindingSeverity, ReviewDecision, RunStatus
from app.llm.schemas import (
    ClassificationResult,
    DocumentCategory,
    ExtractedFact,
    ExtractionResult,
)
from app.main import app
from app.persistence.models.finding import Finding
from app.persistence.models.run import Run
from app.persistence.repositories.finding import FindingRepository
from app.services.finding_service import FindingService
from app.workflow.conflicts import detect_contradictions
from app.workflow.graph import build_workflow
from tests.integration.workflow.test_multi_document_contradiction import _make_model_factory, _build_state


class TestAcmeContradictionPersistence:

    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.v1_facts = [
            ExtractedFact(
                field="Initial Term",
                semantic_key="contract.initial_term",
                value="12 months",
                confidence=0.99,
                source_document="acme_contract_v1.docx",
                source_text="The initial term of this Agreement is twelve (12) months.",
            ),
            ExtractedFact(
                field="Payment Due Period",
                semantic_key="contract.payment_due_period",
                value="30 days",
                confidence=0.99,
                source_document="acme_contract_v1.docx",
                source_text="Acme will pay approved invoices within thirty (30) days of receipt.",
            ),
            ExtractedFact(
                field="Termination Notice",
                semantic_key="contract.termination_notice",
                value="60 days",
                confidence=0.99,
                source_document="acme_contract_v1.docx",
                source_text="Either party may terminate this Agreement by providing sixty (60) days written notice.",
            ),
            ExtractedFact(
                field="Insurance Coverage",
                semantic_key="contract.insurance_coverage",
                value="commercially reasonable coverage",
                confidence=0.99,
                source_document="acme_contract_v1.docx",
                source_text="The Vendor shall maintain commercially reasonable commercial general liability insurance.",
            ),
            ExtractedFact(
                field="Governing Law",
                semantic_key="contract.governing_law",
                value="New York",
                confidence=0.99,
                source_document="acme_contract_v1.docx",
                source_text="This Agreement shall be governed by the laws of the State of New York.",
            ),
            ExtractedFact(
                field="Confidentiality Obligation",
                semantic_key="contract.confidentiality",
                value="Standard obligation",
                confidence=0.99,
                source_document="acme_contract_v1.docx",
                source_text="Both parties shall keep confidential information received from the other party confidential.",
            ),
        ]

        self.v2_facts = [
            ExtractedFact(
                field="Initial Term",
                semantic_key="contract.initial_term",
                value="36 months",
                confidence=0.99,
                source_document="acme_contract_v2.docx",
                source_text="The initial term of this Agreement is thirty-six (36) months.",
            ),
            ExtractedFact(
                field="Payment Due Period",
                semantic_key="contract.payment_due_period",
                value="45 days",
                confidence=0.99,
                source_document="acme_contract_v2.docx",
                source_text="Acme will pay approved invoices within forty-five (45) days of receipt.",
            ),
            ExtractedFact(
                field="Termination Notice",
                semantic_key="contract.termination_notice",
                value="30 days",
                confidence=0.99,
                source_document="acme_contract_v2.docx",
                source_text="Either party may terminate this Agreement by providing thirty (30) days written notice.",
            ),
            ExtractedFact(
                field="Insurance Coverage",
                semantic_key="contract.insurance_coverage",
                value="$1,000,000 minimum",
                confidence=0.99,
                source_document="acme_contract_v2.docx",
                source_text="The Vendor shall maintain commercial general liability insurance with minimum coverage of $1,000,000.",
            ),
            ExtractedFact(
                field="Governing Law",
                semantic_key="contract.governing_law",
                value="California",
                confidence=0.99,
                source_document="acme_contract_v2.docx",
                source_text="This Agreement shall be governed by the laws of the State of California.",
            ),
            ExtractedFact(
                field="Confidentiality Obligation",
                semantic_key="contract.confidentiality",
                value="Standard obligation",
                confidence=0.99,
                source_document="acme_contract_v2.docx",
                source_text="Both parties shall keep confidential information received from the other party confidential.",
            ),
        ]

    def test_1_two_document_contradictions(self):
        all_facts = [f.model_dump() for f in self.v1_facts + self.v2_facts]
        contradictions = detect_contradictions(all_facts)
        assert len(contradictions) == 5, f"Expected 5 contradictions, got {len(contradictions)}"
        expected_keys = {
            "contract.initial_term",
            "contract.payment_due_period",
            "contract.termination_notice",
            "contract.insurance_coverage",
            "contract.governing_law",
        }
        actual_keys = {c["semantic_key"] for c in contradictions}
        assert actual_keys == expected_keys

    def test_2_finding_persistence(self, db_session):
        run_id = uuid4()
        run = Run(id=run_id, name="Persistence Test Run")
        db_session.add(run)
        db_session.commit()

        all_facts = [f.model_dump() for f in self.v1_facts + self.v2_facts]
        contradictions = detect_contradictions(all_facts)

        finding_repo = FindingRepository(db_session)
        finding_service = FindingService(finding_repo)
        finding_service.sync_contradiction_findings(run_id, contradictions)
        db_session.commit()

        findings = finding_repo.get_by_run_id(run_id)
        assert len(findings) == 5
        for f in findings:
            assert f.run_id == run_id
            assert f.severity == FindingSeverity.ERROR
            assert f.review_decision == ReviewDecision.PENDING
            assert f.title.startswith("Conflicting ")

    def test_3_provenance(self, db_session):
        run_id = uuid4()
        run = Run(id=run_id, name="Provenance Test Run")
        db_session.add(run)
        db_session.commit()

        all_facts = [f.model_dump() for f in self.v1_facts + self.v2_facts]
        contradictions = detect_contradictions(all_facts)

        finding_repo = FindingRepository(db_session)
        finding_service = FindingService(finding_repo)
        finding_service.sync_contradiction_findings(run_id, contradictions)
        db_session.commit()

        findings = finding_repo.get_by_run_id(run_id)
        for f in findings:
            assert f.citation is not None
            assert f.citation.get("type") == "contradiction"
            sources = f.citation.get("sources", [])
            assert len(sources) == 2
            docs = {s["document"] for s in sources}
            assert "acme_contract_v1.docx" in docs
            assert "acme_contract_v2.docx" in docs

    def test_4_no_automatic_resolution(self, db_session):
        all_facts = [f.model_dump() for f in self.v1_facts + self.v2_facts]
        contradictions = detect_contradictions(all_facts)
        term_contradiction = next(c for c in contradictions if c["semantic_key"] == "contract.initial_term")
        values = {v["value"] for v in term_contradiction["values"]}
        assert "12 months" in values
        assert "36 months" in values

    def test_5_identical_documents_no_contradiction(self):
        identical_facts = [f.model_dump() for f in self.v1_facts]
        v1_copy = [f.model_dump() for f in self.v1_facts]
        for f in v1_copy:
            f["source_document"] = "acme_contract_v1_copy.docx"
        
        contradictions = detect_contradictions(identical_facts + v1_copy)
        assert len(contradictions) == 0, f"Expected 0 contradictions for identical values, got {len(contradictions)}"

    def test_6_frontend_api_returns_findings(self, db_session):
        run_id = uuid4()
        run = Run(id=run_id, name="API Test Run", status=RunStatus.WAITING_FOR_REVIEW)
        db_session.add(run)
        db_session.commit()

        all_facts = [f.model_dump() for f in self.v1_facts + self.v2_facts]
        contradictions = detect_contradictions(all_facts)

        finding_repo = FindingRepository(db_session)
        finding_service = FindingService(finding_repo)
        finding_service.sync_contradiction_findings(run_id, contradictions)
        db_session.commit()

        client = TestClient(app)
        response = client.get(f"/api/v1/runs/{run_id}/details")
        assert response.status_code == 200
        details = response.json()
        api_findings = details.get("findings", [])
        assert len(api_findings) == 5
        assert details["run"]["pending_finding_count"] == 5

    def test_7_human_review_workflow_interruption(self, db_session):
        run_id = uuid4()
        run = Run(id=run_id, name="E2E Workflow Test Run")
        db_session.add(run)
        db_session.commit()

        extraction_results = iter([
            ExtractionResult(facts=self.v1_facts),
            ExtractionResult(facts=self.v2_facts),
        ])
        model_factory = _make_model_factory(
            extraction_side_effect=lambda *a, **k: next(extraction_results),
        )
        workflow = build_workflow(model_factory)

        state = _build_state(
            run_id,
            documents=[
                {"id": "doc1", "filename": "acme_contract_v1.docx", "text": "Contract v1 text"},
                {"id": "doc2", "filename": "acme_contract_v2.docx", "text": "Contract v2 text"},
            ]
        )
        config = {"configurable": {"thread_id": str(run_id)}}

        result = workflow.invoke(state, config)
        assert "__interrupt__" in result

        db_session.expire_all()
        findings = db_session.query(Finding).filter(Finding.run_id == run_id).all()
        assert len(findings) == 5
        assert all(f.review_decision == ReviewDecision.PENDING for f in findings)
