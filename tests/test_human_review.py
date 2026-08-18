"""Unit and API tests for HumanReviewService, redlines, overrides, and e-signatures."""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from gxpsoft.agents.orchestrator import InvestigationPipeline
from gxpsoft.api.main import app
from gxpsoft.evidence.indexer import evidence_indexer
from gxpsoft.models.enums import CaseSeverity, CaseState, SignatureMeaning
from gxpsoft.review.service import HumanReviewService, OverrideRationaleRequiredError

client = TestClient(app)


@pytest.fixture(autouse=True)
def index_fixtures(fixtures_dir: Path) -> None:
    evidence_indexer.index_document_directory(fixtures_dir / "documents")


def test_override_severity_requires_detailed_rationale(mes_event_payload: dict) -> None:
    payload = dict(mes_event_payload)
    payload["idempotency_key"] = "test:review:override:001"
    payload["event_id"] = "EVT-REV-001"

    _, case, _ = InvestigationPipeline.run_pipeline(payload)
    assert case.severity == CaseSeverity.MAJOR

    # Attempt override without rationale fails
    with pytest.raises(OverrideRationaleRequiredError) as exc_info:
        HumanReviewService.record_redline(
            case_id=case.case_id,
            user_id="USER-QA-LEAD-01",
            severity_override=CaseSeverity.MINOR,
            override_rationale=""
        )
    assert "requires a detailed justification rationale" in str(exc_info.value)

    # Override with valid rationale succeeds
    updated_case = HumanReviewService.record_redline(
        case_id=case.case_id,
        user_id="USER-QA-LEAD-01",
        severity_override=CaseSeverity.MINOR,
        override_rationale="Secondary reference probe confirmed temperature did not exceed 37.8C in bulk liquid."
    )
    assert updated_case.severity == CaseSeverity.MINOR
    assert "severity_override" in updated_case.metadata


def test_atomic_approve_and_sign(mes_event_payload: dict) -> None:
    payload = dict(mes_event_payload)
    payload["idempotency_key"] = "test:review:sign:002"
    payload["event_id"] = "EVT-REV-002"

    _, case, _ = InvestigationPipeline.run_pipeline(payload)
    assert case.state == CaseState.CONTAINMENT_PROPOSED

    updated_case, sig = HumanReviewService.approve_and_sign(
        case_id=case.case_id,
        user_id="USER-QA-LEAD-01",
        password_or_pin="LeadPass2026!",
        meaning=SignatureMeaning.APPROVED_CLASSIFICATION,
        rationale="Confirmed Major deviation classification and batch quarantine containment."
    )

    assert updated_case.state == CaseState.HUMAN_CLASSIFICATION_APPROVED
    assert sig.user_full_name == "Jane Doe"
    assert sig.meaning == SignatureMeaning.APPROVED_CLASSIFICATION


def test_api_decision_packet_and_review_flow(mes_event_payload: dict) -> None:
    payload = dict(mes_event_payload)
    payload["idempotency_key"] = "test:api:review:flow:003"
    payload["event_id"] = "EVT-REV-003"

    res_ingest = client.post("/api/v1/events/ingest", json=payload)
    case_id = res_ingest.json()["case"]["case_id"]

    # Run pipeline up to containment proposed
    from gxpsoft.agents.nc_investigator import NCInvestigatorAgent
    from gxpsoft.agents.sentinel import SentinelAgent
    from gxpsoft.core.repository import repo

    c = repo.get_case(case_id)
    e = repo.get_event(c.initial_event_id)
    SentinelAgent.evaluate_event(event=e, case=c)
    NCInvestigatorAgent.investigate(case_id=case_id)

    # 1. Fetch decision packet via API
    res_pkt = client.get(f"/api/v1/cases/{case_id}/decision-packet")
    assert res_pkt.status_code == 200
    pkt = res_pkt.json()
    assert len(pkt["claims"]) == 5
    assert pkt["policy_gate"]["target_state"] == "HUMAN_CLASSIFICATION_APPROVED"

    # 2. Test redline API with invalid override (missing rationale) -> 422
    res_bad_redline = client.post(
        f"/api/v1/cases/{case_id}/review/redline",
        json={
            "user_id": "USER-QA-LEAD-01",
            "severity_override": "MINOR",
            "override_rationale": "too short"
        }
    )
    assert res_bad_redline.status_code == 422

    # 3. Test approve-and-sign API -> 200
    res_sign = client.post(
        f"/api/v1/cases/{case_id}/review/approve-and-sign",
        json={
            "user_id": "USER-QA-LEAD-01",
            "password_or_pin": "LeadPass2026!",
            "meaning": "APPROVED_CLASSIFICATION",
            "rationale": "Classification and immediate quarantine approved."
        }
    )
    assert res_sign.status_code == 200
    assert res_sign.json()["case"]["state"] == "HUMAN_CLASSIFICATION_APPROVED"

    # 4. Test UI dashboard HTML route
    res_ui = client.get(f"/ui/case/{case_id}")
    assert res_ui.status_code == 200
    assert "GxPSoft" in res_ui.text
    assert "21 CFR Part 11" in res_ui.text
