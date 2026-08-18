"""Unit tests verifying PolicyEngine guardrails and Action Class (A0-A5) enforcement."""

import pytest

from gxpsoft.core.policy import PolicyEngine, PolicyViolationError
from gxpsoft.models.enums import ActionClass, AuthorType, CaseState


def test_agent_prohibited_from_a4_controlled_gxp_action() -> None:
    with pytest.raises(PolicyViolationError) as exc_info:
        PolicyEngine.validate_action(
            action_class=ActionClass.A4_CONTROLLED_GXP_ACTION,
            actor_type=AuthorType.AGENT,
            actor_id="NCAgent-v1.0",
            target_state=CaseState.ROOT_CAUSE_CONFIRMED,
            signature_id="SIG-FAKE-01",
        )
    assert "AI Agent 'NCAgent-v1.0' is strictly prohibited" in str(exc_info.value)
    assert exc_info.value.action_class == ActionClass.A4_CONTROLLED_GXP_ACTION


def test_a5_prohibited_action_rejected_for_all() -> None:
    with pytest.raises(PolicyViolationError) as exc_info:
        PolicyEngine.validate_action(
            action_class=ActionClass.A5_PROHIBITED,
            actor_type=AuthorType.HUMAN,
            actor_id="USER-QA-LEAD-01",
        )
    assert "A5_PROHIBITED" in str(exc_info.value)


def test_unqualified_human_blocked_from_a4_signing() -> None:
    with pytest.raises(PolicyViolationError) as exc_info:
        PolicyEngine.validate_action(
            action_class=ActionClass.A4_CONTROLLED_GXP_ACTION,
            actor_type=AuthorType.HUMAN,
            actor_id="USER-OPERATOR-01",  # Operator without QA signing role
            target_state=CaseState.ROOT_CAUSE_CONFIRMED,
            signature_id="SIG-001",
        )
    assert "lacks required QA signing roles" in str(exc_info.value)


def test_qualified_qa_lead_permitted_for_a4() -> None:
    is_valid = PolicyEngine.validate_action(
        action_class=ActionClass.A4_CONTROLLED_GXP_ACTION,
        actor_type=AuthorType.HUMAN,
        actor_id="USER-QA-LEAD-01",
        target_state=CaseState.ROOT_CAUSE_CONFIRMED,
        signature_id="SIG-001",
    )
    assert is_valid is True


def test_agent_permitted_for_a0_a1_a2_a3() -> None:
    assert PolicyEngine.validate_action(
        action_class=ActionClass.A0_OBSERVE,
        actor_type=AuthorType.AGENT,
        actor_id="SentinelAgent-v1.0",
    ) is True

    assert PolicyEngine.validate_action(
        action_class=ActionClass.A2_PREPARE,
        actor_type=AuthorType.AGENT,
        actor_id="NCAgent-v1.0",
    ) is True
