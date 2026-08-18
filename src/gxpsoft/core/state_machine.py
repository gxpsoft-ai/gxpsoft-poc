"""Deterministic Quality Case State Machine governing all GxP lifecycle transitions."""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from gxpsoft.core.crypto import compute_sha256
from gxpsoft.core.policy import PolicyEngine, PolicyViolationError
from gxpsoft.core.repository import repo
from gxpsoft.core.signature import SignatureService
from gxpsoft.models.audit import StateTransition
from gxpsoft.models.case import QualityCase
from gxpsoft.models.enums import ActionClass, AuthorType, CaseState, SignatureMeaning


class InvalidTransitionError(Exception):
    """Raised when an attempted state transition is illegal in the FSM graph."""
    pass


# Rule specification: (from_state, to_state) -> (ActionClass, PolicyRuleName, RequiredSignatureMeaning)
TRANSITION_RULES: Dict[Tuple[CaseState, CaseState], Tuple[ActionClass, str, Optional[SignatureMeaning]]] = {
    (CaseState.SIGNAL_RECEIVED, CaseState.CASE_CREATED): (
        ActionClass.A0_OBSERVE,
        "POL-001: Automatic or manual case initialization from valid signal",
        None
    ),
    (CaseState.CASE_CREATED, CaseState.EVIDENCE_ASSEMBLED): (
        ActionClass.A0_OBSERVE,
        "POL-002: Continuous evidence assembly from connected GxP systems",
        None
    ),
    (CaseState.EVIDENCE_ASSEMBLED, CaseState.CONTAINMENT_PROPOSED): (
        ActionClass.A2_PREPARE,
        "POL-003: Agent or human prepares containment recommendation",
        None
    ),
    (CaseState.CONTAINMENT_PROPOSED, CaseState.HUMAN_CLASSIFICATION_APPROVED): (
        ActionClass.A4_CONTROLLED_GXP_ACTION,
        "POL-004: Qualified human confirms deviation classification and containment",
        SignatureMeaning.APPROVED_CLASSIFICATION
    ),
    (CaseState.HUMAN_CLASSIFICATION_APPROVED, CaseState.INVESTIGATION_DRAFTED): (
        ActionClass.A2_PREPARE,
        "POL-005: Agent or human stages RCA hypotheses and investigation draft",
        None
    ),
    (CaseState.INVESTIGATION_DRAFTED, CaseState.ROOT_CAUSE_CONFIRMED): (
        ActionClass.A4_CONTROLLED_GXP_ACTION,
        "POL-006: Qualified human authorizes root cause and investigation findings",
        SignatureMeaning.APPROVED_ROOT_CAUSE
    ),
    (CaseState.ROOT_CAUSE_CONFIRMED, CaseState.CAPA_DRAFTED): (
        ActionClass.A2_PREPARE,
        "POL-007: Agent or human prepares CAPA action plan and effectiveness metrics",
        None
    ),
    (CaseState.CAPA_DRAFTED, CaseState.CAPA_AUTHORIZED): (
        ActionClass.A4_CONTROLLED_GXP_ACTION,
        "POL-008: QA Management authorizes CAPA implementation",
        SignatureMeaning.APPROVED_CAPA
    ),
    (CaseState.CAPA_AUTHORIZED, CaseState.EFFECTIVENESS_VERIFIED): (
        ActionClass.A3_EXECUTE_SUPPORT,
        "POL-009: Verification of post-implementation effectiveness evidence",
        None
    ),
    (CaseState.EFFECTIVENESS_VERIFIED, CaseState.CLOSED): (
        ActionClass.A4_CONTROLLED_GXP_ACTION,
        "POL-010: Final QA authorization and case closure",
        SignatureMeaning.APPROVED_CLOSURE
    ),
}


class CaseStateMachine:
    """Finite State Machine enforcing deterministic, auditable case transitions."""

    @staticmethod
    def transition(
        case_id: str,
        to_state: CaseState,
        actor_id: str,
        actor_type: AuthorType,
        signature_id: Optional[str] = None,
        rationale: Optional[str] = None
    ) -> QualityCase:
        """Executes a validated state transition on a QualityCase.
        
        Raises InvalidTransitionError or PolicyViolationError on failure.
        """
        case = repo.get_case(case_id)
        if not case:
            raise InvalidTransitionError(f"QualityCase '{case_id}' not found.")

        from_state = case.state

        # Check for rejection transition (permitted from any state prior to CLOSED/REJECTED)
        if to_state == CaseState.REJECTED:
            if from_state in (CaseState.CLOSED, CaseState.REJECTED):
                raise InvalidTransitionError(f"Cannot reject case already in '{from_state}' state.")
            action_class = ActionClass.A4_CONTROLLED_GXP_ACTION
            rule_name = "POL-099: Case rejection by authorized QA with mandatory rationale"
            req_sig_meaning = SignatureMeaning.REJECTED
        else:
            rule_spec = TRANSITION_RULES.get((from_state, to_state))
            if not rule_spec:
                raise InvalidTransitionError(
                    f"Illegal state transition from '{from_state.value}' to '{to_state.value}'."
                )
            action_class, rule_name, req_sig_meaning = rule_spec

        # Evaluate policy guardrails (RBAC, Action Class, Human e-sig for A4)
        PolicyEngine.validate_action(
            action_class=action_class,
            actor_type=actor_type,
            actor_id=actor_id,
            target_state=to_state,
            severity=case.severity,
            signature_id=signature_id
        )

        # Validate signature semantics if required
        if req_sig_meaning and signature_id:
            sig = repo.get_signature(signature_id)
            if not sig:
                raise InvalidTransitionError(f"SignatureRecord '{signature_id}' not found.")
            if sig.meaning != req_sig_meaning:
                raise InvalidTransitionError(
                    f"Signature meaning '{sig.meaning.value}' does not match required meaning '{req_sig_meaning.value}'."
                )
            if sig.case_id != case_id:
                raise InvalidTransitionError(
                    f"Signature '{signature_id}' belongs to case '{sig.case_id}', not '{case_id}'."
                )

        # Execute state transition
        case.state = to_state
        case.updated_at = datetime.now(timezone.utc)
        if rationale:
            case.metadata["latest_transition_rationale"] = rationale
        repo.update_case(case)

        # Record StateTransition object
        transition = StateTransition(
            case_id=case_id,
            from_state=from_state,
            to_state=to_state,
            actor_type=actor_type,
            actor_id=actor_id,
            action_class=action_class,
            policy_rule=rule_name,
            signature_id=signature_id
        )
        repo.add_transition(transition)

        # Append to Audit Ledger
        repo.audit_ledger.append(
            event_type="STATE_TRANSITION",
            entity_type="QualityCase",
            entity_id=case_id,
            actor_id=actor_id,
            actor_type=actor_type,
            data_snapshot={
                "from_state": from_state.value,
                "to_state": to_state.value,
                "action_class": action_class.value,
                "policy_rule": rule_name,
                "signature_id": signature_id,
                "rationale": rationale
            },
            case_id=case_id
        )

        return case
