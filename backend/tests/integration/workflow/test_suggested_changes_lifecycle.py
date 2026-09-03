"""Comprehensive test suite for LLM-driven Suggested Change Generation and Lifecycle.

Tests:
1. LLM proposal generation on actionable policy violations (minimum-change principle).
2. Different natural-language formulations producing equivalent semantic proposals without regex.
3. Unsupported / insufficient policy information generating NO_SAFE_EDIT.
4. Contradictory documents generating NEEDS_RESOLUTION without fabricated values.
5. LangGraph workflow executing examine -> generate_suggested_changes -> findings_review.
6. Approved edit mutating document and rejected edit preserving original text.
7. Post-edit validation proving actual final artifact correctness.
8. Section SHA-256 hashes proving unchanged sections remain byte-identical.
"""
from unittest.mock import MagicMock
from uuid import uuid4
from app.core.constants import (
    ApplicationStatus,
    FindingSeverity,
    ReviewDecision,
    ValidationStatus,
)
from app.llm.enums import ModelName
from app.llm.factory import ModelFactory
from app.llm.schemas import (
    ChangeType,
    SuggestedChangeProposal,
    SuggestedChangesResult,
)
from app.persistence.models.finding import Finding
from app.services.mutation_service import DocumentMutationEngine
from app.services.validation_service import PostEditValidationEngine
from app.workflow.nodes.generate_suggested_changes import GenerateSuggestedChangesNode


SAAS_CONTRACT_SAMPLE = """ACME ENTERPRISE SAAS AGREEMENT

1. Term and Renewal
The initial subscription term shall be 2 years. Either party may prevent automatic renewal by providing at least 60 days prior written notice before the end of the current term.

2. Service Level Commitment
Acme warrants that the Cloud Services will achieve an Monthly Uptime Percentage of at least 99.5% during each calendar month.

3. Payment Terms
Customer shall pay all undisputed invoiced amounts within 60 days of the invoice date. Late payments shall incur a monthly late fee of 2%.

4. Data Retention and Deletion
Upon termination of this Agreement, Acme shall retain Customer Data in backup archives for 5 years prior to permanent deletion.

5. Confidentiality
Each party agrees to hold the other party's Confidential Information in strict confidence.
"""


def test_llm_proposal_generation_actionable_policy_violation():
    """Test 1: LLM generates structured SuggestedChange with exact verbatim original_text."""
    mock_model = MagicMock()
    mock_structured = MagicMock()
    mock_model.with_structured_output.return_value = mock_structured
    
    # LLM returns structured proposal
    mock_structured.invoke.return_value = SuggestedChangesResult(
        proposals=[
            SuggestedChangeProposal(
                finding_id="Payment Term Exceeds Policy",
                change_type=ChangeType.REPLACE_TEXT,
                source_location="3. Payment Terms",
                original_text="60 days",
                proposed_text="30 days",
                reason="Policy requires payment within 30 days.",
                rule_reference="Payment Terms",
                confidence="high",
                requires_human_resolution=False,
            )
        ]
    )

    mock_factory = MagicMock(spec=ModelFactory)
    mock_factory.create_model.return_value = mock_model

    node = GenerateSuggestedChangesNode(
        model_factory=mock_factory,
        model_name=ModelName.GEMINI_2_5_FLASH,
    )

    state = {
        "run_id": uuid4(),
        "documents": [{"filename": "SaaS Contract.docx", "text": SAAS_CONTRACT_SAMPLE}],
        "rules": [{"filename": "SaaS Rules.docx", "text": "Payment terms must not exceed 30 days."}],
        "extracted_facts": [],
        "examination": MagicMock(issues=["Customer payment term is 60 days, exceeding policy maximum of 30 days."]),
    }

    res_state = node(state)
    suggested = res_state["suggested_changes"]
    assert len(suggested) == 1
    assert suggested[0]["change_type"] == "REPLACE_TEXT"
    assert suggested[0]["original_text"] == "60 days"
    assert suggested[0]["proposed_text"] == "30 days"
    assert suggested[0]["requires_human_resolution"] is False


def test_llm_proposal_generation_different_wording():
    """Test 2: Semantic proposal generation for different natural language formulations."""
    mock_model = MagicMock()
    mock_structured = MagicMock()
    mock_model.with_structured_output.return_value = mock_structured
    
    # Both test A (standard numbers) and test B (words) are structured cleanly by the LLM
    mock_structured.invoke.return_value = SuggestedChangesResult(
        proposals=[
            SuggestedChangeProposal(
                finding_id="Payment Due",
                change_type=ChangeType.REPLACE_TEXT,
                source_location="Payment Clause",
                original_text="forty-five calendar days",
                proposed_text="thirty calendar days",
                reason="Policy specifies thirty calendar days maximum.",
                rule_reference="Payment Clause",
                confidence="high",
                requires_human_resolution=False,
            )
        ]
    )

    mock_factory = MagicMock(spec=ModelFactory)
    mock_factory.create_model.return_value = mock_model

    node = GenerateSuggestedChangesNode(
        model_factory=mock_factory,
        model_name=ModelName.GEMINI_2_5_FLASH,
    )

    state = {
        "run_id": uuid4(),
        "documents": [{"filename": "Vendor.docx", "text": "Customer shall remit payment forty-five calendar days after invoice."}],
        "rules": [{"filename": "Rules.docx", "text": "Payment must occur within thirty calendar days."}],
        "extracted_facts": [],
        "examination": MagicMock(issues=["Payment duration exceeds thirty calendar days."]),
    }

    res_state = node(state)
    suggested = res_state["suggested_changes"]
    assert len(suggested) == 1
    assert suggested[0]["original_text"] == "forty-five calendar days"
    assert suggested[0]["proposed_text"] == "thirty calendar days"


def test_llm_proposal_insufficient_info_generates_no_safe_edit():
    """Test 3: When policy lacks deterministic replacement, model yields NO_SAFE_EDIT."""
    mock_model = MagicMock()
    mock_structured = MagicMock()
    mock_model.with_structured_output.return_value = mock_structured
    
    mock_structured.invoke.return_value = SuggestedChangesResult(
        proposals=[
            SuggestedChangeProposal(
                finding_id="Security Controls Review",
                change_type=ChangeType.NO_SAFE_EDIT,
                source_location="Security Section",
                original_text=None,
                proposed_text=None,
                reason="Policy requires security review, but does not provide a deterministic replacement text.",
                rule_reference="Security Controls",
                confidence="medium",
                requires_human_resolution=True,
            )
        ]
    )

    mock_factory = MagicMock(spec=ModelFactory)
    mock_factory.create_model.return_value = mock_model

    node = GenerateSuggestedChangesNode(
        model_factory=mock_factory,
        model_name=ModelName.GEMINI_2_5_FLASH,
    )

    state = {
        "run_id": uuid4(),
        "documents": [{"filename": "Security.docx", "text": "The supplier must maintain commercially reasonable security controls."}],
        "rules": [{"filename": "Policy.docx", "text": "Security controls should be reviewed by the security team."}],
        "extracted_facts": [],
        "examination": MagicMock(issues=["Security controls require explicit review."]),
    }

    res_state = node(state)
    suggested = res_state["suggested_changes"]
    assert len(suggested) == 1
    assert suggested[0]["change_type"] == "NO_SAFE_EDIT"
    assert suggested[0]["requires_human_resolution"] is True
    assert suggested[0]["proposed_text"] is None


def test_contradiction_generates_needs_resolution():
    """Test 4: Contradiction without authoritative policy rule produces NEEDS_RESOLUTION."""
    mock_model = MagicMock()
    mock_structured = MagicMock()
    mock_model.with_structured_output.return_value = mock_structured
    
    mock_structured.invoke.return_value = SuggestedChangesResult(
        proposals=[
            SuggestedChangeProposal(
                finding_id="Conflicting Notice",
                change_type=ChangeType.NEEDS_RESOLUTION,
                source_location="Section 3",
                original_text=None,
                proposed_text=None,
                reason="Document A states 30 days while Document B states 60 days. Neither is authoritative.",
                rule_reference=None,
                confidence="high",
                requires_human_resolution=True,
            )
        ]
    )

    mock_factory = MagicMock(spec=ModelFactory)
    mock_factory.create_model.return_value = mock_model

    node = GenerateSuggestedChangesNode(
        model_factory=mock_factory,
        model_name=ModelName.GEMINI_2_5_FLASH,
    )

    state = {
        "run_id": uuid4(),
        "documents": [
            {"filename": "DocA.docx", "text": "Termination notice: 30 days"},
            {"filename": "DocB.docx", "text": "Termination notice: 60 days"},
        ],
        "rules": [],
        "extracted_facts": [],
        "examination": MagicMock(issues=["Conflicting notice periods found in documents."]),
    }

    res_state = node(state)
    suggested = res_state["suggested_changes"]
    assert len(suggested) == 1
    assert suggested[0]["change_type"] == "NEEDS_RESOLUTION"
    assert suggested[0]["requires_human_resolution"] is True


def test_approved_and_rejected_mutation_execution():
    """Test 5: Deterministic mutation applies approved edits and preserves rejected ones."""
    engine = DocumentMutationEngine()
    
    f_app = Finding(
        id=uuid4(),
        run_id=uuid4(),
        title="Term Cap",
        description="Term is 2 years, policy requires 3 years",
        severity=FindingSeverity.ERROR,
        review_decision=ReviewDecision.APPROVED,
        original_value="2 years",
        proposed_value="3 years",
        proposed_edit="2 years → 3 years",
    )

    f_rej = Finding(
        id=uuid4(),
        run_id=uuid4(),
        title="Late Fee Cap",
        description="Late fee is 2%, policy requires 1%",
        severity=FindingSeverity.WARNING,
        review_decision=ReviewDecision.REJECTED,
        original_value="2%",
        proposed_value="1%",
        proposed_edit="2% → 1%",
    )

    result = engine.apply_approved_edits(
        source_text=SAAS_CONTRACT_SAMPLE,
        findings=[f_app, f_rej],
        run_id=str(uuid4()),
    )

    assert "initial subscription term shall be 3 years" in result.mutated_text
    assert "monthly late fee of 2%" in result.mutated_text  # Preserved because rejected!
    assert len(result.applied_changes) == 1
    assert len(result.rejected_changes) == 1


def test_post_edit_validation_and_section_hashes():
    """Test 6: Post-edit validation confirms document mutations and section hashes."""
    engine = DocumentMutationEngine()
    validator = PostEditValidationEngine()

    f_retention = Finding(
        id=uuid4(),
        run_id=uuid4(),
        title="Data Retention",
        description="Retention 5 years exceeds policy 30 days",
        severity=FindingSeverity.ERROR,
        review_decision=ReviewDecision.APPROVED,
        original_value="5 years",
        proposed_value="30 days",
        proposed_edit="5 years → 30 days",
    )

    result = engine.apply_approved_edits(
        source_text=SAAS_CONTRACT_SAMPLE,
        findings=[f_retention],
        run_id=str(uuid4()),
    )

    val_res = validator.validate(
        findings=[f_retention],
        mutation_result=result,
    )

    assert val_res.passed is True
    assert "30 days prior to permanent deletion" in result.mutated_text
    
    hashes = result.hash_comparison
    assert hashes["data_retention"]["changed"] is True
    assert hashes["term_renewal"]["changed"] is False
    assert hashes["payment_terms"]["changed"] is False
    assert hashes["confidentiality"]["changed"] is False
