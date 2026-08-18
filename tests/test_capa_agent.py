"""Unit tests for CAPAAgent action generation and effectiveness criteria formulation."""

from pathlib import Path
import pytest

from gxpsoft.agents.capa import CAPAAgent
from gxpsoft.agents.orchestrator import InvestigationPipeline
from gxpsoft.core.repository import repo
from gxpsoft.evidence.indexer import evidence_indexer
from gxpsoft.models.enums import CaseState, SignatureMeaning
from gxpsoft.review.service import HumanReviewService


@pytest.fixture(autouse=True)
def index_fixtures(fixtures_dir: Path) -> None:
    evidence_indexer.index_document_directory(fixtures_dir / "documents")


def test_capa_generation_flow(mes_event_payload: dict) -> None:
    payload = dict(mes_event_payload)
    payload["idempotency_key"] = "test:capa:gen:001"
    payload["event_id"] = "EVT-CAPA-001"

    # Step 1: Run investigation pipeline
    _, case, _ = InvestigationPipeline.run_pipeline(payload)
    assert case.state == CaseState.CONTAINMENT_PROPOSED

    # Step 2: Human signs classification & containment
    case, _ = HumanReviewService.approve_and_sign(
        case_id=case.case_id,
        user_id="USER-QA-LEAD-01",
        password_or_pin="LeadPass2026!",
        meaning=SignatureMeaning.APPROVED_CLASSIFICATION,
        rationale="Approved classification and containment."
    )
    assert case.state == CaseState.HUMAN_CLASSIFICATION_APPROVED

    # Step 3: Human signs root cause confirmation
    case, _ = HumanReviewService.approve_and_sign(
        case_id=case.case_id,
        user_id="USER-QA-LEAD-01",
        password_or_pin="LeadPass2026!",
        meaning=SignatureMeaning.APPROVED_ROOT_CAUSE,
        rationale="Approved RTD-04B expired calibration as confirmed root cause."
    )
    assert case.state == CaseState.ROOT_CAUSE_CONFIRMED

    # Step 4: Run CAPA Agent
    capa_res = CAPAAgent.generate_capa(case_id=case.case_id)

    assert capa_res["actions_count"] == 4
    assert capa_res["state"] == CaseState.CAPA_DRAFTED.value

    # Verify staged CAPA draft artifact
    drafts = repo.get_drafts_for_case(case.case_id)
    capa_draft = next(d for d in drafts if d.artifact_type == "CAPA_PLAN")
    content = capa_draft.structured_content

    assert len(content["capa_actions"]) == 4
    assert any("RTD-04B" in a["title"] for a in content["capa_actions"])
    assert any("Lockout" in a["title"] for a in content["capa_actions"])
    assert content["effectiveness_plan"]["target_consecutive_clean_batches"] == 5
