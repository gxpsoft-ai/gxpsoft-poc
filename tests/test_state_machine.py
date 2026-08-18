"""Unit tests verifying deterministic CaseStateMachine transitions and guardrails."""

import pytest

from gxpsoft.core.crypto import compute_sha256
from gxpsoft.core.policy import PolicyViolationError
from gxpsoft.core.repository import repo
from gxpsoft.core.signature import SignatureService
from gxpsoft.core.state_machine import CaseStateMachine, InvalidTransitionError
from gxpsoft.models.case import QualityCase
from gxpsoft.models.enums import AuthorType, CaseSeverity, CaseState, SignatureMeaning


def test_full_case_lifecycle_progression() -> None:
    # 1. Initialize case in SIGNAL_RECEIVED
    case = QualityCase(
        title="Bioreactor BR-04 Excursion",
        description="Temp reached 39.4C",
        initial_event_id="EVT-001",
        batch_id="BIO-2026-088",
        severity=CaseSeverity.MAJOR,
    )
    repo.add_case(case)
    case_id = case.case_id

    # 2. SIGNAL_RECEIVED -> CASE_CREATED (A0, Agent/System)
    case = CaseStateMachine.transition(
        case_id=case_id,
        to_state=CaseState.CASE_CREATED,
        actor_id="SentinelAgent-v1.0",
        actor_type=AuthorType.AGENT,
    )
    assert case.state == CaseState.CASE_CREATED

    # 3. CASE_CREATED -> EVIDENCE_ASSEMBLED (A0, Agent)
    case = CaseStateMachine.transition(
        case_id=case_id,
        to_state=CaseState.EVIDENCE_ASSEMBLED,
        actor_id="NCAgent-v1.0",
        actor_type=AuthorType.AGENT,
    )
    assert case.state == CaseState.EVIDENCE_ASSEMBLED

    # 4. EVIDENCE_ASSEMBLED -> CONTAINMENT_PROPOSED (A2, Agent)
    case = CaseStateMachine.transition(
        case_id=case_id,
        to_state=CaseState.CONTAINMENT_PROPOSED,
        actor_id="NCAgent-v1.0",
        actor_type=AuthorType.AGENT,
    )
    assert case.state == CaseState.CONTAINMENT_PROPOSED

    # 5. CONTAINMENT_PROPOSED -> HUMAN_CLASSIFICATION_APPROVED (A4, Human with E-Sig)
    sig1 = SignatureService.create_signature(
        case_id=case_id,
        user_id="USER-QA-LEAD-01",
        password_or_pin="LeadPass2026!",
        meaning=SignatureMeaning.APPROVED_CLASSIFICATION,
        target_entity_type="QualityCase",
        target_entity_id=case_id,
        target_content_hash=compute_sha256({"state": "CONTAINMENT_PROPOSED"}),
    )
    case = CaseStateMachine.transition(
        case_id=case_id,
        to_state=CaseState.HUMAN_CLASSIFICATION_APPROVED,
        actor_id="USER-QA-LEAD-01",
        actor_type=AuthorType.HUMAN,
        signature_id=sig1.signature_id,
    )
    assert case.state == CaseState.HUMAN_CLASSIFICATION_APPROVED

    # 6. HUMAN_CLASSIFICATION_APPROVED -> INVESTIGATION_DRAFTED (A2, Agent)
    case = CaseStateMachine.transition(
        case_id=case_id,
        to_state=CaseState.INVESTIGATION_DRAFTED,
        actor_id="NCAgent-v1.0",
        actor_type=AuthorType.AGENT,
    )
    assert case.state == CaseState.INVESTIGATION_DRAFTED

    # 7. INVESTIGATION_DRAFTED -> ROOT_CAUSE_CONFIRMED (A4, Human with E-Sig)
    sig2 = SignatureService.create_signature(
        case_id=case_id,
        user_id="USER-QA-LEAD-01",
        password_or_pin="LeadPass2026!",
        meaning=SignatureMeaning.APPROVED_ROOT_CAUSE,
        target_entity_type="QualityCase",
        target_entity_id=case_id,
        target_content_hash=compute_sha256({"root_cause": "Probe RTD-04B drift"}),
    )
    case = CaseStateMachine.transition(
        case_id=case_id,
        to_state=CaseState.ROOT_CAUSE_CONFIRMED,
        actor_id="USER-QA-LEAD-01",
        actor_type=AuthorType.HUMAN,
        signature_id=sig2.signature_id,
    )
    assert case.state == CaseState.ROOT_CAUSE_CONFIRMED

    # 8. ROOT_CAUSE_CONFIRMED -> CAPA_DRAFTED (A2, Agent)
    case = CaseStateMachine.transition(
        case_id=case_id,
        to_state=CaseState.CAPA_DRAFTED,
        actor_id="CAPAAgent-v1.0",
        actor_type=AuthorType.AGENT,
    )
    assert case.state == CaseState.CAPA_DRAFTED

    # 9. CAPA_DRAFTED -> CAPA_AUTHORIZED (A4, Human with E-Sig)
    sig3 = SignatureService.create_signature(
        case_id=case_id,
        user_id="USER-QA-MGR-01",
        password_or_pin="MgrPass2026!",
        meaning=SignatureMeaning.APPROVED_CAPA,
        target_entity_type="QualityCase",
        target_entity_id=case_id,
        target_content_hash=compute_sha256({"capa_plan": "Recalibrate probe"}),
    )
    case = CaseStateMachine.transition(
        case_id=case_id,
        to_state=CaseState.CAPA_AUTHORIZED,
        actor_id="USER-QA-MGR-01",
        actor_type=AuthorType.HUMAN,
        signature_id=sig3.signature_id,
    )
    assert case.state == CaseState.CAPA_AUTHORIZED

    # 10. CAPA_AUTHORIZED -> EFFECTIVENESS_VERIFIED (A3, System)
    case = CaseStateMachine.transition(
        case_id=case_id,
        to_state=CaseState.EFFECTIVENESS_VERIFIED,
        actor_id="VERIFICATION_SYSTEM",
        actor_type=AuthorType.SYSTEM,
    )
    assert case.state == CaseState.EFFECTIVENESS_VERIFIED

    # 11. EFFECTIVENESS_VERIFIED -> CLOSED (A4, QA Director with E-Sig)
    sig4 = SignatureService.create_signature(
        case_id=case_id,
        user_id="USER-DIR-QA-01",
        password_or_pin="DirPass2026!",
        meaning=SignatureMeaning.APPROVED_CLOSURE,
        target_entity_type="QualityCase",
        target_entity_id=case_id,
        target_content_hash=compute_sha256({"closure": "Verified 5 batches"}),
    )
    case = CaseStateMachine.transition(
        case_id=case_id,
        to_state=CaseState.CLOSED,
        actor_id="USER-DIR-QA-01",
        actor_type=AuthorType.HUMAN,
        signature_id=sig4.signature_id,
    )
    assert case.state == CaseState.CLOSED

    # Verify transitions recorded in repo
    transitions = repo.get_transitions_for_case(case_id)
    assert len(transitions) == 10
    assert repo.audit_ledger.verify_integrity() is True


def test_illegal_state_skip_rejected() -> None:
    case = QualityCase(
        title="Test Case",
        description="Test",
        initial_event_id="EVT-002",
    )
    repo.add_case(case)

    # Attempt illegal skip from SIGNAL_RECEIVED directly to CLOSED
    with pytest.raises(InvalidTransitionError) as exc_info:
        CaseStateMachine.transition(
            case_id=case.case_id,
            to_state=CaseState.CLOSED,
            actor_id="USER-DIR-QA-01",
            actor_type=AuthorType.HUMAN,
            signature_id="SIG-FAKE",
        )
    assert "Illegal state transition" in str(exc_info.value)


def test_agent_cannot_close_or_confirm_root_cause() -> None:
    case = QualityCase(
        title="Test Case",
        description="Test",
        initial_event_id="EVT-003",
        state=CaseState.INVESTIGATION_DRAFTED,
    )
    repo.add_case(case)

    # Agent attempting ROOT_CAUSE_CONFIRMED without human
    with pytest.raises(PolicyViolationError) as exc_info:
        CaseStateMachine.transition(
            case_id=case.case_id,
            to_state=CaseState.ROOT_CAUSE_CONFIRMED,
            actor_id="NCAgent-v1.0",
            actor_type=AuthorType.AGENT,
        )
    assert "strictly prohibited" in str(exc_info.value)
