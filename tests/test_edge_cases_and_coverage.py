"""Exhaustive edge-case, error handling, and coverage stress tests."""

from datetime import datetime, timezone
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from gxpsoft.agents.capa import CAPAAgent
from gxpsoft.agents.nc_investigator import NCInvestigatorAgent
from gxpsoft.agents.orchestrator import InvestigationPipeline
from gxpsoft.agents.sentinel import SentinelAgent
from gxpsoft.api.main import app
from gxpsoft.capa.effectiveness import EffectivenessMonitor
from gxpsoft.capa.export import DecisionLineageExporter
from gxpsoft.core.crypto import canonical_json, compute_audit_hash, compute_sha256
from gxpsoft.core.policy import PolicyEngine, PolicyViolationError, QUALIFIED_USERS, UserQualification
from gxpsoft.core.repository import repo
from gxpsoft.core.signature import SignatureService, SignatureVerificationError
from gxpsoft.core.state_machine import CaseStateMachine, InvalidTransitionError
from gxpsoft.evidence.indexer import evidence_indexer
from gxpsoft.ingestion.service import IngestionService
from gxpsoft.models.case import QualityCase
from gxpsoft.models.enums import ActionClass, AuthorType, CaseSeverity, CaseState, SignatureMeaning
from gxpsoft.review.packet_builder import DecisionPacketBuilder
from gxpsoft.review.service import HumanReviewService
from gxpsoft.tools.gateway import ToolGateway, ToolGatewayError
from gxpsoft.tools.registry import (
    find_similar_deviations,
    get_batch_genealogy,
    get_equipment_calibration,
    get_operator_training,
    search_sops,
    stage_investigation_draft,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def index_fixtures(fixtures_dir: Path) -> None:
    evidence_indexer.index_document_directory(fixtures_dir / "documents")


def test_crypto_edge_cases() -> None:
    # 1. Test bytes hashing
    raw_bytes = b"regulatory_payload_bytes"
    assert len(compute_sha256(raw_bytes)) == 64

    # 2. Test datetime serialization in canonical JSON
    dt_naive = datetime(2026, 8, 18, 12, 0, 0)
    data = {"timestamp": dt_naive}
    c_json = canonical_json(data)
    assert "2026-08-18T12:00:00+00:00" in c_json

    # 3. Test non-serializable object raises TypeError
    class UnserializableClass:
        pass

    with pytest.raises(TypeError):
        canonical_json({"obj": UnserializableClass()})


def test_state_machine_errors() -> None:
    # 1. Non-existent case
    with pytest.raises(InvalidTransitionError) as exc_info:
        CaseStateMachine.transition(
            case_id="NON-EXISTENT-CASE",
            to_state=CaseState.CASE_CREATED,
            actor_id="SentinelAgent",
            actor_type=AuthorType.AGENT,
        )
    assert "not found" in str(exc_info.value)

    # 2. Rejecting closed case raises error
    case = QualityCase(
        case_id="DEV-CLOSED-TEST",
        title="Closed Case",
        description="Test",
        initial_event_id="EVT-001",
        state=CaseState.CLOSED,
    )
    repo.add_case(case)

    with pytest.raises(InvalidTransitionError) as exc_info:
        CaseStateMachine.transition(
            case_id=case.case_id,
            to_state=CaseState.REJECTED,
            actor_id="USER-QA-LEAD-01",
            actor_type=AuthorType.HUMAN,
            signature_id="SIG-001",
        )
    assert "Cannot reject case already in" in str(exc_info.value)

    # 3. Signature meaning mismatch
    case2 = QualityCase(
        case_id="DEV-SIG-MISMATCH",
        title="Sig Mismatch Case",
        description="Test",
        initial_event_id="EVT-001",
        state=CaseState.CONTAINMENT_PROPOSED,
    )
    repo.add_case(case2)

    wrong_sig = SignatureService.create_signature(
        case_id=case2.case_id,
        user_id="USER-QA-LEAD-01",
        password_or_pin="LeadPass2026!",
        meaning=SignatureMeaning.APPROVED_CLOSURE,  # Wrong meaning!
        target_entity_type="QualityCase",
        target_entity_id=case2.case_id,
        target_content_hash="abc",
    )

    with pytest.raises(InvalidTransitionError) as exc_info:
        CaseStateMachine.transition(
            case_id=case2.case_id,
            to_state=CaseState.HUMAN_CLASSIFICATION_APPROVED,
            actor_id="USER-QA-LEAD-01",
            actor_type=AuthorType.HUMAN,
            signature_id=wrong_sig.signature_id,
        )
    assert "does not match required meaning" in str(exc_info.value)

    # 4. Signature belonging to different case
    other_sig = SignatureService.create_signature(
        case_id="OTHER-CASE-ID",
        user_id="USER-QA-LEAD-01",
        password_or_pin="LeadPass2026!",
        meaning=SignatureMeaning.APPROVED_CLASSIFICATION,
        target_entity_type="QualityCase",
        target_entity_id="OTHER-CASE-ID",
        target_content_hash="abc",
    )

    with pytest.raises(InvalidTransitionError) as exc_info:
        CaseStateMachine.transition(
            case_id=case2.case_id,
            to_state=CaseState.HUMAN_CLASSIFICATION_APPROVED,
            actor_id="USER-QA-LEAD-01",
            actor_type=AuthorType.HUMAN,
            signature_id=other_sig.signature_id,
        )
    assert "belongs to case 'OTHER-CASE-ID'" in str(exc_info.value)


def test_policy_engine_user_qualification_checks() -> None:
    # 1. Non-existent user
    with pytest.raises(PolicyViolationError) as exc_info:
        PolicyEngine.validate_action(
            action_class=ActionClass.A4_CONTROLLED_GXP_ACTION,
            actor_type=AuthorType.HUMAN,
            actor_id="USER-UNKNOWN-999",
            target_state=CaseState.ROOT_CAUSE_CONFIRMED,
            signature_id="SIG-001",
        )
    assert "not an active qualified GxP user" in str(exc_info.value)

    # 2. Inactive user
    QUALIFIED_USERS["USER-INACTIVE-01"] = UserQualification(
        user_id="USER-INACTIVE-01",
        full_name="Former Employee",
        roles=["QA_LEAD"],
        is_active=False,
    )
    with pytest.raises(PolicyViolationError) as exc_info:
        PolicyEngine.validate_action(
            action_class=ActionClass.A4_CONTROLLED_GXP_ACTION,
            actor_type=AuthorType.HUMAN,
            actor_id="USER-INACTIVE-01",
            target_state=CaseState.ROOT_CAUSE_CONFIRMED,
            signature_id="SIG-001",
        )
    assert "not an active qualified GxP user" in str(exc_info.value)


def test_tools_not_found_handlers() -> None:
    # 1. Non-existent batch
    res_batch = get_batch_genealogy("NON-EXISTENT-BATCH")
    assert res_batch["found"] is False
    assert "No batch record found" in res_batch["message"]

    # 2. Non-existent equipment
    res_equip = get_equipment_calibration("NON-EXISTENT-EQUIP")
    assert res_equip["found"] is False
    assert "No calibration record found" in res_equip["message"]

    # 3. Non-existent operator
    res_op = get_operator_training("NON-EXISTENT-OPERATOR")
    assert res_op["found"] is False
    assert "not found" in res_op["message"]

    # 4. stage_investigation_draft with invalid case_id
    with pytest.raises(ValueError):
        stage_investigation_draft(
            case_id="INVALID-CASE-ID",
            agent_run_id="RUN-001",
            title="Invalid",
            structured_content={},
            claims_data=[],
        )


def test_effectiveness_monitor_in_progress_state(mes_event_payload: dict) -> None:
    payload = dict(mes_event_payload)
    payload["idempotency_key"] = "test:eff:inprog:001"
    payload["event_id"] = "EVT-EFF-INPROG-01"

    _, case, _ = InvestigationPipeline.run_pipeline(payload)
    case, _ = HumanReviewService.approve_and_sign(
        case_id=case.case_id,
        user_id="USER-QA-LEAD-01",
        password_or_pin="LeadPass2026!",
        meaning=SignatureMeaning.APPROVED_CLASSIFICATION,
        rationale="Approved.",
    )
    case, _ = HumanReviewService.approve_and_sign(
        case_id=case.case_id,
        user_id="USER-QA-LEAD-01",
        password_or_pin="LeadPass2026!",
        meaning=SignatureMeaning.APPROVED_ROOT_CAUSE,
        rationale="Approved root cause.",
    )
    CAPAAgent.generate_capa(case_id=case.case_id)
    case, _ = HumanReviewService.approve_and_sign(
        case_id=case.case_id,
        user_id="USER-QA-MGR-01",
        password_or_pin="MgrPass2026!",
        meaning=SignatureMeaning.APPROVED_CAPA,
        rationale="Authorized CAPA.",
    )

    # Submit 3 clean batches (fewer than 5 required)
    three_batches = [
        {"batch_id": f"BIO-2026-09{i}", "max_temp_celsius": 37.0, "excursion_duration_min": 0.0}
        for i in range(1, 4)
    ]
    res = EffectivenessMonitor.evaluate_batch_results(case_id=case.case_id, batch_results=three_batches)

    assert res["verified"] is False
    assert res["clean_batches_count"] == 3
    assert "In-progress: 3/5 clean batches verified" in res["message"]


def test_api_comprehensive_endpoint_coverage(mes_event_payload: dict) -> None:
    # 1. GET /api/v1/cases (list cases)
    res_list = client.get("/api/v1/cases")
    assert res_list.status_code == 200
    assert isinstance(res_list.json(), list)

    # 2. GET /api/v1/cases/404
    res_404 = client.get("/api/v1/cases/NON-EXISTENT-CASE-404")
    assert res_404.status_code == 404

    # 3. GET /api/v1/cases/404/decision-packet
    res_pkt_404 = client.get("/api/v1/cases/NON-EXISTENT-CASE-404/decision-packet")
    assert res_pkt_404.status_code == 404

    # 4. GET /api/v1/cases/404/audit-trail
    res_audit_404 = client.get("/api/v1/cases/NON-EXISTENT-CASE-404/audit-trail")
    assert res_audit_404.status_code == 404

    # 5. POST /api/v1/cases/404/transition
    res_trans_404 = client.post(
        "/api/v1/cases/NON-EXISTENT-CASE-404/transition",
        json={"to_state": "CASE_CREATED", "actor_id": "Sentinel", "actor_type": "AGENT"},
    )
    assert res_trans_404.status_code == 400

    # 6. POST /api/v1/cases/404/capa/generate
    res_capa_404 = client.post("/api/v1/cases/NON-EXISTENT-CASE-404/capa/generate")
    assert res_capa_404.status_code == 404

    # 7. POST /api/v1/cases/404/capa/verify
    res_verify_404 = client.post(
        "/api/v1/cases/NON-EXISTENT-CASE-404/capa/verify",
        json={"batch_results": []},
    )
    assert res_verify_404.status_code == 404

    # 8. GET /api/v1/cases/404/export/decision-lineage
    res_exp_404 = client.get("/api/v1/cases/NON-EXISTENT-CASE-404/export/decision-lineage")
    assert res_exp_404.status_code == 404

    # 9. Test Ingest failure with invalid payload
    res_bad_ingest = client.post("/api/v1/events/ingest", json={"invalid": "payload"})
    assert res_bad_ingest.status_code == 400
