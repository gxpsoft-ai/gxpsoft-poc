"""Unit tests verifying GxP domain models and schema constraints."""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from gxpsoft.models.enums import (
    ActionClass,
    AuthorType,
    CaseSeverity,
    CaseState,
    CaseType,
    SignatureMeaning,
)
from gxpsoft.models.event import QualityEvent
from gxpsoft.models.case import QualityCase
from gxpsoft.models.evidence import Claim, ClaimEvidenceLink, EvidenceObject
from gxpsoft.models.agent_run import AgentRun, DraftArtifact, ToolCall
from gxpsoft.models.audit import Decision, SignatureRecord, StateTransition


def test_quality_event_initialization(mes_event_payload: dict) -> None:
    event = QualityEvent(**mes_event_payload)
    assert event.event_id == "EVT-MES-20260818-001"
    assert event.event_type == "MES_TEMP_EXCURSION"
    assert event.batch_id == "BIO-2026-088"
    assert len(event.payload_hash) == 64  # SHA-256 hex length


def test_quality_case_defaults() -> None:
    case = QualityCase(
        title="Bioreactor BR-04 Temperature Excursion",
        description="Temperature elevated to 39.4C during feed stage",
        initial_event_id="EVT-MES-20260818-001",
        batch_id="BIO-2026-088",
        severity=CaseSeverity.MAJOR,
    )
    assert case.case_id.startswith("DEV-2026-")
    assert case.state == CaseState.SIGNAL_RECEIVED
    assert case.case_type == CaseType.DEVIATION
    assert case.severity == CaseSeverity.MAJOR


def test_claim_with_evidence_link(bioreactor_sop_text: str) -> None:
    evidence = EvidenceObject(
        uri="fixtures/documents/SOP-PRC-042_bioreactor.md",
        title="Bioreactor Operations SOP",
        doc_type="SOP",
        source_system="DMS",
        raw_content=bioreactor_sop_text,
    )
    assert len(evidence.content_hash) == 64

    link = ClaimEvidenceLink(
        evidence_id=evidence.evidence_id,
        locator="Section 4.2",
        quote_text="Any temperature elevation > 38.5 °C lasting greater than 10 minutes.",
        relevance_score=0.98,
        match_method="EXACT_EXTRACTION",
    )

    claim = Claim(
        case_id="DEV-2026-0001",
        claim_text="The excursion meets the criteria for a Major Deviation under SOP-PRC-042 Section 4.2.",
        author_type=AuthorType.AGENT,
        author_id="SentinelAgent-v1.0",
        confidence=0.95,
        citations=[link],
    )

    assert claim.author_type == AuthorType.AGENT
    assert len(claim.citations) == 1
    assert claim.citations[0].locator == "Section 4.2"


def test_signature_record_hash_generation() -> None:
    sig = SignatureRecord(
        case_id="DEV-2026-0001",
        user_id="USER-QA-LEAD-01",
        user_full_name="Jane Director",
        user_title="Director of Quality Assurance",
        meaning=SignatureMeaning.APPROVED_ROOT_CAUSE,
        target_entity_type="QualityCase",
        target_entity_id="DEV-2026-0001",
        target_content_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    assert len(sig.signature_hash) == 64
    assert sig.meaning == SignatureMeaning.APPROVED_ROOT_CAUSE


def test_agent_run_provenance() -> None:
    run = AgentRun(
        case_id="DEV-2026-0001",
        agent_name="NCAgent",
        agent_version="1.0.0",
        model_name="gemini-3.7-flash",
        prompt_version="v2.1",
        prompt_hash="a" * 64,
        input_payload={"event_id": "EVT-001", "batch_id": "BIO-2026-088"},
        output_payload={"severity_recommendation": "MAJOR", "root_causes": ["Probe drift"]},
    )
    assert len(run.input_hash) == 64
    assert len(run.output_hash) == 64
