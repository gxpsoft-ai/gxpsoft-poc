"""Integration tests for FastAPI REST API endpoints."""

import pytest
from fastapi.testclient import TestClient

from gxpsoft.api.main import app
from gxpsoft.core.crypto import compute_sha256
from gxpsoft.models.enums import AuthorType, CaseState, SignatureMeaning

client = TestClient(app)


def test_api_ingest_event(mes_event_payload: dict) -> None:
    payload = dict(mes_event_payload)
    payload["idempotency_key"] = "api:test:idempotency:001"
    payload["event_id"] = "EVT-API-001"

    response = client.post("/api/v1/events/ingest", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["event"]["event_id"] == "EVT-API-001"
    assert data["case"] is not None
    assert data["case"]["state"] == CaseState.SIGNAL_RECEIVED.value


def test_api_duplicate_event_returns_409(mes_event_payload: dict) -> None:
    payload = dict(mes_event_payload)
    payload["idempotency_key"] = "api:test:dup:002"
    payload["event_id"] = "EVT-API-002"

    res1 = client.post("/api/v1/events/ingest", json=payload)
    assert res1.status_code == 201

    res2 = client.post("/api/v1/events/ingest", json=payload)
    assert res2.status_code == 409
    assert "Duplicate event" in res2.json()["detail"]["message"]


def test_api_state_transition_and_signature_flow(mes_event_payload: dict) -> None:
    # 1. Ingest event
    payload = dict(mes_event_payload)
    payload["idempotency_key"] = "api:test:flow:003"
    payload["event_id"] = "EVT-API-003"
    res = client.post("/api/v1/events/ingest", json=payload)
    case_id = res.json()["case"]["case_id"]

    # 2. Agent transitions to CASE_CREATED
    res_t1 = client.post(
        f"/api/v1/cases/{case_id}/transition",
        json={
            "to_state": "CASE_CREATED",
            "actor_id": "SentinelAgent-v1.0",
            "actor_type": "AGENT",
        },
    )
    assert res_t1.status_code == 200
    assert res_t1.json()["state"] == "CASE_CREATED"

    # 3. Agent transitions to EVIDENCE_ASSEMBLED
    res_t2 = client.post(
        f"/api/v1/cases/{case_id}/transition",
        json={
            "to_state": "EVIDENCE_ASSEMBLED",
            "actor_id": "NCAgent-v1.0",
            "actor_type": "AGENT",
        },
    )
    assert res_t2.status_code == 200

    # 4. Agent transitions to CONTAINMENT_PROPOSED
    res_t3 = client.post(
        f"/api/v1/cases/{case_id}/transition",
        json={
            "to_state": "CONTAINMENT_PROPOSED",
            "actor_id": "NCAgent-v1.0",
            "actor_type": "AGENT",
        },
    )
    assert res_t3.status_code == 200

    # 5. Agent trying A4 transition to HUMAN_CLASSIFICATION_APPROVED must return 403 Forbidden
    res_forbidden = client.post(
        f"/api/v1/cases/{case_id}/transition",
        json={
            "to_state": "HUMAN_CLASSIFICATION_APPROVED",
            "actor_id": "NCAgent-v1.0",
            "actor_type": "AGENT",
        },
    )
    assert res_forbidden.status_code == 403
    assert res_forbidden.json()["detail"]["error"] == "PolicyViolationError"

    # 6. Human creates electronic signature
    target_hash = compute_sha256({"case_id": case_id, "containment": "quarantine lot"})
    res_sig = client.post(
        "/api/v1/signatures/sign",
        json={
            "case_id": case_id,
            "user_id": "USER-QA-LEAD-01",
            "password_or_pin": "LeadPass2026!",
            "meaning": "APPROVED_CLASSIFICATION",
            "target_entity_type": "QualityCase",
            "target_entity_id": case_id,
            "target_content_hash": target_hash,
        },
    )
    assert res_sig.status_code == 201
    sig_id = res_sig.json()["signature_id"]

    # 7. Human executes A4 transition with valid signature
    res_t4 = client.post(
        f"/api/v1/cases/{case_id}/transition",
        json={
            "to_state": "HUMAN_CLASSIFICATION_APPROVED",
            "actor_id": "USER-QA-LEAD-01",
            "actor_type": "HUMAN",
            "signature_id": sig_id,
            "rationale": "Confirmed Major deviation under SOP-PRC-042",
        },
    )
    assert res_t4.status_code == 200
    assert res_t4.json()["state"] == "HUMAN_CLASSIFICATION_APPROVED"

    # 8. Query audit trail
    res_audit = client.get(f"/api/v1/cases/{case_id}/audit-trail")
    assert res_audit.status_code == 200
    audit_data = res_audit.json()
    assert audit_data["integrity_verified"] is True
    assert audit_data["entry_count"] >= 5
