"""Unit tests for DecisionPacketBuilder and hydrated claim compilation."""

from pathlib import Path
import pytest

from gxpsoft.agents.orchestrator import InvestigationPipeline
from gxpsoft.evidence.indexer import evidence_indexer
from gxpsoft.models.enums import ActionClass, CaseState, SignatureMeaning
from gxpsoft.review.packet_builder import DecisionPacketBuilder


@pytest.fixture(autouse=True)
def index_fixtures(fixtures_dir: Path) -> None:
    evidence_indexer.index_document_directory(fixtures_dir / "documents")


def test_build_decision_packet(mes_event_payload: dict) -> None:
    payload = dict(mes_event_payload)
    payload["idempotency_key"] = "test:packet:builder:001"
    payload["event_id"] = "EVT-PKT-001"

    event, case, _ = InvestigationPipeline.run_pipeline(payload)
    packet = DecisionPacketBuilder.build_packet(case_id=case.case_id)

    assert packet.case_id == case.case_id
    assert packet.case.state == CaseState.CONTAINMENT_PROPOSED
    assert packet.latest_draft is not None
    assert len(packet.claims) == 5

    # Verify claim hydration
    rtd_claim = next(c for c in packet.claims if "RTD-04B" in c.claim_text)
    assert len(rtd_claim.citations) >= 1
    citation = rtd_claim.citations[0]
    assert "CALIBRATION_LOG" in citation.doc_type
    assert "RTD-04B" in citation.locator
    assert len(citation.source_uri) > 0

    # Verify policy gate requirements
    gate = packet.policy_gate
    assert gate.action_class == ActionClass.A4_CONTROLLED_GXP_ACTION
    assert gate.target_state == CaseState.HUMAN_CLASSIFICATION_APPROVED
    assert gate.required_signature_meaning == SignatureMeaning.APPROVED_CLASSIFICATION
    assert gate.is_human_signature_mandatory is True
