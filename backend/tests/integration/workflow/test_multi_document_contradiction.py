"""
Multi-Document Contradiction Integration Tests
==============================================

Tests the complete pipeline for processing multiple source documents in a
single run and verifying that contradictions are correctly:

  1. Ingested      - all documents enter state["documents"]
  2. Extracted     - facts extracted from ALL documents with source provenance
  3. Reconciled    - cross-document contradictions detected without resolution
  4. Persisted     - every contradiction becomes a Finding(review_decision=PENDING)
  5. Gated         - workflow stops at human-review gate while findings are pending
  6. Surfaced      - GET /runs/{run_id}/details returns finding rows
  7. Reported      - Database count == API count

No hardcoded filenames, no regex rules, no mock findings, no majority voting.
Contradictions come solely from the normal workflow pipeline.
"""

from uuid import uuid4
from unittest.mock import MagicMock

import pytest

from app.core.constants import FindingSeverity, ReviewDecision
from app.llm.schemas import (
    ClassificationResult,
    DocumentCategory,
    ExaminationResult,
    ExtractedFact,
    ExtractionResult,
)
from app.persistence.models.finding import Finding
from app.persistence.models.run import Run
from app.workflow.graph import build_workflow


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_model_factory(
    classification_res=None,
    extraction_side_effect=None,
    examination_res=None,
):
    """
    Return a MagicMock model factory whose behaviour can be customised per
    LLM schema.

    extraction_side_effect must be a *callable* (lambda / function) that is
    given to mock_structured.invoke.side_effect so callers can return a
    different value each time (e.g. cycling through multiple documents).
    """
    model_factory = MagicMock()
    model = MagicMock()

    default_classification = ClassificationResult(
        document_type=DocumentCategory.CONTRACT,
        confidence=0.95,
        reasoning="Standard service contract",
    )
    default_examination = ExaminationResult(
        is_valid=True,
        confidence=0.95,
        issues=[],
        summary="Documents are internally consistent",
    )

    def _with_structured_output(schema):
        mock_structured = MagicMock()

        if schema == ClassificationResult:
            mock_structured.invoke.return_value = (
                classification_res or default_classification
            )

        elif schema == ExtractionResult:
            if extraction_side_effect is not None:
                mock_structured.invoke.side_effect = extraction_side_effect
            else:
                mock_structured.invoke.return_value = ExtractionResult(facts=[])

        elif schema == ExaminationResult:
            mock_structured.invoke.return_value = (
                examination_res or default_examination
            )

        return mock_structured

    model.with_structured_output.side_effect = _with_structured_output
    model_factory.create_model.return_value = model
    return model_factory


def _build_state(run_id, documents, rules=None):
    return {
        "run_id": run_id,
        "document_ids": [],
        "documents": documents,
        "rules": rules or [],
        "retry_count": 0,
        "max_retries": 3,
    }


# ---------------------------------------------------------------------------
# Test 1 - single source document: no cross-document contradiction
# ---------------------------------------------------------------------------

class TestSingleDocumentNoContradiction:
    """
    With only one source document there can be no cross-document contradiction.
    Expect: findings == 0, workflow completes normally.
    """

    def test_single_document_produces_no_contradictions(self, db_session):
        run_id = uuid4()
        run = Run(id=run_id, name="Single Doc No Contradiction")
        db_session.add(run)
        db_session.commit()

        extraction_results = iter([
            ExtractionResult(
                facts=[
                    ExtractedFact(
                        field="payment terms",
                        semantic_key="payment.due_period",
                        value="30 days",
                        confidence=0.95,
                        source_document="document_a.docx",
                        source_text="Payment is due within 30 days.",
                    ),
                ]
            ),
        ])

        model_factory = _make_model_factory(
            extraction_side_effect=lambda *a, **k: next(extraction_results),
        )
        workflow = build_workflow(model_factory)

        state = _build_state(
            run_id,
            documents=[
                {
                    "id": "doc1",
                    "filename": "document_a.docx",
                    "text": "Payment is due within 30 days.",
                },
            ],
        )
        config = {"configurable": {"thread_id": str(run_id)}}

        result = workflow.invoke(state, config)

        assert result.get("status") == "completed", (
            f"Expected status=completed, got {result.get('status')}"
        )
        assert result.get("contradictions", []) == []

        db_findings = (
            db_session.query(Finding).filter(Finding.run_id == run_id).all()
        )
        assert len(db_findings) == 0, (
            f"Expected 0 findings for single-document run, got {len(db_findings)}"
        )


# ---------------------------------------------------------------------------
# Test 2 - two consistent documents: no contradiction
# ---------------------------------------------------------------------------

class TestTwoConsistentDocumentsNoContradiction:
    """
    Two documents that agree on every overlapping semantic_key must not
    produce any contradiction findings.
    """

    def test_consistent_documents_produce_no_findings(self, db_session):
        run_id = uuid4()
        run = Run(id=run_id, name="Two Consistent Docs")
        db_session.add(run)
        db_session.commit()

        doc_a_extraction = ExtractionResult(
            facts=[
                ExtractedFact(
                    field="governing law",
                    semantic_key="agreement.governing_law",
                    value="New York",
                    confidence=0.95,
                    source_document="document_a.docx",
                    source_text="This agreement is governed by New York law.",
                ),
                ExtractedFact(
                    field="payment terms",
                    semantic_key="payment.due_period",
                    value="30 days",
                    confidence=0.95,
                    source_document="document_a.docx",
                    source_text="Payment due within 30 days.",
                ),
            ]
        )

        doc_b_extraction = ExtractionResult(
            facts=[
                ExtractedFact(
                    field="governing law",
                    semantic_key="agreement.governing_law",
                    value="New York",
                    confidence=0.95,
                    source_document="document_b.docx",
                    source_text="Governed by the laws of the State of New York.",
                ),
                ExtractedFact(
                    field="payment deadline",
                    semantic_key="payment.due_period",
                    value="30 days",
                    confidence=0.95,
                    source_document="document_b.docx",
                    source_text="Invoice must be settled within 30 days.",
                ),
            ]
        )

        extraction_results = iter([doc_a_extraction, doc_b_extraction])
        model_factory = _make_model_factory(
            extraction_side_effect=lambda *a, **k: next(extraction_results),
        )
        workflow = build_workflow(model_factory)

        state = _build_state(
            run_id,
            documents=[
                {
                    "id": "doc1",
                    "filename": "document_a.docx",
                    "text": "Governed by New York law. Payment due 30 days.",
                },
                {
                    "id": "doc2",
                    "filename": "document_b.docx",
                    "text": "Governed by New York law. Invoice settled 30 days.",
                },
            ],
        )
        config = {"configurable": {"thread_id": str(run_id)}}

        result = workflow.invoke(state, config)

        assert result.get("status") == "completed", (
            f"Expected status=completed, got {result.get('status')}"
        )
        assert result.get("contradictions", []) == []

        db_findings = (
            db_session.query(Finding).filter(Finding.run_id == run_id).all()
        )
        assert len(db_findings) == 0, (
            f"Expected 0 findings for consistent-document run, got {len(db_findings)}"
        )


# ---------------------------------------------------------------------------
# Test 3 - two contradictory documents: findings > 0
# ---------------------------------------------------------------------------

class TestTwoContradictoryDocumentsCreatesFindings:
    """
    Two documents that disagree on the same semantic field must produce:
    - state["contradictions"] with the conflicting field
    - Finding records in DB (review_decision=PENDING, severity=ERROR)
    - citation.sources containing both source document filenames
    - workflow interrupting at the human-review gate
    """

    def test_two_contradictory_docs_create_findings(self, db_session):
        run_id = uuid4()
        run = Run(id=run_id, name="Two Contradictory Docs")
        db_session.add(run)
        db_session.commit()

        doc_a_extraction = ExtractionResult(
            facts=[
                ExtractedFact(
                    field="payment terms",
                    semantic_key="payment.due_period",
                    value="30 days",
                    confidence=0.95,
                    source_document="document_a.docx",
                    source_text="Payment is due within 30 days of invoice receipt.",
                ),
            ]
        )
        doc_b_extraction = ExtractionResult(
            facts=[
                ExtractedFact(
                    field="payment deadline",
                    semantic_key="payment.due_period",
                    value="60 days",
                    confidence=0.95,
                    source_document="document_b.docx",
                    source_text="Invoices must be settled within 60 days.",
                ),
            ]
        )

        extraction_results = iter([doc_a_extraction, doc_b_extraction])
        model_factory = _make_model_factory(
            extraction_side_effect=lambda *a, **k: next(extraction_results),
        )
        workflow = build_workflow(model_factory)

        state = _build_state(
            run_id,
            documents=[
                {
                    "id": "doc1",
                    "filename": "document_a.docx",
                    "text": "Payment is due within 30 days of invoice receipt.",
                },
                {
                    "id": "doc2",
                    "filename": "document_b.docx",
                    "text": "Invoices must be settled within 60 days.",
                },
            ],
        )
        config = {"configurable": {"thread_id": str(run_id)}}

        result = workflow.invoke(state, config)

        # 1. All source documents entered the workflow
        docs_in_state = state["documents"]
        assert len(docs_in_state) == 2
        doc_filenames = {d["filename"] for d in docs_in_state}
        assert "document_a.docx" in doc_filenames
        assert "document_b.docx" in doc_filenames

        # 2. Facts extracted from ALL documents with provenance
        facts = result.get("extracted_facts", [])
        assert len(facts) == 2, (
            f"Expected 2 extracted facts (one per document), got {len(facts)}"
        )
        fact_sources = {f.get("source_document") for f in facts}
        assert "document_a.docx" in fact_sources
        assert "document_b.docx" in fact_sources

        for fact in facts:
            assert fact.get("field"), "Every fact must have a 'field' key"
            assert fact.get("value"), "Every fact must have a 'value' key"
            assert fact.get("confidence") is not None, "Every fact must have 'confidence'"
            assert fact.get("source_document"), "Every fact must have 'source_document'"
            assert fact.get("source_text"), "Every fact must have 'source_text'"

        # 3. Reconciliation detected the contradiction
        contradictions = result.get("contradictions", [])
        assert len(contradictions) == 1, (
            f"Expected 1 contradiction, got {len(contradictions)}"
        )
        contradiction = contradictions[0]
        assert contradiction["semantic_key"] == "payment.due_period"
        assert len(contradiction["values"]) == 2

        # 4. Workflow interrupted at the human-review gate
        assert "__interrupt__" in result, (
            "Workflow must interrupt for human review when findings exist"
        )

        # 5. Finding persistence in the database
        db_session.expire_all()
        db_findings = (
            db_session.query(Finding).filter(Finding.run_id == run_id).all()
        )
        assert len(db_findings) > 0, (
            "Database findings must be > 0 for contradictory documents"
        )

        contradiction_findings = [
            f for f in db_findings
            if (f.finding_metadata or {}).get("type") == "contradiction"
        ]
        assert len(contradiction_findings) == 1, (
            f"Expected 1 contradiction Finding, got {len(contradiction_findings)}"
        )

        finding = contradiction_findings[0]

        print(f"\nFinding title: {finding.title}")
        print(f"Finding severity: {finding.severity}")
        print(f"Finding review_decision: {finding.review_decision}")
        print(f"Finding citation: {finding.citation}")

        assert finding.severity == FindingSeverity.ERROR
        assert finding.review_decision == ReviewDecision.PENDING
        assert finding.title is not None and finding.title.strip()

        # Citation must contain both source documents with conflicting values
        assert finding.citation is not None
        assert finding.citation.get("type") == "contradiction"
        sources = finding.citation.get("sources", [])
        assert len(sources) == 2
        source_docs = {s.get("document") for s in sources}
        assert "document_a.docx" in source_docs
        assert "document_b.docx" in source_docs
        source_values = {s.get("value") for s in sources}
        assert "30 days" in source_values
        assert "60 days" in source_values
        source_texts = {s.get("source_text") for s in sources}
        assert any(t for t in source_texts if t)

    def test_print_multi_doc_summary(self, db_session):
        """
        Executes a two-contradictory-document run and prints the required
        summary report: selected source docs, extracted facts, contradictions,
        database findings, final workflow stage and status.
        """
        run_id = uuid4()
        run = Run(id=run_id, name="Multi Document Contradiction Test")
        db_session.add(run)
        db_session.commit()

        doc_a_extraction = ExtractionResult(
            facts=[
                ExtractedFact(
                    field="contract term",
                    semantic_key="agreement.duration",
                    value="12 months",
                    confidence=0.95,
                    source_document="source_a.docx",
                    source_text="The agreement term is 12 months.",
                ),
                ExtractedFact(
                    field="governing law",
                    semantic_key="agreement.governing_law",
                    value="New York",
                    confidence=0.95,
                    source_document="source_a.docx",
                    source_text="Governed by New York law.",
                ),
            ]
        )
        doc_b_extraction = ExtractionResult(
            facts=[
                ExtractedFact(
                    field="agreement length",
                    semantic_key="agreement.duration",
                    value="36 months",
                    confidence=0.95,
                    source_document="source_b.docx",
                    source_text="The agreement length is 36 months.",
                ),
                ExtractedFact(
                    field="governing law",
                    semantic_key="agreement.governing_law",
                    value="California",
                    confidence=0.95,
                    source_document="source_b.docx",
                    source_text="Governed by California law.",
                ),
            ]
        )

        extraction_results = iter([doc_a_extraction, doc_b_extraction])
        model_factory = _make_model_factory(
            extraction_side_effect=lambda *a, **k: next(extraction_results),
        )
        workflow = build_workflow(model_factory)

        documents = [
            {
                "id": "source_a",
                "filename": "source_a.docx",
                "text": "The agreement term is 12 months. Governed by New York law.",
            },
            {
                "id": "source_b",
                "filename": "source_b.docx",
                "text": "The agreement length is 36 months. Governed by California law.",
            },
        ]
        state = _build_state(run_id, documents=documents)
        config = {"configurable": {"thread_id": str(run_id)}}

        result = workflow.invoke(state, config)

        db_session.expire_all()
        db_findings = (
            db_session.query(Finding).filter(Finding.run_id == run_id).all()
        )

        facts = result.get("extracted_facts", [])
        contradictions = result.get("contradictions", [])
        workflow_interrupted = "__interrupt__" in result

        print("\n" + "=" * 60)
        print("MULTI-DOCUMENT CONTRADICTION TEST SUMMARY")
        print("=" * 60)
        print(f"Selected source documents: {[d['filename'] for d in documents]}")
        print(f"Extracted facts: {len(facts)}")
        for fact in facts:
            print(
                f"  field={fact.get('field')} | value={fact.get('value')}"
                f" | source={fact.get('source_document')}"
                f" | confidence={fact.get('confidence')}"
            )
        print(f"Contradictions detected: {len(contradictions)}")
        for c in contradictions:
            print(f"  semantic_key={c['semantic_key']} | field={c.get('field')}")
            for v in c.get("values", []):
                print(f"    source={v.get('source_document')} | value={v.get('value')}")
        print(f"Database findings: {len(db_findings)}")
        for f in db_findings:
            print(
                f"  title={f.title} | severity={f.severity}"
                f" | review_decision={f.review_decision}"
            )
            sources = (f.citation or {}).get("sources", [])
            for s in sources:
                print(f"    doc={s.get('document')} | value={s.get('value')}")
        print(
            f"Final workflow stage: "
            f"{'findings_review (interrupted)' if workflow_interrupted else 'completed'}"
        )
        print(
            f"Final workflow status: "
            f"{'WAITING_FOR_REVIEW' if workflow_interrupted else result.get('status', 'unknown')}"
        )
        print("=" * 60)

        assert len(contradictions) == 2, (
            f"Expected 2 contradictions (duration + governing_law), got {len(contradictions)}"
        )
        assert len(db_findings) == 2, (
            f"Expected 2 DB findings, got {len(db_findings)}"
        )
        assert all(
            f.review_decision == ReviewDecision.PENDING for f in db_findings
        ), "All findings must be PENDING"
        assert workflow_interrupted, "Workflow must stop at review gate"


# ---------------------------------------------------------------------------
# Test 4 - three documents (2 agree, 1 differs): contradiction still raised
# ---------------------------------------------------------------------------

class TestMajorityMustNotResolveContradiction:
    """
    When 2 of 3 documents agree on a value, the workflow must NOT silently
    resolve the conflict via majority voting. The dissenting document's
    value must still produce a contradiction Finding.
    """

    def test_minority_dissent_still_creates_finding(self, db_session):
        run_id = uuid4()
        run = Run(id=run_id, name="Three Docs Majority Should Not Resolve")
        db_session.add(run)
        db_session.commit()

        doc_a_extraction = ExtractionResult(
            facts=[
                ExtractedFact(
                    field="payment terms",
                    semantic_key="payment.due_period",
                    value="60 days",
                    confidence=0.95,
                    source_document="doc_a.docx",
                    source_text="Payment due within 60 days of receipt.",
                ),
            ]
        )
        doc_b_extraction = ExtractionResult(
            facts=[
                ExtractedFact(
                    field="payment deadline",
                    semantic_key="payment.due_period",
                    value="30 days",
                    confidence=0.95,
                    source_document="doc_b.docx",
                    source_text="Invoices must be paid within 30 days.",
                ),
            ]
        )
        doc_c_extraction = ExtractionResult(
            facts=[
                ExtractedFact(
                    field="payment period",
                    semantic_key="payment.due_period",
                    value="60 days",
                    confidence=0.90,
                    source_document="doc_c.docx",
                    source_text="Settlement within 60 days is required.",
                ),
            ]
        )

        extraction_results = iter([doc_a_extraction, doc_b_extraction, doc_c_extraction])
        model_factory = _make_model_factory(
            extraction_side_effect=lambda *a, **k: next(extraction_results),
        )
        workflow = build_workflow(model_factory)

        state = _build_state(
            run_id,
            documents=[
                {
                    "id": "doc1",
                    "filename": "doc_a.docx",
                    "text": "Payment due within 60 days of receipt.",
                },
                {
                    "id": "doc2",
                    "filename": "doc_b.docx",
                    "text": "Invoices must be paid within 30 days.",
                },
                {
                    "id": "doc3",
                    "filename": "doc_c.docx",
                    "text": "Settlement within 60 days is required.",
                },
            ],
        )
        config = {"configurable": {"thread_id": str(run_id)}}

        result = workflow.invoke(state, config)

        # All facts from all three documents must be extracted
        facts = result.get("extracted_facts", [])
        fact_sources = {f.get("source_document") for f in facts}
        assert "doc_a.docx" in fact_sources
        assert "doc_b.docx" in fact_sources
        assert "doc_c.docx" in fact_sources

        # Contradiction must still be detected (no majority voting)
        contradictions = result.get("contradictions", [])
        assert len(contradictions) == 1, (
            f"Expected 1 contradiction (majority voting must NOT resolve), "
            f"got {len(contradictions)}"
        )
        contradiction = contradictions[0]
        assert contradiction["semantic_key"] == "payment.due_period"

        all_values = {v.get("value") for v in contradiction.get("values", [])}
        assert "30 days" in all_values, "Minority value '30 days' must be preserved"
        assert "60 days" in all_values, "Majority value '60 days' must be preserved"

        # Workflow must interrupt for human review
        assert "__interrupt__" in result, (
            "Workflow must stop at review gate even when majority agrees"
        )

        # Finding must be persisted
        db_session.expire_all()
        db_findings = (
            db_session.query(Finding).filter(Finding.run_id == run_id).all()
        )
        assert len(db_findings) > 0, (
            "Finding must be persisted even when 2-of-3 documents agree"
        )
        assert all(f.review_decision == ReviewDecision.PENDING for f in db_findings)

        finding = db_findings[0]
        citation_sources = finding.citation.get("sources", [])
        citation_values = {s.get("value") for s in citation_sources}
        assert "30 days" in citation_values, "Minority value must appear in citation"
        assert "60 days" in citation_values, "Majority value must appear in citation"


# ---------------------------------------------------------------------------
# Test 5 - API + DB alignment: database count must equal API count
# ---------------------------------------------------------------------------

class TestMultiDocumentAPIAndDBAlignment:
    """
    Verifies full pipeline including API layer:
      Database findings == API findings (via GET /api/v1/runs/{run_id}/details)
    """

    def test_database_and_api_findings_match(self, db_session):
        from fastapi.testclient import TestClient
        from app.main import app

        run_id = uuid4()
        run = Run(id=run_id, name="API and DB Alignment Test")
        db_session.add(run)
        db_session.commit()

        doc_a_extraction = ExtractionResult(
            facts=[
                ExtractedFact(
                    field="termination notice",
                    semantic_key="agreement.termination_notice",
                    value="30 days",
                    confidence=0.95,
                    source_document="alpha.docx",
                    source_text="Either party may terminate with 30 days written notice.",
                ),
            ]
        )
        doc_b_extraction = ExtractionResult(
            facts=[
                ExtractedFact(
                    field="notice period",
                    semantic_key="agreement.termination_notice",
                    value="90 days",
                    confidence=0.95,
                    source_document="beta.docx",
                    source_text="Termination requires 90 days written notice.",
                ),
            ]
        )

        extraction_results = iter([doc_a_extraction, doc_b_extraction])
        model_factory = _make_model_factory(
            extraction_side_effect=lambda *a, **k: next(extraction_results),
        )
        workflow = build_workflow(model_factory)

        state = _build_state(
            run_id,
            documents=[
                {
                    "id": "doc1",
                    "filename": "alpha.docx",
                    "text": "Termination with 30 days written notice.",
                },
                {
                    "id": "doc2",
                    "filename": "beta.docx",
                    "text": "Termination requires 90 days written notice.",
                },
            ],
        )
        config = {"configurable": {"thread_id": str(run_id)}}

        workflow.invoke(state, config)

        db_session.expire_all()
        db_findings = (
            db_session.query(Finding).filter(Finding.run_id == run_id).all()
        )
        db_count = len(db_findings)

        client = TestClient(app)
        response = client.get(f"/api/v1/runs/{run_id}/details")
        assert response.status_code == 200
        details = response.json()
        api_findings = details.get("findings", [])
        api_count = len(api_findings)

        print("\n" + "=" * 60)
        print("DATABASE vs API ALIGNMENT")
        print(f"  Database findings: {db_count}")
        print(f"  API findings:      {api_count}")
        print(f"  Frontend findings: {api_count}  (frontend reads the same API)")
        print("=" * 60)

        assert db_count > 0, (
            f"Database findings must be > 0 after contradiction run, got {db_count}"
        )
        assert db_count == api_count, (
            f"Database findings ({db_count}) must equal API findings ({api_count})"
        )

        for api_finding in api_findings:
            assert api_finding.get("id"), "API finding must have 'id'"
            assert api_finding.get("title"), "API finding must have 'title'"
            assert api_finding.get("severity") == "error"
            assert api_finding.get("review_decision") == "pending"


# ---------------------------------------------------------------------------
# Test 6 - idempotency: second sync must not duplicate findings
# ---------------------------------------------------------------------------

class TestContradictionFindingIdempotency:
    """
    Calling sync_contradiction_findings a second time with identical
    contradictions must not create duplicate Finding rows.
    """

    def test_sync_twice_does_not_duplicate_findings(self, db_session):
        from app.persistence.repositories.finding import FindingRepository
        from app.services.finding_service import FindingService

        run_id = uuid4()
        run = Run(id=run_id, name="Idempotency Check Run")
        db_session.add(run)
        db_session.commit()

        contradictions = [
            {
                "semantic_key": "payment.due_period",
                "field": "payment terms",
                "values": [
                    {
                        "source_document": "alpha.docx",
                        "value": "30 days",
                        "source_text": "Payment due 30 days.",
                        "confidence": 0.95,
                    },
                    {
                        "source_document": "beta.docx",
                        "value": "60 days",
                        "source_text": "Payment due 60 days.",
                        "confidence": 0.95,
                    },
                ],
            }
        ]

        finding_repo = FindingRepository(db_session)
        finding_service = FindingService(finding_repo)

        finding_service.sync_contradiction_findings(run_id, contradictions)
        db_session.commit()

        count_after_first = (
            db_session.query(Finding).filter(Finding.run_id == run_id).count()
        )

        finding_service.sync_contradiction_findings(run_id, contradictions)
        db_session.commit()

        db_session.expire_all()
        count_after_second = (
            db_session.query(Finding).filter(Finding.run_id == run_id).count()
        )

        assert count_after_first == 1, (
            f"Expected 1 finding after first sync, got {count_after_first}"
        )
        assert count_after_second == 1, (
            f"Expected 1 finding after second sync (idempotency), "
            f"got {count_after_second}"
        )
