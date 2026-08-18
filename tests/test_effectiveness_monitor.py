"""Unit tests for EffectivenessMonitor batch verification and recurrence detection."""

from pathlib import Path
import pytest

from gxpsoft.agents.capa import CAPAAgent
from gxpsoft.agents.orchestrator import InvestigationPipeline
from gxpsoft.capa.effectiveness import EffectivenessMonitor
from gxpsoft.core.repository import repo
from gxpsoft.evidence.indexer import evidence_indexer
from gxpsoft.models.enums import CaseState, SignatureMeaning
from gxpsoft.review.service import HumanReviewService


@pytest.fixture(autouse=True)
def index_fixtures(fixtures_dir: Path) -> None:
    evidence_indexer.index_document_directory(fixtures_dir / "documents")


def setup_authorized_capa_case(mes_event_payload: dict, idempotency_key: str, event_id: str):
    payload = dict(mes_event_payload)
    payload["idempotency_key"] = idempotency_key
    payload["event_id"] = event_id

    _, case, _ = InvestigationPipeline.run_pipeline(payload)
    case, _ = HumanReviewService.approve_and_sign(
        case_id=case.case_id,
        user_id="USER-QA-LEAD-01",
        password_or_pin="LeadPass2026!",
        meaning=SignatureMeaning.APPROVED_CLASSIFICATION,
        rationale="Approved classification."
    )
    case, _ = HumanReviewService.approve_and_sign(
        case_id=case.case_id,
        user_id="USER-QA-LEAD-01",
        password_or_pin="LeadPass2026!",
        meaning=SignatureMeaning.APPROVED_ROOT_CAUSE,
        rationale="Approved root cause."
    )
    CAPAAgent.generate_capa(case_id=case.case_id)

    # QA Manager authorizes CAPA
    case, _ = HumanReviewService.approve_and_sign(
        case_id=case.case_id,
        user_id="USER-QA-MGR-01",
        password_or_pin="MgrPass2026!",
        meaning=SignatureMeaning.APPROVED_CAPA,
        rationale="Authorized 4 CAPA action items."
    )
    assert case.state == CaseState.CAPA_AUTHORIZED
    return case


def test_effectiveness_monitor_success_flow(mes_event_payload: dict) -> None:
    case = setup_authorized_capa_case(mes_event_payload, "test:eff:success:001", "EVT-EFF-001")

    # Simulate 5 clean consecutive batch runs
    clean_batches = [
        {"batch_id": f"BIO-2026-09{i}", "max_temp_celsius": 37.1, "excursion_duration_min": 0.0}
        for i in range(1, 6)
    ]

    res = EffectivenessMonitor.evaluate_batch_results(case_id=case.case_id, batch_results=clean_batches)

    assert res["verified"] is True
    assert res["clean_batches_count"] == 5
    assert case.state == CaseState.EFFECTIVENESS_VERIFIED


def test_effectiveness_monitor_recurrence_escalation(mes_event_payload: dict) -> None:
    case = setup_authorized_capa_case(mes_event_payload, "test:eff:recur:002", "EVT-EFF-002")

    # Simulate batch stream with 1 recurrence failure
    batches_with_failure = [
        {"batch_id": "BIO-2026-091", "max_temp_celsius": 37.1, "excursion_duration_min": 0.0},
        {"batch_id": "BIO-2026-092", "max_temp_celsius": 38.6, "excursion_duration_min": 14.0},  # FAILED
        {"batch_id": "BIO-2026-093", "max_temp_celsius": 37.0, "excursion_duration_min": 0.0},
    ]

    res = EffectivenessMonitor.evaluate_batch_results(case_id=case.case_id, batch_results=batches_with_failure)

    assert res["verified"] is False
    assert res["escalation_triggered"] is True
    assert len(res["failed_batches"]) == 1
    assert case.state == CaseState.CAPA_AUTHORIZED  # Remains authorized / blocked from closing
