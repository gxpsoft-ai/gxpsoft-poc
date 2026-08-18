"""Unit and API tests for DecisionLineageExporter and regulatory audit trail export."""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from gxpsoft.agents.capa import CAPAAgent
from gxpsoft.agents.orchestrator import InvestigationPipeline
from gxpsoft.api.main import app
from gxpsoft.capa.effectiveness import EffectivenessMonitor
from gxpsoft.capa.export import DecisionLineageExporter
from gxpsoft.evidence.indexer import evidence_indexer
from gxpsoft.models.enums import CaseState, SignatureMeaning
from gxpsoft.review.service import HumanReviewService

client = TestClient(app)


@pytest.fixture(autouse=True)
def index_fixtures(fixtures_dir: Path) -> None:
    evidence_indexer.index_document_directory(fixtures_dir / "documents")


def test_complete_closed_loop_decision_lineage_export(mes_event_payload: dict) -> None:
    payload = dict(mes_event_payload)
    payload["idempotency_key"] = "test:export:full:001"
    payload["event_id"] = "EVT-EXP-001"

    # Step 1: Automated Investigation Pipeline
    _, case, _ = InvestigationPipeline.run_pipeline(payload)
    case_id = case.case_id

    # Step 2: Human Sign 1 - Classification
    HumanReviewService.approve_and_sign(
        case_id=case_id,
        user_id="USER-QA-LEAD-01",
        password_or_pin="LeadPass2026!",
        meaning=SignatureMeaning.APPROVED_CLASSIFICATION,
        rationale="Approved classification & containment."
    )

    # Step 3: Human Sign 2 - Root Cause Confirmation
    HumanReviewService.approve_and_sign(
        case_id=case_id,
        user_id="USER-QA-LEAD-01",
        password_or_pin="LeadPass2026!",
        meaning=SignatureMeaning.APPROVED_ROOT_CAUSE,
        rationale="Approved probe drift root cause."
    )

    # Step 4: CAPA Agent Drafts Plan
    CAPAAgent.generate_capa(case_id=case_id)

    # Step 5: Human Sign 3 - QA Manager Authorizes CAPA
    HumanReviewService.approve_and_sign(
        case_id=case_id,
        user_id="USER-QA-MGR-01",
        password_or_pin="MgrPass2026!",
        meaning=SignatureMeaning.APPROVED_CAPA,
        rationale="Authorized 4 CAPA actions."
    )

    # Step 6: Effectiveness Monitor verifies 5 clean batches
    clean_batches = [
        {"batch_id": f"BIO-2026-09{i}", "max_temp_celsius": 37.1, "excursion_duration_min": 0.0}
        for i in range(1, 6)
    ]
    EffectivenessMonitor.evaluate_batch_results(case_id=case_id, batch_results=clean_batches)
    assert case.state == CaseState.EFFECTIVENESS_VERIFIED

    # Step 7: Human Sign 4 - QA Director Final Closure
    HumanReviewService.approve_and_sign(
        case_id=case_id,
        user_id="USER-DIR-QA-01",
        password_or_pin="DirPass2026!",
        meaning=SignatureMeaning.APPROVED_CLOSURE,
        rationale="All 5 batches clean. CAPA successfully closed."
    )
    assert case.state == CaseState.CLOSED

    # Step 8: Generate Decision Lineage Export
    export_dossier = DecisionLineageExporter.generate_export(case_id=case_id)

    assert export_dossier.case.state == CaseState.CLOSED
    assert export_dossier.audit_trail_integrity_verified is True
    assert len(export_dossier.manifest_sha256) == 64
    assert len(export_dossier.electronic_signatures) == 4
    assert len(export_dossier.agent_runs) >= 3  # Sentinel, NC, CAPA
    assert len(export_dossier.claims) == 5

    # Step 9: Verify REST API endpoint
    res_api = client.get(f"/api/v1/cases/{case_id}/export/decision-lineage")
    assert res_api.status_code == 200
    data = res_api.json()
    assert data["case"]["state"] == "CLOSED"
    assert data["audit_trail_integrity_verified"] is True
